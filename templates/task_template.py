"""
Task template for jev_eval.py — copy to tasks/<name>.py and fill in.

A task = the question sets you want to compare (VARIANTS) + the code that turns Jev's answers
into your decision (derive) + which gold label to score against (LABEL).
Gold rows look like: {"id": "x1", "state": {...}, "labels": {"<LABEL>": "..."}}
"""

from __future__ import annotations

LABEL = "category"          # key inside record["labels"] to score against

WHO = ("One paragraph on who is asking and what the labels MEAN for them. This is the cheapest "
       "accuracy you will ever buy — it closed a 10-point recall gap in our tests.")

# v0: the naive version you'd write first (keep it — it's your baseline)
V0 = {"category": {"type": "choice", "instructions": "Which category?",
                   "criteria": {"a": None, "b": None, "other": None}}}

# v1: concrete situations + boundary cases per option; an 'other'/'unclear' escape
V1 = {"category": {
    "type": "choice",
    "instructions": f"{WHO} Based on `title` and `body`, which category fits best?",
    "criteria": {
        "a": "Concrete situations that are A. Include the borderline case people get wrong and say which way it goes.",
        "b": "Concrete situations that are B. Same.",
        "other": "Anything that fits neither, or where the text genuinely doesn't say.",
    },
}}

# v2: decomposition — narrow nouls/scores combined in code (when the whole is fuzzy but the parts are crisp)
V2 = {
    "mentions_x": {"type": "noul", "instructions": "Does the text explicitly mention X?"},
    "urgency": {"type": "score", "instructions": "How urgent is this?",
                "criteria": ["Can wait; no time pressure", "Needs a reply this week", "Needs action today"]},
}

VARIANTS = {"v0_bare": V0, "v1_rich": V1, "v2_fanout": V2}


def STATE(record: dict, variant: str):
    """Optionally vary the state per variant (title-only vs title+body). Keep it small and relevant."""
    return record["state"]


def derive(answers: dict, variant: str) -> tuple[str, float | None]:
    """Return (prediction, confidence). Code owns the decision; Jev supplies the judgments."""
    if variant in ("v0_bare", "v1_rich"):
        a = answers["category"]
        return a["choice"], a.get("confidence")
    if variant == "v2_fanout":
        x = answers["mentions_x"]["noul"]
        u = answers["urgency"]["score"]
        pred = "a" if x >= 0.6 and u >= 1.0 else "b"
        return pred, abs(x - 0.5) * 2  # derive a usable confidence for gating
    raise KeyError(variant)
