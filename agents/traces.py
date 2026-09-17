"""Network faults, which the metrics cannot see.

About a quarter of the scored reasons in this bundle are network faults --
latency, packet loss, retransmission, corruption. Measured on the dev split, our
metrics-only agent scores **0.111** on those cases against **0.217** on all the
others, and ten of the twelve score exactly zero. That is the single largest hole
in the agent, and it is a retrieval problem rather than a reasoning one: the
signal is not in the metrics we read.

Where it is: **the gap between a parent span and its child**. When service A calls
service B, A's span covers B's span plus the time on the wire in both directions.
If the network between them degrades, A's duration grows while B's does not, and
the difference -- which is time nobody's CPU spent -- is the fault.

    parent span (frontend-0)       |---------------------------|
    child span  (shippingservice-1)     |---------------|
    gap = parent.duration - child.duration  ~= time on the wire

Two design choices here were wrong on the first attempt and are corrected by
measurement, not by argument (both tested against dev cases whose answer we know):

  * **The statistic is the 95th percentile of the gap, not the median.** Packet
    loss, retransmission and corruption affect a *fraction* of calls. The median
    is robust against exactly that, which is the opposite of what we want: on a
    known network case the median moved 1890 -> 2322 microseconds (z=2.8, under
    any sane threshold) while the p95 moved enough to rank the true component
    first by five orders of magnitude.
  * **The suspect is the CALLER, not the callee.** The degraded interface belongs
    to the container whose span is inflated -- the one making the call. Ranking
    callees put the true answer nowhere; ranking callers put it first.

Traces localise; metrics classify. This module says *which component* has a
network problem. Which of the four network reasons it is -- latency, loss,
retransmission, corruption -- is read from that component's own network KPIs in
`rca.reason_for`, because a span gap looks the same for all four.

Two units traps, both live in this file:

  * `trace_span.timestamp` is in **milliseconds**; every metric file is in
    seconds. Mixing them is a 1000x error and the most expensive mistake in this
    dataset.
  * `duration` is in **microseconds**.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from pathlib import Path

ENABLED = os.environ.get("RCA_TRACES", "1") != "0"

CHUNK = 1_000_000
Z_MIN = 4.0
MIN_CALLS = 50          # a component needs this many in-window calls to rank
PCTL = 0.95             # the gap statistic: a tail measure, not a middle one
BASELINE_EVERY = 7      # keep 1 in N out-of-window rows as the baseline sample

_CACHE: dict = {}

COLS = ["timestamp", "cmdb_id", "duration", "span_id", "parent_span"]


@dataclass
class NetFinding:
    """One component whose outbound wire time inflated inside the window."""
    component: str          # the caller: whose interface is degraded
    onset: datetime         # first in-window minute already outside the band
    z: float
    baseline_us: float      # p95 gap over the rest of the day, microseconds
    peak_us: float          # p95 gap inside the window
    calls: int
    worst_peer: str         # the callee it slowed down most, for the evidence file


def _scan(path: Path, lo_ms: int, hi_ms: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One pass over the day: rows inside the window, and a sample of the rest.

    A full day of spans is 1.3 GB and 9.1M rows. We read it once per (day, window)
    in chunks, keeping only five columns, so peak memory stays far below the
    judged machine's 8 GB.
    """
    key = (str(path), lo_ms, hi_ms)
    if key in _CACHE:
        return _CACHE[key]
    inside, outside = [], []
    for chunk in pd.read_csv(path, usecols=COLS, chunksize=CHUNK):
        m = (chunk.timestamp >= lo_ms) & (chunk.timestamp < hi_ms)
        inside.append(chunk[m])
        outside.append(chunk[~m].iloc[::BASELINE_EVERY])
    out = (pd.concat(inside, ignore_index=True) if inside else pd.DataFrame(columns=COLS),
           pd.concat(outside, ignore_index=True) if outside else pd.DataFrame(columns=COLS))
    _CACHE[key] = out
    return out


def _edges(spans: pd.DataFrame) -> pd.DataFrame:
    """Join every span to its parent, and keep the cross-component calls.

    The gap is the parent's duration minus the child's: the part of the call the
    child did not spend working. A parent and child on the SAME component share a
    process, so their gap is not wire time and is dropped.
    """
    if spans.empty:
        return pd.DataFrame(columns=["caller", "callee", "gap", "timestamp"])
    parents = spans[["span_id", "cmdb_id", "duration"]].rename(
        columns={"span_id": "parent_span", "cmdb_id": "caller", "duration": "p_dur"})
    j = spans.merge(parents, on="parent_span", how="inner")
    j = j[j.caller != j.cmdb_id]
    j["gap"] = j.p_dur - j.duration
    j = j[j.gap >= 0]                       # clock skew and partial traces
    return j.rename(columns={"cmdb_id": "callee"})[
        ["caller", "callee", "gap", "timestamp"]]


def network_findings(dataset_dir: Path, date: str, lo: datetime,
                     hi: datetime) -> list[NetFinding]:
    """Components whose outbound wire time inflated in the window, worst first."""
    if not ENABLED:
        return []
    path = Path(dataset_dir) / "telemetry" / date / "trace" / "trace_span.csv"
    if not path.exists():
        return []
    # milliseconds -- the trace files do not share the metrics' unit
    lo_ms, hi_ms = int(lo.timestamp() * 1000), int(hi.timestamp() * 1000)
    inside, outside = _scan(path, lo_ms, hi_ms)
    if inside.empty or outside.empty:
        return []

    win, base = _edges(inside), _edges(outside)
    if win.empty or base.empty:
        return []

    def tail(s: pd.Series) -> float:
        return s.quantile(PCTL)

    b = base.groupby("caller").gap.agg(
        v=tail, mad=lambda s: (s - s.median()).abs().median())
    w = win.groupby("caller").gap.agg(v=tail, calls="size")
    j = w.join(b, how="inner", lsuffix="_w", rsuffix="_b").reset_index()
    j = j[(j.mad > 0) & (j.calls >= MIN_CALLS)]
    if j.empty:
        return []
    j["z"] = (j.v_w - j.v_b) / (1.4826 * j.mad)
    j = j[j.z >= Z_MIN].sort_values("z", ascending=False)

    tz = lo.tzinfo or timezone.utc
    findings = []
    for row in j.itertuples(index=False):
        mine = win[win.caller == row.caller].copy()
        # onset: the first minute whose tail gap is already outside the band
        mine["minute"] = (mine.timestamp // 60000) * 60000
        per_min = mine.groupby("minute").gap.agg(tail)
        band = row.v_b + Z_MIN * 1.4826 * row.mad
        over = per_min[per_min > band]
        onset_ms = int(over.index[0] if len(over) else per_min.idxmax())
        peer = mine.groupby("callee").gap.agg(tail)
        findings.append(NetFinding(
            component=row.caller,
            onset=datetime.fromtimestamp(onset_ms / 1000, tz), z=float(row.z),
            baseline_us=float(row.v_b), peak_us=float(row.v_w),
            calls=int(row.calls),
            worst_peer=str(peer.idxmax()) if len(peer) else "?"))
    return findings
