---
name: jev-playbook
description: The reference brief on Jev, TypeSafe AI's "System One" decision model — what it is (non-autoregressive, RLCD-trained, returns typed calibrated decisions instead of text), what it costs and how fast it is, the three primitives, when to use it and when not to, its documented failure modes, how it compares to an LLM and to plain code, and how to get a key. USE WHEN user says "what is Jev", "explain Jev", "System One model", "TypeSafe", "should we use Jev", "Jev vs LLM", "Jev pricing", "Jev limits", "how do I get a Jev key", or needs the background before jev-fit / jev-design. Read-only knowledge; no artifacts.
---

# jev-playbook

## What Jev is (one paragraph)

Jev is TypeSafe AI's first **System One** model (Kahneman's fast, intuitive judgment — vs
System Two deliberate reasoning). It is **not an LLM**: it doesn't generate text. You send
**state** (text: a string, a JSON object, or an array) plus a set of **typed questions**, and it
returns every answer **in parallel** as a typed value with **calibrated probabilities** — a
`choice` from options you defined, a `score` on levels you defined, or a `noul` (P(yes)).
It's trained with **RLCD** (Reinforcement Learning for Calibrated Decisions), which optimizes
for honest probabilities rather than human preference (RLHF) or verifiable rewards (RLVR).
Think: *a smart if-statement* — programmable common sense at a decision point in your code,
with a confidence number your code can act on.

## Numbers (2026-09, `jev-1.13.0`)

| | |
|---|---|
| Price | **$0.042 per million input tokens; output tokens free** (≈40–1,000× cheaper than LLMs) |
| Latency | **70–500 ms** (we measured p50 ≈ 110–125 ms on ~350-token requests) |
| Rate limits | 250k tokens/s, 1,200 requests/min (dynamic; enterprise higher) |
| Context | 64k per request; 32k for state + the longest question |
| Input | text only (string / JSON / array); English best, other languages handled but test |
| Endpoint | `POST https://api.typesafe.ai/v1/systemone`, `Authorization: Bearer $TYPESAFE_API_KEY` |
| Models | `jev-1.13.0`; aliases `jev-latest`, `jev-preview` (pin the version once thresholds are tuned) |
| Also via | OpenRouter `typesafe/jev-1.13` at `POST /api/alpha/decisions` (same body) |
| Data | not trained on customer data; ZDR for enterprise; no fine-tuning — you shape it through state + criteria |
| Key | https://console.typesafe.ai/keys (Google sign-in; org-scoped keys; playground included) |

## The three primitives

```json
{"state": {"message": "I was charged twice. Fix this today."},
 "model": "jev-1.13.0",
 "questions": {
   "department": {"type": "choice", "instructions": "Which team handles this?",
                  "criteria": {"billing": "Charges, refunds, invoices", "technical": "Bugs, integrations", "other": null}},
   "urgency":    {"type": "score",  "instructions": "How urgent?", "criteria": ["Can wait", "This week", "Today"]},
   "wants_refund": {"type": "noul", "instructions": "Does `message` ask for money back?"}
 }}
```
→ `department.choice/confidence/probabilities`, `urgency.score/confidence/legend/probabilities`, `wants_refund.noul`.

## When to use it — and when not

| Use Jev for | Keep the LLM for | Use code for |
|---|---|---|
| classify, route, score, rank, flag, verify-against-evidence, pick-from-candidates, relevance filter, guardrail checks, as-you-type UX | reasoning, multi-hop, explanation, generation, taste, judging quality of LLM/code output, open-world fact checking | anything you can state as a rule; counting; math; dates; IDs |

**Documented failure modes (jev-1.13):** literal reading · math/counting · date/time comparison ·
indirection & double negatives · large irrelevant state · adversarial content · contradictory
instructions vs criteria · structural invariants not guaranteed (P(a)+P(¬a)≠1; noul ≠ yes/no
choice) · generation. Each has a "do this instead" in `jev-design/references/criteria-rules.md`.

## What we measured (Customs Authority evals)

- **Speed and cost claims hold.** ~120 ms, ≈$0.003 for a 108-row run, on every variant.
- **Criteria text is the lever.** Same binary task: bare 70% → one-line criteria 88% → rich 90%.
- **Confidence is real.** ≥0.8 bucket ≈ 99% right; 0.2–0.4 bucket ≈ 35%. Gates work.
- **Hybrid wins.** Jev@0.85 + Sonnet fallback = 95.4% vs Sonnet alone 96.3%, with 64% fewer LLM calls.
- **Labels can be the ceiling.** On a fuzzy 6-way taxonomy, Jev 51% ≈ Haiku 49% ≈ majority 48%. Fix the taxonomy first.

## The pitch, if you sell builds

"A calibrated decision layer under your LLM features: 100× cheaper, 100× faster, and it tells
you when it isn't sure — so the expensive model or a human only sees the hard cases."

## The kit

`/jev-fit` find where it fits → `/jev-design` write the questions → `/jev-eval` score them and
pick the gate → `/jev-integrate` ship the hybrid. Docs: https://docs.typesafe.ai/llms.txt
(every page also serves as `.md`). TypeSafe's own Claude Code skill:
`claude plugin marketplace add typesafe-ai/skills && claude plugin install typesafe@typesafe-ai`
(docs-reading guidance; complements this kit).
