"""Regenerate the README visuals with gpt-image-2 (edit mode, Frankie404 refs). Prompts live in prompts.json.
Usage: OPENAI_API_KEY=... python assets/generate.py [hero how-it-works three-clerks]
Refs come from assets/_refs (gitignored) — copy them from the Robot Friends brand kit mascot/turnaround + smiley logo.
"""
import json, subprocess, sys, os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

HERE = Path(__file__).parent
GEN = Path.home() / ".claude/skills/gpt-image-2-generator/generate.py"
P = json.loads((HERE / "prompts.json").read_text(encoding="utf-8"))
REFS = [HERE / "_refs" / n for n in ("frankie-front.png", "frankie-designref.png", "frankie-presenting.png", "rf-smiley-logo.png")]
names = sys.argv[1:] or list(P["images"])


def run(name: str) -> str:
    spec = P["images"][name]
    prompt = f"{spec['prompt']}\n\nMASCOT SPEC: {P['frankie']}\n\nSTYLE: {P['style']}"
    out = HERE / f"{name}.png"
    cmd = [sys.executable, str(GEN), "--prompt", prompt, "--output", str(out), "--size", spec["size"], "--quality", "high",
           "--refs", *[str(r) for r in REFS]]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)
    return f"== {name}: rc={r.returncode}\n{r.stdout[-600:]}\n{r.stderr[-600:]}"


with ThreadPoolExecutor(3) as ex:
    for line in ex.map(run, names):
        print(line, flush=True)
