"""
jev_label — build and check the answer key (gold set) for a Jev question set.

Three jobs:
  label   : walk through unlabeled rows in the terminal, show the state, ask for the label
            (numbered options), write gold.jsonl incrementally. Resumable. Blind by default
            (never shows a model's guess). Supports `?`/`u` for unclear, `s` skip, `q` quit.
  agree   : compare two labelers' files (or two label keys) → agreement %, Cohen's kappa,
            per-label confusion, and the rows they disagree on. That number is the ceiling any
            model can reach on this task.
  stats   : class balance, unclear share, rows per labeler, duplicates — the health of a gold set.
  import  : turn a CSV / JSONL export of already-made human decisions into gold.jsonl.

Gold row format (one per line):
  {"id": "x1", "state": {...}, "labels": {"<LABEL>": "..."}, "_labeler": "rv", "_note": ""}

Usage
  python jev_label.py label  --in candidates.jsonl --gold jev/inbox/gold.jsonl --label bucket --options work,personal,unclear --labeler rv
  python jev_label.py label  --in candidates.jsonl --gold gold.jsonl --questions jev/inbox/questions.json --labeler rv   # options from the question set
  python jev_label.py agree  --a gold.rv.jsonl --b gold.jon.jsonl --label bucket
  python jev_label.py stats  --gold gold.jsonl --label bucket
  python jev_label.py import --in decisions.csv --gold gold.jsonl --label bucket --id-col id --label-col decision --state-cols title,url

Candidates file: jsonl with at least {"id", "state"}; any existing "labels" are shown as "already labeled" and skipped
unless --relabel. A CSV works too (columns become state fields; --id-col picks the id).
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path


# ------------------------------------------------------------------ io

def read_rows(path: Path, id_col: str = "id", state_cols: list[str] | None = None) -> list[dict]:
    if path.suffix.lower() == ".csv":
        out = []
        with path.open(encoding="utf-8-sig", newline="") as f:
            for i, r in enumerate(csv.DictReader(f)):
                rid = r.get(id_col) or f"row-{i+1}"
                cols = state_cols or [c for c in r if c != id_col]
                out.append({"id": rid, "state": {c: r[c] for c in cols if c in r}, "_raw": r})
        return out
    rows = []
    for l in path.read_text(encoding="utf-8").splitlines():
        if l.strip():
            rows.append(json.loads(l))
    return rows


def append_row(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def options_from_questions(qpath: Path, label: str | None) -> tuple[str, list[str]]:
    qs = json.loads(qpath.read_text(encoding="utf-8"))
    key = label or next(iter(qs))
    q = qs[key]
    if q["type"] == "choice":
        return key, list(q["criteria"])
    if q["type"] == "score":
        return key, [str(i) for i in range(len(q["criteria"]))]
    if q["type"] == "noul":
        return key, ["yes", "no"]
    raise SystemExit(f"unknown question type {q['type']}")


# ------------------------------------------------------------------ label

def show_state(state, width: int = 100) -> None:
    if isinstance(state, dict):
        for k, v in state.items():
            s = str(v).replace("\n", " ")
            print(f"  {k:<12} {s[:width * 3]}")
    else:
        print("  " + str(state)[:width * 4])


def cmd_label(a: argparse.Namespace) -> None:
    src = read_rows(Path(a.inp), a.id_col, a.state_cols.split(",") if a.state_cols else None)
    if a.questions:
        label, options = options_from_questions(Path(a.questions), a.label)
    else:
        if not (a.label and a.options):
            raise SystemExit("need --questions, or --label + --options")
        label, options = a.label, a.options.split(",")
    gold = Path(a.gold)
    done = {r["id"] for r in read_rows(gold)} if gold.exists() else set()
    todo = [r for r in src if a.relabel or r["id"] not in done]
    if a.shuffle:
        random.Random(a.seed).shuffle(todo)
    if a.limit:
        todo = todo[: a.limit]
    print(f"\n{len(src)} candidates · {len(done)} already in {gold.name} · {len(todo)} to label · label=`{label}`")
    print("Blind mode: you see only the state. Type the number (or the label), `u` = unclear, `s` = skip, `n` = add a note, `q` = save & quit.\n")
    menu = "  ".join(f"[{i+1}] {o}" for i, o in enumerate(options))
    n_done = 0
    for r in todo:
        print(f"── {r['id']}  ({n_done + 1}/{len(todo)})")
        show_state(r["state"])
        note = ""
        while True:
            ans = input(f"  {menu}  [u]nclear [s]kip [n]ote [q]uit > ").strip()
            if ans == "q":
                print(f"\nsaved {n_done} rows to {gold}")
                return
            if ans == "s":
                break
            if ans == "n":
                note = input("  note: ").strip()
                continue
            if ans in ("u", "?"):
                choice = "unclear"
            elif ans.isdigit() and 1 <= int(ans) <= len(options):
                choice = options[int(ans) - 1]
            elif ans in options:
                choice = ans
            else:
                print("  ? try again")
                continue
            row = {"id": r["id"], "state": r["state"], "labels": {**r.get("labels", {}), label: choice},
                   "_labeler": a.labeler, "_note": note}
            append_row(gold, row)
            n_done += 1
            break
    print(f"\ndone · {n_done} rows written to {gold}")
    _stats(read_rows(gold), label)


# ------------------------------------------------------------------ agree

def kappa(pairs: list[tuple[str, str]]) -> float:
    n = len(pairs)
    if not n:
        return float("nan")
    po = sum(1 for x, y in pairs if x == y) / n
    ca, cb = Counter(x for x, _ in pairs), Counter(y for _, y in pairs)
    pe = sum((ca[k] / n) * (cb[k] / n) for k in set(ca) | set(cb))
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def cmd_agree(a: argparse.Namespace) -> None:
    ra = {r["id"]: r for r in read_rows(Path(a.a))}
    rb = {r["id"]: r for r in read_rows(Path(a.b))}
    la, lb = a.label, (a.label_b or a.label)
    common = [i for i in ra if i in rb and la in ra[i].get("labels", {}) and lb in rb[i].get("labels", {})]
    if not common:
        raise SystemExit("no rows with both labels — check --label / ids")
    pairs = [(str(ra[i]["labels"][la]), str(rb[i]["labels"][lb])) for i in common]
    if a.drop_unclear:
        pairs_c = [(x, y) for x, y in pairs if x != "unclear" and y != "unclear"]
    else:
        pairs_c = pairs
    agree = sum(1 for x, y in pairs_c if x == y) / len(pairs_c)
    k = kappa(pairs_c)
    print(f"\nrows compared: {len(pairs_c)} (of {len(common)} shared{' , unclear dropped' if a.drop_unclear else ''})")
    print(f"agreement: {agree*100:.1f}%   Cohen's kappa: {k:.2f}   → {interpret(k)}")
    print(f"\nThis is the ceiling: a model that matches labeler A will disagree with labeler B about {100 - agree*100:.0f}% of the time.")
    conf = defaultdict(Counter)
    for x, y in pairs_c:
        conf[x][y] += 1
    print("\nconfusion (rows = A, cols = B):")
    labels = sorted(set(x for x, _ in pairs_c) | set(y for _, y in pairs_c))
    print("  " + " " * 12 + "".join(f"{l[:10]:>11}" for l in labels))
    for x in labels:
        print(f"  {x[:12]:<12}" + "".join(f"{conf[x][y]:>11}" for y in labels))
    dis = [(i, ra[i]["labels"][la], rb[i]["labels"][lb]) for i in common
           if str(ra[i]["labels"][la]) != str(rb[i]["labels"][lb])]
    if dis:
        print(f"\ndisagreements ({len(dis)}), the first {min(a.show, len(dis))} — these are your boundary cases; put them in the criteria:")
        for i, x, y in dis[: a.show]:
            st = json.dumps(ra[i]["state"], ensure_ascii=False)[:100]
            print(f"  {i}: A={x}  B={y}  | {st}")
    if a.out:
        Path(a.out).write_text("\n".join(json.dumps({"id": i, "a": x, "b": y, "state": ra[i]["state"]}, ensure_ascii=False)
                                         for i, x, y in dis), encoding="utf-8")
        print(f"\ndisagreements written to {a.out}")


def interpret(k: float) -> str:
    if k != k:
        return "n/a"
    if k >= 0.8:
        return "crisp task — the labels are trustworthy; tune the criteria"
    if k >= 0.6:
        return "workable — but expect a ~10-20 pt ceiling; resolve the boundary cases in the criteria"
    if k >= 0.4:
        return "fuzzy — fix the taxonomy (merge/split labels, add unclear) before evaluating any model"
    return "the labelers don't share a definition — redesign the decision before anything else"


# ------------------------------------------------------------------ stats / import

def _stats(rows: list[dict], label: str) -> None:
    n = len(rows)
    ids = Counter(r["id"] for r in rows)
    dups = sum(1 for c in ids.values() if c > 1)
    labs = Counter(str(r.get("labels", {}).get(label, "<missing>")) for r in rows)
    who = Counter(r.get("_labeler", "?") for r in rows)
    print(f"\ngold: {n} rows · {len(ids)} unique ids{f' · {dups} DUPLICATED ids' if dups else ''}")
    print(f"label `{label}`: " + " · ".join(f"{k} {v} ({v/n*100:.0f}%)" for k, v in labs.most_common()))
    if "unclear" in labs and labs["unclear"] / n > 0.2:
        print("  ⚠️  >20% unclear — the decision may be too fuzzy, or the criteria need the boundary cases")
    top = labs.most_common(1)[0][1] / n
    print(f"majority baseline: {top*100:.0f}% (any model must beat this)")
    print("labelers: " + " · ".join(f"{k} {v}" for k, v in who.items()))
    if n < 100:
        print(f"  → {100 - n} more rows to reach 100")


def cmd_stats(a: argparse.Namespace) -> None:
    _stats(read_rows(Path(a.gold)), a.label)


def cmd_import(a: argparse.Namespace) -> None:
    src = Path(a.inp)
    gold = Path(a.gold)
    state_cols = a.state_cols.split(",") if a.state_cols else None
    rows = read_rows(src, a.id_col, state_cols)
    seen = {r["id"] for r in read_rows(gold)} if gold.exists() else set()
    n = 0
    for r in rows:
        raw = r.get("_raw", r)
        lab = raw.get(a.label_col) if isinstance(raw, dict) else None
        if lab is None and "labels" in r:
            lab = r["labels"].get(a.label_col)
        if lab in (None, "") or r["id"] in seen:
            continue
        if a.map:
            lab = dict(kv.split("=") for kv in a.map.split(",")).get(str(lab), lab)
        append_row(gold, {"id": r["id"], "state": r["state"], "labels": {a.label: lab}, "_labeler": a.labeler, "_note": "imported"})
        seen.add(r["id"])
        n += 1
    print(f"imported {n} rows into {gold}")
    _stats(read_rows(gold), a.label)


# ------------------------------------------------------------------ main

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    l = sub.add_parser("label", help="interactive blind labeling")
    l.add_argument("--in", dest="inp", required=True)
    l.add_argument("--gold", required=True)
    l.add_argument("--label")
    l.add_argument("--options", help="comma-separated; or use --questions")
    l.add_argument("--questions", help="questions.json to take label + options from")
    l.add_argument("--labeler", default="me")
    l.add_argument("--id-col", default="id")
    l.add_argument("--state-cols")
    l.add_argument("--relabel", action="store_true", help="label rows already in gold (for a second labeler / blind relabel)")
    l.add_argument("--shuffle", action="store_true")
    l.add_argument("--seed", type=int, default=7)
    l.add_argument("--limit", type=int, default=0)
    l.set_defaults(fn=cmd_label)

    g = sub.add_parser("agree", help="inter-labeler agreement + kappa")
    g.add_argument("--a", required=True)
    g.add_argument("--b", required=True)
    g.add_argument("--label", required=True)
    g.add_argument("--label-b", help="if B used a different label key")
    g.add_argument("--drop-unclear", action="store_true")
    g.add_argument("--show", type=int, default=15)
    g.add_argument("--out", help="write disagreements jsonl")
    g.set_defaults(fn=cmd_agree)

    s = sub.add_parser("stats", help="health of a gold set")
    s.add_argument("--gold", required=True)
    s.add_argument("--label", required=True)
    s.set_defaults(fn=cmd_stats)

    i = sub.add_parser("import", help="existing human decisions → gold.jsonl")
    i.add_argument("--in", dest="inp", required=True)
    i.add_argument("--gold", required=True)
    i.add_argument("--label", required=True, help="label key to write")
    i.add_argument("--label-col", required=True, help="source column / key holding the decision")
    i.add_argument("--id-col", default="id")
    i.add_argument("--state-cols")
    i.add_argument("--map", help="rename values, e.g. 'Yes=work,No=personal'")
    i.add_argument("--labeler", default="import")
    i.set_defaults(fn=cmd_import)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
