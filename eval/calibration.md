# Is the confidence calibrated?

Confidence is computed from the measured gap between the top candidate and its rivals, not asserted. Scored against the dev answers with OpenRCA's own evaluator.

| confidence | cases | mean score | fully solved |
|---|---|---|---|
| High | 21 | 0.103 | 1/21 |
| Medium | 15 | 0.033 | 0/15 |
| Low | 34 | 0.331 | 5/34 |
| **all** | 70 | **0.199** | 6/70 |

Abstaining on every **Low** case would drop 34 of 70 answers (49%) and change accuracy on the rest from 0.199 to 0.074 (0.37x).

**Verdict: the signal is INVERTED.** High scores 0.103 against Low's 0.331 — the cases the agent is most sure of are the ones it gets most wrong, by 3.2x. This is not noise and it is not a calibration; it is a bug in what we decided confidence means.

## Within each task type

If the inversion were an artefact of High landing on harder task
types, it would vanish here. It does not.

| task | High | Medium | Low |
|---|---|---|---|
| task_1 | 0.000 | 0.000 | 0.500 |
| task_2 | 0.000 | 0.000 | 0.250 |
| task_3 | 0.000 | 0.000 | 0.000 |
| task_4 | 0.000 | — | 0.250 |
| task_5 | 0.000 | 0.000 | 0.464 |
| task_6 | 0.500 | 0.125 | 0.250 |
| task_7 | 0.234 | 0.000 | 0.300 |

## What we think is happening, stated as a hypothesis

`High` is awarded when one component both **dominates on magnitude**
and **nothing anomalous started before it**. Those are exactly the
cases we get wrong. The reading we find most plausible: a component
that is both loudest and earliest in *metrics* is often the loud
victim of something metrics barely show — and the brief says about a
third of root causes are network faults, visible only as
parent-to-child span latency in the traces we never open.

We are **not** flipping the label on this evidence. Inverting a
signal fitted to 70 cases of one deployment, to be judged on a
different deployment, is how you turn a finding into an overfit.
We report the number and stop claiming the word means what it says.
