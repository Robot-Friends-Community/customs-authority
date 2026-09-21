---
name: jev-eval
description: Evaluate a Jev (TypeSafe System One) question set against a gold set before it ships — build or grow the gold jsonl, run every variant through the bundled harness, read the scoreboard (accuracy, calibration/ECE, coverage→accuracy at each confidence gate, latency, cost), optionally run a Claude reference on the same criteria for the ceiling, and pick the production gate from the curve. USE WHEN user says "jev-eval", "eval the Jev questions", "score the question set", "build a gold set", "what gate should we use", "how accurate is Jev on this", "compare Jev variants", "Jev vs Claude on this task", or after jev-design produced a task. Rule of the kit: no question set ships without a scoreboard.
---

# jev-eval

100 labeled rows and about a cent is enough to know whether a question set works, where it
fails, and what confidence gate to ship. Do this every time — including when the model alias
moves.

## What you need

- **A task file** (`task.py`) with `VARIANTS`, `derive()`, `LABEL`, optional `STATE()` —
  from `jev-design` or `${CLAUDE_PLUGIN_ROOT}/templates/task_template.py`.
- **A gold set** (`gold.jsonl`): `{"id", "state": {...}, "labels": {"<LABEL>": ...}}` per line.
  Aim for ≥100 rows, class balance roughly like production, and *include the arguable ones*.
- `TYPESAFE_API_KEY` in the environment. `httpx` installed (`pip install httpx`).

## Building the gold set (the part people skip)

1. **Best source: decisions humans already made** — a triaged inbox, a labeled board column,
   last month's routed items, a previous sweep's output. Export, dedupe by id, keep the label.
2. **Second best: label 100 rows now**, blind, with the same criteria text the model will see.
   If two people label, measure agreement — **that number is the ceiling any model can hit.**
   (Our 6-way triage labels put Jev, Haiku, and "always pick the majority" all at ~50%: the
   taxonomy was the problem, not the model.)
3. **Exclude ambiguous rows from gold** (mark them; don't score them) or give them an `unclear`
   label if the question set has that option.
4. Never let the model label its own gold set.

## Procedure

```bash
# 1) run all variants (responses are cached in ./.jev-cache — re-scoring is free)
python "${CLAUDE_PLUGIN_ROOT}/scripts/jev_eval.py" --task jev/<decision>/task.py --gold jev/<decision>/gold.jsonl

# 2) optional: Claude on the same criteria, for the ceiling (uses `claude -p`, your subscription)
python "${CLAUDE_PLUGIN_ROOT}/scripts/llm_reference.py" --task jev/<decision>/task.py --gold jev/<decision>/gold.jsonl --variant v1_rich --model sonnet

# 3) read runs/SCOREBOARD.md and the per-row runs/<stamp>-*.jsonl
```

Then:

1. **Read the misses first**, not the accuracy. For each: is the label wrong (fix gold), is a
   criteria line missing (fix the question — this is where the gains are), or is it a genuine
   model limit (numeric / multi-hop / adversarial → move that part to code or the LLM)?
2. **Compare variants** — v0 baseline vs rich vs decomposed. Keep the simplest one within a
   point or two of the best; it's cheaper to maintain.
3. **Pick the gate from the coverage→accuracy row**, e.g. `@0.85: 64%→99%` means "at gate 0.85
   Jev answers 64% of rows and is right 99% of the time on those". Choose the gate that meets
   the accuracy you need on the auto-handled slice; everything else goes to the fallback.
4. **Compute the hybrid** (Jev where confident, LLM/human elsewhere) — that's the number to
   report, alongside the LLM-alone number and the share of LLM calls avoided.
5. **Check calibration** — ECE under ~0.1 and accuracy rising monotonically with confidence
   buckets means the gate will behave. If not, the question is ambiguous; rewrite.
6. **Record** the chosen variant, gate, model version, and scoreboard excerpt in `DESIGN.md`.
   Copy the chosen variant's questions into `questions.json` (what production sends).

## Reading the scoreboard

| column | meaning |
|---|---|
| acc | top-1 = gold label |
| ECE | expected calibration error (lower is better; <0.1 good) |
| coverage→acc at conf ≥ t | share of rows Jev would auto-answer at gate t → accuracy on that share |
| p50 ms | median live latency (cached rows excluded) |
| in-tok / cost | input tokens and $ for the whole run (output tokens are free) |

Each run also writes every row (state, answers, probabilities, confidence, latency) to
`runs/<stamp>-<task>-<variant>.jsonl` — grep the misses.

## Success criteria (suggested)

- A crisp binary/ternary task: ≥88% top-1, hybrid within ~1 pt of the LLM reference, ≥60% coverage at ≥97% on the gated slice.
- A fuzzy multi-way task: first establish the human–human ceiling; then judge Jev relative to it, not to 100%.
- Any task: every high-confidence miss (≥0.85) has been read and explained.

## Re-run when

- the criteria change (obviously) · the model alias moves (`response.model` changed) · production
  confidence distribution drifts (log it) · you add ≥50 new gold rows.


## Guided mode (default when the person is new or non-technical)

Mode is set by `/customs` and persists. The scoreboard is a wall of numbers; in guided mode
you translate it.

1. **Before running:** "This sends your ~100 examples to Jev a few different ways and compares
   its answers to yours. It costs about a cent and takes under a minute."
2. **Read back the result as three sentences, not a table:**
   - *overall* — "Asked the plain way, Jev agreed with you 70% of the time. With your criteria,
     90%."
   - *ceiling* — "Claude, given the same criteria, got 96%. That's about the best anyone does on
     these labels." (If agreement/κ was measured in `/jev-label`, cite that instead — it's the
     truer ceiling.)
   - *the gate* — "If we only let Jev act when it's at least 85% sure, it handles 64% of items by
     itself and gets 99% of those right. The other 36% go to a person or Claude. Together that's
     95% — as good as Claude alone, with two-thirds fewer expensive calls."
3. **Pick the gate together with AskUserQuestion** — present 2–3 rows from the coverage→accuracy
   line as options in their terms: *"Jev handles 73% on its own, 96% right"* · *"64% on its own,
   99% right"* · *"44% on its own, 98% right"*. Ask which trade they want given the stakes they
   named in `/jev-design` step 5. Record the choice in `DESIGN.md`.
4. **Read the misses with them** (top 5): for each, ask "would you have said that too?" —
   *yes* → fix the gold label; *no, obviously X* → a criteria line is missing (send to
   `/jev-design`); *genuinely could go either way* → mark unclear / route to fallback.
5. **Say what ships:** "So the thing we build is: Jev decides when it's ≥0.85 sure; otherwise
   it goes to <fallback>. That's `/jev-integrate`."

Never present a single accuracy number without its gate line; never present the gate line
without the fallback.

## Expert mode

Run, print the table, list misses with ids, state the recommended gate and the hybrid number,
write `DESIGN.md`. One paragraph max.
