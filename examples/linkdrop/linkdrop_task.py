"""
Task: linkdrop — is a saved link WORK (feed the studio's exploration queue) or PERSONAL?
Gold: gold/linkdrop.jsonl (108 links from Richard's 2026-09-01 WhatsApp sweep, labeled by him).

Variants walk the optimization levers one at a time:
  v0_bare_choice       naive 2-way choice, no criteria text            (baseline)
  v1_choice_desc       2-way choice, one-line descriptions
  v2_choice_rich       2-way choice, concrete situations + boundary cases + who we are
  v2b_rich_title_only  same as v2 but state = title only               (state-design lever)
  v3_noul              one noul "is this work-relevant", threshold 0.5 (absolute vs relative)
  v4_fanout            7 topic nouls -> code decides                   (decomposition lever)
  v5_topic_choice      10-way topic choice -> code maps to bucket      (finer choice, coarse answer)
"""

from __future__ import annotations

LABEL = "bucket"

WHO = ("The link was saved by the founder of a small AI-native software + creative studio "
       "(Claude Code, AI agents, web builds, brand/design, marketing, growth, a toy business with "
       "China sourcing). WORK = anything he would explore, build with, or use for the studio or its "
       "clients. PERSONAL = saved for his own life: cooking, music, history, politics, philosophy, "
       "home/DIY, fitness, gaming, entertainment, shopping.")

V0 = {"bucket": {"type": "choice", "instructions": "Is this saved link work or personal?",
                 "criteria": {"work": None, "personal": None}}}

V1 = {"bucket": {"type": "choice", "instructions": "Is this saved link work-related or personal?",
                 "criteria": {"work": "About software, AI tools, business, marketing, design, or building products",
                              "personal": "About food, music, history, hobbies, home, health, or entertainment"}}}

V2 = {"bucket": {
    "type": "choice",
    "instructions": f"{WHO} Based on `title` (and `url` if the title is uninformative), was this link saved for WORK or for PERSONAL life?",
    "criteria": {
        "work": ("Claude Code, AI agents, coding tools, skills/plugins, prompts, evals, dev workflows; "
                 "website/app building, hosting, no-code tools; business, marketing, growth, branding, "
                 "ads strategy, commerce, pricing; sourcing/manufacturing/China suppliers; creative-AI, "
                 "motion, design references; talks by AI/business figures. A recipe VIDEO ABOUT running a "
                 "food business is still work; a recipe to cook is personal."),
        "personal": ("Recipes and cooking; griddles and kitchen gear; music samples, DJ, jazz lessons; "
                     "history, politics, culture, documentaries; philosophy and mindset; home DIY, gadgets, "
                     "restoration; health, fitness, personal money; gaming; comedy, memes, viral clips; "
                     "products to buy for himself. A short about 'AI' that is a joke or a meme is personal."),
    },
}}

V3 = {"is_work": {"type": "noul",
                  "instructions": f"{WHO} Is this link something he saved for WORK (the studio, its clients, or building things) rather than for his personal life?",
                  "criteria": {"true": "He would explore it, build with it, or use it for the studio or a client.",
                               "false": "It is for cooking, music, history/politics/philosophy, home, health, gaming, or entertainment."}}}

TOPICS = {
    "ai_dev": ("work", "Claude Code, AI agents, coding tools, skills, plugins, prompts, evals, developer workflows, AI research papers"),
    "web_build": ("work", "building websites or apps, hosting, deployment, no-code/low-code tools, productivity software for work"),
    "business": ("work", "business strategy, marketing, growth, branding, advertising, commerce, pricing, startups, founders, sales"),
    "sourcing": ("work", "manufacturing, product sourcing, China suppliers, factories, toy or physical-product production"),
    "creative_ai": ("work", "AI image/video generation, motion design, design references, creative tooling for client work"),
    "food": ("personal", "recipes, cooking techniques, restaurants, kitchen gear, griddles, food travel"),
    "music": ("personal", "music samples, DJ, jazz, music lessons, songs, producers"),
    "culture": ("personal", "history, politics, current events, culture, documentaries, philosophy, mindset, self-improvement"),
    "home_life": ("personal", "home DIY, gadgets, restoration, fitness, health, personal finance, shopping for himself"),
    "fun": ("personal", "gaming, comedy, memes, viral clips, entertainment"),
}

V4 = {k: {"type": "noul", "instructions": f"Is this link mainly about: {desc}?"} for k, (_, desc) in TOPICS.items()}

V5 = {"topic": {"type": "choice",
                "instructions": f"{WHO} Which topic best describes this saved link?",
                "criteria": {k: desc for k, (_, desc) in TOPICS.items()}}}

import copy
V6 = copy.deepcopy(V2)
V6["bucket"]["criteria"]["unclear"] = ("The title alone does not say which; it could plausibly be either (generic self-improvement, "
                                       "'free tools', news about big tech, money tips, productivity hacks).")
V6["bucket"]["instructions"] += " If the title genuinely does not settle it, answer unclear."

# ensemble: rich choice + absolute noul; agree -> answer, disagree -> unclear
V7 = {**copy.deepcopy(V2), **copy.deepcopy(V3)}

VARIANTS = {
    "v0_bare_choice": V0,
    "v1_choice_desc": V1,
    "v2_choice_rich": V2,
    "v2b_rich_title_only": V2,
    "v3_noul": V3,
    "v4_fanout": V4,
    "v5_topic_choice": V5,
    "v6_rich_plus_unclear": V6,
    "v7_ensemble_choice_noul": V7,
}


def STATE(record: dict, variant: str):
    if variant == "v2b_rich_title_only":
        return {"title": record["state"]["title"]}
    return record["state"]


def derive(answers: dict, variant: str) -> tuple[str, float | None]:
    if variant in ("v0_bare_choice", "v1_choice_desc", "v2_choice_rich", "v2b_rich_title_only"):
        a = answers["bucket"]
        return a["choice"], a.get("confidence")
    if variant == "v3_noul":
        p = answers["is_work"]["noul"]
        return ("work" if p >= 0.5 else "personal"), abs(p - 0.5) * 2
    if variant == "v4_fanout":
        work = max(answers[k]["noul"] for k, (b, _) in TOPICS.items() if b == "work")
        pers = max(answers[k]["noul"] for k, (b, _) in TOPICS.items() if b == "personal")
        return ("work" if work > pers else "personal"), abs(work - pers)
    if variant == "v6_rich_plus_unclear":
        a = answers["bucket"]
        return a["choice"], a.get("confidence")  # 'unclear' scores as a miss but is meant to be routed
    if variant == "v7_ensemble_choice_noul":
        c = answers["bucket"]; p = answers["is_work"]["noul"]
        n = "work" if p >= 0.5 else "personal"
        if c["choice"] == n:
            return c["choice"], max(c.get("confidence") or 0, abs(p - 0.5) * 2)
        return "unclear", 0.0
    if variant == "v5_topic_choice":
        a = answers["topic"]
        return TOPICS[a["choice"]][0], a.get("confidence")
    raise KeyError(variant)
