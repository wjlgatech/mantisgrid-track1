# Four minutes, live

A run sheet. Every command here runs from a clean clone with the bundle in `data/`;
nothing is staged or pre-baked. Times are what they actually take.

---

## 0:00 — The problem, in one sentence

> "Here is thirty minutes of telemetry from a microservice system that broke.
> Twelve components are screaming. One of them started it. The published state of
> the art solves about one case in nine."

## 0:20 — Run a case live (~3 seconds)

```bash
make dev N=1 && cat out/dev/evidence/0.md
```

Show the evidence file on screen. Point at three things:

- **`## Answer`** — component, reason, timestamp.
- **`## Evidence`** — a table of real values: baseline median, in-window peak,
  z-score, onset time, each traceable to a named CSV. *"No model wrote these
  numbers. They are carried from the measurement that produced them, because
  evidence that isn't in the data scores zero and is worse than none."*
- **`## Ruled out`** — *"and here it argues against itself: it says `node-6`
  started moving 540 seconds **earlier**, so it is excluded on magnitude alone."*

## 1:00 — The thing that actually paid

```bash
cat eval/results.md
```

> "Our clever idea was: rank by who deviated first, because in a cascade the
> loudest component is usually a victim. We shipped it bundled and scored 0.093 —
> worse than doing nothing. Then we ablated it."

**The 2×2 on screen.** Land the punchline — and land it *honestly*:

> "Bundled, our clever idea scored 0.093, worse than doing nothing. Decomposed,
> the two halves point opposite ways. Then we bootstrapped it — and **neither half
> is significant at seventy cases**. Per-case standard deviation is 0.3; we were
> chasing 0.03.
>
> What *is* significant is the boring one: a **timezone**. The data is UTC+8, the
> starter parses UTC, and 24 of 70 cases answered blank because the window fell
> off the end of the day file. +0.092, confidence interval clear of zero."

```bash
cat eval/significance.md
```

> "We shipped this table because our first draft of the report claimed both halves
> as findings, and the statistics said no."

## 2:00 — Does the model earn its place?

```bash
cat eval/routed_compare.md
```

> "This is the routing track, so we built the routing. GLM-5.2, thinking on,
> handed a ranked candidate table. It changed **zero of twenty answers** — not
> 'no significant difference', byte-identical output. Eight minutes of a
> twenty-minute wall to agree with us. Thinking off, it changed all twenty; that
> score gap is inside the noise, so we claim the behaviour, not the score.
>
> So we ship the free agent. The brief says an agent that gets most of the accuracy
> for a fraction of the cost beats one buying a point at any price. Ours gets *all*
> of it, for nothing, in 1.2 seconds."

If there is time, the two undocumented facts:

> "Also: the cheapest model in the family never puts its answer in `.content` — it
> lands in `.reasoning`, so the starter's own client reads an empty string and
> pays for it. And price does not predict latency: the dearest model answered in
> 1.0s, the cheapest took 24.6s and hit its token cap."

## 3:00 — Where it's wrong, and how we know

```bash
cat eval/calibration.md
```

> "It writes a confidence on every case. We checked it. **It's inverted** — the
> cases it is most sure of are the ones it gets most wrong, by 3.2×. Permutation
> p equals 0.006, and it survives task-type controls. We did not flip the label: inverting a signal fitted
> to seventy cases of one deployment, when we're graded on a different deployment,
> is an overfit wearing a finding's clothes."

## 3:30 — The part we'd keep

```bash
make check
```

> "Everything in this track fails silently. Reorder three JSON keys and the
> evaluator matches nothing and scores zero without telling you. So the gate fails
> the build on all of it — key order, failure count, blank answers, the wall clock,
> and **any component name from this bundle hardcoded in the agent**, because we're
> graded on a deployment where those names don't exist.
>
> One check was written after a real bug: our evidence prose kept narrating the old
> ranking rule after we changed it, calling a component 'the earliest mover' when
> an earlier one was in its own table. Structure checks pass a file that lies."

## 3:50 — Close

> "0.073 to 0.199. Three of our four findings are negative, one of our own
> findings didn't survive our own statistics, and those are the ones we'd want
> on call at 3am."

---

## If a judge asks

**"Why is there no LLM in the judged run?"**
Because we measured it. `eval/routed_compare.md`: thinking on, it changed 0 of 20
answers — identical output, not a statistical tie. Thinking off it changed all 20,
though at n=20 that score gap is not significant. The harness is in
`agents/routed.py`, switchable, and it reproduces with `make compare`.

**"Isn't a static candidate table the wrong experiment for an LLM?"**
Yes, and we say so in the report. We tested a model *choosing from a pre-digested
table*. We never gave it tools to query the telemetry iteratively — narrow the
window, pull another KPI, walk a trace. An agent that asks its own next question is
a different system, and our result says nothing about it.

**"What would you do with another day?"**
Traces. A quarter of scored reasons are network faults and we score 0.111 on them
against 0.217 on everything else. The signal is parent-to-child span latency, which
we do open in `agents/traces.py` — the p95 of the caller's wire time — but we have
not finished measuring where the promotion threshold belongs (`make sweep`).

**"How would this do on our held-out deployment?"**
Worse than 0.199. We tuned against all 70 dev cases. The gate's no-hardcoded-names
check is there precisely because that is the failure mode we could not otherwise see.
