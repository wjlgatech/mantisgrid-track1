# Does the model earn its place?

The brief asks for the routed agent measured against the same agent on a single
model. We ran three configurations over the **same first 20 dev cases** — the size
of the judged run — and added the question the table above it does not ask: *how
many answers did the model actually change?*

| configuration | mean score | fully solved | s/case | $/case | answers changed vs free |
|---|---|---|---|---|---|
| `agents.rca` — no model at all | **0.225** | 2/20 | **1.2** | **$0.0000** | — |
| `agents.routed` — GLM-5.2, thinking **off** | 0.163 | 1/20 | 5.4 | $0.0013 | **20 / 20** |
| `agents.routed` — GLM-5.2, thinking **on** | **0.225** | 2/20 | 24.7 | $0.0049 | **0 / 20** |

Projected over the judged run of 20 cases: 0.4 min free, 1.8 min without thinking,
**8.2 min with** — against a 20-minute wall shared by every case.

## What the last column means

**With thinking on, the strongest model in the family changed nothing.** Handed a
ranked table of candidates with their baselines, peaks, z-scores and onset times,
and asked to pick the root cause, GLM-5.2 chose the top row every single time. It
scored identically to the free ranking because it *was* the free ranking. The
$0.098 and the 8.2 minutes bought agreement.

**With thinking off, it changed every answer and got worse** — 0.225 down to 0.163.
Not noise: it disagreed with the ranking on all twenty cases and was wrong more
often for it.

So the model is either a rubber stamp or a liability, and which one you get is
decided by a flag that costs 20–50× the output tokens.

## Why we think this happens

Our candidate table is already the answer. The free analysis does the work that
matters — parse the window in the right timezone, compute a robust z per series
against the rest of the day, rank, and date the onset — and then presents a sorted
list. Asking a model to choose from a sorted list is not a reasoning task; it is a
formality, and a thinking model formalises it while a fast one fumbles it.

**A model would have to see something the table does not contain to beat it.** The
obvious candidate is in the traces: about a third of root causes here are network
faults, which barely register in metrics and show up as parent-to-child span
latency. Those never reach the prompt, so no amount of reasoning over this table
can recover them. That is a limit of our retrieval, not of the model.

## What we shipped, and why

`run.py` defaults to **`agents.rca`**, the configuration with no model in it.

The brief says an agent that gets most of the accuracy for a fraction of the cost
is worth more than one that buys an extra point at any price. Here the free
configuration does not get *most* of the accuracy — it gets **all** of it, for
nothing, in 1.2 seconds instead of 24.7. Shipping the paid path would mean
spending 41% of the run's wall clock to reproduce an answer we already had.

`agents/routed.py` remains in the repository, working and switchable
(`--agent agents.routed`, `RCA_THINK=0|1`, `RCA_MODEL=<pin one model>`), because
the measurement is the deliverable and it has to be reproducible.

Reproduce: `make compare` (needs `FEATHERLESS_API_KEY`; ~10 minutes, about $0.13).
