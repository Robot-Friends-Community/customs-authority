# Changelog

## 0.2.1 — 2026-09-21 — first-run friction
From the first real run (non-engineer, guided mode, a 237KB monorepo → a draft PR in one session):
- `/jev-design`: **entering from `/jev-fit`** derives the five inputs from the report + code and asks one
  confirm/correct question instead of re-running the wizard.
- `/jev-design`: artifact contract now says the truth about labels — fresh projects emit an unlabeled
  `candidates.jsonl` → `/jev-label`; `gold.jsonl` only when human decisions already exist. Documented
  smoke test with the real client class (`from jev_client import Jev`).
- `jev_status.py`: reports unlabeled `candidates.jsonl` counts and prints the exact `/jev-label` command.
- `patterns.md` §K: dates / deadlines / "how soon?" — split the calendar into code, keep `not_stated`.
- `/jev-fit`: monorepo hint (grep the whole workspace first; the second app is where steps hide).
- `/customs`: free-text answers to menus are normal — map to the nearest option and continue.
- All scripts write JSON/JSONL/MD with LF newlines; `.gitattributes` added (no more CRLF diffs on Windows).

## 0.2.0 — 2026-09-21 — "Customs Authority"
- **Renamed** jev-kit → **Customs Authority · Department of Snap Judgments** (`customs-authority`).
  Same universe as Airport Authority and DoPA. Old GitHub URL redirects.
- **`/customs` front desk** (+ `/jev` alias): guided / expert modes, `help`, `setup` (key + one live
  call + offers to write the CLAUDE.md blocks), `status` (doctor), `tutorial` (10 min on the bundled
  example), `expert`.
- **`/jev-label`** + `scripts/jev_label.py`: blind terminal labeling (resumable), import of existing
  human decisions (CSV/JSONL), gold-set stats (balance, majority baseline, unclear share), and
  inter-labeler agreement with Cohen's κ — the ceiling any model can reach.
- **`scripts/jev_status.py`** doctor: key / httpx / API / model pin vs live model / question sets /
  gold size / scoreboard age / gate + pin in DESIGN.md / drift — every red line with its fix;
  `--json` stage for the concierge to route on.
- **Guided + expert modes** in `/jev-fit` (plain-English column, one AskUserQuestion at a time),
  `/jev-design` (five-input wizard with "why" before each), `/jev-eval` (scoreboard read back as
  three sentences; gate picked together).
- **Docs:** `GLOSSARY.md`, `FAQ.md`, `SETUP.md` (for humans and AIs, with ready-to-paste global +
  project CLAUDE.md blocks).
- `examples/linkdrop/questions.json` (the evaluated variant, for a first live call).
- README rebuilt in the Robot Friends tool-banner style with evergreen visuals (hero, how-it-works,
  the three clerks); nothing version-, command-, or number-specific is baked into an image.

## 0.1.0 — 2026-09-21
- First release: five skills (jev-playbook, jev-fit, jev-design, jev-eval, jev-integrate),
  eval harness, thin Python + TypeScript clients, hybrid router + Next.js proxy templates,
  and the `linkdrop` worked example (108-row gold set, 9-variant scoreboard, Claude references).
