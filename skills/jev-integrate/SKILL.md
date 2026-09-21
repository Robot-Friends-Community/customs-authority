---
name: jev-integrate
description: Wire an evaluated Jev (TypeSafe System One) question set into a real application — key setup (env + secrets manager, never in the browser), the thin Python or TypeScript client, the gated Jev-plus-LLM/human hybrid, a rate-limited proxy route for public tools, logging of model/usage/confidence/source, model-version pinning, and a pre-ship checklist. USE WHEN user says "jev-integrate", "wire Jev into the app", "add Jev to this codebase", "ship the Jev router", "Jev in Next.js", "Jev in Python", "set up the TypeSafe key", "hybrid Jev fallback", "put Jev behind an API route", or after jev-eval picked a gate. Assumes a scoreboard exists; if not, stop and run jev-eval first.
---

# jev-integrate

Ship the hybrid, not the model. Every integration is: **an evaluated `questions.json`, a gate
from the scoreboard, a fallback, and logging** — in that order of importance.

## 0. Preconditions (check, don't assume)

- `runs/SCOREBOARD.md` exists for this question set and a gate was chosen → else `/jev-eval`.
- `questions.json` is the chosen variant, verbatim. Production never builds questions from user input.
- Key: `TYPESAFE_API_KEY` from https://console.typesafe.ai/keys, stored in the team's secrets
  manager (1Password / Vaultwarden / Infisical / the host's env), set as an env var on the
  server. **Never** in client-side code, `NEXT_PUBLIC_*`, or a repo.
- Model pinned: `TYPESAFE_MODEL=jev-1.13.0` (or the version the gate was tuned on).

## 1. Drop in the client

| Stack | File | Notes |
|---|---|---|
| Python | `${CLAUDE_PLUGIN_ROOT}/scripts/jev_client.py` → copy to `app/jev_client.py` | `httpx` only; `Jev().ask()`, `Jev().decide()` (gated hybrid), retries on 429/529 honoring `retry-after` |
| TypeScript / Next.js | `${CLAUDE_PLUGIN_ROOT}/templates/jev.ts` → `lib/jev.ts` | zero deps, typed answers, `ask()` + `decide()` |
| Official SDKs | `pip install typesafe-sdk` / `npm i @typesafe-ai/sdk` | fine too; same request shape; note the Python SDK hardcodes `/v1/systemone` |

## 2. Wire the hybrid

`${CLAUDE_PLUGIN_ROOT}/templates/hybrid_router.py` is the reference shape:

```python
label, conf, source = jev.decide(state, QUESTIONS, key="bucket", gate=GATE, fallback=llm_decide, unclear_option="unclear")
```

- `key` must be a `choice` or `score` (they carry `confidence`; nouls don't).
- `fallback` is your LLM call *with the same criteria text*, or a human queue. It must exist —
  a gate without a fallback is just a worse classifier.
- Return `source` to the caller/UI. "Jev decided" vs "escalated" is information.

## 3. Public tools → proxy + limits

Jev's key is server-side, so a free public tool needs a small route:
`${CLAUDE_PLUGIN_ROOT}/templates/nextjs-route.ts` — caps state length, rate-limits by IP,
returns only what the UI needs, hides upstream errors. Keep the questions server-side; the
browser sends *state*, never questions. Add a spend cap on the host and watch the first week.

## 4. Logging (non-negotiable)

Per call: `model` (from the response, not your config — aliases move), `usage.input_tokens`,
the gating confidence, the chosen label, `source` (`jev` / `fallback`), latency. Weekly: the
confidence histogram. Drift shows up here before it shows up in complaints.

## 5. Pre-ship checklist

- [ ] scoreboard exists; gate chosen from the coverage→accuracy curve; hybrid number recorded
- [ ] `questions.json` = evaluated variant, checked in and versioned; `WHO` preamble present
- [ ] state built in code: only needed fields; numbers/dates/counts pre-computed; user text length-capped
- [ ] adversarial pass: 10 hostile inputs (injected instructions, text arguing for its own label) — behavior acceptable or routed to fallback
- [ ] non-English inputs either tested or routed to fallback by a language check in code
- [ ] key in secrets manager + server env only; model pinned; retries on 429/529
- [ ] fallback implemented and exercised; `unclear` (if any) routes to it
- [ ] logging of model/usage/confidence/source; alert on `model` change
- [ ] public route: state cap, rate limit, spend cap on host
- [ ] a cron or hook re-runs `/jev-eval` when `model` changes or gold grows

## 6. Where it usually lands (patterns)

Inbox/ticket intent router in front of an assistant · priority/at-risk flags on a board,
re-scored on edit · lead/candidate composite scoring · review sentiment + escalation ·
relevance filter before RAG · guardrail nouls before an LLM reply is sent · as-you-type
qualification in a form. Shapes and code in `jev-design/references/patterns.md`.
