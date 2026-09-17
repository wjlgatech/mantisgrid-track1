#!/usr/bin/env python3
"""Ask every model in the family what it actually does, before trusting any of it.

The brief says to check availability before a long run. This checks more than
availability, because two things about this family are not in the docs and both
cost real money:

  1. These are hybrid reasoning models. Left alone they think before answering,
     and the thinking is billed as output tokens -- the priciest and slowest
     thing an agent buys.
  2. `chat_template_kwargs={"enable_thinking": False}` turns that off, but the
     answer then arrives in `message.reasoning` and `message.content` is the
     EMPTY STRING. Any client reading only `.content` -- the starter's llm.py,
     the OpenAI SDK's obvious path -- silently gets nothing back.

So the probe reports, per model: does it answer, where the text lands, how many
output tokens it spends thinking, and how long it takes.

    python eval/probe_models.py            # one cheap call per model, both modes
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

FAMILY = ["zai-org/GLM-4.7-Flash", "zai-org/GLM-5.3-Flash", "zai-org/GLM-4.6",
          "zai-org/GLM-4.7", "zai-org/GLM-5", "zai-org/GLM-5.1", "zai-org/GLM-5.2"]

# $/M tokens (input, output) -- docs/models.md, the table the judged run is priced at
PRICES = {"zai-org/GLM-4.7-Flash": (0.065, 0.40), "zai-org/GLM-5.3-Flash": (0.15, 0.50),
          "zai-org/GLM-4.6": (0.55, 2.20), "zai-org/GLM-4.7": (0.55, 2.20),
          "zai-org/GLM-5": (0.95, 3.15), "zai-org/GLM-5.1": (1.30, 4.30),
          "zai-org/GLM-5.2": (1.40, 4.40)}

PROMPT = ('A microservice failed. Reply with JSON only, no explanation: '
          '{"component": "adservice-0", "reason": "container CPU load"}')


def call(model: str, think: bool, timeout: int) -> dict:
    """One chat call through the SAME SDK the submission ships.

    Not urllib: Featherless sits behind Cloudflare, which 403s (error 1010) on
    urllib's default User-Agent. The failure looks like a dead model -- 403 in
    0.1s on every model in the family -- and it is actually your HTTP client.
    Classify the layer before you blame the key.
    """
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["FEATHERLESS_API_KEY"],
                    base_url=os.environ.get("FEATHERLESS_BASE_URL",
                                            "https://api.featherless.ai/v1"),
                    timeout=timeout, max_retries=0)
    kw = {} if think else {"extra_body": {"chat_template_kwargs":
                                          {"enable_thinking": False}}}
    t0 = time.time()
    try:
        r = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": PROMPT}],
            max_tokens=700, **kw)
    except Exception as e:                       # noqa: BLE001 -- report, never raise
        return {"ok": False, "why": f"{type(e).__name__}: {e}"[:60],
                "s": time.time() - t0}
    s = time.time() - t0
    # A busy model answers HTTP 200 with an error body and no choices.
    if not getattr(r, "choices", None):
        err = getattr(r, "error", None) or {}
        why = err.get("message") if isinstance(err, dict) else str(err)
        return {"ok": False, "why": (why or "no choices")[:40], "s": s}
    msg = r.choices[0].message
    content = (msg.content or "")
    reasoning = (getattr(msg, "reasoning", None) or "")
    u = r.usage
    return {"ok": True, "s": s, "where": "content" if content.strip() else
            ("reasoning" if reasoning.strip() else "NOWHERE"),
            "text": (content or reasoning)[:60].replace("\n", " "),
            "in": (u.prompt_tokens if u else 0), "out": (u.completion_tokens if u else 0)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--models", nargs="*", default=FAMILY)
    args = ap.parse_args()
    if not os.environ.get("FEATHERLESS_API_KEY"):
        sys.exit("FEATHERLESS_API_KEY is not set")

    rows = []
    for model in args.models:
        for think in (True, False):
            r = call(model, think, args.timeout)
            r["model"], r["think"] = model, think
            rows.append(r)
            tag = "think" if think else "no-think"
            if r["ok"]:
                p_in, p_out = PRICES.get(model, (0, 0))
                r["usd"] = (r["in"] * p_in + r["out"] * p_out) / 1e6
                print(f"  {model:<24} {tag:<9} {r['s']:5.1f}s  "
                      f"{r['out']:>4} out  ->{r['where']:<10} ${r['usd']:.6f}")
            else:
                print(f"  {model:<24} {tag:<9} {r['s']:5.1f}s  FAILED: {r['why']}")

    ok = [r for r in rows if r["ok"]]
    lines = ["# The GLM family, probed", "",
             "One identical call per model in each mode. `where` is which field the "
             "answer arrived in — a client reading only `.content` gets an empty "
             "string from every `no-think` row.", "",
             "| model | mode | latency | out tokens | answer lands in | $ |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        if r["ok"]:
            lines.append(f"| `{r['model']}` | {'think' if r['think'] else 'no-think'} | "
                         f"{r['s']:.1f}s | {r['out']} | `{r['where']}` | "
                         f"{r['usd']:.6f} |")
        else:
            lines.append(f"| `{r['model']}` | {'think' if r['think'] else 'no-think'} | "
                         f"{r['s']:.1f}s | — | **{r['why']}** | — |")
    thinking = [r for r in ok if r["think"]]
    quiet = [r for r in ok if not r["think"]]
    if thinking and quiet:
        lines += ["", f"**Turning thinking off cuts output tokens from a median of "
                  f"{statistics.median(r['out'] for r in thinking):.0f} to "
                  f"{statistics.median(r['out'] for r in quiet):.0f}**, and median "
                  f"latency from {statistics.median(r['s'] for r in thinking):.1f}s to "
                  f"{statistics.median(r['s'] for r in quiet):.1f}s — on calls where the "
                  "answer is a short structured fact and the reasoning is waste."]
    lines += ["", f"_Probed {time.strftime('%Y-%m-%d %H:%M')} local. Availability moves; "
              "re-run before a long run._"]
    from pathlib import Path
    Path(__file__).resolve().parent.joinpath("models.md").write_text(
        "\n".join(lines) + "\n")
    print(f"\n{len(ok)}/{len(rows)} calls answered -> eval/models.md")


if __name__ == "__main__":
    main()
