# The GLM family, probed

One identical call per model in each mode. `where` is which field the answer arrived in — a client reading only `.content` gets an empty string from every `no-think` row.

| model | mode | latency | out tokens | answer lands in | $ |
|---|---|---|---|---|---|
| `zai-org/GLM-4.7-Flash` | think | 24.6s | 700 | `reasoning` | 0.000282 |
| `zai-org/GLM-4.7-Flash` | no-think | 1.5s | 26 | `reasoning` | 0.000013 |
| `zai-org/GLM-5.3-Flash` | think | 10.4s | 379 | `content` | 0.000196 |
| `zai-org/GLM-5.3-Flash` | no-think | 35.3s | 348 | `reasoning` | 0.000180 |
| `zai-org/GLM-4.6` | think | 49.2s | 1759 | `content` | 0.003889 |
| `zai-org/GLM-4.6` | no-think | 2.6s | 25 | `content` | 0.000074 |
| `zai-org/GLM-4.7` | think | 42.0s | 336 | `content` | 0.000758 |
| `zai-org/GLM-4.7` | no-think | 6.0s | 50 | `reasoning` | 0.000129 |
| `zai-org/GLM-5` | think | 14.7s | 177 | `content` | 0.000591 |
| `zai-org/GLM-5` | no-think | 2.1s | 22 | `content` | 0.000103 |
| `zai-org/GLM-5.1` | think | 2.8s | 153 | `content` | 0.000703 |
| `zai-org/GLM-5.1` | no-think | 1.5s | 26 | `content` | 0.000157 |
| `zai-org/GLM-5.2` | think | 2.6s | 200 | `content` | 0.000939 |
| `zai-org/GLM-5.2` | no-think | 1.0s | 18 | `content` | 0.000130 |

**Turning thinking off cuts output tokens from a median of 336 to 26**, and median latency from 14.7s to 2.1s — on calls where the answer is a short structured fact and the reasoning is waste.

_Probed 2026-09-17 11:14 local. Availability moves; re-run before a long run._
