#!/usr/bin/env python3
"""Attribute the effect of each decision, one at a time.

This agent differs from the starter baseline in three places. Bundled together
they are a story; separated they are a measurement, and only one of them
survived contact with the data.

    timezone   UTC (starter) vs UTC+8 (the telemetry's actual zone)
    RCA_RANK   peak  -- the loudest anomaly is the cause   (starter)
               onset -- the earliest deviation is the cause
    RCA_TIME   peak  -- answer with the moment it hurt most (starter)
               onset -- answer with the moment it began

Run:  python eval/ablate.py --dataset data/Market-cloudbed-1
It writes eval/results.md and prints the same table.
"""
from __future__ import annotations

import argparse
import itertools
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run_one(agent: str, rank: str, time_by: str, dataset: Path, queries: Path,
            out: Path) -> dict:
    env = dict(os.environ, RCA_RANK=rank, RCA_TIME=time_by)
    t0 = time.time()
    subprocess.run([sys.executable, "run.py", "--dataset", str(dataset),
                    "--queries", str(queries), "--out", str(out), "--agent", agent],
                   cwd=ROOT, env=env, check=True, capture_output=True)
    wall = time.time() - t0
    scored = subprocess.run([sys.executable, "score.py", "--predictions",
                             str(out / "predictions.csv"), "--queries", str(queries)],
                            cwd=ROOT, capture_output=True, text=True, check=True).stdout
    mean = re.search(r"mean score\s*:\s*([\d.]+)", scored)
    solved = re.search(r"fully solved:\s*(\d+)", scored)
    tasks = dict(re.findall(r"(task_\d)\s+\d+ cases\s+mean\s+([\d.]+)", scored))
    blanks = sum(1 for line in (out / "predictions.csv").read_text().splitlines()
                 if '"1": {}' in line)
    return {"mean": float(mean.group(1)) if mean else 0.0,
            "solved": int(solved.group(1)) if solved else 0,
            "blanks": blanks, "wall": wall, "tasks": tasks, "raw": scored}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="data/Market-cloudbed-1")
    ap.add_argument("--queries", default=None)
    args = ap.parse_args()
    dataset = (ROOT / args.dataset).resolve()
    queries = Path(args.queries) if args.queries else dataset / "dev" / "query_dev.csv"

    rows = []
    # the starter, untouched: UTC window parsing, loudest-first, peak time
    rows.append(("baseline (starter, UTC)", "—", "—",
                 run_one("agents.heuristic", "peak", "peak", dataset, queries,
                         ROOT / "out/ab/baseline")))
    # every combination of the two decisions, all in UTC+8
    for rank, time_by in itertools.product(("peak", "onset"), repeat=2):
        rows.append((f"UTC+8", rank, time_by,
                     run_one("agents.rca", rank, time_by, dataset, queries,
                             ROOT / f"out/ab/{rank}-{time_by}")))

    tasks = sorted({t for _, _, _, r in rows for t in r["tasks"]})
    head = (f"| config | rank | time | mean | solved | blank | "
            + " | ".join(tasks) + " | s/case |")
    sep = "|---" * (7 + len(tasks)) + "|"
    lines = [head, sep]
    for label, rank, time_by, r in rows:
        cells = " | ".join(r["tasks"].get(t, "—") for t in tasks)
        lines.append(f"| {label} | {rank} | {time_by} | **{r['mean']:.3f}** | "
                     f"{r['solved']}/70 | {r['blanks']} | {cells} | "
                     f"{r['wall']/70:.1f} |")
    table = "\n".join(lines)
    print(table)
    (ROOT / "eval" / "results.md").write_text(
        "# Ablation: which decision actually paid\n\n"
        "`mean` is OpenRCA's own evaluator over all 70 dev cases. `blank` counts\n"
        "predictions with no answer in them — the starter emits 24, and a blank\n"
        "scores exactly what a wrong guess does.\n\n" + table + "\n")


if __name__ == "__main__":
    main()
