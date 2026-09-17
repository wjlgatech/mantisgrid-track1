"""The routed agent: free analysis, one model call that reasons, one that doesn't.

Routing here is decided by measurement (`eval/models.md`), not by the price list:

  * **One call thinks.** Picking the root cause from a ranked candidate table is
    the only step in this agent that is genuinely a reasoning problem. It goes to
    a strong model with `think=True`.
  * **Everything else runs thinking OFF.** Reading a number out of a question and
    shaping a sentence are not reasoning, and thinking costs 20-50x the output
    tokens -- the priciest and slowest token there is.
  * **The cheap tier is not the fast tier.** GLM-4.7-Flash took 24.6s on our probe
    and hit its token cap; GLM-5.2 answered the same prompt in 1.0s. So the cheap
    tier is used where latency does not matter and the strong tier is not feared.

Everything numeric in the evidence file is still compiled from measured values by
`rca.write_evidence`. The model is allowed to choose an answer and to write prose
around pinned numbers. It is never asked to recall one, because evidence that is
not in the data scores zero -- worse than none.

The safety property that matters: **this agent can never score below the free
one.** Every model call is wrapped; on any failure the baseline answer from
`agents.rca` stands and the evidence says what happened.

    python run.py ... --agent agents.routed
    RCA_MODEL=zai-org/GLM-5.2 python run.py ... --agent agents.routed   # ablation
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from run import Solution, format_prediction                      # noqa: E402
from agents.client import LLM, ModelUnavailable                   # noqa: E402
from agents import rca                                            # noqa: E402

# Preference order per tier. The second name is a real decision: it should be
# close in capability, or a busy provider quietly changes what the agent is.
STRONG = ["zai-org/GLM-5.2", "zai-org/GLM-5.1"]
CHEAP = ["zai-org/GLM-5", "zai-org/GLM-4.6"]

CANDIDATES = 10          # rows of the ranked table shown to the strong model

# Does the reasoning call actually need to think? Thinking costs 20-50x the
# output tokens and output tokens are the slowest thing an agent buys, so this
# is the dial the cost/accuracy curve turns on. eval/routed_compare.py measures it.
THINK = os.environ.get("RCA_THINK", "1") != "0"

# --- the run-level clock ------------------------------------------------------
# The judged run is 20 cases in 20 minutes, enforced from outside. run.py writes
# predictions.csv after every case, so a run that overruns keeps what it finished
# and scores zero on the rest. This module is imported once and solve() is called
# per case, so module state is the whole run's state: we can watch the clock and
# spend less on later cases if we are falling behind.
RUN_BUDGET_S = float(os.environ.get("RCA_RUN_BUDGET_S", 20 * 60))
SAFETY = 0.80            # aim to finish inside this fraction of the budget
MIN_CASE_S = 3.0         # below this, skip the models and answer for free
_started = time.monotonic()
_seen = 0


def _case_budget(dataset_dir: Path) -> float:
    """Seconds this case may spend on model calls, given how the run is going."""
    total = _total_cases(dataset_dir)
    left = RUN_BUDGET_S * SAFETY - (time.monotonic() - _started)
    remaining = max(1, total - _seen)
    return left / remaining


_total: int | None = None


def _total_cases(dataset_dir: Path) -> int:
    """How many cases this run has. The judged command points --queries at
    query.csv inside the dataset, so we can count them without being told."""
    global _total
    if _total is None:
        _total = 20                                    # the judged run's size
        for name in ("query.csv", "dev/query_dev.csv"):
            f = Path(dataset_dir) / name
            if f.exists():
                try:
                    import pandas as pd
                    _total = max(1, len(pd.read_csv(f)))
                    break
                except Exception:                      # noqa: BLE001
                    pass
    return _total


def _json(text: str) -> dict:
    """The first {...} in a reply. Models like to wrap JSON in prose or fences."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def _tier(tier: list[str]) -> list[str]:
    """RCA_MODEL pins one model for the single-model ablation."""
    return [os.environ["RCA_MODEL"]] if os.environ.get("RCA_MODEL") else tier


def _table(a: rca.Analysis) -> str:
    seen, lines = set(), []
    for f in a.findings:
        if f.component in seen:
            continue
        seen.add(f.component)
        lines.append(f"- {f.component}: {f.kpi_name} went from {f.baseline:.3g} to "
                     f"{f.peak:.3g} (z={f.z:.0f}), first outside its band at "
                     f"{f.onset:%H:%M:%S}")
        if len(lines) >= CANDIDATES:
            break
    return "\n".join(lines)


def solve(instruction: str, dataset_dir: Path, ctx: dict) -> Solution:
    global _seen
    _seen += 1
    budget = _case_budget(Path(dataset_dir))

    a = rca.analyse(instruction, Path(dataset_dir))
    free_answers = rca.pick(a)
    notes: list[str] = []

    if not a.findings:
        notes.append("No anomalous series to reason about; answered from the parser.")
        return Solution(prediction=format_prediction(free_answers),
                        evidence=rca.write_evidence(a, free_answers)
                        + "\n" + "\n".join(f"- {n}" for n in notes) + "\n")
    if budget < MIN_CASE_S:
        notes.append(f"Run clock: {budget:.1f}s left for this case, under the "
                     f"{MIN_CASE_S:.0f}s floor. Answered without a model so the "
                     "remaining cases still get one.")
        return Solution(prediction=format_prediction(free_answers),
                        evidence=rca.write_evidence(a, free_answers)
                        + "\n" + "\n".join(f"- {n}" for n in notes) + "\n")

    llm = LLM(timeout=max(8.0, min(30.0, budget)))
    answers = free_answers

    try:
        # THE reasoning call -- the only one that thinks.
        reply = llm.ask(
            _tier(STRONG), think=THINK, max_tokens=900 if THINK else 220,
            prompt=(
                f"A microservice system had {a.n} failure(s) between "
                f"{a.lo:%Y-%m-%d %H:%M} and {a.hi:%H:%M}. These components deviated "
                f"from their own day-long baseline in that window:\n\n{_table(a)}\n\n"
                "When one component fails, everything downstream of it also looks "
                "anomalous, and a victim often deviates harder than its cause. "
                f"Choose the {a.n} component(s) most likely to be the ROOT CAUSE, "
                "each with one reason from this list exactly as written:\n"
                f"{json.dumps(rca.LEGAL_REASONS)}\n"
                "(components named node-* take the node-* reasons.)\n\n"
                'Reply with JSON only: {"answers": [{"component": ..., "reason": ...}],'
                ' "why": "one or two sentences"}'))
        picked = _json(reply).get("answers") or []

        # Check the model's pick against the data before trusting it.
        known = {f.component for f in a.findings}
        checked = []
        for i in range(a.n):
            p = picked[i] if i < len(picked) and isinstance(picked[i], dict) else {}
            comp, reason = p.get("component"), p.get("reason")
            if comp not in known:
                if comp:
                    notes.append(f"The model named `{comp}`, which is not a candidate "
                                 "in the data; kept the ranked pick for that slot.")
                checked.append(free_answers[i] if i < len(free_answers)
                               else free_answers[-1])
                continue
            best = rca._best_for(a, comp)
            item = {"datetime": (best.peak_at if rca.TIME_BY == "peak"
                                 else best.onset).strftime("%Y-%m-%d %H:%M:%S"),
                    "component": comp,
                    "reason": reason if reason in rca.LEGAL_REASONS
                    else (best.reason or free_answers[0]["reason"])}
            if reason and reason not in rca.LEGAL_REASONS:
                notes.append(f"`{reason}` is not a legal reason; used the KPI's own "
                             f"mapping (`{item['reason']}`) instead.")
            checked.append(item)
        if checked:
            answers = checked
        why = _json(reply).get("why", "")
        if why:
            notes.append(f"Model's reasoning: {why}")
    except (ModelUnavailable, Exception) as e:                    # noqa: BLE001
        notes.append(f"The reasoning call failed ({type(e).__name__}: {str(e)[:80]}); "
                     "this is the ranked answer, unchanged.")

    evidence = rca.write_evidence(a, answers)
    evidence += "\n## How this was produced\n\n"
    evidence += (f"Ranking and every number above are computed, not generated. "
                 f"A model chose among the ranked candidates.\n\n")
    for m, u in llm.usage.items():
        evidence += (f"- `{m}`: {u['calls']} call(s), {u['prompt_tokens']:,} in / "
                     f"{u['completion_tokens']:,} out\n")
    if llm.failures:
        evidence += f"- model failures this run: {llm.failures[-3:]}\n"
    if notes:
        evidence += "\n" + "\n".join(f"- {n}" for n in notes) + "\n"
    return Solution(prediction=format_prediction(answers), evidence=evidence,
                    usage=llm.usage)
