---
name: jev-design
description: Turn a decision into a Jev (TypeSafe System One) question set that actually works — pick the primitive (choice / score / noul), design the state, write criteria the way the model needs them (concrete situations, boundary cases, a who-we-are preamble, an escape option), decompose fuzzy judgments into narrow ones combined in code, and emit questions.json + a derive() + a gold-set stub ready for jev-eval. Encodes the rules learned from real evals (criteria text alone moved accuracy 70%→90%). USE WHEN user says "jev-design", "write the Jev questions", "design a question set", "set up Jev for this", "criteria for Jev", "turn this classifier into Jev", "decompose this decision for Jev", or after jev-fit picked a candidate. Produces artifacts; does not run the eval (that's jev-eval).
---

# jev-design

Author the question set. The text you write here *is* the product — in our evals a bare
2-way choice scored 70%, one sentence of criteria per option scored 88%, and concrete
situations + boundary cases + a who-we-are preamble scored 90% with perfect recall on the
class we cared about. Nothing else you do will move the number that much.

## Inputs to collect (ask if missing)

1. **The decision**, in one sentence, and **who acts on the answer** (code path, human, LLM).
2. **The answer space** — the labels / levels / yes-no, and what each *means for this user*.
3. **What the state will contain at runtime** — exactly which fields exist at the moment of the
   decision (not what you wish you had).
4. **5–10 real examples**, including the ones people argue about. These become the boundary
   cases in the criteria and the seed of the gold set.
5. **The consequence of a wrong answer** — sets the gate and whether an escape option is needed.

## Entering from `/jev-fit` (don't re-ask what the audit already established)

If a jev-fit report exists for this target, **derive the five inputs from it and the code**
before asking anything: the decision + who acts on it (from the opportunity row), the answer
space (from the enumerated labels in the prompt / enum column / branch names), the state (the
fields actually available at that call site — read the code), the stakes (from the Risks column),
and 5–10 real examples (from fixtures, logs, seed data, or the DB). Then present **one**
AskUserQuestion: "Here's what I derived — confirm, or tell me what's wrong" with the five items
listed. Only fall back to the five-step wizard for items you genuinely couldn't derive.

## Procedure

1. **Pick the primitive** (`references/criteria-rules.md` §1):
   - one label from an unordered set → `choice` (≤255 options; add `other`/`unclear` unless coverage is complete)
   - ordered levels / severity / relevance → `score` (2–10 *concrete* levels, low→high)
   - a proposition → `noul` (returns P(yes); no confidence field — threshold with a dead band)
   - *several* of these on the same state → send them all in one request (parallel, ~free).
2. **Decide single vs decomposed.** If humans disagree on the top-level label, do **not** ask it
   directly. Ask 4–8 narrow questions whose answers people *would* agree on, and map to the label
   in `derive()`. If the label is crisp, one rich `choice` wins (and is cheaper to maintain).
3. **Design the state** (§2): only fields the question needs; JSON object with named fields;
   reference them in instructions with backticks (`` `title` ``); pre-compute facts in code
   (platform from URL, day-of-week from date, counts); strip boilerplate. Small beats complete.
4. **Write the `WHO` preamble** (§3): 2–4 sentences on who is asking and what the labels mean
   for them. Put it at the front of `instructions`.
5. **Write the criteria** (§4): for every option, concrete situations, the borderline case and
   which way it goes, and a negative ("a meme about AI is personal"). Align instructions and
   criteria — never contradict. No double negatives, no "unless", no numbers to compare.
6. **Add the escape** if the consequence warrants: an `unclear` option (Jev uses it honestly —
   in our test 13 of 14 `unclear`s were the genuinely ambiguous rows).
7. **Write `derive()`** — code owns the final decision and the gating confidence. For `choice`
   use `confidence`; for `noul` derive one (`abs(p-0.5)*2`) or gate on the value with a dead band.
8. **Emit the artifacts** (below) and hand off to `jev-eval`. Keep v0 (your naive first draft)
   as a variant — it's the baseline that shows what the criteria bought.

## Artifacts to produce

```
<project>/jev/<decision-name>/
  questions.json        # the v-current question set (what production sends)
  task.py               # VARIANTS (v0 naive, v1 rich, v2 decomposed…) + STATE() + derive()  — from templates/task_template.py
  gold.jsonl            # ONLY if human decisions already exist (export them); else omit — see below
  candidates.jsonl      # the common case: ≥100 REAL rows, UNLABELED ({"id", "state"}), pulled from
                        #   logs / DB / fixtures / exports — the input to /jev-label
  DESIGN.md             # the decision, answer space, WHO, state fields, gate consequence, open questions
```

`${CLAUDE_PLUGIN_ROOT}/templates/task_template.py` is the starting point for `task.py`.

**Labels come from humans, never from you or the model.** In a fresh project there usually *are*
no labels yet — that's normal. Emit `candidates.jsonl` (real rows, production-shaped state, no
labels) and say: "next is `/jev-label` — you (or someone who makes this call today) label ~100 of
these blind; then `/jev-eval`." Put the 5–10 examples the person gave you in `DESIGN.md` as the
seed boundary cases; don't pretend they're a gold set. If human decisions *do* exist (a triaged
column, last month's routed items), export them with `jev_label.py import` into `gold.jsonl`.

**Write JSON/JSONL with LF newlines** (`open(..., newline="
")` / `write_text(..., newline="
")`)
so Windows doesn't turn every artifact into a CRLF diff.

**Smoke test before handing off** (12 rows, ~100 ms each, under a cent):

```python
import sys; sys.path.insert(0, "<CLAUDE_PLUGIN_ROOT>/scripts")   # or copy jev_client.py next to task.py
from jev_client import Jev                                       # the class is `Jev` (not JevClient)
import json; Q = json.load(open("jev/<decision>/questions.json", encoding="utf-8"))
r = Jev().ask(state, Q); r.answers, r.model, r.latency_s, r.cost_usd
```

or `python "${CLAUDE_PLUGIN_ROOT}/scripts/jev_client.py" ask --state-file row.json --questions jev/<decision>/questions.json`.
Look for: confidence *low on the rows a human would argue about* and high on the clear ones. If
it's confidently wrong on a clear one, a criteria line is missing — fix it now, before labeling.

## Quick rules (the ones that moved numbers)

| Do | Because |
|---|---|
| Write criteria as *situations*, not adjectives ("Blocking; no workaround" not "severe") | literal reader; adjectives are interpreted, situations are matched |
| Put the borderline case in the criteria and say which way it goes | every miss you "explain" is a missing line |
| Add a `WHO` preamble | closed a 10-point recall gap in our test |
| Include URL/platform/channel-type fields when available | +3 points; cheap context |
| Keep the state small | accuracy falls with irrelevant detail (documented context rot) |
| Ask one thing per question | hidden multi-judgments answer the wrong half |
| Pre-compute numbers, dates, counts in code | not a calculator; not a calendar |
| Keep `other`/`unclear` when coverage is incomplete | otherwise it forces a wrong label confidently |
| Don't rely on P(noul) == 1 − P(not noul), or noul thresholds on a choice | structural invariants aren't guaranteed |
| Pin `jev-1.13.0` once thresholds are tuned | aliases move |

Full rules with examples: `references/criteria-rules.md`. Patterns with code: `references/patterns.md`.


## Guided mode (default when the person is new or non-technical)

Mode is set by `/customs` and persists. In guided mode, run the five inputs as a **wizard, one
AskUserQuestion at a time**, and say *why* before each:

| Step | Ask | Why (say it) |
|---|---|---|
| 1 decision | "In one sentence: what's the question, and who acts on the answer?" | "Everything else follows from this; if it takes two sentences it's probably two questions." |
| 2 answers | "What are the possible answers? What does each one mean *for you*?" | "Jev takes your words literally. 'Urgent' means nothing; 'a customer can't log in' means something." |
| 3 state | "At the moment this decision is made, what does your system actually have in hand?" | "We can only send what exists. Sending more than needed makes it *worse*, not better." |
| 4 examples | "Give me 5–10 real ones — especially the ones you'd argue about." | "The arguable ones become sentences in the criteria. Every miss we'd 'explain' later is a missing line now." |
| 5 stakes | "What happens if it's wrong?" | "That sets how sure Jev must be before your software acts without a person." |

Then **show your work in plain words** before emitting files: the primitive you picked and why
("this is 'which one of these' → choice"), whether you split the question ("people would argue
about the label but not about these four smaller questions"), the WHO preamble read aloud, and
each option's criteria as a short paragraph they can correct. Ask "does this sound like how you'd
explain it to a new assistant?" — if they change a word, that's the product improving.

Emit the artifacts, then say what happens next in one line: "Now we check it against your
answer key — `/jev-label` if you don't have one yet, `/jev-eval` if you do."

Gloss terms from `docs/GLOSSARY.md` the first time they appear (state, criteria, gate, confidence).

## Expert mode

Collect the five inputs in one message (they'll usually paste them). Emit the four artifacts and
the v0/v1/v2 ladder without commentary; link `references/criteria-rules.md` instead of
explaining. Flag only violations of the quick-rules table.
