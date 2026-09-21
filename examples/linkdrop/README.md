# Example: linkdrop — is a saved link work or personal?

The task that produced the numbers in the README. Input = what a Slack/WhatsApp unfurl gives
you (title + URL + platform derived in code). Gold = 108 links one founder actually triaged
(37 work / 71 personal), ambiguous rows excluded.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/jev_eval.py" --task linkdrop_task.py --gold linkdrop_gold.jsonl
python "${CLAUDE_PLUGIN_ROOT}/scripts/llm_reference.py" --task linkdrop_task.py --gold linkdrop_gold.jsonl --variant v2_choice_rich --model sonnet
```

`linkdrop_task.py` walks the optimization ladder one lever per variant (bare → one-line
criteria → rich criteria + WHO → title-only state → noul → fan-out → topic choice → `unclear`
escape → ensemble). `SCOREBOARD.md` is the recorded output. The `WHO` preamble is specific to
the founder who labeled the set — rewrite it for yours; that's the point.
