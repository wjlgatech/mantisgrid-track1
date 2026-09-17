#!/usr/bin/env python3
"""Where should the trace promotion threshold sit?

Metric z and trace z are not the same scale, so promoting a trace finding over
the metric ranking is a gate rather than a comparison, and the gate has to be
placed by measurement. This sweeps it over the whole dev split and reports the
score on the twelve cases whose true reason is a network fault alongside the
score on everything else -- because a threshold that fixes network cases by
breaking the rest is not an improvement.

    python eval/sweep_traces.py --thresholds 0 100 1000 10000 inf
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from score import evaluate                                        # noqa: E402

# Rows whose scoring points name a network reason (latency, loss, retransmission,
# corruption). Derived from the dev answers, not hand-picked.
NET_ROWS = [5, 12, 17, 18, 27, 28, 29, 33, 35, 39, 59, 67]


def run(threshold: str, dataset: Path, queries: Path) -> dict:
    out = ROOT / f"out/sweep/{threshold}"
    env = dict(os.environ, RCA_NET_Z=threshold)
    if threshold == "off":
        env["RCA_TRACES"] = "0"
        env["RCA_NET_Z"] = "inf"
    subprocess.run([sys.executable, "run.py", "--dataset", str(dataset), "--queries",
                    str(queries), "--out", str(out), "--agent", "agents.rca"],
                   cwd=ROOT, env=env, check=True, capture_output=True)
    q = pd.read_csv(queries)
    p = pd.read_csv(out / "predictions.csv").drop(
        columns=[c for c in ("task_index",) if c in
                 pd.read_csv(out / "predictions.csv").columns])
    m = q.merge(p, on="row_id")
    rows = []
    for r in m.itertuples(index=False):
        _, _, sc = evaluate(r.prediction, r.scoring_points)
        rows.append({"row_id": r.row_id, "score": sc,
                     "net": r.row_id in NET_ROWS})
    df = pd.DataFrame(rows)
    wall = pd.read_csv(out / "predictions.csv").wall_s
    return {"all": df.score.mean(), "net": df[df.net].score.mean(),
            "rest": df[~df.net].score.mean(),
            "solved": int((df.score >= 1.0).sum()), "s_case": wall.mean()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--thresholds", nargs="*",
                    default=["off", "0", "100", "1000", "10000", "100000"])
    ap.add_argument("--dataset", default="data/Market-cloudbed-1")
    args = ap.parse_args()
    dataset = (ROOT / args.dataset).resolve()
    queries = dataset / "dev" / "query_dev.csv"

    lines = ["| trace promotion | all 70 | 12 network cases | other 58 | solved | s/case |",
             "|---|---|---|---|---|---|"]
    print(lines[0])
    for t in args.thresholds:
        r = run(t, dataset, queries)
        label = ("traces off" if t == "off" else
                 "always promote" if t == "0" else f"z >= {int(float(t)):,}")
        row = (f"| {label} | **{r['all']:.3f}** | {r['net']:.3f} | {r['rest']:.3f} | "
               f"{r['solved']}/70 | {r['s_case']:.1f} |")
        lines.append(row)
        print(row)
    (ROOT / "eval" / "traces.md").write_text(
        "# Placing the trace-promotion threshold\n\n"
        "Trace z and metric z are different scales, so promotion is a gate, not a\n"
        "comparison. Swept over all 70 dev cases. The `12 network cases` column is\n"
        "the ones whose true reason is a network fault; `other 58` is the rest, and\n"
        "it is there to catch a threshold that helps one by breaking the other.\n\n"
        + "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
