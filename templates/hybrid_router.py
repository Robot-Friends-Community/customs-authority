"""
The production shape: Jev answers when it is confident, otherwise an LLM (or a human queue) does.
On our gold set this beat everything: Jev@0.85 handled 64% of rows at 99%, Sonnet took the rest,
blended 95.4% vs 96.3% for Sonnet alone - with 64% fewer LLM calls.

Drop this next to jev_client.py. Replace `llm_decide` with your own call.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from jev_client import Jev

log = logging.getLogger("jev.router")

QUESTIONS = json.load(open("questions.json", encoding="utf-8"))   # the evaluated, versioned question set
KEY = "bucket"        # the choice/score question whose confidence gates the route
GATE = 0.85           # pick it from your scoreboard's coverage->accuracy curve, never by feel
UNCLEAR = "unclear"   # optional escape option in the criteria; None if you don't use one


def llm_decide(state: dict[str, Any]) -> str:
    """Your fallback. Same criteria text, asked of an LLM - or push to a human review queue."""
    raise NotImplementedError


def route(state: dict[str, Any], jev: Jev) -> dict[str, Any]:
    label, conf, source = jev.decide(state, QUESTIONS, key=KEY, gate=GATE, fallback=llm_decide, unclear_option=UNCLEAR)
    log.info("route label=%s conf=%.3f source=%s", label, conf, source)
    return {"label": label, "confidence": conf, "source": source}


if __name__ == "__main__":
    jev = Jev()  # pins TYPESAFE_MODEL / jev-1.13.0; log r.model in production so alias moves are visible
    print(route({"title": "Claude Code hooks, explained simply", "url": "https://youtu.be/x"}, jev))
