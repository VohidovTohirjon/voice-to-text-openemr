/**
 * Hosted-demo engine.
 *
 * The panel talks to "a service" over fetch(). On the hosted demo that service
 * is this file: it answers /analyze and /capabilities from the in-browser
 * Python engine, and /transcribe by sending a clean 16 kHz recording to the
 * speech endpoint. The panel code is identical to the Chrome extension's.
 */
(function () {
  var BASE = "/_engine";
  var MAX_SECONDS = 90;
  var TARGET_RATE = 16000;
  var DEPLOYMENT_NOTE =
    "Online demo: audio goes to Cloudflare Whisper to be transcribed and is not stored. " +
    "Analysis runs in this browser.";

  window.__OPENEMR_ASR_API_BASE = BASE;
  window.__OPENEMR_ASR_ANY_PAGE = true;
  // On a phone the panel is the whole point of this page, so it starts open.
  window.__OPENEMR_ASR_START_OPEN = true;

  var realFetch = window.fetch.bind(window);

  // ---- worker -------------------------------------------------------------

  var worker = null;
  var nextId = 1;
  var pending = {};

  function failAll(message) {
    Object.keys(pending).forEach(function (id) {
      pending[id].reject(new Error(message));
      delete pending[id];
    });
  }

  function getWorker() {
    if (worker) {
      return worker;
    }
    worker = new Worker("/engine-worker.js");
    worker.onmessage = function (event) {
      var reply = event.data;
      var waiting = pending[reply.id];
      if (!waiting) {
        return;
      }
      delete pending[reply.id];
      if (reply.ok) {
        waiting.resolve(reply.result);
      } else {
        waiting.reject(new Error(reply.error));
      }
    };
    worker.onerror = function () {
      worker = null;
      failAll("The analysis engine could not start. Check your connection and reload.");
    };
    return worker;
  }

  function call(op, payload) {
    return new Promise(function (resolve, reject) {
      var id = nextId++;
      pending[id] = { resolve: resolve, reject: reject };
      getWorker().postMessage({ id: id, op: op, payload: payload });
    });
  }

  var promptPromise = null;
  function clinicalPrompt() {
    if (!promptPromise) {
      promptPromise = call("prompt");
    }
    return promptPromise;
  }

  // Start loading the interpreter now, while the page is still being read.
  window.MedVoiceEngine = { ready: call("ping") };
  window.MedVoiceEngine.ready.catch(function () { /* surfaced when the panel asks */ });

  // ---- routes -------------------------------------------------------------

  function json(body, status) {
    return new Response(JSON.stringify(body), {
      status: status || 200,
      headers: { "Content-Type": "application/json" }
    });
  }

  function capabilities() {
    return Promise.all([call("capabilities"), clinicalPrompt()]).then(function (parts) {
      var info = JSON.parse(parts[0]);
      info.whisper = {
        available: true,
        model: "large-v3-turbo",
        loaded: true,
        decoder: {
          clinical_conditioning: true,
          language: "en",
          temperature: 0.0,
          prompt_words: parts[1].split(/\s+/).length
        }
      };
      info.deployment = { mode: "hosted", note: DEPLOYMENT_NOTE };
      return json(info);
    });
  }

  function analyze(init) {
    var request;
    try {
      request = JSON.parse(init.body);
    } catch (error) {
      return Promise.resolve(json({ detail: "Invalid request." }, 400));
    }
    if (!request.transcript || !String(request.transcript).trim()) {
      return Promise.resolve(json({ detail: "transcript must not be empty." }, 400));
    }
    return call("analyze", JSON.stringify(request)).then(function (text) {
      return new Response(text, { status: 200, headers: { "Content-Type": "application/json" } });
    });
  }

  function transcribe(init) {
    var file = init.body && init.body.get && init.body.get("file");
    if (!file) {
      return Promise.resolve(json({ detail: "No audio was sent." }, 400));
    }

    return toWav(file).then(function (wav) {
      return clinicalPrompt().then(function (prompt) {
        var form = new FormData();
        form.append("audio", wav, "dictation.wav");
        form.append("prompt", prompt);
        return realFetch("/api/asr", { method: "POST", body: form });
      });
    }).then(function (response) {
      return response.json().then(function (body) {
        if (!response.ok) {
          throw new Error(body.detail || ("Speech service error " + response.status));
        }
        return body;
      });
    }).then(function (result) {
      var segments = (result.segments || []).map(function (segment) {
        return {
          start: segment.start,
          end: segment.end,
          text: segment.text,
          avg_logprob: segment.avg_logprob,
          compression_ratio: segment.compression_ratio,
          no_speech_prob: segment.no_speech_prob
        };
      });
      // The decoding statistics drive the confidence meter and the
      // hallucination check. If the speech model did not report them there is
      // nothing honest to show, so the meter is simply left out.
      var hasStats = segments.length && typeof segments[0].avg_logprob === "number";
      var quality = hasStats ? call("quality", JSON.stringify(segments)).then(JSON.parse) : Promise.resolve(null);

      return Promise.all([quality, clinicalPrompt()]).then(function (parts) {
        return json({
          transcription: result.text || "",
          language: result.language || "en",
          segments: segments,
          quality: parts[0],
          decoder: {
            clinical_conditioning: true,
            language: "en",
            temperature: 0.0,
            prompt_words: parts[1].split(/\s+/).length
          }
        });
      });
    }).catch(function (error) {
      return json({ detail: error.message }, 502);
    });
  }

  window.fetch = function (input, init) {
    var url = typeof input === "string" ? input : (input && input.url) || "";
    if (url.indexOf(BASE + "/") !== 0) {
      return realFetch(input, init);
    }
    var route = url.slice(BASE.length).split("?")[0];
    var options = init || {};
    var handler = route === "/capabilities" ? capabilities
      : route === "/analyze" ? analyze
      : route === "/transcribe" ? transcribe
      : null;
    if (!handler) {
      return Promise.resolve(json({ detail: "Not found." }, 404));
    }
    return handler(options).catch(function (error) {
      return json({ detail: error.message }, 500);
    });
  };

  // ---- audio: anything the browser recorded -> 16 kHz mono WAV --------------
  //
  // Chrome records WebM/Opus, Safari and iPhones record MP4/AAC. Decoding in the
  // browser and re-encoding to one plain format means the speech endpoint never
  // has to guess, and the upload stays small.

  function toWav(blob) {
    return blob.arrayBuffer().then(function (buffer) {
      var Context = window.AudioContext || window.webkitAudioContext;
      if (!Context) {
        throw new Error("This browser cannot read audio.");
      }
      var context = new Context();
      return new Promise(function (resolve, reject) {
        context.decodeAudioData(buffer, resolve, reject);
      }).then(function (audio) {
        context.close();
        return audio;
      }, function () {
        context.close();
        throw new Error("The recording could not be read. Try again.");
      });
    }).then(function (audio) {
      if (audio.duration < 0.4) {
        throw new Error("The recording is too short. Hold on a little longer.");
      }
      if (audio.duration > MAX_SECONDS + 5) {
        throw new Error("The recording is too long. The limit is " + MAX_SECONDS + " seconds.");
      }
      return encodeWav(resample(mixToMono(audio), audio.sampleRate, TARGET_RATE), TARGET_RATE);
    });
  }

  function mixToMono(audio) {
    var channels = audio.numberOfChannels;
    var length = audio.length;
    var mono = new Float32Array(length);
    for (var c = 0; c < channels; c += 1) {
      var data = audio.getChannelData(c);
      for (var i = 0; i < length; i += 1) {
        mono[i] += data[i] / channels;
      }
    }
    return mono;
  }

  // Averaging each input window acts as a simple low-pass filter, which is all
  // speech needs. OfflineAudioContext is avoided: Safari restricts its sample rate.
  function resample(input, from, to) {
    if (from === to) {
      return input;
    }
    var ratio = from / to;
    var length = Math.floor(input.length / ratio);
    var output = new Float32Array(length);
    for (var i = 0; i < length; i += 1) {
      var start = Math.floor(i * ratio);
      var end = Math.min(input.length, Math.floor((i + 1) * ratio));
      var sum = 0;
      for (var j = start; j < end; j += 1) {
        sum += input[j];
      }
      output[i] = end > start ? sum / (end - start) : 0;
    }
    return output;
  }

  function encodeWav(samples, rate) {
    var buffer = new ArrayBuffer(44 + samples.length * 2);
    var view = new DataView(buffer);
    function text(offset, value) {
      for (var i = 0; i < value.length; i += 1) {
        view.setUint8(offset + i, value.charCodeAt(i));
      }
    }
    text(0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    text(8, "WAVE");
    text(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);          // PCM
    view.setUint16(22, 1, true);          // mono
    view.setUint32(24, rate, true);
    view.setUint32(28, rate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    text(36, "data");
    view.setUint32(40, samples.length * 2, true);
    for (var i = 0; i < samples.length; i += 1) {
      var clamped = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(44 + i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
    }
    return new Blob([buffer], { type: "audio/wav" });
  }
})();
