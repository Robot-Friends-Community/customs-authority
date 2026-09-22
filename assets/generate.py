"""Regenerate the README visuals with OpenAI gpt-image-2 (edit mode, Frankie404 reference images).

Prompts live in prompts.json next to this file. Self-contained: only `requests` is needed
(`pip install requests`) plus OPENAI_API_KEY in the environment.

Usage:  OPENAI_API_KEY=... python assets/generate.py [hero ...]

Reference images go in assets/_refs (gitignored) — copy them from the Robot Friends brand kit:
frankie-front.png, frankie-designref.png, frankie-presenting.png, rf-smiley-logo.png.

Setup problems (unknown image name, missing key, missing refs) are reported and stop the run
before anything is sent. Every API attempt — success or any failure after that point — appends a
record to assets/gpt-image-2-manifest.json (gitignored).
"""
from __future__ import annotations

import base64
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
PNG_SIGNATURE = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])


def check_setup(names: list[str]) -> str:
    """Return the API key, or exit with one clear message per setup problem (nothing is logged —
    no API attempt was made)."""
    problems = [f"unknown image name {n!r} (prompts.json has: {', '.join(PROMPTS['images'])})"
                for n in names if n not in PROMPTS["images"]]
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        problems.append("OPENAI_API_KEY is not set")
    problems += [f"missing reference image {r} (copy it from the Robot Friends brand kit)" for r in REFS if not r.exists()]
    if problems:
        sys.exit("generate.py cannot run:\n  - " + "\n  - ".join(problems))
    return key


def generate(name: str, key: str) -> str:
    spec = PROMPTS["images"][name]
    prompt = f"{spec['prompt']}\n\nMASCOT SPEC: {PROMPTS['frankie']}\n\nSTYLE: {PROMPTS['style']}"
    out = HERE / f"{name}.png"
    t0 = time.time()
    record = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "image": name, "model": MODEL, "size": spec["size"],
              "ok": False, "prompt": prompt}

    def done(msg: str, ok: bool = False) -> str:
        record.update(ok=ok, elapsed_s=round(time.time() - t0, 1))
        if not ok:
            record["error"] = msg[:500]
        _log(record)
        return f"== {name}: {'OK' if ok else 'FAIL'} {msg[:300]}"

    try:
        handles = [r.open("rb") for r in REFS]
        try:
            files = [("image[]", (r.name, fh, "image/png")) for r, fh in zip(REFS, handles)]
            data = {"model": MODEL, "prompt": prompt, "size": spec["size"], "quality": spec.get("quality", "high"), "n": "1"}
            resp = requests.post(API, headers={"Authorization": f"Bearer {key}"}, data=data, files=files, timeout=400)
        finally:
            for fh in handles:
                fh.close()
        if resp.status_code != 200:
            return done(f"HTTP {resp.status_code}: {resp.text}")
        item = resp.json()["data"][0]
        if "b64_json" in item:
            png = base64.b64decode(item["b64_json"], validate=True)
        elif "url" in item:
            dl = requests.get(item["url"], timeout=60)
            if dl.status_code != 200:
                return done(f"download returned HTTP {dl.status_code}")
            png = dl.content
        else:
            return done("no b64_json or url in response")
        if png[:8] != PNG_SIGNATURE:
            return done("response image is not a PNG")
        out.write_bytes(png)
        return done(f"{round(time.time() - t0, 1)}s · {out.stat().st_size // 1024}KB · {out}", ok=True)
    except Exception as e:  # request/DNS/timeout, bad JSON, bad base64, IO — all still get a record
        return done(f"{type(e).__name__}: {e}")


def _log(record: dict) -> None:
    existing = []
    if MANIFEST.exists():
        try:
            existing = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = []
        if not isinstance(existing, list):  # tolerate a hand-edited / foreign manifest
            existing = [existing]
    existing.append(record)
    MANIFEST.write_text(json.dumps(existing, indent=2), encoding="utf-8")


if __name__ == "__main__":
    names = sys.argv[1:] or list(PROMPTS["images"])
    api_key = check_setup(names)
    for n in names:
        print(generate(n, api_key), flush=True)
