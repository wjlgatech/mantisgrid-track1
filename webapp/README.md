# The RCA console

```bash
export FEATHERLESS_API_KEY=<your key>     # needed for the judge; solving is free
make webapp                                # http://127.0.0.1:8100
```

Pick a case, **Solve** it (about 3 seconds, no model, $0), then **Grade the evidence
with GLM-5.2**.

## Why the GLM call is where it is

Track 1 has no interface dimension — the judged run is headless — so this is not
scored. It exists for the demo, and for one design point worth making out loud.

We measured the model twice, under opposite conditions, and **it changed 0 of 20
answers both times** (`marketing/V1_VS_V2.md`). Handed a sorted candidate list it
takes row one and writes a justification. So we ship the diagnosis model-free.

But **judging free-text evidence against a rubric has no deterministic scorer**, and
that is a job a model is genuinely suited to. So `POST /api/judge` sends the evidence
file and the answer to `zai-org/GLM-5.2` on Featherless and returns four grades with
reasoning: grounding, calibration, ruled-out quality, actionability.

That is the honest division of labour this project arrived at:

| Job | Who | Why |
|---|---|---|
| Find the fault | deterministic analysis | measured: the model adds nothing and costs 41% of the wall clock |
| **Grade the explanation** | **GLM-5.2** | no deterministic scorer exists; this is judgement |

A real measured example, on case 0 — grounding 4/5, calibration 5/5, ruled out 4/5,
actionability 3/5, in 15.7s for $0.0048:

> "Well-grounded and honestly calibrated, with transparent alternative analysis, but
> the low confidence undercuts decisiveness for an on-call responder."

Every cost shown in the UI is priced at the published table in `cost.py`, from the
usage Featherless actually returned.

## Endpoints

| | |
|---|---|
| `GET /api/cases` | the 70 dev cases |
| `POST /api/solve` | `{row_id}` → answer, ranked candidates, the compiled evidence file. No model. |
| `POST /api/judge` | `{row_id, evidence, answer}` → GLM-5.2's grades, its token usage, and the dollars |
