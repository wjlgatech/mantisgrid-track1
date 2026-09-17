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
from agents import traces                    # noqa: E402

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
# A trace finding is promoted above the metric ranking only when the wire-time
# inflation is unambiguous. Metric z and trace z are not the same scale, so this
# is a gate, not a comparison -- and the threshold is measured (eval/traces.md),
# not guessed.
NET_PROMOTE_Z = float(os.environ.get("RCA_NET_Z", "inf"))
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

# Ground truth names components at THREE levels -- service (44% of answers),
# node (37%) and pod (19%) -- and v1 only ever produced two of them. A service
# name like `adservice` was unreachable by construction, so 44% of the answer
# space could not be emitted at any rank. metric_service.csv carries it: its
# `service` column is `<name>-<protocol>` (adservice-grpc, frontend-http), and
# stripping the protocol recovers all nine ground-truth service names exactly.
SERVICE_PROTOCOLS = ("-grpc", "-http", "-tcp")


def service_of(raw: str) -> str:
    for suffix in SERVICE_PROTOCOLS:
        if raw.endswith(suffix):
            return raw[: -len(suffix)]
    return raw


def _load_services(dataset: Path, date: str) -> pd.DataFrame:
    """metric_service.csv as (timestamp, cmdb_id, kpi_name, value), so service
    rows flow through exactly the same z-score path as pods and nodes.

    1 MB a day against metric_container's 265 MB -- the cheapest sensor in the
    bundle, and the one that carries nearly half the answers."""
    f = dataset / "telemetry" / date / "metric" / "metric_service.csv"
    if not f.exists():
        return pd.DataFrame(columns=["timestamp", "cmdb_id", "kpi_name", "value", "source"])
    df = pd.read_csv(f)
    df["cmdb_id"] = df.service.map(service_of)
    long = df.melt(id_vars=["timestamp", "cmdb_id"], value_vars=["rr", "sr", "mrt", "count"],
                   var_name="kpi_name", value_name="value")
    long["source"] = "metric_service"
    return long.dropna(subset=["value"])


def _load_day(dataset: Path, date: str) -> pd.DataFrame:
    """Container, node and service metrics for one day. Cached: the judged run
    reuses a day across cases, and re-reading 300 MB per case is how a run times
    out."""
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
    svc = _load_services(dataset, date)
    if not svc.empty:
        frames.append(svc)
    out = (pd.concat(frames, ignore_index=True) if frames else
           pd.DataFrame(columns=["timestamp", "cmdb_id", "kpi_name", "value", "source"]))
    _DAY_CACHE[key] = out
    return out


def component_of(cmdb_id: str) -> str:
    """metric_container is '<node>.<pod>'; metric_node and metric_service already
    carry the component name."""
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


SERVICE_KPI_REASONS = {
    "mrt": "container network latency",     # mean response time rose
    "sr": "container process termination",  # success rate fell: callees dying
    "rr": "container network latency",      # request rate disturbed
    "count": "container network latency",
}


def reason_for(kpi: str, component: str) -> str | None:
    """None means this KPI has no legal reason at this component's level."""
    k = kpi.lower()
    if k in SERVICE_KPI_REASONS:
        return SERVICE_KPI_REASONS[k]
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
    zn: float               # that z as a percentile within its OWN source
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
    findings: list[Finding] = field(default_factory=list)   # ranked, best first
    net: list = field(default_factory=list)                 # traces.NetFinding, worst first
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

    # A z from metric_service (rr/sr/mrt/count) and a z from metric_container
    # (CPU, bytes) are not the same quantity: different distributions, different
    # tails. Ranking them against each other let services take 68% of the rank-1
    # slots when they are only 44% of the answers, and cost 0.048 overall.
    # So each source is scored against ITS OWN distribution: a series' rank is its
    # percentile among that source's series in this window. Distribution-free, and
    # it fits nothing about which answers happen to be correct.
    # `source` is lost in the groupby that builds j, so put it back from the
    # day frame: every cmdb_id comes from exactly one file.
    j["source"] = j.cmdb_id.map(dict(zip(day.cmdb_id, day.source)))
    j["zn"] = j.groupby("source").z.rank(pct=True)

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
            zn=float(getattr(row, "zn", 0.0)),
            baseline=float(row.med), peak=float(row.peak),
            reason=reason_for(row.kpi_name, row.component),
            n_anomalous=per_component.get(row.component, 1)))

    # Network faults barely move a metric, so they get their own pass over the
    # traces. See agents/traces.py for why the statistic is a tail and why the
    # suspect is the caller.
    try:
        a.net = traces.network_findings(Path(dataset_dir), date, lo, hi)
    except Exception as e:                      # noqa: BLE001 -- traces are a bonus
        a.note = (a.note + f" Trace pass failed ({type(e).__name__}).").strip()

    # THE RANKING: earliest mover first, loudness only as tie-break -- or the
    # baseline's loudest-first, when ablating.
    if RANK_BY == "peak":
        findings.sort(key=lambda f: (-f.zn, -f.z))
    else:
        findings.sort(key=lambda f: (f.onset, -f.zn))
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


def _net_reason(a: Analysis, component: str) -> str:
    """Which network reason. Traces localise; metrics classify -- a span gap looks
    identical for latency, loss, retransmission and corruption, so the choice
    comes from that component's own network KPIs when it has any."""
    for f in a.findings:
        if f.component == component and f.reason and "network" in f.reason:
            return f.reason
    for f in a.findings:
        if f.component == component and f.reason and (
                "packet" in f.reason or "loss" in f.reason):
            return f.reason
    return "container network latency"


def pick(a: Analysis) -> list[dict]:
    """The n answers, one per distinct component, best candidate first."""
    seen, out = [], []
    # A decisive wire-time inflation outranks the metric table: metrics cannot
    # see a network fault, so their silence about one is not evidence.
    if a.net and a.net[0].z >= NET_PROMOTE_Z:
        n0 = a.net[0]
        out.append({"datetime": n0.onset.strftime("%Y-%m-%d %H:%M:%S"),
                    "component": n0.component, "reason": _net_reason(a, n0.component)})
        seen.append(n0.component)
        if len(out) >= a.n:
            return out[:a.n]
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
    """A word and a sentence, both derived from measured separation -- not vibes.

    The separation that matters depends on what we ranked by: magnitude if
    RANK_BY is peak, onset ordering if it is onset. Saying the wrong one would be
    a claim the data does not support, which is worse than saying nothing.
    """
    if not a.findings:
        return "Low", a.note or "No anomalous series were found in the window."
    first = a.findings[0]
    others = [f for f in a.findings if f.component != first.component]
    if not others:
        return "Medium", (f"Only `{first.component}` cleared z>={Z_MIN}, so there was "
                          "nothing to separate it from. One candidate is not a "
                          "diagnosis, it is the absence of an alternative.")
    rival = others[0]
    if RANK_BY == "peak":
        ratio = first.z / rival.z if rival.z else float("inf")
        earlier = [f for f in others if f.onset < first.onset]
        if earlier:
            e = min(earlier, key=lambda f: f.onset)
            gap = (first.onset - e.onset).total_seconds()
            return "Low", (
                f"`{first.component}` deviates {ratio:.1f}x harder than the next "
                f"candidate (z={first.z:.0f} vs {rival.z:.0f}), which is why it was "
                f"picked -- but `{e.component}` started moving {gap:.0f}s EARLIER. "
                "If that ordering is causal rather than sampling noise, the earlier "
                "component is the better answer and this one is its victim.")
        if ratio >= 3:
            return "High", (f"`{first.component}` deviates {ratio:.1f}x harder than "
                            f"anything else (z={first.z:.0f} vs {rival.z:.0f}) and "
                            "nothing anomalous started before it.")
        return "Medium", (f"`{first.component}` leads on magnitude but only by "
                          f"{ratio:.1f}x (z={first.z:.0f} vs {rival.z:.0f}); "
                          f"`{rival.component}` is a live alternative.")
    gap = (rival.onset - first.onset).total_seconds()
    if gap >= 30:
        return "High", (f"`{first.component}` moved {gap:.0f}s before the next "
                        f"component (`{rival.component}`), clear of the 60s "
                        "tolerance, so the ordering is unlikely to be noise.")
    if gap > 0:
        return "Low", (f"`{first.component}` moved only {gap:.0f}s before "
                       f"`{rival.component}` -- inside the sampling interval, so "
                       "treat these as tied.")
    return "Low", (f"`{first.component}` and `{rival.component}` first deviate in the "
                   "same sample, so onset ordering cannot separate them.")


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
        if RANK_BY == "peak":
            L.append("Ranked by **peak deviation** (robust z against the rest of the "
                     "day). `onset` is the first sample to leave the band — it dates "
                     "the fault, but it does not order this table.")
        else:
            L.append("Ranked by **first deviation** — in a cascade the loudest "
                     "component is often a victim of the earliest one.")
        L.append("")
        L.append("| onset (UTC+8) | component | KPI | baseline | peak | z |")
        L.append("|---|---|---|---|---|---|")
        for f in a.findings[:MAX_CANDIDATES]:
            L.append(f"| {f.onset:%H:%M:%S} | `{f.component}` | `{f.kpi_name}` | "
                     f"{f.baseline:.3g} | {f.peak:.3g} | {f.z:.1f} |")
        first = a.findings[0]
        lead = ("has the largest deviation" if RANK_BY == "peak"
                else "is the earliest mover")
        L.append("")
        L.append(f"`{first.component}` {lead}: `{first.kpi_name}` leaves its day-long "
                 f"band at {first.onset:%H:%M:%S}, going from a median of "
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
        picked = a.findings[0]
        for f in ruled:
            delta = (f.onset - picked.onset).total_seconds()
            if delta > 0:
                L.append(f"`{f.component}`: anomalous on `{f.kpi_name}` (z={f.z:.0f}) "
                         f"but started {delta:.0f}s AFTER the pick — consistent with "
                         "being downstream of it, an effect rather than the cause.")
            elif delta < 0:
                L.append(f"`{f.component}`: anomalous on `{f.kpi_name}` (z={f.z:.0f}), "
                         f"and it started {-delta:.0f}s BEFORE the pick. Not ruled out "
                         f"on timing — it is ruled out only on magnitude "
                         f"(z={f.z:.0f} vs {picked.z:.0f}). If the fault is one that "
                         "shows small in metrics, this is the better answer.")
            else:
                L.append(f"`{f.component}`: anomalous on `{f.kpi_name}` (z={f.z:.0f}) "
                         "and first deviates in the SAME sample as the pick. Timing "
                         "cannot separate these two at this sampling rate.")
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
