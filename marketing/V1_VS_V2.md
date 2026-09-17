# v1 vs v2: the root-cause analysis of our own root-cause agent

**Question asked:** accuracy graded C+ (0.199 against a 0.073 baseline). Find the real
cause and fix it, leaving no obvious shortcoming behind.

**Answer, in one line:** the bottleneck was never ranking quality. **44% of the correct
answers were impossible for v1 to say out loud.** v2 fixes that — reachability goes from
53.7% to 96.3% — and in doing so converts a retrieval problem into a re-ranking problem
that v2 has not yet solved.

---

## How we found it: decompose before you optimise

The evaluator scores three elements independently. Nobody had looked at them separately.

| Element | v1 accuracy |
|---|---|
| Occurrence time | 27.3% |
| **Root cause component** | **14.8%** |
| Failure reason | 23.6% |

Component was the weakest, so we asked the only question that matters next:
**is the true component even in our candidate list?**

| v1 | |
|---|---|
| True component appears anywhere in our ranking | **53.7%** |
| recall@1 | 14.8% |
| recall@10 | 40.7% |
| Median rank when present | 6 |

`recall@1` (14.8%) equals our component accuracy (14.8%) exactly — confirming we emit
rank 1 and nothing else. But **46% of the time the answer was not in the list at any
rank**, and no re-ranking can fix that.

## The root cause: we could only name two of the three levels

Looking at what was missing revealed it immediately. The absent names were
`recommendationservice`, `paymentservice`, `emailservice`, `productcatalogservice`,
`adservice`, `cartservice` — **service-level names, with no pod suffix**.

The ground truth names components at three levels. v1 produced two:

| Level | Share of answers | v1 could emit it? |
|---|---|---|
| **Service** (`adservice`) | **44%** | **No — never produced** |
| Node (`node-5`) | 37% | Yes |
| Pod (`adservice-0`) | 19% | Yes |

v1's `component_of()` turns `node-5.adservice-2` into the pod. A bare service name was
unreachable **by construction**, which put a hard ceiling of **56%** on component
accuracy before a single line of ranking logic ran.

**And the sensor was sitting right there.** `metric_service.csv` is 1 MB a day against
`metric_container.csv`'s 265 MB — the cheapest file in the bundle — and v1 never opened
it. Its `service` column is `<name>-<protocol>` (`adservice-grpc`, `frontend-http`);
stripping the protocol recovers **all nine** ground-truth service names exactly.

## v2: the third sensor

`metric_service.csv` is reshaped into the same `(timestamp, cmdb_id, kpi_name, value)`
form as the other two, so service rows flow through the identical z-score path.

| | v1 | v2 |
|---|---|---|
| Sensors read | container, node | container, node, **service** |
| True component reachable at all | 53.7% | **96.3%** |
| recall@1 | 14.8% | 16.7% |
| recall@3 | — | **38.9%** |
| recall@10 | 40.7% | 53.7% |
| **Overall score, all 70** | **0.199** | **0.169** |
| Wall-clock | 1.3 s/case | 2.5 s/case |

**The ceiling is gone and the score went down.** That is the honest headline, and the
reason is worth more than the fix would have been.

## Why adding the right sensor made the score worse

A z-score from `metric_service` (request rate, success rate, mean response time) and a
z-score from `metric_container` (CPU seconds, bytes) are **not the same quantity**.
Different distributions, different tails. Ranked against each other, services took
**68% of the rank-1 slots** while being only 44% of the answers — they shouted louder,
so they won, and they displaced correct node and pod answers.

We had already made this exact mistake once today, with the trace view. Same shape,
same afternoon: *a new view is only as good as the rule that decides when it wins.*

**The attempted fix** (v2.1) scores each series against its own source's distribution —
a percentile within its own file, which is distribution-free and fits nothing about
which answers are correct:

| | all 70 | first 20 | `task_3` | `task_4` | `task_5` |
|---|---|---|---|---|---|
| v1 | **0.199** | 0.225 | 0.000 | 0.071 | 0.225 |
| v2 raw z | 0.151 | 0.225 | 0.000 | 0.143 | 0.225 |
| **v2.1 normalised** | 0.169 | **0.250** | **0.062** | **0.179** | **0.275** |

Normalisation recovered most of the loss and **`task_3` scored above zero for the first
time in any configuration we have run** — the component-only task that had been stuck at
0.000 through five previous variants. `task_4` and `task_5` also improved.

It is still below v1 on all 70. And note the trap in that table: **v2.1 beats v1 on the
first 20 cases (0.250 vs 0.225) and loses on all 70.** Earlier today a paired bootstrap
showed that per-case scores here have a standard deviation near 0.3, so a 20-case
comparison cannot resolve a 0.03 effect. We are not going to quote the 20.

## What we shipped, and why

**v1 remains the shipped default.** It is the configuration with the best measured score
on the full dev split, and we do not ship a regression to make a story neater.

v2 lives in the tree behind its own switch, with this document, because the finding is
more valuable than the fix:

> **Retrieval was the bottleneck and now it is not. Ranking is.**

## What this does to our other headline finding

Earlier today we reported that GLM-5.2, with reasoning enabled, **changed 0 of 20
answers** when asked to pick the root cause from our ranked candidate table — and we
concluded the model added nothing.

**That conclusion was tested on a table that did not contain the answer 46% of the
time.** A model cannot choose a name it was never shown. The measurement was correct and
the interpretation was too broad, and we would have shipped it that way if we had not
decomposed the accuracy.

With v2's table the situation is different in exactly the way that matters:
`recall@1` is 16.7% while `recall@3` is 38.9%. **The answer is usually in the top three
and we pick the wrong one of them** — a judgement problem on a short list, not retrieval.

So we predicted the model would finally earn its place, and re-ran it on the fixed table.

| On the same 20 cases | Score | Answers changed |
|---|---|---|
| v1, shipped | 0.225 | — |
| v2.1, no model | **0.250** | — |
| v2.1 + GLM-5.2, reasoning on | **0.250** | **0 / 20** |

**It changed zero of twenty answers again** — on a table that now contains the answer 96%
of the time. Two independent runs, opposite retrieval conditions, identical behaviour.
Our hypothesis was wrong, and that is the useful part.

The model was never information-starved. Handed a list that is already sorted, it takes
row one and writes a justification: **it anchors on our ordering and rubber-stamps it.**
Give it better rows and it rubber-stamps those instead — which is precisely what
0.250 → 0.250 is.

That relocates the problem a second time. It is not the data we showed the model, it is
the **shape**: a ranked list carries our answer inside its order, and the model reads the
order as the answer. Independent judgement would mean removing the ordering — shuffling
the candidates, or scoring each alone without its neighbours. **We have not tested that,
and we are not claiming it works.**

## No obvious shortcoming left unnamed

1. **Reachability: fixed.** 53.7% → 96.3%.
2. **Cross-source comparability: identified, partially fixed.** Percentile normalisation
   recovers most of the regression; it is not yet a win on all 70.
3. **Ranking: now the whole problem.** recall@3 is 2.3× recall@1. That gap is the work.
4. **Traces: still off.** The second view lifts the twelve network cases 75% and the
   promotion rule spends the gain elsewhere. Same failure mode as v2's merge — and
   plausibly the same fix, which is the next thing we would try.
5. **Leakage: still present and still named.** `Z_MIN`, `PCTL` and the percentile rule
   were all chosen while looking at all 70 cases.
6. **`task_6` regressed** in v2.1 (0.250 → 0.083) and we do not know why. Stated, not hidden.

## Where the model does earn its place

Two runs said the model cannot pick a root cause better than a sort. Neither says
a model is useless here — they say it is useless **at that job**.

The job it is suited to is the one with no deterministic scorer. Accuracy has one
(OpenRCA's `evaluate`). **Evidence quality does not** — it was our own assertion
that our evidence was good.

So `webapp/` puts `zai-org/GLM-5.2` exactly there: `POST /api/judge` grades the
evidence file on grounding, calibration, ruled-out quality and actionability,
with reasoning. On case 0 — 4/5, 5/5, 4/5, **3/5**, 15.7s, $0.004833.

| Job | Who | Why |
|---|---|---|
| Find the fault | deterministic analysis | measured twice: 0 of 20 answers changed, 41% of the wall clock |
| **Grade the explanation** | **GLM-5.2** | no deterministic scorer exists; this is judgement |

That is the division of labour this project argued its way to, and every row of it
is a measurement rather than a preference.

## Reproduce

```bash
make dev && make score          # v1, the shipped default
RCA_SERVICES=1 make dev && make score
make significance               # why a 20-case comparison proves nothing here
```
