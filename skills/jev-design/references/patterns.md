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
