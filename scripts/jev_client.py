"""
jev_client — a thin, dependency-light client for TypeSafe's System One API (Jev).

Why not the official SDK? You can use it (`pip install typesafe-sdk`). This file exists so a
project can call Jev with nothing but `httpx`, pin a model version, log usage, and run the
gated hybrid pattern in ~100 lines you can read. Copy it into your project or import it.

Env:  TYPESAFE_API_KEY  (required)   TYPESAFE_MODEL (optional, default jev-1.13.0)

Python:
    from jev_client import Jev
    jev = Jev()                                  # reads env
    r = jev.ask(state={"title": "..."}, questions={"bucket": {"type": "choice", ...}})
    r.answers["bucket"]["choice"], r.answers["bucket"]["confidence"], r.usage, r.model

    # gated hybrid: Jev if confident, else your fallback (LLM / human queue)
    label = jev.decide(state, questions, key="bucket", gate=0.85, fallback=lambda s: call_llm(s))

CLI:
    python jev_client.py ask --state '{"title":"Claude Code hooks"}' --questions questions.json
    python jev_client.py ask --state-file record.json --questions questions.json --model jev-1.13.0
    python jev_client.py models
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

API = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai")
DEFAULT_MODEL = os.environ.get("TYPESAFE_MODEL", "jev-1.13.0")  # pin; move aliases on your schedule
PRICE_PER_MTOK = 0.042  # input tokens; output is free (2026-09)


@dataclass
class Result:
    answers: dict[str, Any]
    model: str
    usage: dict[str, int]
    latency_s: float
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @property
    def cost_usd(self) -> float:
        return self.usage.get("input_tokens", 0) / 1e6 * PRICE_PER_MTOK


class JevError(RuntimeError):
    pass


class Jev:
    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL, timeout: float = 15.0, retries: int = 3):
        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY")
        if not self.api_key:
            raise JevError("TYPESAFE_API_KEY is not set (console.typesafe.ai/keys)")
        self.model, self.timeout, self.retries = model, timeout, retries
        self._client = httpx.Client(timeout=timeout)

    def ask(self, state: Any, questions: dict[str, dict], model: str | None = None) -> Result:
        body = {"model": model or self.model, "state": state, "questions": questions}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        last = None
        for attempt in range(self.retries + 1):
            t0 = time.perf_counter()
            r = self._client.post(f"{API}/v1/systemone", headers=headers, json=body)
            dt = time.perf_counter() - t0
            if r.status_code in (429, 529):
                retry_after = float(r.headers.get("retry-after", 0) or 0)
                time.sleep(retry_after or 1.5 * (attempt + 1))
                last = r
                continue
            if r.status_code != 200:
                raise JevError(f"{r.status_code}: {r.text[:400]}")
            d = r.json()
            return Result(answers=d["answers"], model=d.get("model", ""), usage=d.get("usage", {}), latency_s=dt, raw=d)
        raise JevError(f"rate-limited after {self.retries} retries: {last.status_code if last else '?'}")

    def decide(self, state: Any, questions: dict[str, dict], key: str, gate: float,
               fallback: Callable[[Any], Any] | None = None, unclear_option: str | None = None) -> tuple[Any, float, str]:
        """Gated hybrid. Returns (label, confidence, source) where source is 'jev' or 'fallback'.
        - `key` must be a Choice or Score question (they carry `confidence`; a Noul does not).
        - If confidence < gate, or the answer equals `unclear_option`, call `fallback(state)`.
        """
        r = self.ask(state, questions)
        a = r.answers[key]
        conf = a.get("confidence")
        if conf is None:
            raise JevError("decide() needs a choice or score question; nouls have no confidence")
        label = a.get("choice", a.get("score"))
        if conf >= gate and label != unclear_option:
            return label, conf, "jev"
        if fallback is None:
            return label, conf, "jev-low-confidence"
        return fallback(state), conf, "fallback"

    def models(self) -> list[dict]:
        r = self._client.get(f"{API}/v1/models", headers={"Authorization": f"Bearer {self.api_key}"})
        r.raise_for_status()
        return r.json().get("models", [])


def _main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask")
    a.add_argument("--state", help="JSON string or plain text")
    a.add_argument("--state-file")
    a.add_argument("--questions", required=True, help="path to a questions JSON file")
    a.add_argument("--model", default=DEFAULT_MODEL)
    sub.add_parser("models")
    args = ap.parse_args()

    jev = Jev(model=getattr(args, "model", DEFAULT_MODEL))
    if args.cmd == "models":
        print(json.dumps(jev.models(), indent=1))
        return
    if args.state_file:
        raw = open(args.state_file, encoding="utf-8").read()
    else:
        raw = args.state or sys.stdin.read()
    try:
        state = json.loads(raw)
    except json.JSONDecodeError:
        state = raw
    questions = json.load(open(args.questions, encoding="utf-8"))
    r = jev.ask(state, questions)
    print(json.dumps({"model": r.model, "answers": r.answers, "usage": r.usage,
                      "latency_ms": round(r.latency_s * 1000), "cost_usd": round(r.cost_usd, 6)}, indent=1))


if __name__ == "__main__":
    _main()
