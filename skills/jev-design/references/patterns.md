# patterns — architectural shapes for building with Jev (with code)

Condensed from TypeSafe's patterns docs + Customs Authority evals. Code is Python against the raw
response shape (`answers[id]`); the same applies to `jev_client.Result.answers`.

## A. Speculative fan-out — ask everything you *might* need, in one call
Use when one state has several possible code paths and some questions only matter on some paths.
Questions run in parallel; unused answers cost only their tokens.

```python
a = jev.ask(state, {
  "category":   {"type": "choice", "instructions": "...", "criteria": {...}},
  "severity":   {"type": "score",  "instructions": "...", "criteria": [...]},
  "has_repro":  {"type": "noul",   "instructions": "Does `body` include steps to reproduce?"},
  "wants_refund": {"type": "noul", "instructions": "Does `body` ask for money back?"},
}).answers
if a["category"]["choice"] == "bug":
    if a["severity"]["score"] > 1.5 and a["has_repro"]["noul"] > 0.6: escalate()
    else: backlog()
elif a["category"]["choice"] == "billing":
    billing(flag_refund=a["wants_refund"]["noul"] > 0.7)
```

## B. Confidence-gated routing — answer + "safe enough?"
```python
c = a["intent"]
if c["confidence"] < GATE:            # pick GATE from the coverage→accuracy curve
    return llm_or_human(state)
if c["choice"] == "approve_transfer" and c["confidence"] < 0.9:
    return ask_user_to_confirm()
return handlers[c["choice"]](state)
```
`jev_client.Jev.decide()` implements this with an optional `unclear` option.

## C. Composite scoring — atomic scores, weights in code
```python
def norm(ans, key, levels): return ans[key]["score"] / (levels - 1)
fit   = norm(a, "icp_fit", 4); urgency = norm(a, "urgency", 3); budget = norm(a, "budget_signal", 3)
lead_score = 0.5 * fit + 0.3 * urgency + 0.2 * budget     # defensible, tunable, auditable
```
Never ask for one "overall score" — you can't tune or explain it.

## D. Intent routing — Jev in front of expensive workers
```python
i = a["intent"]
if i["confidence"] < 0.5: return human(ticket)
if i["choice"] == "order_status": return deterministic_lookup(ticket)      # code
if i["choice"] == "product_question": return llm(ticket, PRODUCT_SPECIALIST)  # LLM only here
if i["choice"] == "complaint" and (a["complexity"]["score"] > 1 or a["complexity"]["confidence"] < 0.5): return human(ticket)
```

## E. Extraction-as-choice
Code/regex/LLM proposes candidates → Jev picks (`choice` over candidates + `not_stated`).
Dates: three choices (month, day, year) over enumerated values → `datetime` in code.

## F. Relevance filter before RAG / map-reduce
One `noul` per chunk ("Does `chunk` help answer `question`?"), keep ≥0.6, then the LLM sees
only relevant chunks. Thousands of calls are fine (1,200 req/min).

## G. Guardrail before send
`noul`s on the LLM draft: on_topic, safe_to_send, makes_promise, mentions_competitor. Dead band:
≤0.2 pass, ≥0.8 block, middle → review. Not a judge of reasoning quality.

## H. Real-time / as-you-type
Re-ask on every state change; render probabilities live. Server-side key → proxy with rate
limiting for public tools (`templates/nextjs-route.ts`).

## I. Self-consistency (from the cookbooks)
Jev is deterministic in *format* and highly consistent in *content* for semantically similar
inputs. If you need a stability estimate, sample the same state N times and look at the spread —
cheap with output tokens free. Don't rely on arithmetic identities between separate questions.

## J. Version pinning + logging
Pin `jev-1.13.0` where thresholds were tuned; log `response.model`, `usage.input_tokens`,
confidence and the routed source (`jev` / `fallback`) per call. When an alias moves, re-run
`jev-eval` on the gold set before adopting.

## L. Agentic OS — Jev inside the harness (model routing + skill receptionist)

The two uses the Claude Code community jumped on first. Both are ordinary decisions and get the
ordinary treatment: criteria as situations, a gold set, a scoreboard, a gate.

```python
TIERS = {"tier": {"type": "choice",
    "instructions": f"{WHO} From `task`, which model tier is the cheapest that will do this well?",
    "criteria": {
        "small":  "Mechanical edits with a clear spec: rename, format, one-file fix, write a test for given code, answer from a doc already in context.",
        "medium": "Multi-file changes with a known pattern; summaries of long text; ordinary feature work with tests.",
        "large":  "Design decisions across modules; ambiguous specs; debugging with no repro; anything where a wrong answer costs hours.",
    }}}
tier, conf, source = jev.decide(state={"task": user_msg, "files_mentioned": n}, questions=TIERS,
                                key="tier", gate=0.8, fallback=lambda s: "medium")   # unsure → mid tier, never small
```

**Skill receptionist** — `choice skill` over installed skill names + `none`. With >255 skills, ask
`choice category` first, then `choice skill` within it (two calls, still ~200 ms). Gold set: your own
session history — which skill actually fired for which message. Anti-fit: if picking the skill
requires *reading the repo first*, leave it to the LLM; Jev only sees the message.

**How to wire it in Claude Code:** a `UserPromptSubmit` hook that calls Jev and injects one line
("suggested skill: /x · tier: medium · confidence 0.91") for the model to honour or ignore.
Log `source` and the model's actual choice — that's the next gold set.

## K. Dates, deadlines, and "how soon?" — split the calendar out of the judgment

Jev is not a calendar. "Is this due within 7 days?" mixes a *judgment* (does the text state a
deadline at all, and how firm is it?) with *arithmetic* (deadline − today). Split them:

1. **Code first:** extract explicit dates with a date parser (`dateparser`, `chrono`), compute
   `days_until = (date - today).days`, and put the *result* in the state as a field
   (`"days_until_deadline": 5`). Never make the model count.
2. **Jev on the words:** ask what only the text can tell you —
   - `choice deadline_kind`: `explicit_date` / `relative_soon` ("by Friday", "ASAP", "this week") /
     `event_bound` ("before the trade show") / `not_stated` — with criteria per option;
   - `score urgency_tone` from the language, with concrete rungs;
   - `noul is_firm`: "The customer states the date as a hard requirement, not a preference."
3. **Derive in code:** if `days_until` exists, it wins; else map `relative_soon` to your policy
   buckets; `not_stated` routes to a human question ("when do you need this?") — the honest answer
   for a quote request with no timeline is *ask*, not *guess*.

**Real-world phrase set** (from 116 sales-rep notes in the first pilot — put these in the criteria
as situations, they dominate real data): "later in the year", "in the future", "eventually",
"when we open the second location", "eta 5/1", "budgeted for next fiscal year", "this quarter",
"just looking / comparing", "ASAP", "before the show in March". Each maps to exactly one of
`explicit_date` / `relative_soon` / `event_bound` / `vague_horizon` / `not_stated` — add
`vague_horizon` as its own option when "later / in the future" is common, so it doesn't get
forced into `not_stated` or a bucket.

Keep the `not_stated` escape: in the first real pilot it was what stopped the model from
inventing a timeline from a quote request. Gate on the `choice` confidence as usual.
