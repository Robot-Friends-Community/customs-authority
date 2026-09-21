<div align="center">

# jev-kit

**The decision-layer toolkit for Claude Code.** Find where TypeSafe's Jev fits in your project, write question sets that actually work, prove them on a gold set, and ship the gated Jev + LLM hybrid.

[![Claude Code](https://img.shields.io/badge/Claude-Code-blueviolet?style=for-the-badge)](https://claude.ai/code)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)
[![Community](https://img.shields.io/badge/Robot%20Friends-Community-orange?style=for-the-badge)](https://github.com/Robot-Friends-Community)

</div>

---

## What is this?

[Jev](https://typesafe.ai) is a new kind of model: not an LLM, a **System One decision model**.
You give it text and typed questions — *which category? how severe? is this urgent?* — and it
returns every answer in parallel with calibrated probabilities, in ~100 ms, for $0.042 per
million input tokens (output is free). It can't write a sentence. It can make ten thousand
small judgments a minute and tell you which ones it's unsure about.

That makes it the missing middle in every AI-powered app:

| | Code | **Jev** | LLM |
|---|---|---|---|
| Good at | rules | **narrow judgment over text, bounded answer** | reasoning, generation, taste |
| Cost | free | ~free | $ |
| Latency | µs | **~100 ms** | seconds |

**jev-kit** is how you use it well. Five skills that walk the whole path, a shared eval harness,
and drop-in clients — built from real evals, not vibes.

## The skills

| Skill | What it does |
|---|---|
| `/jev-playbook` | What Jev is, costs, limits, when (not) to use it. Read this first. |
| `/jev-fit` | Audit a project / pipeline / codebase / workflow for steps where Jev is the right tool. Three-way triage (code / Jev / LLM), Jev shape per step, ranked report, first pilot. Sibling of `algo-lens`. |
| `/jev-design` | Turn a decision into a question set that works: primitive choice, state design, criteria writing (situations, boundary cases, a who-we-are preamble, escape option), decomposition, `derive()` code. |
| `/jev-eval` | Score it before it ships: gold set → variants → scoreboard (accuracy, calibration, coverage→accuracy per gate, latency, cost), Claude reference for the ceiling, pick the gate. |
| `/jev-integrate` | Ship it: key handling, Python/TS client, the gated hybrid with fallback, public-tool proxy, logging, version pinning, pre-ship checklist. |

Plus: `scripts/jev_eval.py` (the harness), `scripts/jev_client.py` (thin client + CLI),
`scripts/llm_reference.py`, `templates/` (task, hybrid router, `jev.ts`, Next.js route), and a
worked example in `examples/linkdrop/`.

## Install

```bash
claude plugin marketplace add Robot-Friends-Community/jev-kit
claude plugin install jev-kit@jev-kit
```

Then get a key at https://console.typesafe.ai/keys and set `TYPESAFE_API_KEY`. `pip install httpx`
for the scripts.

## What we learned building it (the reason the rules exist)

Same 108 links, same model, nine ways of asking:

| | accuracy |
|---|---|
| bare 2-way choice, no criteria text | 70% |
| one sentence of criteria per option | **88%** |
| concrete situations + boundary cases + who-we-are | **90%** |
| Claude Sonnet, same criteria (the ceiling) | 96% |
| **Jev at confidence ≥0.85, Sonnet for the rest** | **95.4%, with 64% fewer LLM calls** |

Criteria text is the lever. Confidence is the product. Ship the hybrid.
Full ladder: [`examples/linkdrop/SCOREBOARD.md`](examples/linkdrop/SCOREBOARD.md).

## The workflow

```
/jev-fit  →  /jev-design  →  /jev-eval  →  /jev-integrate
 where?       questions       scoreboard     hybrid in prod
```

## Not a fit for

Creative direction, critique, naming · judging the quality of LLM or code output · research
claim verification · numbers, dates, counting · multi-hop conditions · text generation ·
adversarial public input without criteria and tests. The playbook has the full list and the
model's documented failure modes.

## Lineage

Built at [Robot Friends](https://github.com/Robot-Friends-Community) in September 2026 after a
two-day deep dive: watch the launch coverage → read every doc page → benchmark on our own
labeled data → map it to our business → distill the rules into skills. Sibling of
[`algo-lens`](https://github.com/Robot-Friends-Community/toolbox) ("fire the LLM, hire an
algorithm") — jev-kit covers the judgment steps algo-lens leaves on the LLM.

## Contributing

Question sets and gold sets are the valuable part. PRs that add a worked example (task +
gold + scoreboard) for a new decision family are the most welcome kind.

## License

MIT © Robot Friends (404NOTFOUND LLC). Not affiliated with TypeSafe AI.
