---
name: jev-fit
description: Audit a project, pipeline, codebase, prompt chain, n8n workflow, product spec, or plain-English process for steps where TypeSafe's Jev (a "System One" decision model) is the right tool — narrow judgment over text with a bounded answer that today goes to an LLM call or a human. Three-way triage of every step (code / Jev / LLM), names the Jev shape (choice / score / noul, fan-out, gate), estimates the win, and outputs a prioritized opportunities report with a recommended first pilot. USE WHEN user says "jev-fit", "where would Jev fit", "assess for Jev", "should we use Jev here", "System One opportunities", "decision layer audit", "which LLM calls could be Jev", "find classification/routing/scoring steps", or asks whether a project could use Jev. Sibling of algo-lens (which offloads CLERICAL work to code); jev-fit covers the JUDGMENT steps that are System-1. DIAGNOSE + RECOMMEND ONLY — hand off to jev-design to build the question set.
---

# jev-fit

Find the steps in a system where a small, fast, calibrated judgment over text is being bought
at LLM prices (or a human's attention) — and where Jev would do it in 100 ms for ~nothing,
*with a confidence number your code can act on*. Diagnose and rank. Don't build.

## Core model — three clerks

| Worker | Good at | Cost / latency | Hand it |
|---|---|---|---|
| **Code / algorithm** | rules you can write in one sentence; counting, matching, math, dates | free / µs | clerical work (→ `algo-lens`) |
| **Jev (System One)** | *common-sense judgment over text with a bounded answer*: classify, route, score, flag, rank, verify, pick-from-candidates | $0.042/M input tokens, output free / 70–500 ms | narrow judgments at volume |
| **LLM (System Two)** | reasoning, multi-hop, generation, taste, explanation, long context | $ / seconds | everything that needs thought or words |

The single question for every step: **is this a judgment that could be written as a
multiple-choice question with good criteria?** If yes, it's a Jev candidate. If it needs an
essay, a chain of thought, or new text — it stays on the LLM. If it's a rule — it's code.

## Procedure

1. **Read the target** (see *Reading each target*). Inventory every step that takes text in and
   produces a decision out: each LLM call, each "the assistant decides…", each manual triage,
   each `if`-on-meaning, each workflow branch, each score/priority/flag field.
   - **Coverage rule:** a prompt that enumerates N categories or N checks hides N candidate
     questions. Evaluate each branch/bucket separately.
2. **Triage each step** with the decision tree below → `CODE` / `JEV` / `LLM` / `MIXED`
   (split MIXED into its parts).
3. **For each `JEV` step, name the shape** — see `references/fit-catalog.md`:
   primitive(s) (`choice` / `score` / `noul`), fan-out vs single question, whether a gate +
   fallback is needed, what the state should contain (and what to strip), what code computes
   first (dates, counts, IDs).
4. **Estimate the win** honestly: calls/day × (LLM cost − Jev cost), latency (seconds → ~100 ms),
   *and* the new capability — decisions that were too expensive to make at all (every row, every
   keystroke, every message), plus a calibrated confidence for escalation. Say when the win is
   marginal.
5. **Flag risks** per step: adversarial input (public forms, stranger email), non-English,
   numeric/date logic hiding inside, label fuzziness (will humans agree?), need for explanation.
6. **Rank and report** (contract below). Order by frequency × cost-per-call × label crispness.
   Recommend **one first pilot** — the crispest, highest-volume, internal-facing candidate.

## Decision tree (per step)

1. Can the rule be written in one sentence with no interpretation? → **CODE**.
2. Does the answer need *new text*, an explanation, or a plan? → **LLM**.
3. Does it need multiple hops, comparison across long documents, or arithmetic/date logic? → **LLM** (or split: extract with Jev, compute in code).
4. Is it a judgment over text whose answer is one of a bounded set (label, level, yes/no, pick-from-list ≤255)? → **JEV**.
5. Is it "which of these candidates is right?" after code/LLM produced candidates? → **JEV** (extraction-as-choice).
6. Is it a check on an LLM's own output (on-topic? safe to send? matches schema intent?) → **JEV** guardrail — *unless* judging quality/correctness of reasoning, which is **LLM**.
7. Does it need taste, brand fit, or persuasion? → **LLM** (or human).

Rules of thumb: *"Could a sharp new assistant answer this in two seconds with a checklist?" → Jev.*
*"Would they need to think about it?" → LLM.* Where humans disagree with each other on the
label, Jev will match them about as well as an LLM does — the label is the ceiling, not the model.

## Reading each target

- **Code (Python/TS/…):** grep for LLM SDK calls (`anthropic`, `openai`, `messages.create`,
  `generateText`, `chat.completions`), prompt strings with enumerated labels, `classify`, `route`,
  `score`, `priority`, `triage`, `sentiment`, `intent`, `is_*` booleans set from model output.
- **Prompt chains / agents / skills:** every "decide / classify / choose / rate / flag / route"
  instruction; every enumerated option list in a prompt.
- **n8n / workflow JSON:** every AI node feeding an IF/Switch; every Switch on free text.
- **Product spec / process description:** every place a person "checks", "sorts", "flags",
  "prioritizes", "decides which", "reviews for".
- **Databases / boards:** enum columns and status fields set by hand (`priority`, `category`,
  `stage`, `at_risk`) — each is a candidate question.

## Output contract

```
# jev-fit report — <target>  (<date>)

## Summary
<2–3 sentences: how many steps, how many JEV candidates, the headline win, the first pilot>

## Opportunities (ranked)
| # | Step | Today | Verdict | Jev shape | Win | Risks |
|---|------|-------|---------|-----------|-----|-------|
| 1 | <where + what decision> | LLM call / human | JEV | choice{...} + noul, gate 0.85 → LLM | <calls/day, $/mo saved, latency, new capability> | <adversarial / fuzzy labels / numeric> |

## Keep on the LLM
- <step> — <why: reasoning / generation / taste>

## Hand to code (algo-lens)
- <step> — <the rule>

## First pilot
<one candidate; why it's first (crisp labels, volume, internal-facing); the gold set you'd build
(source of ~100 labeled rows); success criterion (e.g. ≥60% coverage at ≥97% accuracy at the gate)>

## Next
→ /jev-design for the question set · /jev-eval to score it · /jev-integrate to ship the hybrid
```

## Anti-fits (say them out loud)

Creative direction, critique, naming; judging the *quality* of LLM output or code; research
claim verification; anything numeric/date/counting; multi-hop conditions; text generation;
adversarial public input without criteria + edge-case tests; non-English without a test. See
`jev-playbook` for the full list and the model's documented failure modes.


## Guided mode (default when the person is new or non-technical)

Mode is set by `/customs` (guided / expert) and persists for the session. In guided mode:

1. **Say what you're about to do and why**, before reading anything: "I'm going to list every
   place in this project where something makes a decision about text — a category, a priority, a
   yes/no. Then I'll sort each one into three piles: things a rule can do, things Jev can do, and
   things that need a big model. You'll get a ranked list and one recommendation to start with."
2. **Ask for the target with one AskUserQuestion** if it isn't obvious: a codebase here · a
   workflow (n8n / Zapier JSON) · a process you'd describe in words · a prompt or skill.
   For "describe it in words": ask them to narrate one item's journey through the system ("an
   email arrives, then what happens?") — every "then someone checks / decides / sorts" is a step.
3. **Show the three piles in plain words** before the table: *rule* ("if the subject contains
   'invoice'"), *judgment* ("is this a complaint or a question?"), *thinking* ("write the reply").
4. **For each JEV candidate say the win in their units** — "you make this call ~200 times a day;
   Jev does it in a tenth of a second for a fraction of a cent, and tells you when it isn't sure so
   a person can look" — and the risk in their units ("customers could word things to game it").
5. **Recommend one pilot and say why in one sentence** (crisp labels, volume, internal-facing).
   Then offer the next step with AskUserQuestion: build the answer key (`/jev-label`) · write the
   questions (`/jev-design`) · show me on the example first (`/customs tutorial`).
6. Add a **plain-English column** to the opportunities table in guided mode: `What it means` —
   one sentence a non-engineer can act on.

## Expert mode

Skip the narration; deliver the report in the output contract and stop. Assume `algo-lens`
vocabulary. Name the pilot and the gold-set source in one line each.
