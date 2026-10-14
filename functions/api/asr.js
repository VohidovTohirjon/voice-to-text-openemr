/**
 * Speech endpoint for the hosted demo.
 *
 * Receives a short 16 kHz WAV recording plus the clinical vocabulary prompt,
 * runs it through Whisper on Cloudflare Workers AI, and returns the text with
 * per-segment statistics. The recording is never stored or logged.
 */
const MODEL = "@cf/openai/whisper-large-v3-turbo";
// 90 s of 16 kHz, 16-bit mono is about 2.9 MB.
const MAX_BYTES = 3700000;

const HEADERS = {
  "Content-Type": "application/json",
  "Cache-Control": "no-store",
  "X-Robots-Tag": "noindex, nofollow",
  "X-Content-Type-Options": "nosniff"
};

function reply(body, status) {
  return new Response(JSON.stringify(body), { status: status || 200, headers: HEADERS });
}

function toBase64(bytes) {
  let text = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    text += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return btoa(text);
}

function isWav(bytes) {
  const tag = (start) => String.fromCharCode(bytes[start], bytes[start + 1], bytes[start + 2], bytes[start + 3]);
  return bytes.length > 44 && tag(0) === "RIFF" && tag(8) === "WAVE";
}

// Free-tier Workers AI has a daily allowance, and this endpoint is reachable by
// anyone with the link. Two counters keep a stray script from using it up:
// recordings per network per hour, and recordings per data centre per day.
// They live in the edge cache, so no key or database is needed. They are
// approximate (not atomic, and per data centre), which is enough for a demo.
const PER_IP_PER_HOUR = 15;
const PER_REGION_PER_DAY = 150;

async function checkLimits(request, env) {
  const hourly = Number(env.RATE_LIMIT_PER_HOUR) || PER_IP_PER_HOUR;
  const daily = Number(env.RATE_LIMIT_PER_DAY) || PER_REGION_PER_DAY;
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const now = Date.now();
  const counters = [
    { key: `https://limits.invalid/ip/${ip}/${Math.floor(now / 3600000)}`, limit: hourly, ttl: 3600 },
    { key: `https://limits.invalid/day/${Math.floor(now / 86400000)}`, limit: daily, ttl: 86400 }
  ];
  try {
    const cache = caches.default;
    for (const counter of counters) {
      const hit = await cache.match(new Request(counter.key));
      counter.count = hit ? Number(await hit.text()) || 0 : 0;
      if (counter.count >= counter.limit) {
        return { allowed: false, retryAfter: counter.ttl };
      }
    }
    for (const counter of counters) {
      await cache.put(new Request(counter.key), new Response(String(counter.count + 1), {
        headers: { "Cache-Control": `max-age=${counter.ttl}` }
      }));
    }
  } catch (error) {
    // A broken cache must not take the demo down with it.
    console.error("rate limit check failed:", error && error.message);
  }
  return { allowed: true };
}

export async function onRequestPost({ request, env }) {
  const origin = request.headers.get("Origin");
  if (origin && origin !== new URL(request.url).origin) {
    return reply({ detail: "Not allowed." }, 403);
  }
  if (!env.AI) {
    return reply({ detail: "The speech service is not configured." }, 503);
  }
  if (Number(request.headers.get("Content-Length") || 0) > MAX_BYTES + 20000) {
    return reply({ detail: "The recording is too long." }, 413);
  }

  let form;
  try {
    form = await request.formData();
  } catch (error) {
    return reply({ detail: "Expected a multipart upload." }, 400);
  }

  const audio = form.get("audio");
  if (!audio || typeof audio === "string") {
    return reply({ detail: "No audio was sent." }, 400);
  }
  const bytes = new Uint8Array(await audio.arrayBuffer());
  if (bytes.length > MAX_BYTES) {
    return reply({ detail: "The recording is too long." }, 413);
  }
  if (bytes.length < 4000 || !isWav(bytes)) {
    return reply({ detail: "The recording could not be read." }, 400);
  }

  const limits = await checkLimits(request, env);
  if (!limits.allowed) {
    return new Response(JSON.stringify({
      detail: "Too many recordings from your network for now. Use Demo text, or try again later."
    }), { status: 429, headers: { ...HEADERS, "Retry-After": String(limits.retryAfter) } });
  }

  const prompt = String(form.get("prompt") || "").slice(0, 1500);
  const input = {
    audio: toBase64(bytes),
    task: "transcribe",
    language: "en",
    // A rambling loop is the typical Whisper failure on long audio; each
    // segment is decoded on its own so one bad stretch cannot feed the next.
    condition_on_previous_text: false
  };
  if (prompt) {
    input.initial_prompt = prompt;
  }

  try {
    const result = await env.AI.run(MODEL, input);
    const info = result.transcription_info || {};
    return reply({
      text: String(result.text || "").trim(),
      language: info.language || "en",
      duration: info.duration,
      segments: (result.segments || []).map((segment) => ({
        start: segment.start,
        end: segment.end,
        text: segment.text,
        avg_logprob: segment.avg_logprob,
        compression_ratio: segment.compression_ratio,
        no_speech_prob: segment.no_speech_prob
      }))
    });
  } catch (error) {
    console.error("speech model failed:", error && error.message);
    return reply({ detail: "The speech model could not process this recording." }, 502);
  }
}

export function onRequest() {
  return reply({ detail: "Use POST." }, 405);
}
