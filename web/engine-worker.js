/**
 * Analysis engine for the hosted demo.
 *
 * Runs the clinical pipeline (the same Python package the local service uses)
 * inside the browser through Pyodide, in a worker so the page never freezes
 * while the interpreter starts or an analysis runs. Text never leaves this
 * browser tab.
 */
var PYODIDE_VERSION = "0.27.7";
var PYODIDE_BASE = "https://cdn.jsdelivr.net/pyodide/v" + PYODIDE_VERSION + "/full/";

importScripts(PYODIDE_BASE + "pyodide.js");

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

var ready = (function () {
  return loadPyodide({ indexURL: PYODIDE_BASE }).then(function (pyodide) {
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
      return pyodide;
    });
  });
})();

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
