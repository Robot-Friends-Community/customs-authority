# FAQ

The questions people ask at the front desk. Short answers; the skill named at the end of
each has the long version.

## Basics

**Is Jev an LLM? Can I chat with it?**
No. It never produces text. You send text + typed questions, it returns answers with
probabilities. If you need a sentence written or a plan made, that's an LLM's job. → `/jev-playbook`

**So what is it good for?**
Every place your software (or a person) makes a small bounded judgment about text: which
category, how urgent, is it on-topic, which of these candidates, should this be flagged. It
does that in ~100 ms, for ~nothing, thousands of times a minute, and tells you how sure it is.
→ `/jev-fit`

**Why not just use Claude / GPT for that?**
You can, and for a handful of calls a day you should. Jev earns its place when the decision
happens *a lot* (every message, every row, every keystroke), when latency matters (as-you-type),
or when you need a calibrated confidence your code can act on. In our test the hybrid — Jev where
confident, Claude for the rest — matched Claude alone within a point with 64% fewer LLM calls.
→ `/jev-playbook`

**What does it cost?**
$0.042 per million input tokens; output is free. A full evaluation of 100 rows × 7 variants cost
us about two cents. → `/jev-playbook`

**How fast is it?**
We measured p50 ≈ 110–130 ms per request, with several questions per request answered in
parallel. → `/jev-playbook`

**Do I need to know how to code?**
To *decide* whether it fits and to *design and evaluate* the questions — no; `/customs` walks you
through it and the harness runs itself. To *ship* it inside an app — someone needs to wire the
client and fallback (`/jev-integrate` gives them the drop-in code).

## Accuracy

**How accurate is it?**
That's the wrong first question. The right one is: *how accurate is it at the gate you set?* A
question set that's 88% overall may be 99% on the 70% of items it's confident about — and that
70% is what you automate. → `/jev-eval`

**It's only getting 70% on my task. Is Jev bad at this?**
Almost always the criteria are missing. A bare 2-way question scored 70% for us; one sentence
per option took it to 88%; concrete situations + boundary cases + a who-we-are preamble to 90%.
Rewrite the criteria before you blame the model. → `/jev-design`

**I rewrote the criteria and it's still stuck.**
Check the labels. If two humans would disagree on 20% of rows, no model beats ~80%. Measure
agreement with `/jev-label` (two labelers, κ). If κ < 0.6, fix the taxonomy — merge or split
labels — before anything else. Our 6-way triage task put Jev, Claude Haiku, and "always pick the
majority" all at ~50%: the taxonomy was the problem.

**Can I trust the confidence number?**
When ECE on the scoreboard is under ~0.1 and accuracy rises with confidence bucket, yes. If not,
the question is ambiguous — rewrite it. `noul` values are probabilities, not confidences; gate
them with a dead band (e.g. act if <0.2 or >0.8). → `/jev-eval`

**What gate should I use?**
Read the coverage→accuracy row and pick the lowest gate that hits the accuracy you need on the
automated slice. Everything below the gate goes to the fallback. Record it in `DESIGN.md`.
→ `/jev-eval`

## Design

**One big question or several small ones?**
If the label is crisp (humans agree), one rich `choice` wins and is cheaper to maintain. If the
label is fuzzy, ask 4–8 narrow questions people *would* agree on and combine them in code.
→ `/jev-design`

**How much text should I send?**
Only the fields the question needs. Accuracy *falls* with irrelevant detail. Pre-compute numbers,
dates, counts in code and send the result as a field. → `/jev-design`

**Should I include an "other" / "unclear" option?**
Yes, unless your labels cover every possible input. Without it the model is forced to pick a wrong
label confidently. Jev uses `unclear` honestly — 13 of 14 `unclear`s in our test were the genuinely
ambiguous rows. Route `unclear` to the fallback. → `/jev-design`

**Can it handle non-English?**
Untested by us. Either test it on a gold set in that language or detect language in code and route
non-English to the fallback. → `/jev-integrate`

**Can I use it on public / adversarial input (a web form, stranger email)?**
Yes, with care: cap the state length, keep the questions server-side, run a hostile-input pass
(injected instructions, text arguing for its own label), and put a rate limit + spend cap on the
route. → `/jev-integrate`

## Things it can't do (say them out loud)

- Write, summarize, explain, or plan → LLM.
- Arithmetic, dates, counting, "more than N" → code.
- Multi-hop conditions, comparing long documents → LLM, or split (Jev extracts, code computes).
- Judging the *quality* of an LLM's or a person's reasoning → LLM / human.
- Creative direction, taste, naming, critique → LLM / human.
- Research claim verification → LLM with sources.
→ `/jev-playbook` has the model's documented failure modes.

## Operations

**Where does the key go?**
Secrets manager + server-side env var `TYPESAFE_API_KEY`. Never in a repo, never in browser code,
never `NEXT_PUBLIC_*`. → `docs/SETUP.md`

**The model version changed. Now what?**
Re-run `/jev-eval`. Gates are tuned per version. Pin an exact version (`TYPESAFE_MODEL=jev-1.13.0`)
and log the `model` field from every response so you notice when it moves. `/customs status`
flags drift.

**How do I know it's still working in production?**
Log per call: model, input tokens, confidence, label, source (`jev` / `fallback`), latency. Watch
the weekly confidence histogram; drift shows up there before it shows up in complaints.
→ `/jev-integrate`

**Can I use the official SDKs instead of the bundled client?**
Yes (`pip install typesafe-sdk` / `npm i @typesafe-ai/sdk`). Same request shape. The bundled client
exists so a project can call Jev with nothing but `httpx`, pin a model, and run the gated hybrid
in ~100 readable lines.

**Is this affiliated with TypeSafe?**
No. Customs Authority is an independent toolkit from Robot Friends, built from our own evals.
