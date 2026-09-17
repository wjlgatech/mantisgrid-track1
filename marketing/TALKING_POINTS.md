# Talking points — two minutes, start to finish

**60 seconds of slides. 60 seconds of demo.** Words in quotes are the script.

- Slides → https://wjlgatech.github.io/mantisgrid-track1/marketing/PRESENTATION.html
- Demo → https://wjlgatech.github.io/mantisgrid-track1/docs/demo/

---

# Part 1 · The presentation — 60 seconds, 3 slides

### Slide 1 · WHAT — 20 seconds

> "When a system breaks, everything downstream breaks too — and the parts nearest the
> customer scream loudest. So **twelve things are shouting and the loudest one is almost
> never the cause.**
>
> We built a machine that reads a whole night of data in **one second** and says when it
> started, which part caused it, and why. **Two-point-seven times better** than the
> starting point we were given. Costs nothing to run."

*(the picture is doing the work — let the cascade play)*

### Slide 2 · WHY — 25 seconds

> "Our machine writes down how confident it is. We checked whether that meant anything.
>
> **It's backwards.** When it says 'I'm confident' it's right one time in ten. When it says
> **'I'm not sure' — one time in three.** Three times better when it doubts itself.
>
> That matters because everyone builds the same safety net: *if the machine isn't sure,
> ask a human.* Here that hands people the **easy** ones and lets the mistakes through.
>
> The reason: a clean picture means 'nothing's wrong' — **or** 'the fire is in a room I
> can't see into.' From inside the thermometer those look identical."

### Slide 3 · HOW — 15 seconds

> "For every dial it asks one question: **is this unusual for this machine, tonight?**
> Then it writes a report where **every number is one it actually measured** — nothing
> invented, because a made-up detail sends someone chasing nothing at 3am.
>
> Then a **second AI grades that report.** It gave us three out of five. We published it."

---

# Part 2 · The demo — 60 seconds, 3 clicks

Open https://wjlgatech.github.io/mantisgrid-track1/docs/demo/

### Click 1 — pick an incident *(5s)*

> "Real production data. Half an hour, one failure, gigabytes of readings."

### Click 2 — **Solve** *(25s)*

While it runs:

> "One second. No AI involved in this part at all."

Then point at **two** things, and only two:

**① The table.**
> "Every row is a real measurement. **`z` is the surprise score** — how many normal-sized
> wobbles away from normal this thing is. Not 'how hot' — **'how unusual for this one.'**
> A machine that runs hot every night isn't news."

**② Scroll to "Ruled out".**
> "And here it **argues against itself** — 'this other component started moving nine minutes
> *earlier* than my answer, so I might be wrong.' That's the bit an engineer actually needs."

### Click 3 — **Grade the evidence** *(30s)*

> "Now a second AI reads our report and marks it. Grounding, honesty, did it consider
> alternatives, and — **would this help someone at 3am.**"

When the cards land:

> "**Three out of five** on that last one. It marked us down. **We shipped the bad grade.**
>
> And that's the only job the AI has here. We tested it as the *decision-maker* twice —
> it changed **zero of twenty** answers both times. It just agreed with our list. So it
> doesn't get to decide; it gets to grade."

---

# If they ask — three answers

**"Where's the AI, in an AI competition?"**
> "We hired it twice and both times it read our shortlist and said 'yep, the first one.'
> Zero of twenty changed — even after we fixed the shortlist so the right answer was on it
> 96% of the time. It anchors on the order we hand it. So it grades instead of decides."

**"Why should I trust the report?"**
> "Every number in it is carried straight from the measurement that made it. No model is
> ever asked to *remember* a number. And it tells you what it ruled out and why — so you
> can check it in thirty seconds instead of redoing the work."

**"Will it work on a system you've never seen?"**
> "Two thirds of it will — 'is this unusual for this machine *tonight*' needs no prior
> knowledge; it brings its own normal with it. One third won't travel as well: the part
> that turns 'this is broken' into *why* is a keyword list we wrote by hand. We're telling
> you that rather than letting you find it."

---

# The map — only if someone asks for real terms

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

**The alarm tells you *which*. The smoke tells you *when*.** Different questions, different
signals — and we only learned to separate them by measuring it.

---

# The one line, if you get 15 seconds

> "We built something that finds why a system broke — and the thing we're proudest of is
> discovering its own confidence runs **backwards**, which means the safety design everyone
> ships would have sent humans to the wrong incidents."
