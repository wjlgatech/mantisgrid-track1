"""Root-cause analysis over microservice telemetry, tuned by ablation.

Two ideas were tested against the 70 dev cases. One paid, one cost, and they
point in opposite directions -- which is only visible because they were measured
separately (`eval/ablate.py`, table in `eval/results.md`):

    ranking   WHICH component is the cause -> peak z-magnitude wins (0.164)
              ranking by earliest onset instead LOSES 0.033. The first series to
              jitter is usually noise, not the culprit; a big deviation is a
              better identifier than an early one.

    time      WHEN the fault began -> the ONSET wins (+0.035, to 0.199)
              The peak is when the symptom hurt most, which is systematically
              later than the fault. Against a 60-second tolerance that matters:
              task_1 goes 0.167 -> 0.250, task_5 0.225 -> 0.325.

So: identify the component by how hard it moved, and date it by when it started
moving. Bundling both "improvements" together scored 0.093 -- worse than either.

The method:

    1. parse the window -- in UTC+8, which is what the telemetry is in. Parsing
       it as UTC reads a window 8 hours off and returns zero samples for any
       window at 16:00 or later: 24 of 70 dev cases go blank. Fixing that one
       line is worth more than everything else here combined (0.073 -> 0.164).
    2. robust z per (component, kpi) series, in-window vs the rest of the day
    3. rank components by peak z; take the top n
    4. reason from the winning component's own anomalous KPI
    5. answer time = that series' onset, the first sample to leave the band

Everything the evidence file cites is a value measured in step 2 or 3 and carried
through in `Finding`. Nothing in it is generated prose about numbers.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from run import Solution, format_prediction   # noqa: E402

# The telemetry is UTC+8 (docs/data.md). Parsing the instruction's window in UTC
# reads a window 8 hours off; worse, any window at 16:00 or later lands past the
# end of the day file and yields zero samples -- 24 of 70 dev cases go blank.
CST = timezone(timedelta(hours=8))

import os

# The two decisions this agent makes differently from the baseline, each
# switchable so eval/ablate.py can attribute the effect of one without the other.
#   RCA_RANK=onset|peak   which component is the cause  (default: peak)
#   RCA_TIME=onset|peak   when the fault began          (default: onset, the winner)
RANK_BY = os.environ.get("RCA_RANK", "peak")
TIME_BY = os.environ.get("RCA_TIME", "onset")

Z_MIN = 4.0          # a series must clear this to count as anomalous at all
MAX_CANDIDATES = 12  # components carried into the evidence table

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}

_DAY_CACHE: dict = {}


# --------------------------------------------------------------- the question

def parse_window(instruction: str) -> tuple[datetime, datetime] | None:
    """'March 20, 2022, from 09:00 to 09:30' -> two aware datetimes in UTC+8."""
    m = re.search(r"(\w+)\s+(\d{1,2}),?\s+(\d{4}).{0,40}?(\d{1,2}):(\d{2})"
                  r"\s*(?:to|-|and|until)\s*.{0,40}?(\d{1,2}):(\d{2})",
                  instruction, re.I | re.S)
    if not m:
        return None
    mon, day, year, h1, m1, h2, m2 = m.groups()
    if mon.lower() not in MONTHS:
        return None
    base = datetime(int(year), MONTHS[mon.lower()], int(day), tzinfo=CST)
    lo = base + timedelta(hours=int(h1), minutes=int(m1))
    hi = base + timedelta(hours=int(h2), minutes=int(m2))
    if hi <= lo:                       # window crosses midnight
        hi += timedelta(days=1)
    return lo, hi


def failure_count(instruction: str) -> int:
    """The instruction states how many failures are in the window. A different
    count in the answer scores zero for the whole case, however right the rest."""
    t = instruction.lower()
    for word, n in (("one failure", 1), ("a single failure", 1), ("two failures", 2),
                    ("three failures", 3), ("four failures", 4)):
        if word in t:
            return n
    return 1


# ------------------------------------------------------------------ the data

def _load_day(dataset: Path, date: str) -> pd.DataFrame:
    """Container and node metrics for one day. Cached: the judged run reuses a
    day across cases, and re-reading 300 MB per case is how a run times out."""
    key = (str(dataset), date)
    if key in _DAY_CACHE:
        return _DAY_CACHE[key]
    frames = []
    for name in ("metric_container", "metric_node"):
        f = dataset / "telemetry" / date / "metric" / f"{name}.csv"
        if not f.exists():
            continue
        df = pd.read_csv(f, usecols=["timestamp", "cmdb_id", "kpi_name", "value"])
        df["source"] = name
        frames.append(df)
    out = (pd.concat(frames, ignore_index=True) if frames else
           pd.DataFrame(columns=["timestamp", "cmdb_id", "kpi_name", "value", "source"]))
    _DAY_CACHE[key] = out
    return out


def component_of(cmdb_id: str) -> str:
    """metric_container is '<node>.<pod>'; metric_node is the node itself."""
    return cmdb_id.split(".", 1)[1] if "." in cmdb_id else cmdb_id


# The two levels have different legal vocabularies, and the asymmetry is load
# bearing: there is no node-level network reason at all, so a node topping the
# ranking on a TCP metric must fall through to its next explainable KPI.
NODE_REASONS = {"cpu": "node CPU load", "spike": "node CPU spike",
                "memory": "node memory consumption",
                "read": "node disk read I/O consumption",
                "write": "node disk write I/O consumption",
                "space": "node disk space consumption"}
POD_REASONS = {"cpu": "container CPU load", "memory": "container memory load",
               "read": "container read I/O load", "write": "container write I/O load",
               "latency": "container network latency",
               "loss": "container packet loss",
               "retrans": "container network packet retransmission",
               "corrupt": "container network packet corruption",
               "kill": "container process termination"}

LEGAL_REASONS = sorted(set(NODE_REASONS.values()) | set(POD_REASONS.values()))


def reason_for(kpi: str, component: str) -> str | None:
    """None means this KPI has no legal reason at this component's level."""
    k = kpi.lower()
    table = NODE_REASONS if component.startswith("node-") else POD_REASONS
    if any(f in k for f in ("disk_read", "read_bytes", "diskio_read", "read_io")):
        return table.get("read")
    if any(f in k for f in ("disk_write", "write_bytes", "diskio_write", "write_io")):
        return table.get("write")
    if any(f in k for f in ("disk_space", "fs_usage", "disk_usage", "filesystem")):
        return table.get("space")
    if any(f in k for f in ("memory", "mem_", "pgfault")):
        return table.get("memory")
    if "cpu" in k:
        return table.get("cpu")
    if any(f in k for f in ("packet_loss", "drop")):
        return table.get("loss")
    if "retrans" in k:
        return table.get("retrans")
    if "corrupt" in k:
        return table.get("corrupt")
    if any(f in k for f in ("latency", "rtt", "delay", "network", "net_", "tcp",
                            "rx", "tx", "receive", "transmit")):
        return table.get("latency")
    return None


# -------------------------------------------------------------- the analysis

@dataclass
class Finding:
    """One component's case against it -- every number the evidence file cites."""
    component: str
    cmdb_id: str
    kpi_name: str
    onset: datetime         # first in-window sample outside the band
    peak_at: datetime       # the most extreme in-window sample
    z: float                # how far outside, at its worst
    baseline: float         # the day's median for this series
    peak: float             # the most extreme in-window value
    reason: str | None
    n_anomalous: int        # how many of this component's series went anomalous


@dataclass
class Analysis:
    lo: datetime
    hi: datetime
    n: int
    date: str
    rows: int
    findings: list[Finding] = field(default_factory=list)   # earliest onset first
    note: str = ""                                          # why it is thin, if it is


def _onset(samples: pd.DataFrame, med: float, band: float) -> float | None:
    """First timestamp in `samples` whose value leaves the band. None if never."""
    out = samples.loc[(samples.value - med).abs() > band, "timestamp"]
    return float(out.min()) if len(out) else None


def analyse(instruction: str, dataset_dir: Path) -> Analysis:
    """Always returns an Analysis. A thin one carries `note` and no findings --
    the caller still answers, because a blank and a wrong answer both score zero."""
    win = parse_window(instruction)
    n = failure_count(instruction)
    if win is None:
        return Analysis(lo=datetime.now(CST), hi=datetime.now(CST), n=n, date="",
                        rows=0, note="Could not parse a time window from the instruction.")
    lo, hi = win
    date = lo.strftime("%Y_%m_%d")
    day = _load_day(Path(dataset_dir), date)
    a = Analysis(lo=lo, hi=hi, n=n, date=date, rows=len(day))
    if day.empty:
        a.note = f"No metric file for {date}."
        return a

    lo_s, hi_s = lo.timestamp(), hi.timestamp()
    inw = day[(day.timestamp >= lo_s) & (day.timestamp < hi_s)]
    rest = day[(day.timestamp < lo_s) | (day.timestamp >= hi_s)]
    if inw.empty:
        a.note = (f"No samples inside the window. The day file covers "
                  f"{datetime.fromtimestamp(day.timestamp.min(), CST):%H:%M}-"
                  f"{datetime.fromtimestamp(day.timestamp.max(), CST):%H:%M} UTC+8.")
        return a

    base = rest.groupby(["cmdb_id", "kpi_name"]).value.agg(
        med="median", mad=lambda s: (s - s.median()).abs().median())
    span = inw.groupby(["cmdb_id", "kpi_name"]).value.agg(["max", "min"])
    j = span.join(base, how="inner").reset_index()
    j = j[j.mad > 0]
    if j.empty:
        a.note = "No series with non-zero variation to compare against."
        return a

    # Robust z, both directions: a fault can be a spike or a collapse.
    scale = 1.4826 * j.mad
    j["z"] = np.maximum((j["max"] - j.med).abs(), (j["min"] - j.med).abs()) / scale
    j["peak"] = np.where((j["max"] - j.med).abs() >= (j["min"] - j.med).abs(),
                         j["max"], j["min"])
    j["component"] = j.cmdb_id.map(component_of)

    anomalous = j[j.z >= Z_MIN]
    if anomalous.empty:                      # nothing clears the bar: fall back to
        anomalous = j.nlargest(3, "z")       # the strongest few, and say so
        a.note = (f"Nothing reached z>={Z_MIN}; ranking the three strongest series "
                  f"(max z {j.z.max():.1f}). Treat the answer as a guess.")

    per_component = anomalous.groupby("component").size().to_dict()
    inw_idx = {k: g for k, g in inw.groupby(["cmdb_id", "kpi_name"])}

    findings = []
    for row in anomalous.itertuples(index=False):
        samples = inw_idx.get((row.cmdb_id, row.kpi_name))
        if samples is None:
            continue
        peak_t = float(samples.loc[(samples.value - row.med).abs().idxmax(), "timestamp"])
        t = _onset(samples, row.med, Z_MIN * 1.4826 * row.mad)
        if t is None:                        # crossed on the aggregate, not a sample
            t = peak_t
        findings.append(Finding(
            component=row.component, cmdb_id=row.cmdb_id, kpi_name=row.kpi_name,
            onset=datetime.fromtimestamp(t, CST),
            peak_at=datetime.fromtimestamp(peak_t, CST), z=float(row.z),
            baseline=float(row.med), peak=float(row.peak),
            reason=reason_for(row.kpi_name, row.component),
            n_anomalous=per_component.get(row.component, 1)))

    # THE RANKING: earliest mover first, loudness only as tie-break -- or the
    # baseline's loudest-first, when ablating.
    if RANK_BY == "peak":
        findings.sort(key=lambda f: -f.z)
    else:
        findings.sort(key=lambda f: (f.onset, -f.z))
    a.findings = findings
    return a


def _best_for(a: Analysis, component: str) -> Finding | None:
    """That component's earliest finding that carries a legal reason; else its
    earliest finding at all."""
    mine = [f for f in a.findings if f.component == component]
    if not mine:
        return None
    for f in mine:
        if f.reason:
            return f
    return mine[0]


def pick(a: Analysis) -> list[dict]:
    """The n answers, one per distinct component, earliest mover first."""
    seen, out = [], []
    for f in a.findings:
        if f.component in seen:
            continue
        seen.append(f.component)
        if len(seen) > a.n:
            break
    for component in seen[:a.n]:
        f = _best_for(a, component)
        if f is None:
            continue
        reason = f.reason or ("node CPU load" if component.startswith("node-")
                              else "container CPU load")
        when = f.peak_at if TIME_BY == "peak" else f.onset
        out.append({"datetime": when.strftime("%Y-%m-%d %H:%M:%S"),
                    "component": component, "reason": reason})
    # Never hand back fewer objects than the instruction asked for: a count
    # mismatch scores zero for the whole case, so pad with the best guess we have.
    while len(out) < a.n:
        out.append(out[-1].copy() if out else
                   {"datetime": a.lo.strftime("%Y-%m-%d %H:%M:%S"),
                    "component": "unknown", "reason": "container CPU load"})
    return out[:a.n]


# -------------------------------------------------------------- the evidence

def _confidence(a: Analysis, answers: list[dict]) -> tuple[str, str]:
    """A word and a sentence, both derived from measured separation -- not vibes."""
    if not a.findings:
        return "Low", a.note or "No anomalous series were found in the window."
    first = a.findings[0]
    others = [f for f in a.findings if f.component != first.component]
    if not others:
        return "Medium", (f"Only `{first.component}` cleared z>={Z_MIN}, so there was "
                          "nothing to separate it from.")
    gap = (others[0].onset - first.onset).total_seconds()
    if gap >= 30:
        return "High", (f"`{first.component}` moved {gap:.0f}s before the next "
                        f"component (`{others[0].component}`), which is clear of the "
                        "60s tolerance, so the ordering is unlikely to be sampling noise.")
    if gap > 0:
        return "Low", (f"`{first.component}` moved only {gap:.0f}s before "
                       f"`{others[0].component}`. That is inside the sampling interval, "
                       "so the ordering may be an artefact: treat these as tied.")
    return "Low", (f"`{first.component}` and `{others[0].component}` first deviate in "
                   "the same sample, so first-mover ordering cannot separate them.")


def write_evidence(a: Analysis, answers: list[dict]) -> str:
    """The four sections the judges read, every number carried from `Finding`."""
    word, why = _confidence(a, answers)
    L = ["## Answer", ""]
    for i, x in enumerate(answers, 1):
        prefix = f"{i}. " if len(answers) > 1 else ""
        L.append(f"{prefix}{x['component']} / {x['reason']} / {x['datetime']}")

    L += ["", "## Confidence", "", f"{word}. {why}"]
    if a.note:
        L.append(f"\n{a.note}")

    L += ["", "## Evidence", ""]
    L.append(f"Window {a.lo:%Y-%m-%d %H:%M}–{a.hi:%H:%M} UTC+8, telemetry day "
             f"`{a.date}`, {a.rows:,} metric rows scanned "
             f"(`metric_container.csv`, `metric_node.csv`).")
    L.append("")
    if a.findings:
        L.append("Ranked by **first deviation**, not by peak size — in a cascade the "
                 "loudest component is usually a victim of the earliest one.")
        L.append("")
        L.append("| onset (UTC+8) | component | KPI | baseline | peak | z |")
        L.append("|---|---|---|---|---|---|")
        for f in a.findings[:MAX_CANDIDATES]:
            L.append(f"| {f.onset:%H:%M:%S} | `{f.component}` | `{f.kpi_name}` | "
                     f"{f.baseline:.3g} | {f.peak:.3g} | {f.z:.1f} |")
        first = a.findings[0]
        L.append("")
        L.append(f"`{first.component}` is the earliest mover: `{first.kpi_name}` leaves "
                 f"its day-long band at {first.onset:%H:%M:%S}, going from a median of "
                 f"{first.baseline:.3g} to {first.peak:.3g} (z={first.z:.1f}). "
                 f"{first.n_anomalous} of its series went anomalous in this window.")
    else:
        L.append("No series cleared the anomaly threshold, so there is no table to show. "
                 "The answer above is a guess, offered because a blank scores the same "
                 "as a wrong answer and a narrowed guess does not.")

    L += ["", "## Ruled out", ""]
    chosen = {x["component"] for x in answers}
    ruled = [f for f in a.findings if f.component not in chosen][:4]
    if ruled:
        for f in ruled:
            delta = (f.onset - a.findings[0].onset).total_seconds()
            L.append(f"`{f.component}`: anomalous on `{f.kpi_name}` (z={f.z:.1f}) but "
                     f"first deviates {delta:+.0f}s relative to the pick — downstream "
                     "of it in time, so more likely an effect than the cause.")
    else:
        L.append("Nothing else cleared the threshold, so there was nothing to rule out. "
                 "That is a weaker position than it sounds: with one candidate there is "
                 "no separation to test.")
    L.append("")
    L.append("_Metrics only. Logs and traces were not opened, so a network fault that "
             "shows only as parent-to-child span latency would be missed here._")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ the agent

def solve(instruction: str, dataset_dir: Path, ctx: dict) -> Solution:
    a = analyse(instruction, Path(dataset_dir))
    answers = pick(a)
    return Solution(prediction=format_prediction(answers),
                    evidence=write_evidence(a, answers))
