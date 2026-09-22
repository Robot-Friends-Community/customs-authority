# Changelog

## 0.2.3 — 2026-09-21 — agent-harness patterns
From the launch-week coverage (RoboNuggets "Jev will 10x your Claude Code"):
- fit-catalog §11–14: **inside the agent harness** (model-tier routing, the skill receptionist with the
  two-stage trick for >255 options), moderation / rule checks, search-by-meaning over a library,
  element / DOM classification for real-time filtering.
- patterns §L: Agentic OS — tier-routing question set + `decide()` with "unsure → mid tier, never small",
  skill receptionist, and how to wire it as a Claude Code `UserPromptSubmit` hook.
- playbook: access reported via Vercel AI Gateway and Cloudflare Workers AI (verify before pinning).

## 0.2.2 — 2026-09-21 — back-half friction
From the shadow-mode deploy on a guarded client monorepo (765 tests, 9 gates):
- `/jev-integrate` §0b **shadow mode**: the sanctioned first deploy when labels are pending — log
  `would_stamp` + confidence, change nothing users see, PROVISIONAL gate, mode ladder
  `off → shadow → suggest → auto`. Checklist adds *unconfigured ⇒ silent no-op* and *unknown mode ⇒ fail closed*.
- `templates/jev.ts` reads `TYPESAFE_*` per call (was module-load) so tests can vary env and negative
  controls can't silently pass.
- `/jev-label`: AskUserQuestion's 4-option cap handled (≤3 labels in-chat; >3 → terminal or 4 + free text);
  every candidate/gold row keeps a `_ref` to its source record.
- `patterns.md` §K: real-world phrase set ("later in the year", "eta 5/1", "budgeted next fiscal year"…)
  and a `vague_horizon` option.
- `jev_status.py`: prints state fields + median length for each set (catches state-shape drift).

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
