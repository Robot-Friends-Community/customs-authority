"""
LLM reference for a gold set: same criteria text, answered by Claude via `claude -p` (subscription).
Tells us the ceiling a frontier model reaches on the same labels, so Jev's number has context.

  python llm_reference.py --task tasks/linkdrop.py --gold gold/linkdrop.jsonl --variant v2_choice_rich --model sonnet
Uses `claude -p` (your Claude Code subscription, no API key). Appends to runs/SCOREBOARD.md.
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent


def ask(batch: list[dict], question: dict, model: str) -> dict[str, str]:
    crit = "\n".join(f"- {k}: {v or '(self-explanatory)'}" for k, v in question["criteria"].items())
    items = "\n".join(f"{r['id']}: {json.dumps(r['state'], ensure_ascii=False)}" for r in batch)
    prompt = (f"{question['instructions']}\n\nOptions:\n{crit}\n\nFor each item below answer with exactly one option key. "
              f"Return ONLY a JSON object mapping id -> option key.\n\n{items}")
    out = subprocess.run(["claude", "-p", "--model", model, "--output-format", "text"], input=prompt,
                         capture_output=True, text=True, encoding="utf-8", timeout=300, shell=(sys.platform == "win32")).stdout
    m = re.search(r"\{[\s\S]*\}", out)
    return json.loads(m.group(0)) if m else {}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--variant", required=True, help="a single-choice variant whose criteria to reuse")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--batch", type=int, default=30)
    args = ap.parse_args()

    sys.path.insert(0, str(HERE))
    from jev_eval import load_task
    task = load_task(args.task)
    q = next(iter(task.VARIANTS[args.variant].values()))
    assert q["type"] == "choice", "reference needs a single choice question"
    recs = [json.loads(l) for l in Path(args.gold).read_text(encoding="utf-8").splitlines() if l.strip()]
    preds: dict[str, str] = {}
    t0 = time.perf_counter()
    for i in range(0, len(recs), args.batch):
        preds.update(ask(recs[i:i + args.batch], q, args.model))
    dt = time.perf_counter() - t0
    sc = [r for r in recs if r["id"] in preds]
    n = len(sc)
    hit = sum(1 for r in sc if preds[r["id"]] == r["labels"][task.LABEL])
    conf = defaultdict(Counter)
    for r in sc:
        conf[r["labels"][task.LABEL]][preds[r["id"]]] += 1
    line = f"| `LLM:{args.model} ({args.variant} criteria)` | {n} | **{hit/n*100:.1f}%** | – | – | {dt/n*1000:.0f} (batched) | – |"
    print(line)
    print("   confusion:", {t: dict(c) for t, c in conf.items()})
    for r in [r for r in sc if preds[r["id"]] != r["labels"][task.LABEL]][:8]:
        print(f"   miss {r['id']}: truth={r['labels'][task.LABEL]} pred={preds[r['id']]} | {r['state'].get('title','')[:70]}")
    runs = Path.cwd() / "runs"; runs.mkdir(exist_ok=True)
    (runs / f"llm-{args.model}-{Path(args.task).stem}-{args.variant}.json").write_text(json.dumps(preds, indent=1), encoding="utf-8")
    with (HERE / "runs" / "SCOREBOARD.md").open("a", encoding="utf-8") as f:
        f.write(f"\n{line}  ← LLM reference, task `{args.task}`\n")


if __name__ == "__main__":
    main()
