# Placing the trace-promotion threshold

Network faults are 25% of the scored reasons here and the metrics barely see them.
We built a second view -- the p95 of a caller's parent-to-child span gap, its wire
time -- and swept how hard to promote it over the metric ranking, across all 70
dev cases.

The `12 network cases` column is the ones whose true reason is a network fault.
`other 58` is there to catch a threshold that helps one by breaking the other.

| trace promotion | all 70 | 12 network cases | other 58 | s/case |
|---|---|---|---|---|
| **traces off (shipped)** | **0.199** | 0.111 | **0.217** | **1.1** |
| always promote | 0.163 | **0.194** | 0.157 | 16.6 |
| promote z >= 1,000 | 0.194 | 0.111 | 0.211 | 20.1 |

## What this says

**The signal is real.** Always promoting the trace view lifts the twelve network
cases from 0.111 to 0.194 -- a 75% gain on exactly the cases we built it for, and
the largest single improvement we found all day.

**And we cannot collect it.** The same rule drags the other 58 cases from 0.217 to
0.157, because it also fires where the metrics were already right. Net, the whole
run drops from 0.199 to 0.163. A magnitude gate at z >= 1,000 avoids the damage by
never firing on a network case either -- it buys 20 seconds a case and changes
nothing.

So we ship with traces **off**, and we keep the module. The honest state is not
"traces do not work"; it is **we found the signal and do not yet know how to
promote it without collateral damage**. That is a sharper next move than anything
else on our list: the fix is a rule that asks *which view should decide this case*
rather than one that lets the loud view win.

Reproduce: `python eval/sweep_traces.py --thresholds off 0 1000` (~30 min, no key).
