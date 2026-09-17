"""A Featherless client that actually gets the answer out of a GLM model.

The starter's `llm.py` reads `response.choices[0].message.content`. We probed all
seven models in the family twice each (`eval/probe_models.py`, results in
`eval/models.md`) and that is not where the text reliably is:

    GLM-4.7-Flash   -> message.reasoning   in BOTH modes
    GLM-5.3-Flash   -> content when thinking, reasoning when not
    GLM-4.7         -> content when thinking, reasoning when not
    GLM-4.6/5/5.1/5.2 -> content

So a client reading only `.content` gets the empty string from the **cheapest
model in the family** every single time -- silently, with a successful HTTP 200
and a bill for the tokens. `text_of()` below reads content, then reasoning.

Two more things the probe settled, both of which the routing depends on:

  * `chat_template_kwargs={"enable_thinking": False}` cuts output tokens by
    roughly 20-50x on a short structured answer (GLM-4.6: 1759 -> 25). Thinking
    is billed as output, which is both the priciest and the slowest token an
    agent buys, so it is off for every call whose answer is a fact.
  * **Price does not predict latency.** GLM-5.2 answered in 1.0s; GLM-4.7-Flash
    took 24.6s and hit its token cap. Routing a call to the cheap model to "save
    time" is exactly backwards in this family, and the 20-minute wall is the
    limit most likely to bind.

Capacity errors arrive as HTTP 200 with an error body and no `choices`, so that
is checked before anything is read. A model that fails twice is dropped for the
rest of the run: retries cost no dollars but they do spend the case's clock, and
an unavailable model stays unavailable for minutes.
"""
from __future__ import annotations

import os
import re
import time

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

DEFAULT_BASE_URL = "https://api.featherless.ai/v1"
RETRIES = 2          # per model, before moving to the next
BACKOFF = 1.5        # seconds, doubling
BREAKER = 2          # drop a model for the whole run after this many failures


class ModelUnavailable(RuntimeError):
    """Every model offered was busy, or failed, for this call."""


def text_of(message) -> str:
    """The answer, wherever this model decided to put it.

    Order matters: `content` first, because when a model fills both, content is
    the answer and reasoning is the scratch work.
    """
    for field in ("content", "reasoning", "reasoning_content"):
        value = getattr(message, field, None)
        if value and value.strip():
            # Some builds inline the scratch work in content instead.
            return re.sub(r"<think>.*?</think>", "", value, flags=re.S).strip()
    return ""


class LLM:
    def __init__(self, retries: int = RETRIES, backoff: float = BACKOFF,
                 breaker: int = BREAKER, timeout: float = 60.0) -> None:
        key = os.environ.get("FEATHERLESS_API_KEY")
        if not key:
            raise RuntimeError("FEATHERLESS_API_KEY is not set")
        self.client = OpenAI(
            api_key=key,
            base_url=os.environ.get("FEATHERLESS_BASE_URL", DEFAULT_BASE_URL),
            timeout=timeout, max_retries=0)      # our own retry policy, not the SDK's
        self.usage: dict[str, dict[str, int]] = {}
        self.retries, self.backoff, self.breaker = retries, backoff, breaker
        self.failures: list[str] = []            # for the evidence file
        self.down: dict[str, int] = {}           # model -> failures this run

    def ask(self, model: str | list[str], prompt: str | list[dict],
            think: bool = False, max_tokens: int = 700, **kwargs) -> str:
        """One chat call. `model` is a name or several in preference order.

        `think=False` (the default) disables the reasoning pass. Turn it on only
        for the call that genuinely reasons -- it costs 20-50x the output tokens.
        """
        messages = ([{"role": "user", "content": prompt}]
                    if isinstance(prompt, str) else prompt)
        models = [model] if isinstance(model, str) else list(model)
        live = [m for m in models if self.down.get(m, 0) < self.breaker]
        if not live:
            raise ModelUnavailable(f"all of {models} tripped the breaker this run")

        for name in live:
            for attempt in range(self.retries + 1):
                try:
                    return self._once(name, messages, think, max_tokens, **kwargs)
                except (ModelUnavailable, APITimeoutError, APIConnectionError) as e:
                    self._failed(name, type(e).__name__ if not isinstance(
                        e, ModelUnavailable) else str(e)[:60])
                    if attempt < self.retries and self.down.get(name, 0) < self.breaker:
                        time.sleep(self.backoff * 2 ** attempt)
                    else:
                        break
                except APIStatusError as e:
                    # A 4xx that is not capacity. Retrying cannot fix it.
                    self._failed(name, f"HTTP {e.status_code}")
                    break
        raise ModelUnavailable(f"none of {models} answered: {self.failures[-3:]}")

    def _failed(self, model: str, why: str) -> None:
        self.failures.append(f"{model}: {why}")
        self.down[model] = self.down.get(model, 0) + 1

    def _once(self, model: str, messages: list[dict], think: bool,
              max_tokens: int, **kwargs) -> str:
        if not think:
            extra = kwargs.setdefault("extra_body", {})
            extra.setdefault("chat_template_kwargs", {})["enable_thinking"] = False
        r = self.client.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens, **kwargs)

        # A busy model answers 200 with an error body and no choices. The SDK
        # parses that happily, so the check has to be ours.
        if not getattr(r, "choices", None):
            err = getattr(r, "error", None) or {}
            msg = err.get("message") if isinstance(err, dict) else str(err)
            raise ModelUnavailable(msg or "no choices in the response")

        # Only a call that produced something is billed, so count it only here.
        u = self.usage.setdefault(
            model, {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0})
        u["calls"] += 1
        if r.usage:
            u["prompt_tokens"] += r.usage.prompt_tokens or 0
            u["completion_tokens"] += r.usage.completion_tokens or 0

        text = text_of(r.choices[0].message)
        if not text:
            # Billed and empty. Treat it as a failure so the fallback fires,
            # rather than handing the agent a silent empty string.
            raise ModelUnavailable(f"{model} returned no text in any field")
        return text
