#!/usr/bin/env python3
"""The finish line. Fails on the things that make a submission unjudgeable.

A low score is a result. An unjudgeable submission is a wasted day, and every
failure mode below is one the track docs warn about and the evaluator punishes
silently -- it scores zero and tells you nothing.

    python eval/gate.py --out out/dev --queries data/Market-cloudbed-1/query.csv

Exit code is non-zero if any check fails, so `make check` gates on it.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

# The evaluator reads predictions with THIS regex -- not a JSON parser. Key order
# is load-bearing: reorder them and it matches nothing and scores zero in silence.
EVALUATOR_RE = (r'{\s*'
                r'(?:"root cause occurrence datetime":\s*"(.*?)")?,?\s*'
                r'(?:"root cause component":\s*"(.*?)")?,?\s*'
                r'(?:"root cause reason":\s*"(.*?)")?\s*}')

REQUIRED_SECTIONS = ("## Answer", "## Confidence", "## Evidence", "## Ruled out")

# 20 judged cases share a 20-minute wall. Leave headroom for a slower machine
# than this one (the judges run 2 CPUs and 8 GB).
RUN_BUDGET_S = 20 * 60
JUDGED_CASES = 20
SAFETY = 0.60          # we must fit in this fraction of the budget to pass

WORD_COUNTS = {"one failure": 1, "a single failure": 1, "two failures": 2,
               "three failures": 3, "four failures": 4}

fails: list[str] = []
warns: list[str] = []


def check(ok: bool, msg: str, hard: bool = True) -> None:
    if ok:
        print(f"  ok    {msg}")
    elif hard:
        print(f"  FAIL  {msg}")
        fails.append(msg)
    else:
        print(f"  warn  {msg}")
        warns.append(msg)


def declared_failures(instruction: str) -> int:
    t = instruction.lower()
    for word, n in WORD_COUNTS.items():
        if word in t:
            return n
    return 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/dev")
    ap.add_argument("--queries", default="data/Market-cloudbed-1/dev/query_dev.csv")
    args = ap.parse_args()
    out, queries = ROOT / args.out, ROOT / args.queries

    print("\n-- output shape --")
    pred_path = out / "predictions.csv"
    if not pred_path.exists():
        print(f"  FAIL  {pred_path} does not exist -- run the agent first")
        sys.exit(1)
    preds = pd.read_csv(pred_path)
    q = pd.read_csv(queries)
    check(set(["row_id", "prediction"]) <= set(preds.columns),
          "predictions.csv has row_id and prediction")
    check(len(preds) == len(q),
          f"one row per case ({len(preds)} predictions, {len(q)} queries)")
    check(set(preds.row_id) == set(q.row_id), "row_ids match the query file exactly")

    print("\n-- the evaluator's regex (key order is load-bearing) --")
    merged = q.merge(preds, on="row_id")
    unparsed, miscount, blank = [], [], []
    for r in merged.itertuples(index=False):
        found = re.findall(EVALUATOR_RE, str(r.prediction))
        if not found:
            unparsed.append(r.row_id)
            continue
        if all(not any(g) for g in found):
            blank.append(r.row_id)
        want = declared_failures(r.instruction)
        if len(found) != want:
            miscount.append((r.row_id, want, len(found)))
    check(not unparsed, f"every prediction matches the evaluator's regex"
          + (f" (bad: {unparsed[:8]})" if unparsed else ""))
    check(not miscount, "failure count matches the instruction on every case"
          + (f" (wrong: {miscount[:5]})" if miscount else ""))
    check(not blank, f"no blank answers -- a blank scores what a wrong guess does"
          + (f" ({len(blank)} blank: {blank[:8]})" if blank else ""))

    print("\n-- evidence files (the largest single share of the grade) --")
    ev_dir = out / "evidence"
    missing = [int(r) for r in q.row_id if not (ev_dir / f"{r}.md").exists()]
    check(not missing, f"one evidence file per case"
          + (f" (missing: {missing[:8]})" if missing else ""))
    bad_sections, empty = [], []
    for r in q.row_id:
        f = ev_dir / f"{r}.md"
        if not f.exists():
            continue
        text = f.read_text()
        if len(text.strip()) < 80:
            empty.append(int(r))
        if not all(s in text for s in REQUIRED_SECTIONS):
            bad_sections.append(int(r))
    check(not bad_sections,
          "every evidence file has all four sections the brief asks for"
          + (f" (bad: {bad_sections[:8]})" if bad_sections else ""))
    check(not empty, "no stub evidence files" + (f" ({empty[:8]})" if empty else ""))

    print("\n-- the wall clock, which is the limit most likely to bind --")
    if "wall_s" in preds.columns and len(preds):
        per_case = preds.wall_s.mean()
        projected = per_case * JUDGED_CASES
        check(projected < RUN_BUDGET_S * SAFETY,
              f"{JUDGED_CASES} cases project to {projected/60:.1f} min "
              f"({per_case:.1f}s/case), budget {RUN_BUDGET_S/60:.0f} min")
        check(preds.wall_s.max() < 600,
              f"slowest case {preds.wall_s.max():.1f}s, per-case limit 600s")
    else:
        check(False, "predictions.csv has no wall_s column", hard=False)

    print("\n-- portability: we are judged on a DIFFERENT deployment --")
    # Component names there are not the names here. Anything matching a pod name
    # from this bundle, hardcoded in the agent, is a trap we set for ourselves.
    src = "\n".join(p.read_text() for p in (ROOT / "agents").glob("*.py"))
    leaked = sorted(set(re.findall(r"\b[a-z]+service-\d\b", src)))
    check(not leaked, "no component name from this bundle is hardcoded in agents/"
          + (f" (found: {leaked})" if leaked else ""))

    print()
    if fails:
        print(f"{len(fails)} check(s) failed.")
        sys.exit(1)
    print(f"All checks passed. {len(warns)} warning(s).")


if __name__ == "__main__":
    main()
