# criteria-rules — how to write questions Jev answers well

Sources: TypeSafe docs (primitives, state, confidence, jaggedness for jev-1.13, 2026-09) and
jev-kit's own evals (`examples/linkdrop/SCOREBOARD.md`).

## 1. Primitives

| Primitive | Returns | Use for | Notes |
|---|---|---|---|
| `choice` | `choice`, `probabilities{}`, `confidence` | one label from an unordered set | ≤255 options; `criteria` = `{key: description-or-null}`; descriptions may be strings, objects, arrays |
| `score` | `score` (probability-weighted level), `probabilities{}`, `legend{}`, `confidence` | ordered rubric | 2–10 levels, low→high, each a concrete situation; don't interpolate exact magnitudes |
| `noul` | `noul` = P(yes) | a proposition | optional `criteria: {true: …, false: …}`; **no confidence field** |

Request shape (HTTP `POST /v1/systemone`):
```json
{"model": "jev-1.13.0", "state": {...}, "questions": {"id": {"type": "choice|score|noul", "instructions": "...", "criteria": ...}}}
```
All questions in a request are evaluated independently and in parallel against the same state;
adding questions barely changes latency. Context: 64k per request, 32k for state + longest question.

## 2. State

- Shapes: string, JSON object, array of text. Text only.
- Prefer an **object with named fields**; reference fields in instructions with backticks.
- **Only what the question needs.** Irrelevant detail is a distractor (documented). Filter and
  retrieve in code first; if you can't, ask a `noul` "is this passage relevant?" and drop the noes.
- **Pre-compute deterministic facts** in code and pass them as fields or named buckets:
  platform from URL, weekday from date, amount bucket, count of items.
- State is *data*, not hostile by default. If users can write into it, write criteria for the
  manipulation you expect and test edge cases.
- English is where accuracy is best; test other languages before relying on them.

## 3. The `WHO` preamble

Two to four sentences at the front of `instructions`: who is asking, what the labels *mean for
them*, and the one distinction people get wrong. Example (from linkdrop):

> The link was saved by the founder of a small AI-native software + creative studio (Claude
> Code, AI agents, web builds, brand/design, marketing, a toy business with China sourcing).
> WORK = anything he would explore, build with, or use for the studio or its clients. PERSONAL
> = saved for his own life: cooking, music, history, politics, home/DIY, fitness, gaming.

This alone took work-recall from 35/37 to 37/37.

## 4. Writing criteria

**Situations, not adjectives.**
- ✗ `"severe": "a serious problem"`
- ✓ `"severe": "Blocking issue; no workaround exists"`

**Boundary cases, with the direction.**
- ✓ `"work": "... A recipe VIDEO ABOUT running a food business is still work; a recipe to cook is personal."`

**Negatives inside the option.**
- ✓ `"personal": "... A short about 'AI' that is a joke or a meme is personal."`

**One judgment per question.** "Is it urgent and about billing?" → two nouls.

**No indirection or double negatives.** "Is the customer NOT asking for something other than a
refund?" → "Is the customer asking for a refund?"

**Align instructions and criteria.** A noul whose `true` means "no" will underperform.

**Coverage.** Add `other` / `unclear` / `not_stated` whenever the options don't cover the space.
Jev uses an escape honestly — it will not force a label if you give it a lane.

**Scores:** describe each level as a situation; use as many levels as you can *distinguish* and
no more; normalize by `len(levels)-1` before combining scores of different lengths.

**Nouls:** threshold the value; keep a dead band (`≤0.2` no, `≥0.8` yes, middle → review).
Don't carry a threshold tuned on a noul to a choice or vice versa.

## 5. Confidence

- Only on `choice` and `score`. A statistic of the probability distribution (concentrated → high).
- Not a correctness guarantee — `1.0` means all mass on one option, not "right".
- Use it as a **second axis**: the answer says *what*, confidence says *whether to act*.
- Docs' starting points: `< 0.5` → human; `> 0.9` for destructive actions; tune on your data.
- The number to ship is the **coverage → accuracy curve** from `jev-eval`, not a single accuracy.

## 6. Failure modes (jev-1.13, from TypeSafe's jaggedness page) → what to do

| Failure | Do instead |
|---|---|
| Literal reading | write the exact condition; boundary cases in criteria; split interpretation into two literal questions |
| Math / counting | count and compute in code; one noul per item, sum yourself |
| Date/time comparison | extract components as `choice`s (month/day/year + `not_stated`), compare in code |
| Indirection / double negatives | reduce hops; point at the field by name |
| Large irrelevant state | filter first; send only what the question needs |
| Adversarial content | explicit criteria; test edge cases before exposing to strangers |
| Contradictory instructions vs criteria | align them |
| Structural invariants (P(a) + P(not a) ≠ 1; noul ≠ yes/no choice) | ask each decision one way; enforce identities in code |
| Generation | use a generative model; turn extraction into a choice over candidates |

## 7. What moved the number in our evals (linkdrop, n=108, title+URL)

| change | acc |
|---|---|
| bare 2-way choice, `criteria: {work: null, personal: null}` | 70.4% |
| + one line per option | 88.0% |
| + WHO preamble + situations + boundary cases | 89.8% (recall 37/37) |
| − URL/platform (title only) | 87.0% |
| single noul instead of choice | 89.8% but no usable confidence |
| 10 topic nouls → code (max vs max) | 88.9% |
| 10-way topic choice → map to 2 | 86.1% |
| + `unclear` option | 91.5% on answered; 14 routed to unclear (13 genuinely ambiguous) |
| Claude Sonnet, same criteria | 96.3% (ceiling; its misses are arguable labels too) |
| **Jev@0.85 + Sonnet fallback** | **95.4%, 64% fewer LLM calls** |
