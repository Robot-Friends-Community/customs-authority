// app/api/decide/route.ts - a minimal server-side proxy so a PUBLIC tool can use Jev
// without exposing the key. Jev's input is text, so validate + cap it, and rate-limit by IP:
// a free tool on a public page is exactly where a cost cap matters.

import { NextRequest, NextResponse } from "next/server";
import { ask } from "@/lib/jev";
import questions from "@/lib/questions.json"; // the evaluated, versioned question set - never built from user input

const MAX_STATE_CHARS = 4000;
const LIMIT = 60;
const WINDOW_MS = 60_000;
const hits = new Map<string, { n: number; t: number }>(); // swap for Upstash/KV in production

function limited(ip: string): boolean {
  const now = Date.now();
  const h = hits.get(ip);
  if (!h || now - h.t > WINDOW_MS) {
    hits.set(ip, { n: 1, t: now });
    return false;
  }
  h.n += 1;
  return h.n > LIMIT;
}

export async function POST(req: NextRequest) {
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0] ?? "anon";
  if (limited(ip)) return NextResponse.json({ error: "rate limited" }, { status: 429 });
  const body = await req.json().catch(() => null);
  const text = typeof body?.text === "string" ? body.text.slice(0, MAX_STATE_CHARS) : "";
  if (!text) return NextResponse.json({ error: "text required" }, { status: 400 });
  try {
    const r = await ask({ text }, questions as never);
    // Return only what the UI needs; probabilities are fine to show - confidence is the product.
    return NextResponse.json({ answers: r.answers, model: r.model });
  } catch {
    return NextResponse.json({ error: "decision service unavailable" }, { status: 502 });
  }
}
