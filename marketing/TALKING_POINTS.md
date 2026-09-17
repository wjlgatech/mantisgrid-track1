# Talking points

**One rule: never say a technical word before the everyday word for it.**
Tell the kitchen story. Then, once, show the map. That's it.

---

## 1. The story — no technical words at all

> A restaurant is running **thirty minutes late**. Customers are complaining at the front.
>
> Someone hands you a box. Inside is **everything that happened that night**: every
> temperature reading from every stove, every cook's notes, and every order slip — each
> one stamped at each station it passed through.
>
> Enough paper to fill a room. For **half an hour** of one bad evening.
>
> The manager wants three things. **When** did it start? **Which station** caused it?
> **Why?**

Then the trap, which is the whole problem:

> When one station jams, **every station after it jams too.** And the ones closest to the
> customer complain loudest.
>
> **Twelve stations are shouting. One of them started it. The loudest one is almost never
> the culprit.**

Stop there. Don't explain anything yet. Let that sit.

---

## 2. What we built — still no technical words

> We built a machine that reads the whole box **in one second**.
>
> For every stove it asks one question: *"Did this run hotter tonight than it normally
> does?"* Then it ranks them, and writes a short report — with the actual numbers it saw,
> and the stoves it considered and dropped.

**2.7× better than the starting point. One second a case. Costs nothing to run.**

> For scale: the best published attempt at this problem gets it right about **one case in
> nine**. This isn't solved. So most of what I'll show you is what we *learned*.

---

## 3. The four things worth telling

### "Our biggest win was a clock."

> Every timestamp in the box was written in **Beijing time**. We were reading them as
> **London time**. Eight hours off.
>
> So for anything after 4pm, we were looking past the end of the night — at **nothing**.
> On **24 cases out of 70** we handed in a blank answer and didn't know it.
>
> One line of code. Worth more than every clever idea we had.

### "Watch it work." *(the live bit)*

Solve a case. Three seconds. Then open the report and point at two things:

> ① **Every number here is one it actually measured.** Nothing invented.
> ② **It argues against itself** — "this other station started moving nine minutes
> *earlier* than my answer, so I might be wrong."

Then click **Grade**:

> A second machine reads our report and marks it. It gave us **3 out of 5** on *"would
> this actually help someone at 3am."* **It marked us down. We published that.**

### "When our machine is sure, it's usually wrong."

| it told us | how often it was right |
|---|---|
| "I'm confident" | **1 time in 10** |
| "I'm not sure" | **1 time in 3** |

> Three times *better* when it doubts itself. We checked — it isn't luck.
>
> Normally you'd say *"when the machine isn't sure, ask a human."* **That would have been
> exactly backwards.** Humans would get handed the easy ones, and the mistakes would sail
> straight through.

**Why** — this is the line to land:

> It says "I'm confident" when the picture is **clean**: one stove clearly hottest,
> nothing else moving. But a clean picture also happens when **the fire is somewhere a
> thermometer can't reach.**
>
> **From inside the thermometer, those two look identical.**

### "We tried an AI. Twice. It just agreed with us."

> We handed it our shortlist and asked it to pick. It changed **0 of 20** answers.
> We thought our shortlist was the problem, so we fixed it — the right answer went from
> being on the list half the time to **96%** of the time. Re-ran it. **0 of 20 again.**
>
> Give it a sorted list and it takes the top one and explains why. It wasn't thinking.
> It was agreeing.
>
> So we don't use it to pick. **We use it to grade our homework** — the one job where no
> simple rule can do the checking.

---

## 4. Reading the report out loud

When you open the evidence file on stage, this table is on screen. Explain it once,
in this order — it takes twenty seconds and it makes everything after it land.

| column | say this | what it really is |
|---|---|---|
| **onset** | "when this stove *first* started acting odd — the first wisp of smoke" | first sample outside the normal band |
| **component** | "which stove, or which whole station" | the container / node / service |
| **KPI** | "which dial we're reading on it — heat? gas? fan speed?" | the metric name |
| **baseline** | "what that dial reads on a **normal** night" | median over the rest of that day |
| **peak** | "the worst it got **tonight**" | max deviation inside the window |
| **z** | "**the surprise score** — how many normal-sized wobbles away from normal this is" | robust z-score (median + MAD) |

**The one to dwell on is `z`.** Say it like this:

> Every dial wobbles a bit. If a stove normally swings two degrees either way, and
> tonight it swung two hundred — that's a hundred wobbles' worth of surprise. That's what
> `z` counts. **It's not "how hot", it's "how unusual for this stove."**
>
> Which matters, because a stove that runs hot every single night isn't news. We're
> looking for the one that broke its own habit.

And the design in one sentence, pointing at two columns:

> **The alarm tells you *which*. The smoke tells you *when*.** `z` picks the culprit,
> `onset` dates the crime — and we only learned to separate those by measuring it.

---

## 5. The story, mapped to money

Every piece of the kitchen has a cost attached. This is what makes it a business problem
rather than a puzzle.

| In the story | What it is | What it costs a real company |
|---|---|---|
| Orders 30 minutes late | A production outage | Revenue stops. For a mid-size shop, thousands of dollars a minute |
| Twelve stations shouting | Alert storm | Everyone is paged; nobody knows who owns it |
| Sending someone to the loudest station | Chasing the symptom | **The outage continues while you fix the wrong thing** — this is the expensive mistake |
| One second to read the whole box | Automated triage | The first 20 minutes of an incident are usually spent just *locating* it. That's the bill this removes |
| A report with real numbers in it | Checkable evidence | The engineer trusts it in 30 seconds instead of redoing the work. Trust is what makes automation usable |
| A report with *invented* numbers | Hallucinated evidence | **Worse than nothing.** Sends someone chasing something that isn't there, at 3am, while the outage runs |
| "I'm confident" being wrong | Miscalibrated confidence | You automate the cases it gets wrong and hand humans the ones it got right. **You've paid for automation and bought risk** |
| The second machine grading the report | Automated review | The only part of this a person can't check cheaply at scale |

**The one-line business case:**

> *"The costly part of an outage usually isn't the fix — it's the twenty minutes of six
> people arguing about which team owns it. That's the part this removes. And the reason we
> care so much about the confidence being backwards is that getting it wrong doesn't just
> waste the automation — it actively routes your humans to the wrong incidents."*

---

## 6. The map — say this once, near the end

| in the story | what it really is |
|---|---|
| One stove | a container — one copy of one service |
| The building's gas main | a node — the machine they share |
| A whole station | a service |
| Temperature readings | metrics (CPU, memory, disk) |
| An order slip stamped at each station | a trace — spans with timings |
| Time between two stamps | span latency — time on the wire |
| **First wisp of smoke** | **onset** — how we date it |
| **The fire alarm** | **peak / z** — how we pick it |
| "Hotter than it normally runs" | robust z-score vs the rest of that day |
| The written report | the evidence file |
| The second machine that grades it | GLM-5.2, as judge |

No orphans: every row has both halves. If you catch yourself saying something in the
right column that isn't in the left, stop and say the left instead.

---

## 7. Backup — the three questions you'll get

**"Why is there no AI in the judged run? This is the AI track."**

> We hired the chef twice, and both times he read our shortlist and said "yes, the first
> one." Zero of twenty changed. He wasn't short of information — the second time our
> shortlist contained the right answer 96% of the time and he *still* just agreed. He
> anchors on the order we hand him.
> *(GLM-5.2, reasoning on, 0/20 twice, under opposite retrieval conditions. The harness is
> in the repo, switchable; `make compare` reproduces it.)*

**"So where does the AI earn its place?"**

> Grading the report. Whether a stove was hot is arithmetic — no opinion required.
> Whether a **write-up** is any good is judgement, and nothing simple can check that.
> That's its one job, and it marks us down on it.
> *(Accuracy has a deterministic scorer; evidence quality had none — it was our own
> assertion until GLM supplied one.)*

**"Will this work in a kitchen you've never seen?"**

> Two thirds of it will. "Was this stove hotter than usual **tonight**" needs no prior
> knowledge of that kitchen — it brings its own normal with it.
>
> One third won't travel as well: the part that turns "hot stove" into *why* is a keyword
> list we wrote by hand. If the next kitchen labels its dials differently, that third gets
> worse. We're telling you rather than letting you find it.
> *(Component and time come from a per-case statistic; reason comes from a 19-entry map
> deciding 40 of 121 gradeable items. Constants were tuned on all 70 cases — leakage,
> stated in the report.)*

---

## 8. If you only get thirty seconds

> *"We built something that finds why a system broke. The thing we're proudest of is
> discovering that its own confidence runs backwards — which means the safety design
> everyone ships would have sent humans to the wrong incidents."*
