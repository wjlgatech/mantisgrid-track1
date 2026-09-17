# REPORT — Track 1, root cause analysis

**Score: 0.199 over all 70 dev cases, up from the starter's 0.073.** 6 cases fully
solved against 2. Every number here is reproducible from this repository with `make`.

We set out to build a routed LLM agent. We finished with a free one, because we
measured the model and it did not earn its place. This report is mostly about how
we found that out, since the finding is more useful than the score.

---

## 1. What we actually changed, measured one at a time

Three changes separate this agent from the starter baseline. Bundled, they look
like a story. Separated (`make ablate`), two of them cancel:

| config | ranks by | dates by | mean | solved | blank |
|---|---|---|---|---|---|
| starter, as shipped | peak z | peak | 0.073 | 2/70 | **24** |
| + timezone fix | peak z | peak | 0.164 | 4/70 | 0 |
| **+ onset timestamps — shipped** | **peak z** | **onset** | **0.199** | **6/70** | 0 |
| first-mover ranking | onset | peak | 0.131 | 2/70 | 0 |
| both changes together | onset | onset | 0.093 | 1/70 | 0 |

### The timezone was worth more than every idea we had

The telemetry is UTC+8. The starter parses each question's window as UTC. That is
eight hours off — and because a day file covers 00:00–23:59 **UTC+8**, any window
at 16:00 or later lands past the end of the file and matches *zero samples*. The
baseline answers blank on **24 of 70 cases**, and the brief is explicit that a
blank scores exactly what a wrong guess scores. One line, `0.073 → 0.164`.

We found it by checking the epoch range of `metric_node.csv` against both
timezones before trusting any analysis — the day boundaries are clean in UTC+8 and
ragged in UTC, which settles it in one command.

### Magnitude answers *which*; onset answers *when* — probably

Our hypothesis was cascade-shaped and, we thought, obviously right: when one
component fails everything downstream looks anomalous, the loudest is usually a
victim, so **rank by who deviated first**. Shipped as a bundle it scored 0.093 —
worse than doing nothing.

Decomposed, the two halves point opposite ways: dating by onset gains +0.035,
ranking by onset loses −0.033. **Neither of those individual effects survives the
sample size** (`make significance`):

| effect | delta | 95% CI | verdict |
|---|---|---|---|
| onset timestamps | +0.035 | [−0.023, +0.095] | not significant |
| onset ranking | −0.033 | [−0.085, +0.016] | not significant |
| **both bundled** | **−0.071** | **[−0.132, −0.014]** | **significant** |

Per-case scores have a standard deviation near 0.3 against effects near 0.03, so
70 cases cannot resolve a third of a case per case. What we can say honestly:

- **The bundle is genuinely worse.** That one clears the bar.
- **The decomposition is directional, not proven.** `task_1` moves 0.167 → 0.250
  and `task_5` 0.225 → 0.325, which is consistent with onset being a better
  timestamp, and the mechanism is sound — the peak of a symptom is necessarily
  later than the fault. But we would need several times this many cases to claim it.
- **We ship peak-rank/onset-time because it is the point-estimate maximum, and we
  state plainly that it is not distinguishable from peak/peak (0.199 vs 0.164).**

The lesson is procedural: bundling two changes cost us the ability to attribute
either, and unbundling them was not enough — the sample size still refuses to
adjudicate. An earlier draft of this report presented both halves as findings.
That was an overstatement, corrected here.

---

## 2. Does the model earn its place? No.

Three configurations over the same first 20 dev cases — the size of the judged run
(`make compare`):

| configuration | mean | solved | s/case | $/case | answers changed vs free |
|---|---|---|---|---|---|
| `agents.rca` — no model | **0.225** | 2/20 | **1.2** | **$0.0000** | — |
| `agents.routed` — GLM-5.2, thinking off | 0.163 | 1/20 | 5.4 | $0.0013 | **20 / 20** |
| `agents.routed` — GLM-5.2, thinking on | **0.225** | 2/20 | 24.7 | $0.0049 | **0 / 20** |

**With thinking on, the strongest model in the family changed none of the twenty
answers.** Given a ranked candidate table with baselines, peaks, z-scores and onset
times, it picked the top row every time. It scored identically to the free ranking
because it *was* the free ranking; $0.098 and 8.2 minutes bought agreement.

**With thinking off it changed all twenty answers**, and scored 0.163 against
0.225 — though at n=20 that gap is *not* statistically significant
([−0.212, +0.075]). The reliable part of this row is the behaviour, not the score:
it disagreed with the ranking on every single case.

Our reading: the candidate table is already the answer. The free analysis does the
work that matters and hands over a sorted list, and choosing from a sorted list is
not a reasoning task. **A model would need to see something the table does not
contain to beat it** — and the obvious missing thing is in the traces, which we
never open (§4).

So `run.py` defaults to `agents.rca`. The brief says an agent that gets most of the
accuracy for a fraction of the cost beats one that buys a point at any price; here
the free path gets *all* of the accuracy, for nothing, in 1.2s instead of 24.7s.
Shipping the paid path would spend 41% of the run's wall clock reproducing an
answer we already had.

`agents/routed.py` stays in the repository, working and switchable, because the
measurement has to be reproducible.

### Two things about this model family that are not in the docs

Found by probing all seven models twice each before building on any of them
(`make probe` → `eval/models.md`):

**1. The cheapest model never puts its answer in `.content`.** These are hybrid
reasoning models, and with `chat_template_kwargs={"enable_thinking": False}` the
text arrives in `message.reasoning` while `message.content` is the empty string.
For `GLM-4.7-Flash` that is true in *both* modes. The starter's `llm.py` reads
`.content` only — so its CHEAP tier returns empty strings, billed, on a successful
HTTP 200. `agents/client.py` reads content, then reasoning.

**2. Price does not predict latency.** GLM-5.2, the dearest model, answered our
probe in 1.0s. GLM-4.7-Flash, the cheapest, took 24.6s and hit its token cap
without producing an answer; GLM-4.6 took 49.2s. The brief describes the family as
running "from cheap and fast to large and strong". On our measurements the cheap
end is the *slow* end, and since the 20-minute wall is the limit most likely to
bind, routing a call downward to save money can cost you the run.

Turning thinking off cuts output tokens 20–50× (GLM-4.6: 1759 → 25) and latency
with them. Thinking is billed as output, which is both the priciest and the slowest
token an agent buys.

---

## 3. Where it fails, and what it does not know

### The confidence signal is inverted

The agent writes High/Medium/Low into every evidence file, computed from the
measured gap between the top candidate and its rivals. Scored against the answers
(`make calib`):

| confidence | cases | mean score |
|---|---|---|
| High | 21 | 0.103 |
| Medium | 15 | 0.033 |
| Low | 34 | **0.331** |

**The cases it is most sure of are the ones it gets most wrong, by 3.2×.** This one
*does* survive: Low − High = +0.228, 95% CI [+0.064, +0.385], permutation
p = **0.0056**. It is not task-type confounding either — the inversion holds inside
`task_1` (High 0.000 vs Low 0.500) and `task_5` (0.000 vs 0.464).

`High` is awarded when one component both dominates on magnitude and has nothing
anomalous before it. Our hypothesis, labelled as one: a component that is both
loudest *and* earliest **in metrics** is often the loud victim of something metrics
barely show — which points straight at the network faults in §4.

We did not flip the label. A signal inverted to fit 70 cases of one deployment,
graded on a different deployment, is an overfit wearing a finding's clothes.

### `task_3` scores 0.000 in all five configurations

Component-only. It did not move for any ranking rule we tried. Whatever identifies
the component is not in the metrics we read.

---

## 4. What we did not get to

**Traces.** About a third of root-cause reasons are network faults, and the brief
says they barely show in metrics — you need parent-to-child span latency from
`trace_span.csv`. We never open it. This is the single biggest lever left, the most
likely explanation for `task_3`, the most likely explanation for the inverted
confidence, and the most likely thing that would let a model beat the table.

**Logs.** Also never opened.

**Honest estimate of our held-out score:** lower than 0.199, and we cannot put an
interval on it. Resampling these 70 cases bounds sampling noise on *this*
deployment; the judged run is a different deployment with different components, and
nothing we can compute here estimates that gap. Our tunable constants (`Z_MIN`,
`PCTL`, the trace threshold) were also chosen while looking at all 70, which is
leakage we did not have time to remove with proper stratified k-fold.

**A limitation of our headline result.** "The model adds nothing" is established
only for the experiment we ran: a model choosing from a *static, pre-digested
candidate table*. We never gave it tools to query the telemetry iteratively —
narrow the window, pull a different KPI, walk a trace. An agent that asks its own
next question is a different system and might well beat the table. We did not test
it, and we are not claiming otherwise.

---

## 5. The part we would keep regardless of score

`eval/gate.py`, run by `make check`. An RCA submission is graded on things that
fail *silently*, so the gate fails the build unless:

- every prediction matches the evaluator's **actual regex**, keys in order
- the answer count equals the failure count the question states
- no answer is blank
- every evidence file carries all four required sections
- 20 cases project to under 60% of the 20-minute wall
- **no component name from this bundle appears in `agents/`** — we are graded on a
  deployment where those names do not exist
- **no evidence file narrates a rule the agent is not running.** This one was
  written after a real bug: switching the ranking default left the prose calling a
  component "the earliest mover" while an earlier one sat in its own table, and
  describing a negative time delta as "downstream". Structure checks pass a file
  that lies. Evidence that contradicts the data scores zero and is worse than none.

Every number in an evidence file is carried from the measurement that produced it
in a `Finding` dataclass and formatted directly. No model is asked to recall one.

---

## 6. Reproducing everything here

```bash
pip install -r requirements.txt
make dev && make score      # 0.199 over 70 cases
make check                  # the gate
make ablate                 # §1 table
make calib                  # §3 table
make probe                  # §2 model table   (needs FEATHERLESS_API_KEY)
make compare                # §2 comparison    (needs the key; ~10 min, ~$0.13)
make docker                 # build and run exactly as judging does
```
