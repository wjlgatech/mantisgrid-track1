# Ablation: which decision actually paid

`mean` is OpenRCA's own evaluator over all 70 dev cases. `blank` counts
predictions with no answer in them — the starter emits 24, and a blank
scores exactly what a wrong guess does.

| config | rank | time | mean | solved | blank | task_1 | task_2 | task_3 | task_4 | task_5 | task_6 | task_7 | s/case |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline (starter, UTC) | — | — | **0.073** | 2/70 | 0 | 0.125 | 0.100 | 0.000 | 0.107 | 0.000 | 0.083 | 0.075 | 0.6 |
| UTC+8 | peak | peak | **0.164** | 4/70 | 0 | 0.167 | 0.150 | 0.000 | 0.107 | 0.225 | 0.250 | 0.182 | 0.9 |
| UTC+8 | peak | onset | **0.199** | 6/70 | 0 | 0.250 | 0.150 | 0.000 | 0.071 | 0.325 | 0.250 | 0.243 | 0.9 |
| UTC+8 | onset | peak | **0.131** | 2/70 | 0 | 0.167 | 0.150 | 0.000 | 0.107 | 0.100 | 0.188 | 0.152 | 1.0 |
| UTC+8 | onset | onset | **0.093** | 1/70 | 0 | 0.000 | 0.150 | 0.000 | 0.071 | 0.075 | 0.188 | 0.137 | 0.9 |
