# Which findings survive the sample size?

Per-case scores have a standard deviation around 0.3; the effects we
chase are around 0.03. Paired bootstrap, 10,000 resamples, seed 0.

## Each configuration on its own

| configuration | mean | 95% CI | sd |
|---|---|---|---|
| starter (UTC) | 0.073 | [0.031, 0.123] | 0.202 |
| timezone fix only | 0.164 | [0.105, 0.231] | 0.278 |
| shipped (peak rank / onset time) | 0.199 | [0.130, 0.276] | 0.315 |
| onset rank / peak time | 0.131 | [0.079, 0.190] | 0.238 |
| onset rank / onset time | 0.093 | [0.050, 0.143] | 0.201 |

## Paired comparisons — the claims we actually made

| claim | delta | 95% CI | verdict |
|---|---|---|---|
| the timezone fix | +0.092 | [+0.031, +0.153] | **significant** |
| shipped (peak rank / onset time) vs timezone fix alone | +0.035 | [-0.023, +0.095] | not significant — CI spans zero |
| onset rank / peak time vs timezone fix alone | -0.033 | [-0.085, +0.016] | not significant — CI spans zero |
| onset rank / onset time vs timezone fix alone | -0.071 | [-0.132, -0.014] | **significant** |

## The routed comparison (n=20, so the bar is higher)

| claim | delta | 95% CI | verdict |
|---|---|---|---|
| routed no-think vs free (n=20) | -0.062 | [-0.212, +0.075] | not significant — CI spans zero |
| routed think vs free (n=20) | +0.000 | [+0.000, +0.000] | not significant — CI spans zero |

**The `think` row is not a statistical result.** Its answers were
identical to the free agent's on 20 of 20 cases —
the model changed nothing, so there is no difference to detect rather
than a difference too small to see. That is an exact observation and a
stronger statement than any p-value.

## Is the confidence inversion real?

| | n | mean |
|---|---|---|
| High confidence | 21 | 0.103 |
| Low confidence | 34 | 0.331 |

Low − High = **+0.228**, 95% CI [+0.064, +0.385], permutation p = **0.0056**.

**Yes.** The agent is reliably most wrong where it is most confident.

## What this does not tell us

Every interval here is sampling noise on **this** deployment. The judged
run is 20 cases from a *different* deployment with different components,
and no resampling of these 70 cases estimates that gap. Our honest
expectation for the judged score is *below* the numbers above, because
our tunable constants were chosen while looking at all 70.
