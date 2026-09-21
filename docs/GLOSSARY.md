# Glossary

Plain-language definitions of every term the kit uses. The officer (`/customs`) glosses these
inline in guided mode; experts can skip.

| Term | Plain meaning | Where it shows up |
|---|---|---|
| **Jev** | TypeSafe AI's model. Not a chatbot: you give it text plus multiple-choice questions, it gives back answers with a confidence, in ~100 ms. It can't write or reason. | everywhere |
| **System One / System Two** | Kahneman's two modes of thinking. System One = fast, intuitive judgment ("this email is a complaint"). System Two = slow, deliberate reasoning ("draft the reply"). Jev is a System One model; LLMs are System Two. | `/jev-playbook`, `/jev-fit` |
| **snap judgment** | A System One answer: fast, bounded, with a confidence attached. The kit's job is to make sure the snap judgments you ship are the ones that deserve to be. | the name |
| **state** | The text you send to be judged — a string, or a small JSON object with named fields (`title`, `body`, `platform`). Keep it small and relevant. | `/jev-design` |
| **question** | One typed question about the state. Three types: `choice`, `score`, `noul`. You can send several in one request. | `/jev-design` |
| **choice** | "Which one of these?" — pick one label from a list you define (≤255 options). Returns the label, a confidence, and the probability of each option. | most classifiers, routers |
| **score** | "How much?" — an ordered scale you define with concrete rungs (low → high). Returns the level and a confidence. | urgency, severity, relevance |
| **noul** | "Yes or no?" — a proposition; returns P(yes) as a number 0–1. No separate confidence field, so gate on the value with a dead band. | flags, guardrails |
| **criteria** | The text under each option that says *what it means*, as concrete situations and boundary cases. **This is where accuracy comes from** — in our evals it moved a task from 70% to 90% with nothing else changed. | `/jev-design` |
| **instructions** | The question's stem. Include the `WHO` preamble and name the state fields you want it to look at. | `/jev-design` |
| **WHO preamble** | 2–4 sentences at the front of the instructions saying who is asking and what the labels mean *for them*. Cheapest accuracy you'll buy. | `/jev-design` |
| **escape option** | An `other` / `unclear` choice so the model isn't forced to pick a wrong label confidently. Jev uses it honestly. | `/jev-design` |
| **decomposition / fan-out** | Instead of one fuzzy question, ask several narrow ones (people would agree on each) and combine the answers in code. | `/jev-design` |
| **derive()** | Your code that turns Jev's answers into the final decision and a confidence to gate on. Code owns the decision; Jev supplies the judgments. | `task.py` |
| **confidence** | How sure Jev is about a `choice` or `score` answer, 0–1. Calibrated: 0.9 should be right ~90% of the time. **The product** — it's what lets your code decide when to act and when to escalate. | everywhere |
| **calibration / ECE** | Whether the confidence numbers mean what they say. ECE (expected calibration error) below ~0.1 = trustworthy gate. | scoreboard |
| **gate** | The confidence threshold you set. At or above it, Jev's answer is used (**CLEARED**); below it, the item goes to the fallback (**Secondary Inspection**). | `/jev-eval`, `/jev-integrate` |
| **coverage → accuracy** | The scoreboard row that decides the gate. `@0.85: 64%→99%` means: at gate 0.85, Jev clears 64% of items on its own and is right on 99% of those. | scoreboard |
| **hybrid** | Jev where it's confident, an LLM or a person for the rest. The number to report and the thing to ship. Ours: 95.4% accuracy with 64% fewer LLM calls. | `/jev-integrate` |
| **fallback / Secondary Inspection** | Where low-confidence items go: an LLM call with the *same criteria*, or a human queue. A gate without a fallback is just a worse classifier. | `/jev-integrate` |
| **gold set** | The answer key: ~100 real examples with the label a human gave. Stored as `gold.jsonl`. Without it you can't measure anything. | `/jev-label`, `/jev-eval` |
| **label** | The human's answer for one gold row. The model can only be as good as the labels; if two people disagree 20% of the time, no model will beat ~80%. | `/jev-label` |
| **agreement / kappa** | How often two labelers agree, corrected for chance (Cohen's κ). Sets the ceiling for any model on that task. κ > 0.8 = crisp task; < 0.6 = fix the taxonomy first. | `/jev-label` |
| **variant** | One version of a question set (`v0_bare`, `v1_rich`…). The harness scores every variant so you can see what each change bought. | `task.py`, scoreboard |
| **scoreboard** | `runs/SCOREBOARD.md` — accuracy, ECE, coverage→accuracy per gate, latency, cost, per variant. Rule of the kit: nothing ships without one. | `/jev-eval` |
| **reference model / ceiling** | Claude (or another LLM) run on the same criteria, to see the best achievable number and to compute the hybrid. | `llm_reference.py` |
| **model pin** | Using an exact version (`jev-1.13.0`) instead of an alias (`jev-latest`) so the gate you tuned keeps meaning what it meant. Re-eval when you move it. | `DESIGN.md`, `TYPESAFE_MODEL` |
| **drift** | The API answering with a different model version than you pinned, or production confidences shifting over time. Both mean: re-run `/jev-eval`. | `/customs status` |
| **jaggedness** | The model's documented unevenness: great at bounded judgment over text, bad at arithmetic, dates, counting, multi-hop, adversarial input. Move those parts to code or the LLM. | `/jev-playbook` |
| **three clerks** | The kit's mental model: **code** for rules, **Jev** for narrow judgment, **LLM** for reasoning and words. Every step in a system goes to one of the three. | `/jev-fit` |
