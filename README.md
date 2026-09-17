# Which by magnitude, when by onset — MantisGrid Hackathon 2026, Track 1

**What this is:** an agent that reads a few gigabytes of microservice telemetry and
answers three questions about a failure it has never seen — *when did it start, which
component caused it, and why*.

**The two ideas it is built on**, both of which we tested separately rather than
asserting:

1. **Identify the culprit by how hard it moved.** A dozen components go red at once when
   one breaks; the biggest deviation is the best single clue to which one is the cause.
2. **But date the fault by when it *started* moving, not when it hurt most.** The peak of
   a symptom is systematically later than the fault that caused it.

Think of a kitchen where one burner starts smoking. Within a minute the plating station,
the pass and the delivery counter are all backed up. To find *which* station is broken you
look for the biggest mess — but to say *when* it broke you need the moment the first wisp
of smoke appeared, not the moment the fire alarm went off. Those are different questions
and they want different evidence.

In technical terms: rank candidates by **peak robust z-score** (median/MAD against the rest
of the day), and answer the timestamp with that series' **onset** — the first in-window
sample to leave its band.

---

## The honest headline

We expected the opposite. Our hypothesis was that *ranking* by earliest onset — first
mover is the culprit — would be the win. **It is actively harmful**, and we only know
that because we measured the two changes separately instead of shipping them together.

| config | ranks by | dates by | mean | fully solved | blank |
|---|---|---|---|---|---|
| starter baseline, as shipped | peak z | peak | 0.073 | 2/70 | **24** |
| + timezone fix only | peak z | peak | 0.164 | 4/70 | 0 |
| **+ onset timestamps (shipped)** | **peak z** | **onset** | **0.199** | **6/70** | **0** |
| first-mover ranking | onset | peak | 0.131 | 2/70 | 0 |
| both "improvements" together | onset | onset | 0.093 | 1/70 | 0 |

**2.7× the baseline.** Reproduce with `make ablate`; raw table in
[`eval/results.md`](eval/results.md).

Three things that table says:

**1. A timezone was worth more than every clever idea combined (0.073 → 0.164).** The
telemetry is UTC+8; the starter parses each question's window as UTC. That is 8 hours off,
and any window at 16:00 or later lands past the end of the day file and returns *zero
samples* — which is why the baseline emits **24 blank answers out of 70**. One line.

**2. Onset timestamps pay (+0.035).** Against a 60-second tolerance, dating the fault by
when a series first left its band beats dating it by the peak: `task_1` 0.167 → 0.250,
`task_5` 0.225 → 0.325.

**3. Onset *ranking* costs (−0.033), and bundled with #2 it looked like total failure
(0.093).** For twenty minutes we believed the whole first-mover idea was dead. It was half
dead: the earliest series to jitter is usually noise, while a large deviation is a real
identifier. Magnitude answers *which*; onset answers *when*. Ship them to different
questions.

That is the result we are proudest of, and it is a negative one.

---

## Run it

```bash
pip install -r requirements.txt
# the bundle is not in this repo -- see the track's GET_DATA.md
make dev        # run over the 70 dev cases -> out/dev/
make score      # OpenRCA's own evaluator, unchanged
make check      # THE GATE: is this submission judgeable?
make ablate     # reproduce the table above
```

Judging builds the Dockerfile at the repository root — the only one here, so there is
nothing to pick wrong:

```bash
docker build -t rca .
docker run --rm -e FEATHERLESS_API_KEY=<key> \
  -v <bundle>:/data:ro -v <empty dir>:/out rca \
  python run.py --dataset /data --queries /data/query.csv --out /out
```

## `make check` — the part we would keep

An RCA agent is graded on things that fail *silently*. The evaluator reads predictions
with a regex, so reordering three JSON keys scores zero and says nothing. A prediction
with two answers where the question said one failure scores zero however right both
are. A run that averages three minutes a case finishes seven of twenty.

So the gate ([`eval/gate.py`](eval/gate.py)) refuses to pass unless:

- every prediction matches **the evaluator's actual regex**, keys in order
- the number of answers equals the number of failures the question states
- **no answer is blank** — a blank scores exactly what a wrong guess scores, so
  guessing strictly dominates
- every evidence file carries all four sections the brief asks for
- 20 cases project to **under 60% of the 20-minute wall**
- **no component name from this bundle appears anywhere in `agents/`** — we are judged
  on a different deployment, where those names do not exist

That last check is the one we would port to any agent scored on held-out infrastructure.

## Evidence is compiled, not narrated

Evidence is the largest single share of this track's grade, and the brief is explicit
that evidence which isn't in the data scores **zero — worse than none**, because in
production it sends someone chasing nothing at 3am.

So no model writes the numbers. Every value in an `evidence/<row_id>.md` — onset
timestamp, baseline median, in-window peak, z-score, the count of anomalous series — is
carried in a `Finding` dataclass from the measurement that produced it and formatted
directly. A language model can shape the prose around those numbers; it is never asked
to recall one.

## What we did not get to

- **Traces are never opened.** About a third of root-cause reasons are network faults,
  which barely show in metrics at all — you need parent-to-child span latency. This is the
  single biggest accuracy lever left, and it is the most likely explanation for `task_3`
  (component only) scoring **0.000 in all five configurations** — the one number that did
  not move no matter what we did to the ranking.
- **Logs.** Also never opened.

## The model does not earn its place, and we can show it

Three configurations over the same 20 cases ([`eval/routed_compare.md`](eval/routed_compare.md)):

| configuration | mean | s/case | $/case | answers changed vs free |
|---|---|---|---|---|
| no model at all | **0.225** | **1.2** | **$0.0000** | — |
| GLM-5.2, thinking off | 0.163 | 5.4 | $0.0013 | **20 / 20** |
| GLM-5.2, thinking on | **0.225** | 24.7 | $0.0049 | **0 / 20** |

**Thinking on, the strongest model in the family changed none of the twenty answers.**
It was handed a ranked table and picked the top row every time — $0.098 and 8.2 minutes
to agree. Thinking off, it changed all twenty and scored worse.

Two things about this family that are not in the docs, found by probing all seven models
twice each ([`eval/models.md`](eval/models.md)):

- **The cheapest model never puts its answer in `.content`** — it lands in
  `message.reasoning`, so a client reading `.content` gets an empty string, billed, on a
  successful 200. The starter's `llm.py` does exactly that.
- **Price does not predict latency.** GLM-5.2 answered in 1.0s; GLM-4.7-Flash took 24.6s
  and hit its token cap. The cheap end is the *slow* end, and the 20-minute wall is the
  limit most likely to bind.

So `run.py` defaults to the free agent, and the routing harness stays in the repo,
switchable, because the measurement is the deliverable.

## The confidence signal is inverted

| confidence | cases | mean score |
|---|---|---|
| High | 21 | 0.103 |
| Medium | 15 | 0.033 |
| Low | 34 | **0.331** |

The cases it is most sure of are the ones it gets most wrong, by 3.2× — and it survives
task-type controls. We did not flip the label; that would be an overfit wearing a
finding's clothes. [`eval/calibration.md`](eval/calibration.md).

## AI disclosure

Required by §5 of the participant agreement, and accurate.

| | |
|---|---|
| **Coding assistant** | Claude Code (Opus 5), used throughout |
| **Models called by the agent itself** | `zai-org/GLM-5.2` via Featherless in `agents/routed.py`; the shipped default calls none, for the measured reason above |
| **Written by the assistant** | `agents/rca.py`, `agents/routed.py`, `agents/client.py`, `eval/*.py`, `Dockerfile`, `Makefile`, this README, `REPORT.md` |
| **Written by MantisGrid** | `run.py`, `llm.py`, `cost.py`, `score.py`, `agents/heuristic.py` — the provided starter, used as the baseline we measure against. `score.py` vendors OpenRCA's evaluator (MIT) |
| **Directed by the team** | the first-mover hypothesis, the decision to ablate rather than assert, and the decision to ship the configuration the evidence supports instead of the one the brief expects |

The timezone bug, the ablation design, and the gate's held-out-deployment check came out
of assistant-run measurement against the dev split; the team chose what to build and what
to keep.
