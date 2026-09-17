# Rule-based vs LLM-based vs hybrid — what we measured

**The concern:** 70 cases is a tiny sample. A deterministic solution overfits patterns
that won't hold on the held-out deployment. An LLM with reasoning would generalise.

**The concern is right about one third of our system and wrong about the other two
thirds.** Here is the split, measured, not argued.

## We built all three. Only one ships.

| | what it is | measured |
|---|---|---|
| **Rule-based** | robust z-score per series, ranked | **0.199** — ships |
| **LLM-based** | GLM-5.2 picks from the candidate table | 0 of 20 answers changed |
| **Hybrid** | rules rank, GLM overrides where it disagrees | 0 of 20 answers changed |

`agents/routed.py` is the hybrid, still in the repo, switchable with `--agent
agents.routed`. We tested it **twice under opposite conditions**: once when the
candidate table contained the true answer 54% of the time, once after we fixed
retrieval to 96%. **It changed zero answers both times.** It anchors on our sort order.

So the LLM did not act as a safeguard when we gave it the chance to. That is
an empirical result about *this* prompt shape, not a claim that no LLM could.

## Where we are NOT overfit (2/3 of the answer)

The z-score is **not a learned rule**. For each case it compares that case's 30-minute
window against **that same case's own day**. Nothing is fitted across cases; a new
deployment brings its own baseline with it.

| what we actually carry from the 70 cases | size |
|---|---|
| Tunable constants (`Z_MIN=4.0`, rank-by, time-by) | **3 numbers** |
| Component names hardcoded | **0** — `make check` fails the build if any appear |

**Component (41 items) and time (40 items) come from that statistic alone.** They have
no learned content to transfer badly.

## Where we ARE overfit — and it's exactly your point

The **reason** is decided by a **hand-written 19-entry keyword map** (`cpu` → container
CPU load, `read_bytes` → container read I/O load, …).

**That map decides 40 of 121 gradeable items — a third of our score.** If the held-out
deployment names its KPIs differently, the map degrades and we have no fallback. It is
the one genuinely brittle surface in the system, and it is hand-written from what we saw
in these 70 cases.

## The right hybrid, which we did not have time to test

Not "let the LLM re-rank" — measured twice, changes nothing. Instead:

> **Let the LLM decide the reason only when the keyword map has no confident match.**

The reason is effectively a 15-way multiple choice with the options published in the
brief. When a winning KPI matches no keyword, we currently fall back to a blind default
(`container CPU load`). That is exactly where a reasoning model should be asked
"given this KPI name, this baseline and this peak, which of these 15 labels is it?" —
a task with no ordering to anchor on, which is why we expect it to behave differently
from the re-ranking test.

**Untested. We are not claiming it works.** It is the first thing we would run next,
and it is a ten-line change to `rca.reason_for`.

## Honest summary for the judges

- Two thirds of our answer rests on a per-case statistic with no training and nothing
  deployment-specific to carry across.
- One third rests on a hand-written map that could plausibly break on new KPI names.
- We tested the LLM as a safeguard at the ranking layer twice; it added nothing.
- We identified, but did not get to test, the layer where it probably *would* help.

That is the state. We would rather name the brittle third than let it be discovered.
