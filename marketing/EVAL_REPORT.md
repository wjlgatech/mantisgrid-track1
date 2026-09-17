# Self-evaluation against the judging criteria, term by term

**Project:** First-mover RCA — MantisGrid Hackathon 2026, Track 1
**Repo:** https://github.com/wjlgatech/mantisgrid-track1
**Date:** 2026-09-17 · **Graded by:** the team, before submission, against criteria we did not write

Two rubrics govern this event and they are not the same document. We grade against
both, because a submission can be strong on one and absent on the other.

- **The participant agreement, §8** — the panel rubric, and *the document that governs*:
  Technical Execution 40% · Innovation 30% · Potential Impact 20% · Presentation 10%.
- **The Track 1 brief** (`docs/scoring.md`) — the track focus applied inside those:
  accuracy · evidence and explainability · evaluation quality · cost efficiency.

Grades are ours. Where we think a judge would mark us lower than we would, we say so.

---

## Summary

| Criterion | Weight | Grade | One line |
|---|---|---|---|
| Technical Execution | 40% | **A−** | 2.7× the baseline, every claim reproducible by a `make` target; leakage named, not hidden |
| Innovation / Wow | 30% | **B+** | The gate and the calibration inversion are genuinely novel; a judge skimming may see "no LLM" first |
| Potential Impact | 20% | **A−** | The inverted-confidence finding transfers to any system that rates its own certainty |
| Presentation / Demo | 10% | **INCOMPLETE** | Run sheet written, demo **not yet recorded**. This is a real zero until it is. |
| — | | | |
| Accuracy (track focus) | — | **C+** | 0.199 vs 0.073 baseline. Real, but far from solved, and held-out will be lower |
| Evidence & explainability | — | **A** | Every number compiled from measurement; a gate fails the build if the prose contradicts the config |
| Evaluation quality | — | **A** | Ablation, paired bootstrap, calibration, threshold sweep, provider probe — and one self-retraction |
| Cost efficiency | — | **A** | $0.00 and 1.3 s/case in the judged configuration |

**Weighted panel estimate: ~B+/A− if the demo is recorded. ~C+ if it is not.**
Presentation is 10% and currently unearned; nothing else moves that.

---

## Technical Execution — 40% — **A−**

**What we claim.** 0.073 → **0.199** on all 70 dev cases, 6 fully solved against 2.
Docker build verified with the judges' exact command, 1.3 s/case native and 3.6 s/case
in-container, so 20 cases project to 1.2 min against a 20-minute wall.

**Evidence.** `make dev && make score` reproduces the number. `make check` fails the
build on the seven ways this track scores zero silently.

**Why not an A.** Three things a strict judge should hold against us:

1. **Leakage we did not remove.** `Z_MIN`, `PCTL` and the trace threshold were chosen
   while looking at all 70 cases. Proper stratified k-fold was the right answer and we
   ran out of clock. We name it in `REPORT.md` rather than reporting a clean number.
2. **`task_3` scores 0.000** in all five configurations. Component-only identification
   never worked. We know the likely cause (network faults live in traces) and did not
   close it.
3. **The headline gain was a bug fix, not a design.** The timezone correction is worth
   +0.092 of the +0.126 total. Honest, but it is not evidence of architectural skill.

**What would move it to an A.** The trace view promoted by a rule that does not cost
the other 58 cases, plus k-fold hyperparameter selection.

---

## Innovation / Wow Factor — 30% — **B+**

**The two things here that we have not seen elsewhere:**

1. **A gate that fails the build when the agent's prose contradicts its own
   configuration.** Written after a real bug: we switched the ranking rule and the
   evidence files kept narrating the old one — calling a component "the earliest mover"
   while an earlier one sat in its own table, and describing a negative time delta as
   "downstream". Structure checks pass a file that lies. `eval/gate.py` does not.
2. **A measured, significant confidence inversion** (High 0.103 vs Low 0.331,
   permutation p = 0.006) with a mechanism: a confidence computed inside one sensor
   cannot detect "wrong sensor", because a blind spot is maximally tidy. This
   generalises past the benchmark.

Also novel, smaller: a portability check that fails if any component name from this
bundle appears in `agents/`, because we are judged on a deployment where those names
do not exist.

**Why not an A.** **Our judged run makes zero model calls**, and this is the routing
track. We can defend it — we measured the model changing 0 of 20 answers while
spending 41% of the wall clock — but a judge forms an impression before reading the
defence. That is a presentation risk sitting inside an innovation score.

---

## Potential Impact — 20% — **A−**

The transferable asset is not the RCA agent; it is the finding that **a system's
self-reported confidence can be anti-correlated with its correctness, silently, and
the standard human-in-the-loop design will then escalate backwards.** Any team
shipping a model that gates work can run our four-step test on their own data in an
afternoon.

**Why not an A.** One deployment, 70 cases, one confidence rule. The mechanism
generalises; the coefficient does not, and we say so rather than implying otherwise.

---

## Presentation / Demo — 10% — **INCOMPLETE**

`DEMO.md` is a beat-by-beat four-minute run sheet with the exact commands, what to
point at on screen, and pre-answers for the three questions a judge will ask.

**It has not been recorded.** Until it is, this criterion scores zero, and no amount
of work elsewhere compensates — it is the only criterion that cannot be earned by the
repository.

---

## Track focus — accuracy — **C+**

0.199 against a 0.073 baseline is a 2.7× lift and it is still **one case in five at
best on a benchmark whose published state of the art is about one in nine**. Our
held-out score will be lower than 0.199 for the leakage reason above, and we cannot
put an interval on the gap: the judged run is a different deployment with different
components, and no resampling of these 70 cases estimates that.

Honest framing: this is a respectable engineering result on an unsolved problem, not
a solution to it.

---

## Track focus — evidence and explainability — **A**

Worth more than accuracy in this track, and it is our strongest surface.

- Every evidence file carries the four required sections.
- **Every number in them is compiled from the measurement that produced it** — carried
  in a `Finding` dataclass and formatted directly. No model is asked to recall a value,
  because evidence that is not in the data scores zero and is worse than none.
- The "Ruled out" section argues **against** our own answer where the data does: when a
  rival moved earlier, it says so, and says the rival is excluded on magnitude alone.
- Confidence is computed from measured separation, not asserted — **and we then
  measured that the computation is inverted and reported it.**

---

## Track focus — evaluation quality — **A**

The dimension we spent the most on:

| Artifact | What it establishes |
|---|---|
| `eval/ablate.py` | 2×2 ablation; the bundled "improvement" scored worse than either half |
| `eval/significance.py` | Paired bootstrap — **two of our own findings did not survive and were retracted** |
| `eval/calibration.py` | The confidence inversion, with a permutation test |
| `eval/sweep_traces.py` | Threshold sweep with a "does it break the other 58?" column |
| `eval/probe_models.py` | Every model in the family probed twice before we built on any |
| `eval/gate.py` | Seven silent-failure modes, failing the build |

The retraction is the part we would point a judge at. An earlier draft of `REPORT.md`
claimed the onset decomposition as two findings; the paired bootstrap said both CIs
span zero, and we rewrote it.

---

## Track focus — cost efficiency (dollars and wall-clock) — **A**

| | Judged configuration |
|---|---|
| Dollars per case | **$0.0000** |
| Wall-clock per case | **1.3 s** native, 3.6 s in-container |
| 20-case run projection | **1.2 min** of a 20-minute budget |
| Token usage | **zero** |

The brief says an agent that gets most of the accuracy for a fraction of the cost beats
one buying a point at any price. Ours gets **all** of its accuracy for nothing — because
we measured the paid path reproducing an answer we already had.

The supporting measurement (`eval/routed_compare.md`): GLM-5.2 with reasoning on,
handed the ranked candidate table, changed **0 of 20 answers** while spending $0.098 and
8.2 minutes. With reasoning off it changed all 20 and scored lower, though at n=20 that
score gap is not significant.

**The caveat we do not bury:** this tests a model *choosing from a static table*. We
never gave it tools to query the telemetry itself. That is a different system and our
result says nothing about it.

---

## The three things a judge could fairly use against us

1. **No model in the judged run**, in the routing track. Defensible, measured, still a risk.
2. **Hyperparameters chosen on the full dev set.** Named, not fixed.
3. **The demo is unrecorded** as of this writing. 10% sitting on the floor.

## The one thing we would defend hardest

Three of our four findings are negative, and one is a retraction of our own earlier
claim. On a benchmark where the state of the art solves one case in nine, a team
reporting only wins is a team that did not look.
