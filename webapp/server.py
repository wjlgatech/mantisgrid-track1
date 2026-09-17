"""The RCA console: run the agent on a case, then have GLM grade its own evidence.

Track 1 has no interface dimension -- the judged run is headless. This exists for
two other reasons, both honest:

  1. **The demo.** Watching a case resolve in three seconds, opening the evidence
     it just compiled, and seeing a second model grade that evidence is a far
     better four minutes than a terminal scrollback.
  2. **GLM does the judging.** Our shipped agent is deliberately model-free (we
     measured the model changing 0 of 20 answers, twice). But *evaluating* free-text
     evidence against a rubric is the one job here a model is actually suited to,
     and there is no deterministic scorer for it. So `/api/judge` sends the evidence
     to `zai-org/GLM-5.2` on Featherless and returns its grades with reasoning.

Run:  make webapp        (needs FEATHERLESS_API_KEY for the judge; solving is free)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents import rca                                          # noqa: E402
from agents.client import LLM, ModelUnavailable                 # noqa: E402

DATASET = Path(os.environ.get("RCA_DATASET", ROOT / "data/Market-cloudbed-1"))
QUERIES = DATASET / "dev" / "query_dev.csv"
JUDGE_MODELS = ["zai-org/GLM-5.2", "zai-org/GLM-5.1"]

app = FastAPI(title="RCA console")


def _cases() -> pd.DataFrame:
    return pd.read_csv(QUERIES)


class SolveIn(BaseModel):
    row_id: int


class JudgeIn(BaseModel):
    row_id: int
    evidence: str
    answer: str


@app.get("/api/cases")
def cases():
    try:
        q = _cases()
    except Exception as e:                                       # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}", "dataset": str(DATASET)}
    return {"cases": [
        {"row_id": int(r.row_id), "task": r.task_index,
         "instruction": r.instruction[:260]}
        for r in q.itertuples(index=False)]}


@app.post("/api/solve")
def solve(body: SolveIn):
    """Run the shipped, model-free agent. Free, and ~1-3 seconds."""
    q = _cases()
    row = q[q.row_id == body.row_id]
    if row.empty:
        return {"error": f"no case {body.row_id}"}
    instruction = row.iloc[0].instruction
    t0 = time.time()
    a = rca.analyse(instruction, DATASET)
    answers = rca.pick(a)
    evidence = rca.write_evidence(a, answers)
    return {
        "row_id": body.row_id,
        "task": row.iloc[0].task_index,
        "instruction": instruction,
        "seconds": round(time.time() - t0, 2),
        "answers": answers,
        "evidence": evidence,
        "candidates": [
            {"component": f.component, "kpi": f.kpi_name, "z": round(f.z, 1),
             "onset": f.onset.strftime("%H:%M:%S"),
             "baseline": float(f"{f.baseline:.4g}"), "peak": float(f"{f.peak:.4g}")}
            for f in a.findings[:12]],
        "model_calls": 0,
    }


RUBRIC = """You are grading one root-cause-analysis evidence file from a
microservice incident, against the rubric this competition publishes.

Grade each dimension 1-5 and give one sentence of reasoning for each:

1. GROUNDING - is every number traceable to a named file and window, or are there
   claims the data could not support? Evidence that is not in the data scores ZERO
   in this competition; treat invented specifics as the worst failure available.
2. CALIBRATION - does the stated confidence match the strength of the argument?
   Confidently wrong is penalised harder than uncertain and close.
3. RULED OUT - does it genuinely consider and exclude alternatives, with reasons,
   including any that argue AGAINST its own pick?
4. ACTIONABILITY - at 3am, would an on-call engineer know what to look at next?

Reply with JSON only, no prose outside it:
{"grounding": {"score": n, "why": "..."},
 "calibration": {"score": n, "why": "..."},
 "ruled_out": {"score": n, "why": "..."},
 "actionability": {"score": n, "why": "..."},
 "overall": n, "one_line": "..."}"""


@app.post("/api/judge")
def judge(body: JudgeIn):
    """GLM-5.2 grades the evidence. This is the only model call in the product."""
    if not os.environ.get("FEATHERLESS_API_KEY"):
        return {"error": "FEATHERLESS_API_KEY is not set — the judge needs it. "
                         "Solving still works without it."}
    llm = LLM(timeout=90)
    t0 = time.time()
    try:
        reply = llm.ask(JUDGE_MODELS, think=True, max_tokens=1200, prompt=(
            f"{RUBRIC}\n\n--- THE AGENT'S ANSWER ---\n{body.answer}\n\n"
            f"--- THE EVIDENCE FILE ---\n{body.evidence}"))
    except (ModelUnavailable, Exception) as e:                   # noqa: BLE001
        return {"error": f"{type(e).__name__}: {str(e)[:200]}",
                "usage": llm.usage, "failures": llm.failures[-3:]}
    m = re.search(r"\{.*\}", reply, re.S)
    try:
        grades = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        grades = {}
    # price it at the published table, so the cost is real and visible
    from cost import by_model
    try:
        usd = sum(by_model(llm.usage).values())
    except Exception:                                            # noqa: BLE001
        usd = 0.0
    return {"grades": grades, "raw": reply[:2000], "usage": llm.usage,
            "seconds": round(time.time() - t0, 2), "usd": round(usd, 6),
            "judge_model": JUDGE_MODELS[0]}


@app.get("/", response_class=HTMLResponse)
def index():
    return (Path(__file__).resolve().parent / "index.html").read_text()
