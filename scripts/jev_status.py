"""
jev_status — the Customs Authority doctor. Answers "where am I?" for a person or an AI in one screen.

Checks, in order:
  1. TYPESAFE_API_KEY present (never printed)      4. question sets found under jev/**/questions.json (+ unlabeled candidates.jsonl)
  2. httpx importable                              5. per set: gold size, DESIGN.md gate + model pin, last scoreboard + age
  3. API reachable, models listed, pin vs live     6. model drift: pinned model vs what the API answers with

Every failing line comes with the one command (or skill) that fixes it, so `/jev status` can read it back.

Usage
  python jev_status.py                 # human-readable report for the current directory
  python jev_status.py --json          # machine-readable (used by /jev to pick the next step)
  python jev_status.py --root path     # inspect another project
  python jev_status.py --offline       # skip the API call (no key needed)

Exit code: 0 = green, 1 = something to fix (details in the report). Never raises on a missing key.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

DEFAULT_MODEL = os.environ.get("TYPESAFE_MODEL", "jev-1.13.0")
API = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai")
STALE_DAYS = 30

OK, WARN, FAIL, INFO = "ok", "warn", "fail", "info"
ICON = {OK: "✅", WARN: "⚠️ ", FAIL: "❌", INFO: "·"}


def line(level: str, what: str, fix: str | None = None) -> dict:
    return {"level": level, "what": what, "fix": fix}


# ---------------------------------------------------------------- environment

def check_key() -> dict:
    key = os.environ.get("TYPESAFE_API_KEY", "")
    if not key:
        return line(FAIL, "TYPESAFE_API_KEY is not set in this shell",
                    "run `/jev setup` (get a free key at https://console.typesafe.ai/keys, store it in your "
                    "secrets manager, then set the env var and restart the terminal)")
    if len(key) < 20:
        return line(WARN, "TYPESAFE_API_KEY is set but looks too short to be a real key", "re-copy it from the console")
    return line(OK, f"TYPESAFE_API_KEY present ({key[:4]}…, {len(key)} chars)")


def check_httpx() -> dict:
    try:
        import httpx  # noqa: F401
        return line(OK, f"httpx installed (v{httpx.__version__})")
    except ImportError:
        return line(FAIL, "httpx is not installed (the scripts need it)", "pip install httpx")


def check_api(pinned: str) -> tuple[list[dict], str | None]:
    """Returns (lines, live_model_id). Only called when the key + httpx are present."""
    out: list[dict] = []
    try:
        import httpx
    except ImportError:
        return out, None
    headers = {"Authorization": f"Bearer {os.environ['TYPESAFE_API_KEY']}"}
    try:
        t0 = time.perf_counter()
        r = httpx.get(f"{API}/v1/models", headers=headers, timeout=10)
        dt = (time.perf_counter() - t0) * 1000
    except Exception as e:  # network down, DNS, proxy
        out.append(line(FAIL, f"API unreachable: {type(e).__name__}: {e}", "check your network / proxy, then retry"))
        return out, None
    if r.status_code == 401:
        out.append(line(FAIL, "API rejected the key (401)", "the key is wrong or revoked — make a new one at console.typesafe.ai/keys"))
        return out, None
    if r.status_code != 200:
        out.append(line(FAIL, f"API returned {r.status_code} on /v1/models", "retry in a minute; if it persists check status.typesafe.ai"))
        return out, None
    models = r.json().get("models", [])
    ids = [str(m.get("name") or m.get("id")) for m in models if isinstance(m, dict)]
    out.append(line(OK, f"API reachable in {dt:.0f} ms · models: {', '.join(ids) or '(none listed)'}"))

    # one tiny live call so we know what the alias/pin actually resolves to
    body = {"model": pinned, "state": "ping", "questions": {"q": {"type": "noul", "instructions": "Is this a greeting?"}}}
    try:
        t0 = time.perf_counter()
        r2 = httpx.post(f"{API}/v1/systemone", headers=headers, json=body, timeout=15)
        dt2 = (time.perf_counter() - t0) * 1000
    except Exception as e:
        out.append(line(WARN, f"live call failed: {type(e).__name__}", "retry; if it persists the API may be degraded"))
        return out, None
    if r2.status_code != 200:
        out.append(line(FAIL, f"live call with model `{pinned}` returned {r2.status_code}: {r2.text[:120]}",
                        "check the model id (`python jev_client.py models`) or TYPESAFE_MODEL"))
        return out, None
    live = r2.json().get("model", "")
    out.append(line(OK, f"live call ok · {dt2:.0f} ms · answered by `{live}`"))
    if live and live != pinned:
        out.append(line(WARN, f"you asked for `{pinned}` but the API answered with `{live}` (alias moved or pin ignored)",
                        "pin an exact version in TYPESAFE_MODEL / your client config and re-run `/jev-eval`"))
    return out, live


# ---------------------------------------------------------------- project

def count_lines(p: Path) -> int:
    try:
        return sum(1 for l in p.read_text(encoding="utf-8").splitlines() if l.strip())
    except OSError:
        return 0


def parse_design(p: Path) -> dict:
    """Best-effort read of DESIGN.md for the recorded gate / model / variant. Loose regexes on purpose."""
    d = {"gate": None, "model": None, "variant": None}
    if not p.exists():
        return d
    txt = p.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"gate[^0-9\n]{0,40}(0\.\d+)", txt, re.I)
    if m:
        d["gate"] = float(m.group(1))
    m = re.search(r"(jev-\d+\.\d+(?:\.\d+)?|jev-latest|jev-preview)", txt)
    if m:
        d["model"] = m.group(1)
    m = re.search(r"variant[^\n`]{0,30}`([\w\-]+)`", txt, re.I)
    if m:
        d["variant"] = m.group(1)
    return d


def last_scoreboard(runs: Path) -> dict | None:
    board = runs / "SCOREBOARD.md"
    if not board.exists():
        return None
    txt = board.read_text(encoding="utf-8", errors="replace")
    stamps = re.findall(r"^## (\d{8}-\d{6})", txt, re.M)
    if not stamps:
        return {"stamp": None, "age_days": None, "best": None}
    stamp = stamps[-1]
    try:
        ts = time.mktime(time.strptime(stamp, "%Y%m%d-%H%M%S"))
        age = (time.time() - ts) / 86400
    except ValueError:
        age = None
    # best accuracy in the last block
    last_block = txt.split(f"## {stamp}", 1)[1]
    accs = re.findall(r"\| `([\w\-]+)` \| \d+ \| \*\*([\d.]+)%\*\*", last_block)
    best = max(accs, key=lambda a: float(a[1])) if accs else None
    return {"stamp": stamp, "age_days": age, "best": best}


def check_project(root: Path, live_model: str | None) -> tuple[list[dict], list[dict]]:
    lines: list[dict] = []
    sets: list[dict] = []
    qfiles = sorted(p for p in root.glob("jev/**/questions.json") if ".jev-cache" not in p.parts)
    if not qfiles:
        lines.append(line(INFO, f"no question sets under {root / 'jev'}",
                          "new here? `/jev tutorial` · know your decision? `/jev-design` · not sure where Jev helps? `/jev-fit`"))
        return lines, sets
    lines.append(line(OK, f"{len(qfiles)} question set(s) under jev/"))
    for q in qfiles:
        d = q.parent
        name = d.relative_to(root).as_posix()
        entry = {"name": name, "path": str(d)}
        try:
            qs = json.loads(q.read_text(encoding="utf-8"))
            entry["questions"] = list(qs) if isinstance(qs, dict) else []
            entry["has_who"] = any("who" in (v.get("instructions", "") or "").lower()[:400] or
                                   len((v.get("instructions", "") or "")) > 200
                                   for v in qs.values() if isinstance(v, dict))
        except (OSError, json.JSONDecodeError, AttributeError) as e:
            lines.append(line(FAIL, f"{name}/questions.json is not valid JSON ({type(e).__name__})", "fix the file or re-emit it with `/jev-design`"))
            sets.append(entry)
            continue
        gold = d / "gold.jsonl"
        entry["gold_rows"] = count_lines(gold) if gold.exists() else 0
        design = parse_design(d / "DESIGN.md")
        entry.update({f"design_{k}": v for k, v in design.items()})
        sb = last_scoreboard(d / "runs")
        entry["scoreboard"] = sb
        entry["task_py"] = (d / "task.py").exists()

        # verdicts for this set
        if not entry["task_py"]:
            lines.append(line(WARN, f"{name}: no task.py (the harness needs VARIANTS + derive())", "`/jev-design` emits it from templates/task_template.py"))
        cand = d / "candidates.jsonl"
        entry["candidate_rows"] = count_lines(cand) if cand.exists() else 0
        if entry["gold_rows"] == 0 and entry["candidate_rows"]:
            lines.append(line(FAIL, f"{name}: {entry['candidate_rows']} unlabeled candidates, no gold.jsonl yet — nothing to measure against",
                              f"`/jev-label` → python \"${{CLAUDE_PLUGIN_ROOT}}/scripts/jev_label.py\" label --in {name}/candidates.jsonl --gold {name}/gold.jsonl --questions {name}/questions.json --labeler <you>"))
        elif entry["gold_rows"] == 0:
            lines.append(line(FAIL, f"{name}: no gold.jsonl — nothing to measure against", "`/jev-label` to build the answer key (≥100 rows; include the arguable ones)"))
        elif entry["gold_rows"] < 100:
            lines.append(line(WARN, f"{name}: gold set has {entry['gold_rows']} rows (aim for ≥100)", "`/jev-label` to grow it"))
        else:
            lines.append(line(OK, f"{name}: gold set {entry['gold_rows']} rows"))
        if sb is None:
            lines.append(line(FAIL, f"{name}: never evaluated (no runs/SCOREBOARD.md) — the one step that decides whether it works",
                              f"`/jev-eval` → python \"${{CLAUDE_PLUGIN_ROOT}}/scripts/jev_eval.py\" --task {name}/task.py --gold {name}/gold.jsonl"))
        else:
            best = f"best `{sb['best'][0]}` {sb['best'][1]}%" if sb.get("best") else "no variant rows parsed"
            age = sb.get("age_days")
            if age is not None and age > STALE_DAYS:
                lines.append(line(WARN, f"{name}: last scoreboard {sb['stamp']} is {age:.0f} days old ({best})", "re-run `/jev-eval` if criteria, gold, or the model moved"))
            else:
                lines.append(line(OK, f"{name}: scoreboard {sb['stamp']} · {best}"))
        if design["gate"] is None:
            lines.append(line(WARN, f"{name}: no gate recorded in DESIGN.md", "pick it from the coverage→accuracy row in `/jev-eval` and write `gate: 0.85` (or similar) into DESIGN.md"))
        else:
            lines.append(line(OK, f"{name}: gate {design['gate']} · pinned {design['model'] or '(no model pin!)'}"))
        if design["model"] is None:
            lines.append(line(WARN, f"{name}: no model version pinned in DESIGN.md", "write the `model` from your scoreboard run (e.g. jev-1.13.0) into DESIGN.md and TYPESAFE_MODEL"))
        elif live_model and design["model"] != live_model and not design["model"].startswith("jev-latest"):
            lines.append(line(WARN, f"{name}: DESIGN.md pins `{design['model']}` but the API now answers with `{live_model}` (drift)",
                              "re-run `/jev-eval` on the new version before trusting the old gate"))
        sets.append(entry)
    return lines, sets


# ---------------------------------------------------------------- report

def stage_of(sets: list[dict], key_ok: bool) -> str:
    """Coarse stage for /jev to route on."""
    if not key_ok:
        return "no-key"
    if not sets:
        return "no-project"
    if any(s.get("scoreboard") is None for s in sets):
        return "unevaluated"
    if any(s.get("design_gate") is None for s in sets):
        return "no-gate"
    return "evaluated"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--offline", action="store_true", help="skip the API check")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="pinned model to verify against the API")
    args = ap.parse_args()
    root = Path(args.root).resolve()

    env = [check_key(), check_httpx()]
    key_ok = env[0]["level"] == OK
    live_model = None
    api: list[dict] = []
    if args.offline:
        api.append(line(INFO, "API check skipped (--offline)"))
    elif key_ok and env[1]["level"] == OK:
        api, live_model = check_api(args.model)
    proj, sets = check_project(root, live_model)

    report = {
        "root": str(root), "pinned_model": args.model, "live_model": live_model,
        "stage": stage_of(sets, key_ok),
        "environment": env, "api": api, "project": proj, "sets": sets,
    }
    worst = max((l["level"] for l in env + api + proj), key=lambda lv: [INFO, OK, WARN, FAIL].index(lv), default=OK)
    report["healthy"] = worst in (OK, INFO)

    if args.json:
        print(json.dumps(report, indent=1, ensure_ascii=False))
    else:
        print(f"Customs Authority · status · {root}\n")
        for title, block in (("environment", env), ("api", api), ("project", proj)):
            if not block:
                continue
            print(f"{title}")
            for l in block:
                print(f"  {ICON[l['level']]} {l['what']}")
                if l["fix"] and l["level"] in (WARN, FAIL, INFO):
                    print(f"       → {l['fix']}")
        print(f"\nstage: {report['stage']}  ·  {'all green' if report['healthy'] else 'something to fix above'}")
    sys.exit(0 if report["healthy"] else 1)


if __name__ == "__main__":
    main()
