"""Regenerate the README visuals with OpenAI gpt-image-2 (edit mode, Frankie404 reference images).

Prompts live in prompts.json next to this file. Self-contained: only `requests` is needed
(`pip install requests`) plus OPENAI_API_KEY in the environment.

Usage:  OPENAI_API_KEY=... python assets/generate.py [hero ...]

Reference images go in assets/_refs (gitignored) — copy them from the Robot Friends brand kit:
frankie-front.png, frankie-designref.png, frankie-presenting.png, rf-smiley-logo.png.
Every run appends a record to assets/gpt-image-2-manifest.json (gitignored).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover
    sys.exit("generate.py needs the `requests` package: pip install requests")

HERE = Path(__file__).parent
PROMPTS = json.loads((HERE / "prompts.json").read_text(encoding="utf-8"))
REFS = [HERE / "_refs" / n for n in ("frankie-front.png", "frankie-designref.png", "frankie-presenting.png", "rf-smiley-logo.png")]
MANIFEST = HERE / "gpt-image-2-manifest.json"
API = "https://api.openai.com/v1/images/edits"
MODEL = os.environ.get("GPT_IMAGE_MODEL", "gpt-image-2")


def generate(name: str) -> str:
    spec = PROMPTS["images"][name]
    prompt = f"{spec['prompt']}\n\nMASCOT SPEC: {PROMPTS['frankie']}\n\nSTYLE: {PROMPTS['style']}"
    out = HERE / f"{name}.png"
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("OPENAI_API_KEY is not set")
    missing = [str(r) for r in REFS if not r.exists()]
    if missing:
        sys.exit("missing reference images (see docstring): " + ", ".join(missing))

    t0 = time.time()
    handles = [r.open("rb") for r in REFS]
    try:
        files = [("image[]", (r.name, fh, "image/png")) for r, fh in zip(REFS, handles)]
        data = {"model": MODEL, "prompt": prompt, "size": spec["size"], "quality": spec.get("quality", "high"), "n": "1"}
        resp = requests.post(API, headers={"Authorization": f"Bearer {key}"}, data=data, files=files, timeout=400)
    finally:
        for fh in handles:
            fh.close()
    elapsed = round(time.time() - t0, 1)

    record = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "image": name, "model": MODEL, "size": spec["size"],
              "elapsed_s": elapsed, "ok": resp.status_code == 200, "prompt": prompt}
    if resp.status_code != 200:
        record["error"] = resp.text[:500]
        _log(record)
        return f"== {name}: FAIL HTTP {resp.status_code}: {resp.text[:300]}"
    item = resp.json()["data"][0]
    if "b64_json" in item:
        import base64
        out.write_bytes(base64.b64decode(item["b64_json"]))
    else:
        out.write_bytes(requests.get(item["url"], timeout=60).content)
    _log(record)
    return f"== {name}: OK {elapsed}s · {out.stat().st_size // 1024}KB · {out}"


def _log(record: dict) -> None:
    existing = []
    if MANIFEST.exists():
        try:
            existing = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []
    existing.append(record)
    MANIFEST.write_text(json.dumps(existing, indent=2), encoding="utf-8")


if __name__ == "__main__":
    names = sys.argv[1:] or list(PROMPTS["images"])
    for n in names:
        print(generate(n), flush=True)
