// jev.ts - thin TypeScript client for TypeSafe's System One API (Jev). No dependencies.
// Server-side only: the key must never reach the browser. For a public tool, put this behind
// a route handler with rate limiting (see nextjs-route.ts).

export type Choice = { type: "choice"; instructions: string; criteria: Record<string, unknown> };
export type Score = { type: "score"; instructions: string; criteria: unknown[] };
export type Noul = { type: "noul"; instructions: string; criteria?: { true?: unknown; false?: unknown } };
export type Question = Choice | Score | Noul;

export type ChoiceAnswer = { type: "choice"; choice: string; confidence: number; probabilities: Record<string, number> };
export type ScoreAnswer = { type: "score"; score: number; confidence: number; probabilities: Record<string, number>; legend: Record<string, string> };
export type NoulAnswer = { type: "noul"; noul: number };

export type SystemOneResponse<Q extends Record<string, Question>> = {
  model: string;
  answers: { [K in keyof Q]: Q[K] extends Choice ? ChoiceAnswer : Q[K] extends Score ? ScoreAnswer : NoulAnswer };
  usage: { input_tokens: number; output_tokens: number };
};

const BASE = process.env.TYPESAFE_BASE_URL ?? "https://api.typesafe.ai";
const MODEL = process.env.TYPESAFE_MODEL ?? "jev-1.13.0"; // pin; move on your own schedule

export async function ask<Q extends Record<string, Question>>(
  state: unknown,
  questions: Q,
  opts: { model?: string; retries?: number; signal?: AbortSignal } = {},
): Promise<SystemOneResponse<Q>> {
  const key = process.env.TYPESAFE_API_KEY;
  if (!key) throw new Error("TYPESAFE_API_KEY is not set");
  const retries = opts.retries ?? 3;
  for (let attempt = 0; ; attempt++) {
    const res = await fetch(`${BASE}/v1/systemone`, {
      method: "POST",
      headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
      body: JSON.stringify({ model: opts.model ?? MODEL, state, questions }),
      signal: opts.signal,
    });
    if ((res.status === 429 || res.status === 529) && attempt < retries) {
      const ra = Number(res.headers.get("retry-after") ?? 0);
      await new Promise((r) => setTimeout(r, (ra || 1.5 * (attempt + 1)) * 1000));
      continue;
    }
    if (!res.ok) throw new Error(`Jev ${res.status}: ${(await res.text()).slice(0, 400)}`);
    return (await res.json()) as SystemOneResponse<Q>;
  }
}

/** Gated hybrid: returns Jev's answer when confident, else calls `fallback`. */
export async function decide<Q extends Record<string, Question>>(
  state: unknown,
  questions: Q,
  key: keyof Q,
  gate: number,
  fallback: (state: unknown) => Promise<string>,
  unclearOption?: string,
): Promise<{ label: string | number; confidence: number; source: "jev" | "fallback"; model: string }> {
  const r = await ask(state, questions);
  const a = r.answers[key] as ChoiceAnswer | ScoreAnswer;
  if (!("confidence" in a)) throw new Error("decide() needs a choice or score question");
  const label = "choice" in a ? a.choice : a.score;
  if (a.confidence >= gate && label !== unclearOption) return { label, confidence: a.confidence, source: "jev", model: r.model };
  return { label: await fallback(state), confidence: a.confidence, source: "fallback", model: r.model };
}
