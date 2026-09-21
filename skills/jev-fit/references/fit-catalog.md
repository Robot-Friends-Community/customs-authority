# jev-fit catalog — decision families and their Jev shapes

For each family: the shape to recommend, what code should pre-compute, the gate/fallback need,
and what makes the labels crisp or fuzzy. Numbers cited are from Customs Authority's own evals
(`examples/linkdrop`) and TypeSafe's docs (2026-09).

## 1. Intent routing (inbox, tickets, chat, forms)
- **Shape:** one `choice` over intents (+ `other`/`unclear`) **fanned out** with `noul`s that
  matter for the route (needs_human, is_urgent, mentions_refund…) and a `score` for urgency —
  all in one call (they run in parallel; ~free).
- **Gate:** yes. `choice.confidence ≥ 0.8` → deterministic handler; else LLM or human.
- **Code first:** strip signatures/quoted history, pull known IDs, detect language.
- **Crispness:** high when intents are operational (order status / quote / complaint); fuzzy when
  intents overlap ("feedback" vs "complaint") — merge or add boundary cases.
- **Risk:** adversarial senders. Write criteria for the manipulation you expect; test it.

## 2. Priority / at-risk / needs-attention flags (boards, CRMs, queues)
- **Shape:** `score` with 3–5 *concrete* levels ("Blocking; no workaround exists") + `noul`s per
  flag. Re-run on every edit — that's the new capability.
- **Gate:** threshold the score in code; show probability to the operator.
- **Code first:** due-date math, SLA arithmetic, amount thresholds. Jev never compares dates.

## 3. Lead / candidate / vendor scoring
- **Shape:** composite — 4–8 atomic `score`s (fit, urgency, budget signal, authority, …),
  normalized by `len(levels)-1`, weighted in code (their *composite scoring* pattern). Never one
  "overall score" question.
- **Gate:** none needed for ranking; gate the *action* (auto-outreach) on the top factor's confidence.
- **Crispness:** each atomic factor is crisp; the composite weights are yours to tune and defend.

## 4. Content / link / item triage into queues
- **Shape:** `choice` over queues with rich criteria + `WHO` preamble (what the queues mean *for
  you*). If the queues are fuzzy even to humans, decompose: narrow `noul`s/`score`s → code maps.
- **Gate:** yes; `unclear` option as the human lane.
- **Evidence:** 2-way work/personal on title+URL: bare 70% → one-line criteria 88% → rich 90%;
  Jev@0.85 + Sonnet fallback = 95.4% (Sonnet alone 96.3%) with 64% fewer LLM calls.
  6-way build/signal/learning/… on fuzzy human labels: Jev 51% ≈ Haiku 49% ≈ majority 48% —
  the labels were the ceiling. Fix the taxonomy before blaming the model.

## 5. Sentiment / tone / escalation on reviews and messages
- **Shape:** `score` (calm → civil-frustrated → angry) + `noul` needs_reply + `noul` escalate.
- **Gate:** escalate when `noul ≥ 0.7`; draft replies with an LLM only for those.

## 6. Guardrails on LLM output (pre-send checks)
- **Shape:** `noul`s: on_topic, safe_to_send, mentions_competitor, promises_something, tone_ok.
  Absolute yes/no per check; no confidence field on nouls — threshold the value, keep a dead band
  (≤0.2 no / ≥0.8 yes / middle → review).
- **Not for:** judging whether the LLM's *reasoning* is correct.

## 7. Extraction-as-choice (dates, entities, fields)
- **Shape:** code or an LLM proposes candidates; Jev picks (`choice` over candidates + `not_stated`).
  Dates: month/day/year as three `choice`s over enumerated values, assembled in code.
- **Never:** ask Jev to generate the value.

## 8. Relevance filtering / RAG passage selection / map-reduce over a corpus
- **Shape:** one `noul` "does this passage answer X?" per chunk; thousands of calls are fine
  (1,200 req/min, 250k tok/s). Then feed only the yeses to the LLM.
- **Win:** the LLM's context shrinks; accuracy goes up, cost goes down.

## 9. Real-time / as-you-type UX (forms, generative UI, games)
- **Shape:** whatever the decision is, re-asked per keystroke/state change; show probabilities.
- **Constraint:** server-side key → a tiny proxy with rate limiting for public tools.

## 10. Verification / QA of structured facts
- **Shape:** `noul` per claim against provided evidence in `state` ("Does `evidence` support
  `claim`?"). Works when evidence is *in the state*; not for open-world fact checking.

## Anti-catalog (recommend against)
| Looks like a fit | Why it isn't | Instead |
|---|---|---|
| "Summarize then classify" | generation | LLM summary → Jev classify, or classify raw text |
| "Is this code correct?" | reasoning | LLM / tests |
| "Which of these two essays is better?" | taste + reasoning | LLM judge with rubric |
| "How many complaints in this thread?" | counting | one noul per message, sum in code |
| "Is the deadline within 30 days?" | date math | extract in Jev, compare in code |
| "Detect prompt injection in this user text" | adversarial by definition | dedicated classifier + criteria + tests; don't rely on Jev alone |
