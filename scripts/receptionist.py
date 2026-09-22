"""
receptionist — Sifu's System One. Which skill should this message go to?

Two-stage Jev routing over a skill manifest (the iron-ledger census, or any JSON with the same shape):
  stage 1  choice: which SECTION (17 options + none)      → gate
  stage 2  choice: which SKILL inside that section (+ none) → gate
Code owns the decision: both stages must clear their gate or the answer is "none" (Secondary Inspection —
whatever the caller does when the receptionist isn't sure: the existing Haiku+SIFU path, or nothing).

Why two stages: Jev choice questions cap out well under 300 options and the criteria text gets diluted;
section→skill keeps every question small and its criteria sharp. (rv-522 "two-stage >255 trick".)

Usage
  python scripts/receptionist.py "can you watch this youtube video and tell me what's useful"
  python scripts/receptionist.py --eval gold.jsonl [--gate 0.6] [--gate1 0.5] [--limit 50] [--out runs/] [--flat]
  python scripts/receptionist.py --sections            # print the stage-1 option list

Gold format (same as jev_eval): {"id":..., "state":{"message":...}, "labels":{"skill": "<skill-id>" | "none"}}
Env: TYPESAFE_API_KEY (console.typesafe.ai/keys) · RF_SKILL_MANIFEST (path; default = iron-ledger manifest)
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from jev_client import Jev, JevError  # noqa: E402

DEFAULT_MANIFEST = os.environ.get(
    "RF_SKILL_MANIFEST", "C:/Dev/_PROJECTS/_SCRIPTS/rv404-skill-registry/manifest.json")
NONE = "none"
MAX_DESC = 320  # chars of a skill description we send as its criterion (criteria text is the lever — keep the USE WHEN triggers)

WHO = ("The message is from the founder of a small AI-native software + creative studio, typed into a "
       "Claude Code session. A 'skill' is a packaged workflow he can invoke. Most messages need NO skill "
       "(ordinary coding, questions, approvals, chat). Only route to a skill when the message clearly asks "
       "for the kind of work that skill packages.")


# ----------------------------------------------------------------------------- intent taxonomy
# The manifest's `section` field is a filing system, not a routing taxonomy (jean-paul files under
# "hardware"). Stage 1 routes on INTENT instead: a dozen hand-written buckets with real criteria text,
# and every skill is placed into one of them by Jev from its own description (cached in a taxonomy file).
INTENTS = {
    "session": "Save, restore, hand off, close or recover a Claude Code session; flight logs, takeoff/landing, memory, beads/issue-tracker setup, session bus between sessions.",
    "team-comms": "Message or task a teammate; Slack posts, standups, kudos, dispatch/status broadcasts, crew tasking, email drafting/turnaround, internal comms.",
    "media-intake": "Watch, summarize, triage or extract from a video/link/transcript/meeting note; YouTube/TikTok/IG URLs, 'watch this', signal-to-strategy, corpus triage.",
    "visuals": "Generate or edit images, banners, heroes, moodboards, mascots, logos, art direction, design references, canvas/slide visuals, motion/video generation.",
    "web-build": "Build, scaffold, style, animate, test or deploy a website/app; Next.js init, Vercel, UI/UX, scroll worlds, premium UI, browser QA, performance.",
    "writing": "Write, rewrite, humanize or edit prose and copy: blog/Substack posts, marketing copy, taglines, naming, voice, dehumanize AI text, content batches.",
    "marketing-growth": "Marketing strategy and execution: SEO, paid ads, launches, calendars, email campaigns, social, analytics, pricing, ICP, referral, brand audits.",
    "sales-clients": "Prospects, leads, pitches, proposals, CRO/website audits for a client, deal scoring, client onboarding/assistant, timesheets, client project setup.",
    "planning-orchestration": "Turn an idea into a plan and run it: blueprint/PRD hardening, greenlight, operations, wave/parallel agent builds, GSD phases, roundtables, advisors.",
    "repo-code-ops": "Git/GitHub/repo hygiene and safety: repo standards, share checks, safety scans, security audits, changelogs, migrations, docker/proxmox/nssm deploys, port conflicts.",
    "skills-tooling-meta": "Create, audit, register, prune or share skills/agents/plugins/MCPs themselves; harness design and certification; system health; capability census.",
    "research-analysis": "Research a topic or market, compare tools or repos, competitive intel, evaluate a repo/skill before adopting, financial/accounting analysis.",
}
DEFAULT_TAXONOMY = os.environ.get("RF_RECEPTIONIST_TAXONOMY",
                                  str(Path.home() / ".claude" / "sifu" / "receptionist-taxonomy.json"))


def build_taxonomy(skills: list[dict], jev: "Jev", path: str = DEFAULT_TAXONOMY, refresh: bool = False) -> dict[str, dict]:
    """skill id -> {intent, confidence}. Cached; only new/changed skills are classified on later runs."""
    p = Path(path)
    cache = json.loads(p.read_text(encoding="utf-8")) if p.exists() and not refresh else {}
    q = {"intent": {"type": "choice",
                    "instructions": ("A Claude Code skill is described below. Which INTENT bucket would a user's request "
                                     "most likely fall in when this skill is the right tool?"),
                    "criteria": INTENTS}}
    todo = [s for s in skills if s["id"] not in cache or cache[s["id"]].get("description") != s["description"]]
    for i, s in enumerate(todo, 1):
        r = jev.ask({"skill": s["id"], "description": s["description"] or s["id"], "manifest_section": s["section"]}, q)
        a = r.answers["intent"]
        cache[s["id"]] = {"intent": a.get("choice"), "confidence": float(a.get("confidence") or 0), "description": s["description"]}
        if i % 25 == 0:
            print(f"[taxonomy] {i}/{len(todo)}", file=sys.stderr)
    if todo:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
    return cache


def apply_taxonomy(skills: list[dict], tax: dict[str, dict]) -> list[dict]:
    return [{**s, "section": tax.get(s["id"], {}).get("intent") or s["section"]} for s in skills]


# ----------------------------------------------------------------------------- manifest → option lists
def load_skills(path: str = DEFAULT_MANIFEST) -> list[dict]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    skills = d["capabilities"]["skills"] if "capabilities" in d else d["skills"]
    out = []
    for s in skills:
        if s.get("status", "active") != "active":
            continue
        desc = (s.get("description") or "").strip().replace("\n", " ")
        out.append({"id": s["id"], "section": s.get("section") or "other", "description": desc})
    return out


def _trim(text: str, n: int = MAX_DESC) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rsplit(" ", 1)[0] + "…"


def section_criteria(skills: list[dict]) -> dict[str, str]:
    """Stage-1 options: each section described by its name + a sample of the skills in it."""
    by = collections.defaultdict(list)
    for s in skills:
        by[s["section"]].append(s)
    crit = {}
    for sec, lst in sorted(by.items()):
        names = ", ".join(x["id"] for x in lst[:10]) + (", …" if len(lst) > 10 else "")
        crit[sec] = f"{INTENTS[sec]} (e.g. {names})" if sec in INTENTS else f"{len(lst)} skills such as: {names}"
    crit[NONE] = ("No skill applies: ordinary coding or file edits, a question, an approval/answer to Claude, "
                  "casual chat, or a task Claude should just do directly.")
    return crit


def skill_criteria(skills: list[dict], section: str) -> dict[str, str]:
    crit = {s["id"]: _trim(s["description"]) or s["id"] for s in skills if s["section"] == section}
    crit[NONE] = "None of these skills fits the message; Claude should handle it directly or it belongs elsewhere."
    return crit


def stage1_questions(skills: list[dict]) -> dict:
    return {"section": {"type": "choice",
                        "instructions": f"{WHO} Which SECTION of the skill library, if any, does this message call for?",
                        "criteria": section_criteria(skills)}}


def flat_questions(skills: list[dict]) -> dict:
    """Single-stage variant: one choice over every skill (fine while the library is under Jev's option cap)."""
    crit = {s["id"]: _trim(s["description"]) or s["id"] for s in skills}
    crit[NONE] = ("No skill applies: ordinary coding or file edits, a question, an approval/answer to Claude, "
                  "casual chat, or a task Claude should just do directly.")
    return {"skill": {"type": "choice",
                      "instructions": f"{WHO} Which skill, if any, should handle this message?",
                      "criteria": crit}}


def stage2_questions(skills: list[dict], section: str) -> dict:
    return {"skill": {"type": "choice",
                      "instructions": f"{WHO} Within the '{section}' section, which skill (if any) should handle this message?",
                      "criteria": skill_criteria(skills, section)}}


# ----------------------------------------------------------------------------- routing
class Receptionist:
    def __init__(self, skills: list[dict] | None = None, gate1: float = 0.5, gate: float = 0.6, jev: Jev | None = None,
                 flat: bool = False, taxonomy: str | None = DEFAULT_TAXONOMY):
        self.skills = skills or load_skills()
        self.jev = jev or Jev()
        if taxonomy:
            self.skills = apply_taxonomy(self.skills, build_taxonomy(self.skills, self.jev, taxonomy))
        self.gate1, self.gate, self.flat = gate1, gate, flat
        self._q1 = stage1_questions(self.skills)
        self._qflat = flat_questions(self.skills) if flat else None
        self._q2: dict[str, dict] = {}

    def route(self, message: str, context: dict | None = None) -> dict:
        """Returns {skill, confidence, section, section_confidence, source, latency_s, calls}.
        source: 'jev' when both gates cleared, else 'none:<why>' (caller decides what Secondary Inspection is)."""
        state = {"message": message, **(context or {})}
        t0 = time.perf_counter()
        if self.flat:
            r = self.jev.ask(state, self._qflat)
            a = r.answers["skill"]
            sk, c = a.get("choice"), float(a.get("confidence") or 0)
            sec = next((s["section"] for s in self.skills if s["id"] == sk), NONE)
            out = {"section": sec, "section_confidence": c, "skill": NONE, "confidence": c, "calls": 1,
                   "latency_s": time.perf_counter() - t0, "raw_skill": sk}
            if sk == NONE or c < self.gate:
                out["source"] = "none:skill-gate" if sk != NONE else "none:skill-none"
                return out
            out.update(skill=sk, source="jev")
            return out
        r1 = self.jev.ask(state, self._q1)
        a1 = r1.answers["section"]
        sec, c1 = a1.get("choice"), float(a1.get("confidence") or 0)
        out = {"section": sec, "section_confidence": c1, "skill": NONE, "confidence": 0.0, "calls": 1}
        if sec == NONE or c1 < self.gate1:
            out["source"] = "none:section-gate" if sec != NONE else "none:section-none"
            out["latency_s"] = time.perf_counter() - t0
            return out
        q2 = self._q2.get(sec) or self._q2.setdefault(sec, stage2_questions(self.skills, sec))
        r2 = self.jev.ask(state, q2)
        a2 = r2.answers["skill"]
        sk, c2 = a2.get("choice"), float(a2.get("confidence") or 0)
        out.update(calls=2, confidence=c2, latency_s=time.perf_counter() - t0)
        if sk == NONE or c2 < self.gate:
            out["source"] = "none:skill-gate" if sk != NONE else "none:skill-none"
            out["raw_skill"] = sk
            return out
        out.update(skill=sk, source="jev")
        return out


# ----------------------------------------------------------------------------- eval
def evaluate(gold_path: str, gate1: float, gate: float, limit: int | None, out_dir: str, flat: bool = False,
             taxonomy: str | None = DEFAULT_TAXONOMY) -> dict:
    rows = [json.loads(l) for l in Path(gold_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    if limit:
        rows = rows[:limit]
    rc = Receptionist(gate1=gate1, gate=gate, flat=flat, taxonomy=taxonomy)
    ids = {s["id"] for s in rc.skills}
    variant = "flat" if flat else ("two-stage-intents" if taxonomy else "two-stage-sections")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    detail = Path(out_dir) / f"{stamp}-receptionist-{variant}.jsonl"
    n = correct = calls = 0
    tp = fp = fn = 0  # on the positive (a-skill-fires) class
    sec_ok = sec_n = 0
    conf_pos: list[tuple[float, bool]] = []
    with detail.open("w", encoding="utf-8") as fh:
        for r in rows:
            truth = r["labels"]["skill"]
            if truth != NONE and truth not in ids:
                continue  # not routable by this manifest — reported separately by the gold builder
            res = rc.route(r["state"]["message"])
            n += 1
            calls += res["calls"]
            pred = res["skill"]
            ok = pred == truth
            correct += ok
            if truth != NONE:
                sec_n += 1
                sec_ok += (res["section"] == next(s["section"] for s in rc.skills if s["id"] == truth))
            if pred != NONE:
                conf_pos.append((res["confidence"], ok))
                if ok:
                    tp += 1
                else:
                    fp += 1
            elif truth != NONE:
                fn += 1
            fh.write(json.dumps({"id": r["id"], "truth": truth, **res, "correct": ok}, ensure_ascii=False) + "\n")
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    summary = {"rows": n, "accuracy": correct / n if n else 0, "section_accuracy_on_positives": sec_ok / sec_n if sec_n else 0,
               "suggest_precision": prec, "suggest_recall": rec, "suggested": tp + fp, "false_suggestions": fp,
               "missed": fn, "avg_calls": calls / n if n else 0, "gate1": gate1, "gate": gate, "variant": variant, "detail": str(detail)}
    board = Path(out_dir) / "SCOREBOARD.md"
    line = (f"| {stamp} | receptionist/{variant} | gate1={gate1} gate={gate} | n={n} | acc={summary['accuracy']:.3f} | "
            f"section@pos={summary['section_accuracy_on_positives']:.3f} | suggest P={prec:.3f} R={rec:.3f} "
            f"(fp={fp}, missed={fn}) | calls/row={summary['avg_calls']:.2f} |\n")
    if not board.exists():
        board.write_text("| run | task | gates | rows | accuracy | section acc | suggestion quality | cost |\n|---|---|---|---|---|---|---|---|\n", encoding="utf-8")
    board.open("a", encoding="utf-8").write(line)
    return summary


# ----------------------------------------------------------------------------- cli
def main() -> None:
    ap = argparse.ArgumentParser(description="Two-stage Jev skill receptionist.")
    ap.add_argument("message", nargs="?", help="a user message to route")
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--gate1", type=float, default=0.5, help="stage-1 (section) confidence gate")
    ap.add_argument("--gate", type=float, default=0.6, help="stage-2 (skill) confidence gate")
    ap.add_argument("--eval", metavar="GOLD", help="score against a gold jsonl instead of routing one message")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", default="runs")
    ap.add_argument("--sections", action="store_true", help="print the stage-1 option list and exit")
    ap.add_argument("--flat", action="store_true", help="single-stage: one choice over every skill (no sections)")
    ap.add_argument("--taxonomy", default=DEFAULT_TAXONOMY, help="intent taxonomy cache (skill -> intent); '' to route on raw manifest sections")
    ap.add_argument("--rebuild-taxonomy", action="store_true", help="re-classify every skill into an intent bucket")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    os.environ["RF_SKILL_MANIFEST"] = a.manifest
    skills = load_skills(a.manifest)
    tax = a.taxonomy or None
    if a.rebuild_taxonomy:
        build_taxonomy(skills, Jev(), a.taxonomy, refresh=True)
        print(f"taxonomy rebuilt -> {a.taxonomy}")
        return
    if a.sections and tax:
        skills = apply_taxonomy(skills, build_taxonomy(skills, Jev(), tax))
    if a.sections:
        for k, v in section_criteria(skills).items():
            print(f"{k:24s} {v}")
        return
    try:
        if a.eval:
            s = evaluate(a.eval, a.gate1, a.gate, a.limit, a.out, flat=a.flat, taxonomy=tax)
            print(json.dumps(s, indent=2) if a.json else
                  f"n={s['rows']}  accuracy={s['accuracy']:.3f}  section@pos={s['section_accuracy_on_positives']:.3f}  "
                  f"suggest P={s['suggest_precision']:.3f} R={s['suggest_recall']:.3f}  calls/row={s['avg_calls']:.2f}\n→ {s['detail']}")
            return
        if not a.message:
            ap.error("give a message, --eval GOLD, or --sections")
        res = Receptionist(skills, a.gate1, a.gate, flat=a.flat, taxonomy=tax).route(a.message)
        if a.json:
            print(json.dumps(res, indent=2))
        elif res["skill"] != NONE:
            print(f"suggested skill: /{res['skill']} · confidence {res['confidence']:.2f}  (section {res['section']} {res['section_confidence']:.2f}, {res['latency_s']*1000:.0f} ms)")
        else:
            print(f"no suggestion ({res['source']}; section {res['section']} {res['section_confidence']:.2f}, {res['latency_s']*1000:.0f} ms)")
    except JevError as e:
        sys.exit(f"[receptionist] Jev error: {e}")


if __name__ == "__main__":
    main()
