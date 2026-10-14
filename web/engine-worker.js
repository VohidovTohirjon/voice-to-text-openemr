/**
 * Analysis engine for the hosted demo.
 *
 * Runs the clinical pipeline (the same Python package the local service uses)
 * inside the browser through Pyodide, in a worker so the page never freezes
 * while the interpreter starts or an analysis runs. Text never leaves this
 * browser tab.
 */
// The runtime ships with this site (see scripts/build-site.sh), so the demo does
// not depend on a public CDN being reachable.
var PYODIDE_BASE = "/pyodide-0.27.7/";
var WASM_BYTES = 10105545;   // size of pyodide.asm.wasm at this version

importScripts(PYODIDE_BASE + "pyodide.js");

function report(stage, percent) {
  self.postMessage({ event: "progress", stage: stage, percent: percent });
}

// Pyodide cannot report its own download progress. The big file is read once
// here with a counter; Pyodide's own request for it then comes from the HTTP cache.
function warmDownload() {
  report("download", 0);
  return fetch(PYODIDE_BASE + "pyodide.asm.wasm").then(function (response) {
    var reader = response.body.getReader();
    var loaded = 0;
    var last = -1;
    function pump() {
      return reader.read().then(function (chunk) {
        if (chunk.done) {
          return;
        }
        loaded += chunk.value.length;
        var percent = Math.min(90, Math.round(loaded / WASM_BYTES * 90));
        if (percent !== last) {
          last = percent;
          report("download", percent);
        }
        return pump();
      });
    }
    return pump();
  }).catch(function () { /* progress is cosmetic; loading proceeds either way */ });
}

// Thin JSON-in, JSON-out layer over the package, so nothing Python-specific
// crosses into the page.
var GLUE = [
  "import json, sys",
  "sys.path.insert(0, '/app')",
  "from nlp import asr_quality, pipeline, prompting",
  "",
  "def analyze_json(payload):",
  "    req = json.loads(payload)",
  "    result = pipeline.analyze(",
  "        req['transcript'],",
  "        segments=req.get('segments'),",
  "        use_llm=False,",
  "        include_phi=req.get('include_phi', True),",
  "        redact_phi=req.get('redact_phi', False),",
  "        suggest_icd=req.get('suggest_icd', True),",
  "    )",
  "    return json.dumps(result, default=str)",
  "",
  "def capabilities_json():",
  "    return json.dumps(pipeline.capabilities(), default=str)",
  "",
  "def quality_json(payload):",
  "    quality = asr_quality.analyze_segments(json.loads(payload))",
  "    quality['low_confidence_spans'] = asr_quality.low_confidence_spans(quality)",
  "    return json.dumps(quality, default=str)",
  "",
  "def clinical_prompt():",
  "    return prompting.decode_options()['initial_prompt']"
].join("\n");

var ready = warmDownload().then(function () {
  report("python", 92);
  return loadPyodide({ indexURL: PYODIDE_BASE });
}).then(function (pyodide) {
  report("package", 97);
  return fetch("py/nlp-bundle.json").then(function (response) {
    if (!response.ok) {
      throw new Error("analysis package not found (" + response.status + ")");
    }
    return response.json();
  }).then(function (bundle) {
    Object.keys(bundle.files).forEach(function (path) {
      var full = "/app/" + path;
      pyodide.FS.mkdirTree(full.slice(0, full.lastIndexOf("/")));
      pyodide.FS.writeFile(full, bundle.files[path], { encoding: "utf8" });
    });
    pyodide.runPython(GLUE);
    report("ready", 100);
    return pyodide;
  });
});

function call(pyodide, name, argument) {
  var fn = pyodide.globals.get(name);
  try {
    return argument === undefined ? fn() : fn(argument);
  } finally {
    fn.destroy();
  }
}

self.onmessage = function (event) {
  var message = event.data;
  ready.then(function (pyodide) {
    var result;
    if (message.op === "analyze") {
      result = call(pyodide, "analyze_json", message.payload);
    } else if (message.op === "capabilities") {
      result = call(pyodide, "capabilities_json");
    } else if (message.op === "quality") {
      result = call(pyodide, "quality_json", message.payload);
    } else if (message.op === "prompt") {
      result = call(pyodide, "clinical_prompt");
    } else if (message.op === "ping") {
      result = "pong";
    } else {
      throw new Error("unknown operation: " + message.op);
    }
    self.postMessage({ id: message.id, ok: true, result: result });
  }).catch(function (error) {
    self.postMessage({ id: message.id, ok: false, error: String(error && error.message || error) });
  });
};
