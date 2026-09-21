"""
jev_eval — the jev-kit eval harness for TypeSafe/Jev question-set design.

Rule of the kit: no question set ships without a scoreboard. 100 labeled rows and a cent is enough.

Concepts
  gold set : jsonl, one record per line: {"id": ..., "state": {...}, "labels": {"<task>": <truth>}}
  task     : a python file (path) exposing
               VARIANTS: dict[name -> dict of Jev questions]      (what we send)
               derive(answers, variant_name) -> (prediction, confidence)   (code owns the decision)
               LABEL: the key inside record["labels"] to score against
               STATE(record, variant_name) -> state to send  (optional; default record["state"])
  cache    : every (model, state, questions) response is cached in .cache/ so re-scoring a variant
             costs nothing and runs are reproducible (same idea as TypeSafe's cookbooks).

Usage
  python jev_eval.py --task tasks/linkdrop.py --gold gold/linkdrop.jsonl              # all variants
  python jev_eval.py --task tasks/linkdrop.py --gold gold/linkdrop.jsonl --variant v2_choice_rich
  python jev_eval.py --task tasks/linkdrop.py --gold gold/linkdrop.jsonl --limit 40 --no-cache
Outputs: runs/SCOREBOARD.md (appended) + runs/<stamp>-<task>-<variant>.jsonl (every row, answers, confidence)
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import httpx

HERE = Path(__file__).parent
CACHE = Path.cwd() / ".jev-cache"   # per-project cache; add to .gitignore
RUNS = Path.cwd() / "runs"
URL = "https://api.typesafe.ai/v1/systemone"
PRICE_PER_MTOK = 0.042


def key_of(model: str, state, questions) -> str:
    blob = json.dumps({"m": model, "s": state, "q": questions}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


async def call(client: httpx.AsyncClient, sem: asyncio.Semaphore, model: str, state, questions, use_cache: bool) -> dict:
    k = key_of(model, state, questions)
    f = CACHE / f"{k}.json"
    if use_cache and f.exists():
        d = json.loads(f.read_text(encoding="utf-8"))
        d["_cached"] = True
        return d
    body = {"model": model, "state": state, "questions": questions}
    headers = {"Authorization": f"Bearer {os.environ['TYPESAFE_API_KEY']}"}
    async with sem:
        for attempt in range(4):
            t0 = time.perf_counter()
            r = await client.post(URL, headers=headers, json=body, timeout=30)
            dt = time.perf_counter() - t0
            if r.status_code in (429, 529):
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code != 200:
                return {"error": f"{r.status_code}: {r.text[:300]}", "_latency": dt}
            d = r.json()
            d["_latency"] = dt
            d["_cached"] = False
            CACHE.mkdir(exist_ok=True)
            f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            return d
    return {"error": "rate-limited after retries", "_latency": 0}


def ece(pairs: list[tuple[float, bool]], bins: int = 10) -> float:
    """Expected calibration error over (confidence, correct) pairs."""
    if not pairs:
        return float("nan")
    buckets = defaultdict(list)
    for c, ok in pairs:
        buckets[min(int(c * bins), bins - 1)].append(ok)
    n = len(pairs)
    return sum(len(v) / n * abs(sum(v) / len(v) - ((b + 0.5) / bins)) for b, v in buckets.items())


def summarize(name: str, rows: list[dict]) -> dict:
    ok = [r for r in rows if "error" not in r]
    n = len(ok)
    if not n:
        return {"variant": name, "n": 0, "errors": len(rows)}
    hits = [r["pred"] == r["truth"] for r in ok]
    acc = sum(hits) / n
    confs = [r["conf"] if r["conf"] is not None else 1.0 for r in ok]
    pairs = list(zip(confs, hits))
    cov = {}
    for thr in (0.5, 0.7, 0.85, 0.95):
        sel = [h for c, h in pairs if c >= thr]
        cov[thr] = (len(sel) / n, (sum(sel) / len(sel)) if sel else float("nan"))
    lat = sorted(r["latency"] for r in ok if not r.get("cached"))
    tok = sum(r["in_tok"] for r in ok)
    conf_m = defaultdict(Counter)
    for r in ok:
        conf_m[r["truth"]][r["pred"]] += 1
    return {
        "variant": name, "n": n, "errors": len(rows) - n, "acc": acc, "ece": ece(pairs),
        "coverage": cov, "p50_ms": (lat[len(lat) // 2] * 1000) if lat else None,
        "p95_ms": (lat[int(len(lat) * 0.95)] * 1000) if lat else None,
        "in_tok": tok, "cost_usd": tok / 1e6 * PRICE_PER_MTOK,
        "confusion": {t: dict(c) for t, c in conf_m.items()},
        "misses": [r for r in ok if r["pred"] != r["truth"]],
    }


def fmt(s: dict) -> str:
    if not s.get("n"):
        return f"| {s['variant']} | 0 | errors={s.get('errors')} |"
    cov = " · ".join(f"@{t}: {c*100:.0f}%→{a*100:.0f}%" for t, (c, a) in s["coverage"].items())
    p50 = f"{s['p50_ms']:.0f}" if s["p50_ms"] else "cache"
    return (f"| `{s['variant']}` | {s['n']} | **{s['acc']*100:.1f}%** | {s['ece']:.3f} | {cov} | {p50} | "
            f"{s['in_tok']:,} / ${s['cost_usd']:.4f} |")


async def run_variant(task, name: str, records: list[dict], model: str, use_cache: bool, conc: int) -> list[dict]:
    questions = task.VARIANTS[name]
    raw_state = getattr(task, "STATE", lambda r, v: r["state"])
    state_fn = lambda r: raw_state(r, name)  # tasks may vary the state per variant
    sem = asyncio.Semaphore(conc)
    async with httpx.AsyncClient() as client:
        resps = await asyncio.gather(*(call(client, sem, model, state_fn(r), questions, use_cache) for r in records))
    out = []
    for r, d in zip(records, resps):
        if "error" in d:
            out.append({"id": r["id"], "error": d["error"]})
            continue
        pred, conf = task.derive(d["answers"], name)
        out.append({
            "id": r["id"], "truth": r["labels"][task.LABEL], "pred": pred, "conf": conf,
            "answers": d["answers"], "latency": d["_latency"], "cached": d["_cached"],
            "in_tok": d.get("usage", {}).get("input_tokens", 0), "model": d.get("model"),
            "state": state_fn(r),
        })
    return out


def load_task(spec: str):
    """Load a task from a file path (tasks/linkdrop.py) or a dotted module name."""
    p = Path(spec)
    if p.suffix == ".py" and p.exists():
        import importlib.util
        mod_spec = importlib.util.spec_from_file_location(p.stem, p)
        mod = importlib.util.module_from_spec(mod_spec)
        mod_spec.loader.exec_module(mod)
        return mod
    return importlib.import_module(spec)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, help="path to task .py (or dotted module)")
    ap.add_argument("--gold", required=True)
    ap.add_argument("--variant", action="append")
    ap.add_argument("--model", default="jev-1.13.0")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=10)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--show-misses", type=int, default=6)
    args = ap.parse_args()

    task = load_task(args.task)
    records = [json.loads(l) for l in Path(args.gold).read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        records = records[: args.limit]
    names = args.variant or list(task.VARIANTS)
    print(f"task={args.task} gold={len(records)} model={args.model} variants={names}")

    RUNS.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    header = ("| variant | n | acc | ECE | coverage→acc at conf ≥ | p50 ms | in-tok / cost |\n"
              "|---|---|---|---|---|---|---|")
    lines = [header]
    for name in names:
        rows = asyncio.run(run_variant(task, name, records, args.model, not args.no_cache, args.concurrency))
        s = summarize(name, rows)
        print(fmt(s))
        lines.append(fmt(s))
        (RUNS / f"{stamp}-{Path(args.task).stem}-{name}.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
        if s.get("n"):
            print("   confusion:", {t: c for t, c in s["confusion"].items()})
            for m in s["misses"][: args.show_misses]:
                st = json.dumps(m["state"], ensure_ascii=False)[:90]
                print(f"   miss {m['id']}: truth={m['truth']} pred={m['pred']} conf={m['conf'] if m['conf'] is None else round(m['conf'],2)} | {st}")
    board = RUNS / "SCOREBOARD.md"
    with board.open("a", encoding="utf-8") as f:
        f.write(f"\n## {stamp} · task `{args.task}` · gold n={len(records)} · {args.model}\n\n" + "\n".join(lines) + "\n")
    print(f"\nappended to {board}")


if __name__ == "__main__":
    main()
