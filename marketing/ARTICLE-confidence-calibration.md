# Confidence Calibration: the Agent Was Most Wrong Exactly Where It Was Most Sure

*Long-form writeup of this project's central finding. Canonical HTML version, with the
cover and the mechanism diagram:*
**https://agentic-portfolio-lovat.vercel.app/articles/confidence-calibration-runs-backwards.html**

---

## 1-minute takeaway

**What this is.** A measurement. A root-cause agent was asked to rate its own certainty —
High, Medium or Low — on 70 production incidents whose true answers we held. The rating ran
*backwards*: cases it called High it got right 10% of the time; cases it called Low, 33%.
Permutation test, p = 0.006.

**Why it matters.** The standard human-in-the-loop design escalates *low-confidence* cases
to a person. On this agent that design would have routed humans to work already done
correctly, and auto-approved the errors. Any system that rates its own certainty inside a
single source of evidence has this failure available to it, and the failure is silent.

**What you can do.** Stop thresholding on self-reported confidence. Build a second view
that fails *differently* and escalate on **disagreement** between the two.

---

## The kitchen, and the three questions

A restaurant is failing. Orders are twenty minutes late and the manager hands you a box:
every thermometer reading from every stove, every line cook's notebook, every order ticket
stamped at each station. Thirty minutes of one bad evening, several gigabytes. Three
questions: **when** did it start, **which station** caused it, and **why**.

Swap the restaurant for a microservice system and you have OpenRCA, an ICLR 2025 benchmark
of real production telemetry with injected, labelled faults.

| Kitchen | System |
|---|---|
| A station (one stove) | A container — one replica of one service |
| The building's gas main | A node — the host several containers share |
| Thermometer readings, sampled | Metrics — CPU, memory, I/O, per series, per minute |
| An order ticket, stamped at each station | A trace — parent and child spans with durations |
| "Which station jammed, when, and why" | Root cause: component, timestamp, failure reason |

The hard part is not spotting trouble. When one station jams, every station downstream backs
up, and the ones nearest the customer complain loudest. Twelve stations are screaming.
**The loudest complaint is usually a victim, not the culprit.** Published state of the art
solves about one case in nine.

## The measurement

Our agent ranks candidates by deviation from their own day-long baseline (robust z-score,
median and MAD) and dates the fault at the first sample to leave the band. It scores
**0.199** against the provided baseline's 0.073 on all 70 dev cases.

It also writes a confidence word into every case file, computed rather than asserted: **High**
when one component dominates on magnitude and nothing anomalous started before it, **Low**
when a rival moved earlier or the margin is thin.

| Stated confidence | Cases | Mean score |
|---|---|---|
| **High** | 21 | **0.103** |
| Medium | 15 | 0.033 |
| **Low** | 34 | **0.331** |

Low minus High is **+0.228**, bootstrap 95% CI [+0.064, +0.385], permutation p = **0.006**.
Not task-type confounding: the inversion holds *inside* task types — on the time-only task,
High scores 0.000 against Low's 0.500.

Two disclosures. This is **70 cases**, and per-case scores have a standard deviation near 0.3
— which is exactly why two *other* findings from the same afternoon did not survive the same
test and were struck from our report. The inversion survived it. And the confidence rule is
ours; a different rule would invert differently or not at all. What generalises is the
mechanism, not the coefficient.

## Why it runs backwards

**High** is awarded for a clean picture: one component clearly worst, nothing moving before
it. But a clean picture is also precisely what you see when **the fault is invisible to the
instrument you are holding**.

About a quarter of the true causes in this data are network faults. They barely register in
metrics; they live in the gap between a parent span and its child — the time on the wire
nobody's CPU spent. Our metrics-only agent scores **0.111** on those against **0.217** on
everything else.

So when the thermometers look tidy, sometimes nothing is wrong with the stoves — and
sometimes the fire is somewhere a thermometer cannot see. **From inside the thermometer,
those two look identical.**

> **A confidence score measured inside one instrument cannot detect the failure "we are using
> the wrong instrument."** A blind spot and a clean result are the same reading.

A physician reading only bloodwork can be certain and wrong, and the bloodwork will not warn
them — only an X-ray will. A survey with a tight margin of error is still wrong if it sampled
the wrong frame. **Precision is not accuracy, and a system measuring its own precision will
mistake one for the other every time.**

## What to build instead

```python
view_a = rank_from_metrics(window)      # thermometers
view_b = rank_from_traces(window)       # order tickets
if view_a.top == view_b.top:            # agreement across failure modes
    decide()
else:
    escalate(view_a, view_b)            # this is the edge case
```

We built the second view — the 95th percentile of each caller's parent-to-child span gap —
and the honest result is mixed:

| Configuration | All 70 | The 12 network cases | Other 58 |
|---|---|---|---|
| **Traces off (shipped)** | **0.199** | 0.111 | **0.217** |
| Always prefer the trace view | 0.163 | **0.194** | 0.157 |
| Prefer it above a magnitude gate | 0.194 | 0.111 | 0.211 |

**The second view works** — it lifts the network cases 75%. **And our rule for using it is too
blunt to collect the gain**, because it also fires on the 58 cases the metrics already had
right. So we shipped with it off. That is the finding, not a failure: *we located the signal
and do not yet know how to promote it without collateral damage.*

## Where the humans go

| Work | Who leads | Why |
|---|---|---|
| Parsing, arithmetic, output format | Machine alone | A wrong answer is caught by a test in one second |
| Picking the culprit from evidence | Machine leads, human audits | It writes down every number it used |
| **Cases where the two views disagree** | **Human leads, machine assists** | The only honest signal that this case is unusual |
| Defining the answer for a novel failure class | Human alone | No ground truth to check against |

**Never escalate on the model's self-assessment alone.** We have a measured case where that
is worse than random.

## Run this on your own system this week

1. Find 50–100 cases where you know the answer.
2. Bucket by what your system said about itself — confidence, priority, risk tier.
3. Compute accuracy per bucket and run a permutation test. Flat is common. Inverted is the one that costs you.
4. If it is flat or inverted, **do not tune the threshold.** Add a second view that fails differently and measure agreement.

## What we are not claiming

**We did not beat the AI; we beat one way of using it.** The shipped agent calls no language
model. We tested one — strongest in its family, reasoning enabled, handed the ranked
candidate table — and it changed **zero of twenty answers** while spending eight minutes of a
twenty-minute budget. But we gave it a finished summary and asked it to choose. **We never
gave it tools to query the telemetry itself.** That is a different system and this result says
nothing about it.

**Our held-out score will be lower.** Constants were chosen while looking at all 70 cases.
That is leakage, named rather than hidden.

---

*Measured 2026-09-17 on Market/cloudbed-1 of OpenRCA, 70 labelled cases. Bootstrap and
permutation at 10,000 resamples, seed 0. Every table reproduces from this repo's `make`
targets: `make ablate`, `make significance`, `make calib`, `make compare`.*
