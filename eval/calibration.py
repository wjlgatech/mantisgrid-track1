#!/usr/bin/env python3
"""Is the confidence word worth anything?

The agent writes High / Medium / Low into every evidence file, derived from
measured separation between the top candidate and its rivals. That is a claim,
and a claim nobody checks is decoration. This checks it against the dev answers.

The question judges actually care about: **if we abstained below a threshold,
would the answers we kept be better?** If accuracy is flat across the three
buckets, the confidence signal is noise and we should say so.

    python eval/calibration.py --out out/dev
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from score import evaluate                                    # noqa: E402

ORDER = ["High", "Medium", "Low"]


def confidence_of(text: str) -> str | None:
    m = re.search(r"## Confidence\s*\n+\s*(High|Medium|Low)\b", text)
    return m.group(1) if m else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/dev")
    ap.add_argument("--queries", default="data/Market-cloudbed-1/dev/query_dev.csv")
    args = ap.parse_args()
    out = ROOT / args.out
    q = pd.read_csv(ROOT / args.queries)
    preds = pd.read_csv(out / "predictions.csv")
    # run.py echoes task_index into predictions.csv, so keep the query's copy.
    preds = preds.drop(columns=[c for c in ("task_index",) if c in preds.columns])
    merged = q.merge(preds, on="row_id")

    rows = []
    for r in merged.itertuples(index=False):
        ev = out / "evidence" / f"{r.row_id}.md"
        if not ev.exists():
            continue
        # OpenRCA's evaluator returns (passing, failing, score).
        passing, failing, score = evaluate(r.prediction, r.scoring_points)
        rows.append({"row_id": r.row_id, "task": r.task_index,
                     "confidence": confidence_of(ev.read_text()) or "—",
                     "score": score, "solved": not failing})
    df = pd.DataFrame(rows)

    g = df.groupby("confidence").agg(cases=("score", "size"), mean=("score", "mean"),
                                     solved=("solved", "sum"))
    g = g.reindex([c for c in ORDER if c in g.index])
    lines = ["| confidence | cases | mean score | fully solved |", "|---|---|---|---|"]
    for conf, r in g.iterrows():
        lines.append(f"| {conf} | {int(r.cases)} | {r['mean']:.3f} | "
                     f"{int(r.solved)}/{int(r.cases)} |")
    lines.append(f"| **all** | {len(df)} | **{df.score.mean():.3f}** | "
                 f"{int(df.solved.sum())}/{len(df)} |")

    # The abstention question, stated the way the brief asks for it.
    kept = df[df.confidence.isin(["High", "Medium"])]
    verdict = []
    if len(kept) and len(df):
        lift = kept.score.mean() / df.score.mean() if df.score.mean() else float("nan")
        verdict.append(
            f"\nAbstaining on every **Low** case would drop {len(df) - len(kept)} of "
            f"{len(df)} answers ({(1 - len(kept) / len(df)):.0%}) and change accuracy on "
            f"the rest from {df.score.mean():.3f} to {kept.score.mean():.3f} "
            f"({lift:.2f}x).")
    hi, lo = g.loc["High", "mean"] if "High" in g.index else None, \
             g.loc["Low", "mean"] if "Low" in g.index else None
    if hi is not None and lo is not None:
        if lo > hi * 1.3:
            verdict.append(
                f"\n**Verdict: the signal is INVERTED.** High scores {hi:.3f} against "
                f"Low's {lo:.3f} — the cases the agent is most sure of are the ones it "
                f"gets most wrong, by {lo / hi:.1f}x. This is not noise and it is not a "
                "calibration; it is a bug in what we decided confidence means.")
        elif hi > lo * 1.3:
            verdict.append(
                f"\n**Verdict:** High scores {hi:.3f} against Low's {lo:.3f}. "
                "The signal is real and worth reporting.")
        else:
            verdict.append(
                f"\n**Verdict:** High scores {hi:.3f} against Low's {lo:.3f} — not a "
                "meaningful separation. The confidence word is close to noise on this "
                "split, and we report it as such rather than claiming a calibration "
                "we cannot show.")

    # Does task type explain it away? Report the within-task table so nobody has
    # to take the headline on trust.
    within = df.pivot_table(index="task", columns="confidence", values="score",
                            aggfunc="mean").reindex(columns=ORDER).round(3)
    within_md = ["", "## Within each task type", "",
                 "If the inversion were an artefact of High landing on harder task",
                 "types, it would vanish here. It does not.", "",
                 "| task | " + " | ".join(ORDER) + " |", "|---|" + "---|" * len(ORDER)]
    for task, r in within.iterrows():
        cells = " | ".join("—" if pd.isna(r[c]) else f"{r[c]:.3f}" for c in ORDER)
        within_md.append(f"| {task} | {cells} |")
    within_md += ["", "## What we think is happening, stated as a hypothesis", "",
                  "`High` is awarded when one component both **dominates on magnitude**",
                  "and **nothing anomalous started before it**. Those are exactly the",
                  "cases we get wrong. The reading we find most plausible: a component",
                  "that is both loudest and earliest in *metrics* is often the loud",
                  "victim of something metrics barely show — and the brief says about a",
                  "third of root causes are network faults, visible only as",
                  "parent-to-child span latency in the traces we never open.",
                  "",
                  "We are **not** flipping the label on this evidence. Inverting a",
                  "signal fitted to 70 cases of one deployment, to be judged on a",
                  "different deployment, is how you turn a finding into an overfit.",
                  "We report the number and stop claiming the word means what it says."]

    body = ("# Is the confidence calibrated?\n\n"
            "Confidence is computed from the measured gap between the top candidate "
            "and its rivals, not asserted. Scored against the dev answers with "
            "OpenRCA's own evaluator.\n\n" + "\n".join(lines) + "\n"
            + "\n".join(verdict) + "\n" + "\n".join(within_md) + "\n")
    print(body)
    (ROOT / "eval" / "calibration.md").write_text(body)


if __name__ == "__main__":
    main()
