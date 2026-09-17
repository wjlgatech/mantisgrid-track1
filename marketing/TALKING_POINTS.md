# Talking points — ONE minute

**35 seconds of demo. 25 seconds of slides.** Words in quotes are the script. Nothing else.

1. **Demo** → https://wjlgatech.github.io/mantisgrid-track1/docs/demo/
2. **Slides** → https://wjlgatech.github.io/mantisgrid-track1/marketing/PRESENTATION.html

**Open both tabs before you start.** Have the demo already on screen with a case selected.

---

# Demo — 35 seconds

### Click **Solve** *(15s)*

> "A system broke. Half an hour of production data, gigabytes of it.
> **One second. No AI in this part at all.**"

Point at **one** column:

> "**`z` is the surprise score** — not *how hot*, but **how unusual for this machine.**
> Something that runs hot every night isn't news."

Scroll once, to **Ruled out**:

> "And here it **argues against itself** — 'this other one moved nine minutes *earlier*,
> so I might be wrong.'"

### Click **Grade the evidence** *(20s)*

> "Now a second AI marks our report. Would this actually help someone at 3am?"

When the cards land:

> "**Three out of five.** It marked us down — and we shipped that.
>
> That's the *only* job the AI has here. We tested it as the **decision-maker** twice, and
> it changed **zero of twenty** answers. It just agreed with our list. So it grades; it
> doesn't decide."

---

# Slides — 25 seconds

### Slide 1 · WHAT *(8s)*

> "When something breaks, everything downstream breaks too — so **twelve things are
> shouting and the loudest is almost never the cause.** We find the one that moved
> *first*. **2.7× better** than where we started."

### Slide 2 · WHY *(12s)* — **this is the one that has to land**

> "Our machine says how sure it is. **It's backwards.**
> Confident → right **1 time in 10**. Not sure → **1 in 3**.
>
> Everyone builds the same safety net — *if it's unsure, ask a human.* That would hand
> people the **easy** ones and let the mistakes through.
>
> Because a clean picture means 'nothing's wrong' — **or** 'the fire is in a room I can't
> see into.'"

### Slide 3 · HOW *(5s)*

> "Every number in the report is one it **measured**. Nothing invented — a made-up detail
> sends someone chasing nothing at 3am."

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
