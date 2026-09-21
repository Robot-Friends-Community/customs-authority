---
name: jev-label
description: Build the answer key (gold set) for a Jev question set and find out how good it can possibly get — import decisions humans already made, or label ~100 rows blind in the terminal, then measure inter-labeler agreement (Cohen's kappa) to learn the ceiling any model can reach on this task. USE WHEN user says "jev-label", "build a gold set", "label these rows", "make the answer key", "how do we get training data for Jev", "blind relabel", "do two people agree on these labels", "measure agreement", "kappa", "what's the human ceiling", or when jev-eval / customs status reports no gold set or fewer than 100 rows. Produces gold.jsonl; the labeling is done by humans, never by a model.
---

# jev-label

The gold set is the part people skip, and it's the part that decides everything. A model
can only match the labels you give it — if two people disagree on 20% of rows, no model will
score above ~80% and *that's not the model's fault*. This skill builds the answer key and
tells you that ceiling before you spend a minute tuning criteria.

Script: `${CLAUDE_PLUGIN_ROOT}/scripts/jev_label.py` (`label` · `agree` · `stats` · `import`).

## Guided mode — what to say before each step

**Why we're doing this:** "We need about 100 real examples with the answer *you* would give.
That's the yardstick. Without it, any accuracy number is a guess."

**Why blind:** "You'll see only the item, never what the model thinks — otherwise you'd be
grading the model's homework with its own pen."

**Why two people:** "If we can get a second person to label the same 50, we learn the most
important number in the whole project: how often humans agree. Jev can't beat that."

## Procedure

### 1. Find rows (prefer decisions already made)

| Source | How |
|---|---|
| A triaged inbox, a board column, last month's routed items, a previous sweep | export to CSV/JSONL → `import` |
| Nothing labeled yet | collect ~150 raw candidates (more than 100: some will be unclear) → `label` |

State fields must be **what production will have at decision time** — not more. If the app
will only see a title and a URL, the gold set only has a title and a URL.

```bash
# existing decisions → gold (rename values with --map)
python "${CLAUDE_PLUGIN_ROOT}/scripts/jev_label.py" import --in export.csv --gold jev/<decision>/gold.jsonl \
  --label <LABEL> --label-col decision --id-col id --state-cols title,url --map "Yes=work,No=personal"
```

### 2. Label blind (terminal, resumable)

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/jev_label.py" label --in candidates.jsonl --gold jev/<decision>/gold.jsonl \
  --questions jev/<decision>/questions.json --labeler <name> --shuffle
```

- Options come from `questions.json` (or `--label x --options a,b,c`).
- `u` = unclear (keep these! they're the boundary cases), `s` = skip, `n` = note, `q` = save & quit.
- Aim for ≥100 rows with class balance roughly like production. Include the arguable ones.
- **Never let a model label the gold set.** If the person asks Claude to "just label them", explain
  why not (the model would be grading itself) and offer to sit with them instead: show each row,
  they answer, you type it.

If you (the agent) are driving: run `label` with `--limit 10` batches, present each row to the
person with AskUserQuestion (options = the labels + unclear), and pipe their answer in. Slower
but it works inside Claude Code without a terminal hand-off.

### 3. Measure the ceiling (when two labelers exist)

```bash
# second labeler relabels the same rows (blind) into their own file
python "${CLAUDE_PLUGIN_ROOT}/scripts/jev_label.py" label --in jev/<decision>/gold.jsonl --gold gold.<name2>.jsonl \
  --questions jev/<decision>/questions.json --labeler <name2> --relabel --limit 50

python "${CLAUDE_PLUGIN_ROOT}/scripts/jev_label.py" agree --a jev/<decision>/gold.jsonl --b gold.<name2>.jsonl --label <LABEL> --out disagreements.jsonl
```

Read back:

| κ | Means | Do |
|---|---|---|
| ≥ 0.8 | crisp task | tune criteria; judge Jev against ~agreement% |
| 0.6–0.8 | workable | put every disagreement into the criteria as a boundary case, then eval |
| 0.4–0.6 | fuzzy | fix the taxonomy: merge/split labels, add `unclear`; relabel |
| < 0.4 | no shared definition | redesign the decision (`/jev-design`) before evaluating anything |

**The disagreements are gold of a second kind** — each one is a sentence missing from the
criteria. Hand `disagreements.jsonl` to `/jev-design`.

### 4. Health check

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/jev_label.py" stats --gold jev/<decision>/gold.jsonl --label <LABEL>
```

Reports class balance, unclear share (>20% = the decision is too fuzzy), majority baseline
(the number any model must beat), duplicates, rows to 100.

### 5. Hand off

→ `/jev-eval`. Record in `DESIGN.md`: gold size, labelers, agreement/κ if measured, majority
baseline. Those three numbers frame every accuracy figure that follows.

## Expert mode

Skip the narration. `import` or `label --shuffle`, `agree`, `stats`, done. Reminder only:
exclude ambiguous rows or label them `unclear`; never model-label; state = production state.
