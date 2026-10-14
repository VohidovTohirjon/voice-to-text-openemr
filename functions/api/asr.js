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
