# Talking points — ONE minute

**35 seconds of demo. 25 seconds of slides.** Words in quotes are the script. Nothing else.

*Measured: 181 spoken words — **64 seconds** at a normal 170 wpm, 57 at a brisk pace.
Counted, not estimated. If you narrate the clicks as well, budget 75.*

1. **Demo** → https://wjlgatech.github.io/mantisgrid-track1/docs/demo/
2. **Slides** → https://wjlgatech.github.io/mantisgrid-track1/marketing/PRESENTATION.html

**Open both tabs before you start.** Have the demo already on screen with a case selected.

---

# Demo — 35 seconds

### Click **Solve** *(15s)*

> "A system broke. Gigabytes of data, one half-hour.
> **One second. No AI here.**"

Point at one column:

> "**`z` is the surprise score** — not *how hot*, but **how unusual for this machine.**"

Scroll to **Ruled out**:

> "And it **argues against itself** — 'this one moved nine minutes *earlier*.'"

### Click **Grade the evidence** *(20s)*

> "Now a second AI marks it. Would this help someone at 3am?"

When the cards land:

> "**Three out of five.** It marked us down. We shipped that.
>
> That's its only job. As the **decision-maker** it changed **zero of twenty** answers,
> twice. It grades; it doesn't decide."

---

# Slides — 25 seconds

### Slide 1 · WHAT *(7s)*

> "Everything downstream breaks too — so **the loudest alarm is almost never the cause.**
> We find what moved *first*. **2.7× the baseline.**"

### Slide 2 · WHY *(13s)* — **the one that has to land**

> "It says how sure it is. **It's backwards.** Confident → **1 in 10**. Not sure → **1 in 3**.
>
> Everyone ships the same safety net — *if unsure, ask a human.* That hands people the
> **easy** ones and lets mistakes through.
>
> A clean picture means 'nothing's wrong' — **or** 'the fire is somewhere I can't see.'"

### Slide 3 · HOW *(5s)*

> "Every number is one it **measured**. Nothing invented — a made-up detail sends someone
> chasing nothing at 3am."

---

# If they ask

**"Where's the AI?"**
> "We hired it twice; both times it read our shortlist and said 'yep, the first one.' Zero
> of twenty changed — even when the right answer was on the list 96% of the time. It
> anchors on our ordering. So it grades instead."

**"Why trust the report?"**
> "Every number comes straight from the measurement that made it. No model is ever asked
> to *remember* one. And it tells you what it ruled out — check it in thirty seconds
> instead of redoing the work."

**"Will it work somewhere new?"**
> "Two thirds will — 'unusual for this machine *tonight*' brings its own normal with it.
> One third won't: turning 'broken' into *why* is a keyword list we wrote by hand. We're
> telling you rather than letting you find it."

---

# 15 seconds, if that's all you get

> "We built something that finds why a system broke — and what we're proudest of is
> discovering its own confidence runs **backwards**, which means the safety design everyone
> ships would have sent humans to the wrong incidents."

---

<details>
<summary>The story→tech map, only if someone wants real terms</summary>

| in the story | what it is |
|---|---|
| one stove | a container |
| the gas main | a node |
| a whole station | a service |
| temperature readings | metrics |
| an order slip stamped at each station | a trace |
| **first wisp of smoke** | **onset — how we date it** |
| **the fire alarm** | **peak / z — how we pick it** |
| "hotter than it normally runs" | robust z-score vs the rest of that day |
| the written report | the evidence file |
| the second machine that grades it | GLM-5.2, as judge |

**The alarm tells you *which*. The smoke tells you *when*.**

</details>
