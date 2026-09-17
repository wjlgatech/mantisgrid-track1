# Talking points — one story, mapped to every technical term

**Rule for this whole talk: never say a technical word before the plain idea it stands
for.** Say the kitchen thing, then name the real thing in the same breath. One domain,
start to finish — we never leave the restaurant.

---

## The story (say this first, ~40 seconds)

> A restaurant is failing. Orders that should take ten minutes are taking thirty.
> Customers are complaining at the front.
>
> The manager hands you a box. Inside: every thermometer reading from every stove that
> evening, every line cook's notebook, and every order ticket — each one stamped at each
> station it passed through. Several gigabytes of paper for **thirty minutes** of one bad
> night.
>
> Three questions. **When** did it start going wrong? **Which station** caused it?
> **Why?**
>
> Here's what makes it hard. When one station jams, every station downstream jams too —
> and the ones nearest the customer complain loudest. Twelve stations are screaming.
> **The loudest complaint is almost never the culprit.**

Then land the stakes: *"The best published attempt at this solves about one case in
nine. So this is genuinely unsolved — and most of what I'll show you is what we
learned, not what we won."*

---

## The map — every piece of the story, and exactly what it is

| In the kitchen | In the system | Where it lives |
|---|---|---|
| One stove | A **container** — one replica of one service | `metric_container.csv`, 265 MB/day |
| The building's gas main | A **node** — the host several containers share | `metric_node.csv`, 21 MB/day |
| A whole station (all its stoves) | A **service** | `metric_service.csv`, **1 MB/day** |
| Thermometer readings, taken every minute | **Metrics** — CPU, memory, disk I/O | the three files above |
| An order ticket stamped at each station | A **trace** — parent and child spans with durations | `trace_span.csv`, 1.3 GB/day |
| Time between two stamps on one ticket | **Span latency** — time on the wire | the gap we compute |
| "This stove ran way hotter than it does all night" | **Robust z-score** — median + MAD vs the rest of that day | `rca.analyse()` |
| The first wisp of smoke | **Onset** — first sample to leave the band | how we date the fault |
| The fire alarm going off | **Peak** — the largest deviation | how we pick the culprit |
| The manager's three questions | `datetime` / `component` / `reason` | what the evaluator grades |
| "Which of these 15 things went wrong" | The **reason label set**, published in the brief | 15 fixed strings |
| A new head chef reading your report at 3am | The **evidence file** | `evidence/<row_id>.md` |
| A second inspector grading your report | **GLM-5.2 as judge** | `POST /api/judge` |

**No orphans.** Every row has both halves. If you find yourself saying a technical word
that isn't in the right column, stop and say the left column instead.

---

## The four beats

### Beat 1 — "We got 2.7× better, and the biggest win was embarrassing" (0:00–1:00)

**Say:** *"We went from 0.073 to 0.199. And the single biggest gain wasn't a clever
idea — it was a clock."*

> The kitchen's thermometers were stamped in **Beijing time**. We were reading them in
> **London time**. Eight hours off. For any incident after 4pm we were looking past the
> end of the night's records and finding **nothing at all** — so on 24 of 70 cases we
> handed in a **blank answer**.

**Technical:** the telemetry is UTC+8; the starter parses the window as UTC. Any window
at 16:00 or later falls past the end of the day file. One line. **+0.092, the largest
single gain available, and it's a bug fix.**

### Beat 2 — the live demo (1:00–2:00)

**Do:** `make webapp` → pick a case → **Solve** → **Grade with GLM-5.2**

**Say while it runs:** *"Three seconds. No AI model at all. Zero dollars."*

Then open the evidence file and point at three things:

1. **"Every number here is one we measured."** *(Technical: values are carried in a
   `Finding` dataclass from the computation that produced them and formatted directly —
   no model is ever asked to recall a number. Evidence not in the data scores **zero**
   in this competition, which is worse than none, because at 3am it sends someone
   chasing nothing.)*
2. **"Ruled out — and look, it argues against itself."** *"It says node-6 started moving
   540 seconds EARLIER than our answer. So our own pick is excluded on size alone, and
   it tells you that."*
3. **Click Grade.** *"Now a second model reads our report and grades it. 4 out of 5 on
   grounding, 5 on calibration — and 3 out of 5 on actionability. **It marks us down.**
   We left that in the README."*

### Beat 3 — the finding (2:00–3:00)

**Say:** *"Our agent writes down how sure it is on every case. We checked whether that
meant anything. It's backwards."*

| it said | cases | actually right |
|---|---|---|
| High confidence | 21 | **0.103** |
| Low confidence | 34 | **0.331** |

*"Three times worse when it's confident. Permutation test, p = 0.006."*

> **Why.** "High confidence" is awarded for a **clean picture** — one stove clearly
> hottest, nothing moving before it. But a clean picture is *also* exactly what you see
> when **the fire is somewhere a thermometer can't reach.** A quarter of the real causes
> in this data are network faults, which live on the order tickets. We were reading
> thermometers.

**The line to land:** *"A confidence score measured inside one instrument cannot detect
the failure 'we are using the wrong instrument.' A blind spot and a clean result are the
same reading."*

**Why it matters:** *"The standard design escalates low-confidence cases to a human. On
our agent that would have handed people the work it already got right, and auto-approved
the mistakes. Backwards, silently, in the expensive direction."*

### Beat 4 — the honesty close (3:00–4:00)

Three things, fast:

1. **"We tested the AI twice and it changed nothing."** Given our ranked list, GLM-5.2
   with reasoning on changed **0 of 20 answers**. We fixed the list so it held the answer
   96% of the time instead of 54%, re-ran, and it changed **0 of 20 again**. It anchors
   on our ordering. So the judged run ships with **no model**, and the model does the one
   job with no deterministic scorer — grading our evidence.
2. **"Two of our own findings didn't survive our own statistics."** Per-case scores have
   a standard deviation of 0.3; we were chasing 0.03. We ran a paired bootstrap, two
   claims came back with confidence intervals spanning zero, and we **retracted them.**
3. **"A third of our score rides on a hand-written keyword map."** If the judged
   deployment names its sensors differently, that third degrades. We're naming it rather
   than letting you find it.

**Close:** *"Three of our four findings are negative and one is a retraction of our own
claim. On a problem where the best published attempt solves one case in nine, a team
reporting only wins is a team that didn't look. These are the findings we'd want in the
room at 3am, when something is actually broken."*

---

## Does this hit the judging criteria?

The panel rubric is **Technical Execution 40 · Innovation 30 · Impact 20 · Presentation
10**, with the Track 1 focus (accuracy, explainability, evaluation strength, token usage)
applied inside them.

| Criterion | Where the talk earns it |
|---|---|
| **Technical Execution 40%** | Beat 1's number with its provenance; Beat 2 running live, not a recording; every claim reproducible by a named `make` target |
| **Innovation 30%** | Beat 3 — a measured, significant calibration inversion with a mechanism, plus a gate that fails the build when the agent's prose contradicts its own config |
| **Impact 20%** | Beat 3's closing line — it transfers to any system that rates its own certainty, not just to incident response |
| **Presentation 10%** | One story throughout, a live demo instead of screenshots, every technical term introduced by its plain-language twin |
| *focus:* accuracy | 0.199 vs 0.073, stated with the held-out caveat |
| *focus:* **explainability** | Beat 2 is entirely this — and worth more than accuracy in this track |
| *focus:* **evaluation strength** | Beat 4.2, the retraction. This is our strongest dimension. |
| *focus:* token usage | Beat 2 — 0 tokens, $0.00, said out loud while it runs |

**The two questions to expect, and the answers:**

> *"Why is there no LLM in the judged run — this is the routing track?"*
> Because we measured it twice under opposite conditions and it changed 0 of 20 answers
> both times, while costing 41% of the wall clock. The harness is in the repo, switchable,
> and the comparison reproduces with `make compare`.

> *"How will this do on the held-out deployment?"*
> Worse than 0.199. We tuned constants while looking at all 70 cases — that's leakage and
> we name it in the report. Two thirds of the answer rests on a per-case statistic with
> nothing learned across cases; one third rests on a keyword map that could degrade.

---

## One-sentence version, if you only get 30 seconds

> *"We built an agent that finds why a system broke — and the thing we're proudest of is
> discovering that its own confidence runs backwards, which means the human-in-the-loop
> design everyone ships would have escalated exactly the wrong cases."*
