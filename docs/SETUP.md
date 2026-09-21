# Setup — for humans and for AI agents

This page is written to be read by **you** and by **your Claude Code session**. Every step has a
"human" line (what to click or paste) and an "AI" line (what an agent should do when it runs
`/customs setup`). Skip what you've already done.

## 1. Install the plugin

**Human:** in any terminal —

```bash
claude plugin marketplace add Robot-Friends-Community/customs-authority
claude plugin install customs-authority@customs-authority
```

Then start (or restart) Claude Code and type `/customs`.

**AI:** if `/customs` doesn't resolve, run the two lines above and tell the person to restart the
session.

## 2. Get a key

**Human:** https://console.typesafe.ai/keys → sign in (Google works) → create an org → *API Keys*
→ *Create key*. Copy it once; the console won't show it again. Free credits cover a lot of
evaluations (one full eval ≈ a cent).

**AI:** if a browser tool is available and the person wants it, drive the signup with them.
Otherwise give the three steps and wait. **Never** ask them to paste the key into the chat; ask
them to store it (step 3) and tell you when it's done.

## 3. Store the key

Order of preference:

1. **Secrets manager** (1Password / Vaultwarden / Infisical / the host's secret store) — so it's
   recoverable and rotatable.
2. **Environment variable** `TYPESAFE_API_KEY` — what the scripts and clients read.

**Human — Windows (PowerShell):**

```powershell
[Environment]::SetEnvironmentVariable('TYPESAFE_API_KEY', '<paste-key>', 'User')
```

Close and reopen the terminal (and Claude Code) — a session started before this won't see it.

**Human — macOS / Linux:** add to `~/.zshrc` or `~/.bashrc`:

```bash
export TYPESAFE_API_KEY="<paste-key>"
```

**Optional but recommended:** pin the model version the gates are tuned on:

```
TYPESAFE_MODEL=jev-1.13.0
```

**AI:** confirm with `python "${CLAUDE_PLUGIN_ROOT}/scripts/jev_status.py"` — it reports the key
as present/absent without printing it. Never `echo` the variable. Never write the key into a
file inside a repo. If the person pasted the key into the chat by mistake, tell them to revoke
it in the console and make a new one.

## 4. Dependencies

```bash
pip install httpx
```

That's the only one. `llm_reference.py` additionally needs the `claude` CLI on PATH (it uses your
subscription for the reference run).

## 5. Prove it

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/jev_client.py" models
python "${CLAUDE_PLUGIN_ROOT}/scripts/jev_client.py" ask --state "Claude Code hooks, explained" \
  --questions "${CLAUDE_PLUGIN_ROOT}/examples/linkdrop/questions.json"
```

You should see an answer, a confidence, and a latency around 100–400 ms. Then `/customs` (or
`/customs tutorial`) takes it from here.

---

## 6. The blocks — teaching your CLAUDE.md files about the kit

Claude Code reads `CLAUDE.md` files at the start of every session. Two small blocks make every
future session use the kit at the right moments without being told. `/customs setup` offers to
write them; you can also paste them yourself.

**Rules for the AI writing these:** *append*, never overwrite. If the marker line
(`<!-- customs-authority -->`) is already present, replace that block in place. Fill the
placeholders with real values. Ask before writing the global one (it affects every project).

### 6a. Global block → `~/.claude/CLAUDE.md`

*When:* once per machine. *What it does:* makes the agent notice decision steps that belong to
Jev, in any project.

```markdown
<!-- customs-authority -->
## Decision layer — Customs Authority (Jev / System One)

When a step in any pipeline, prompt chain, workflow, or app **classifies, routes, scores,
flags, ranks, or picks-from-candidates over text** with a bounded answer — and it's currently
an LLM call or a human — consider TypeSafe's Jev before reaching for the LLM: run `/jev-fit`
on the target. Rules of thumb: a rule you can write in one sentence → code; a bounded judgment
a sharp assistant could make in two seconds with a checklist → Jev; anything needing new text,
reasoning, taste, arithmetic, or dates → LLM / code.

Three rules the kit encodes: **criteria text is the lever** (write situations and boundary
cases, not adjectives), **confidence is the product** (gate on it, escalate below it), **ship
the hybrid** (Jev where sure, LLM/human for the rest). Nothing ships without a scoreboard
(`/jev-eval`). Front desk: `/customs`. Key lives in `TYPESAFE_API_KEY` (never in a repo).
<!-- /customs-authority -->
```

### 6b. Project block → `<project>/CLAUDE.md`

*When:* the first time a project gets a `jev/<decision>/` folder. *What it does:* tells every
session where the question sets are, what's been evaluated, and what not to touch blindly.

```markdown
<!-- customs-authority -->
## Jev decision sets (Customs Authority)

Question sets live under `jev/<decision>/`: `questions.json` (what production sends — the
evaluated variant, verbatim), `task.py` (variants + `derive()`), `gold.jsonl` (the answer key),
`DESIGN.md` (decision, WHO, gate, model pin), `runs/SCOREBOARD.md` (the evidence).

- **Never edit `questions.json` without re-running `/jev-eval`** and updating the gate in
  `DESIGN.md`. Criteria changes move accuracy by tens of points in either direction.
- **Gate + model pin are recorded in `DESIGN.md`** for each set. The gate is only valid for
  that model version — if `/customs status` reports drift, re-eval before trusting it.
- Production calls go through `<path to client: app/jev_client.py or lib/jev.ts>` with the
  gated hybrid; the fallback for low-confidence / `unclear` is `<LLM call or human queue>`.
- Key: `TYPESAFE_API_KEY` in `<secrets manager + server env>`; model pinned via
  `TYPESAFE_MODEL=<jev-x.y.z>`.
- Current sets: `<jev/<name> — gate 0.85 — jev-1.13.0 — hybrid 95% / −64% LLM calls>`.
<!-- /customs-authority -->
```

### 6c. What the AI fills in

| Placeholder | Source |
|---|---|
| client path | wherever `/jev-integrate` dropped it (`app/jev_client.py`, `lib/jev.ts`) |
| fallback | from `DESIGN.md` or the router code |
| secrets location | what the person said in step 3 |
| model pin | `DESIGN.md` → `model`, or the `model` field of the last scoreboard run |
| current sets line | one per `jev/*/` with the recorded gate, model, and hybrid number |

---

## 7. Uninstall

```bash
claude plugin uninstall customs-authority@customs-authority
claude plugin marketplace remove customs-authority
```

Remove the two CLAUDE.md blocks (everything between the `<!-- customs-authority -->` markers)
and the env var. Your `jev/` folders are yours; they don't depend on the plugin.
