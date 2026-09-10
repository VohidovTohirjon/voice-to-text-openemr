/**
 * OpenEMR voice capture panel.
 *
 * Flow:
 *   record -> POST /transcribe        transcript + per-segment ASR confidence
 *   analyze -> POST /analyze          SOAP, vitals, meds, ICD-10, PHI, warnings
 *   review  -> operator ticks fields  nothing is pre-accepted that needs review
 *   insert  -> confirm -> fill        each write is verified after the fact
 *
 * The panel never writes to the form without an explicit confirmation step,
 * and any suggestion the service marked `needs_review` starts unticked.
 */
(function () {
  if (window.__openemrAsrLoaded) {
    return;
  }
  if (shouldAbortForCurrentPage()) {
    return;
  }
  window.__openemrAsrLoaded = true;

  // Local dev override. Chrome runs content scripts in an isolated world, so a
  // page cannot reach this in the real extension — it only takes effect in the
  // validation fixtures, which load these files as ordinary page scripts.
  var API_BASE = (typeof window.__OPENEMR_ASR_API_BASE === "string" &&
                  window.__OPENEMR_ASR_API_BASE) || "http://127.0.0.1:8000";
  var DEMO_TRANSCRIPT =
    "Patient reports headache and mild fever for two days. She denies chest pain. " +
    "On examination temperature 38.0 degrees, blood pressure 148 over 92, pulse 96. " +
    "Impression is likely viral upper respiratory infection with uncontrolled hypertension. " +
    "Plan is acetaminophen 500 mg, continue lisinopril 10 mg daily, follow up in one week.";
  var PANEL_STATE_KEY = "openemr-asr-panel-state";
  var PANEL_WIDTH = 380;

  var state = {
    transcript: "",
    analyzedTranscript: null,
    analysis: null,
    resolved: [],
    unresolved: [],
    selected: {},
    isRecording: false,
    isBusy: false,
    status: "Looking for the encounter form...",
    showPulse: false,
    mediaRecorder: null,
    stream: null,
    audioChunks: [],
    asrQuality: null,
    capabilities: null,
    ui: null,
    panelState: loadPanelState()
  };

  boot();

  // -------------------------------------------------------------------------
  // Page gating
  // -------------------------------------------------------------------------

  function shouldAbortForCurrentPage() {
    return (window.location.pathname || "").indexOf("/interface/login/") >= 0;
  }

  function isRelevantPage() {
    var path = window.location.pathname || "";
    return (
      path.indexOf("/encounter/") >= 0 ||
      path.indexOf("/forms/") >= 0 ||
      path.indexOf("/newpatient/") >= 0 ||
      path.indexOf("/newGroupEncounter/") >= 0 ||
      path.indexOf("/patient_file/") >= 0
    );
  }

  function boot() {
    if (window.OpenEMRASRScanner.hasFillableFields()) {
      initialize();
      return;
    }
    if (!isRelevantPage()) {
      return;
    }

    var timeoutId = null;
    var observer = new MutationObserver(function () {
      if (!window.OpenEMRASRScanner.hasFillableFields()) {
        return;
      }
      observer.disconnect();
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
      initialize();
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    timeoutId = window.setTimeout(function () {
      observer.disconnect();
    }, 10000);
  }

  function initialize() {
    injectStyles();
    buildUI();
    applySavedPanelState();
    highlightReasonTarget();
    setStatus("Ready. Record audio, or paste a transcript and analyze it.");
    loadCapabilities();
  }

  // -------------------------------------------------------------------------
  // Service
  // -------------------------------------------------------------------------

  function loadCapabilities() {
    fetch(API_BASE + "/capabilities")
      .then(function (response) {
        return response.ok ? response.json() : null;
      })
      .then(function (data) {
        state.capabilities = data;
        render();
      })
      .catch(function () {
        state.capabilities = null;
        setStatus("Local ASR service is not reachable. Demo text still works.");
      });
  }

  function requestTranscription(audioBlob) {
    var formData = new FormData();
    formData.append("file", audioBlob, "encounter-recording.webm");

    return fetch(API_BASE + "/transcribe", { method: "POST", body: formData })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Transcription failed with status " + response.status);
        }
        return response.json();
      })
      .then(function (data) {
        if (!data || typeof data.transcription !== "string") {
          throw new Error("Transcription response contained no text.");
        }
        state.asrQuality = data.quality || null;
        return data.transcription;
      });
  }

  function requestAnalysis(transcript) {
    return fetch(API_BASE + "/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transcript: transcript, include_phi: true, suggest_icd: true })
    }).then(function (response) {
      if (!response.ok) {
        return response.json().then(
          function (body) { throw new Error(body.detail || ("Analysis failed: " + response.status)); },
          function () { throw new Error("Analysis failed with status " + response.status); }
        );
      }
      return response.json();
    });
  }

  // -------------------------------------------------------------------------
  // Recording
  // -------------------------------------------------------------------------

  function startRecording() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus("This browser cannot capture microphone audio here. Use demo text.");
      return;
    }

    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      var recorder = new MediaRecorder(stream);
      state.audioChunks = [];
      state.stream = stream;
      state.mediaRecorder = recorder;
      state.isRecording = true;

      recorder.addEventListener("dataavailable", function (event) {
        if (event.data && event.data.size > 0) {
          state.audioChunks.push(event.data);
        }
      });
      recorder.addEventListener("stop", handleRecordingStopped);
      recorder.start();
      setStatus("Recording. Speak now, then press Stop.", true);
      render();
    }).catch(function (error) {
      console.error("Microphone error:", error);
      setStatus("Microphone access was denied. You can still paste or use demo text.");
    });
  }

  function stopRecording() {
    if (!state.mediaRecorder || state.mediaRecorder.state === "inactive") {
      return;
    }
    state.isRecording = false;
    state.mediaRecorder.stop();
    setStatus("Transcribing audio...");
    render();
  }

  function handleRecordingStopped() {
    var blob = new Blob(state.audioChunks, { type: "audio/webm" });
    state.isBusy = true;
    render();

    requestTranscription(blob).then(function (transcript) {
      setTranscript(transcript);
      var confidence = state.asrQuality ? state.asrQuality.overall_confidence : null;
      setStatus(
        confidence === null
          ? "Transcript ready. Review it, then analyze."
          : "Transcript ready (ASR confidence " + Math.round(confidence * 100) + "%). Review, then analyze."
      );
    }).catch(function (error) {
      console.error("Transcription error:", error);
      state.asrQuality = null;
      setTranscript(DEMO_TRANSCRIPT);
      setStatus("Local ASR service unavailable — loaded demo text so the workflow still runs.");
    }).then(function () {
      cleanupRecording();
      state.isBusy = false;
      render();
    });
  }

  function cleanupRecording() {
    if (state.stream) {
      state.stream.getTracks().forEach(function (track) { track.stop(); });
    }
    state.isRecording = false;
    state.mediaRecorder = null;
    state.stream = null;
    state.audioChunks = [];
  }

  // -------------------------------------------------------------------------
  // Analysis
  // -------------------------------------------------------------------------

  function analyzeTranscript() {
    var transcript = (state.transcript || "").trim();
    if (!transcript) {
      return;
    }

    state.isBusy = true;
    setStatus("Analyzing transcript...");
    render();

    requestAnalysis(transcript).then(function (analysis) {
      state.analysis = analysis;
      state.analyzedTranscript = transcript;

      var resolution = window.OpenEMRASRScanner.resolveFieldMappings(analysis.field_mappings || []);
      state.resolved = resolution.resolved;
      state.unresolved = resolution.unresolved;

      // A suggestion the service flagged for review starts unticked: the
      // operator opts in to it rather than opting out.
      state.selected = {};
      state.resolved.forEach(function (item, index) {
        state.selected[index] = !item.mapping.needs_review;
      });

      var count = state.resolved.length;
      setStatus(
        count
          ? "Found " + count + " field" + (count === 1 ? "" : "s") + " to fill. Review the ticks, then insert."
          : "Analysis finished, but no matching fields were found on this page."
      );
    }).catch(function (error) {
      console.error("Analysis error:", error);
      setStatus("Analysis failed: " + error.message);
    }).then(function () {
      state.isBusy = false;
      render();
    });
  }

  // -------------------------------------------------------------------------
  // Filling
  // -------------------------------------------------------------------------

  function insertSelectedFields() {
    var chosen = state.resolved.filter(function (_item, index) {
      return state.selected[index];
    });

    if (!chosen.length) {
      setStatus("Nothing ticked. Select at least one field to insert.");
      render();
      return;
    }

    var summary = chosen.map(function (item) {
      return "• " + item.description + ": " + previewValue(item.mapping.value, 60);
    }).join("\n");

    if (!window.confirm("Insert " + chosen.length + " value(s) into this form?\n\n" + summary)) {
      setStatus("Insert cancelled. Nothing was written.");
      render();
      return;
    }

    var written = 0;
    var failed = [];
    chosen.forEach(function (item) {
      if (!document.contains(item.field)) {
        failed.push(item.description + " (no longer on the page)");
        return;
      }
      if (fillField(item.field, String(item.mapping.value))) {
        written += 1;
        flashField(item.field);
      } else {
        failed.push(item.description);
      }
    });

    setStatus(
      failed.length
        ? "Wrote " + written + " field(s). Could not write: " + failed.join(", ") + "."
        : "Wrote " + written + " field(s) into the form."
    );
    render();
  }

  function insertIntoReasonOnly() {
    var target = window.OpenEMRASRScanner.getReasonTarget();
    var text = (state.transcript || "").trim();
    if (!target) {
      setStatus("No Reason for Visit field on this page.");
      render();
      return;
    }
    if (!text) {
      return;
    }
    if (!window.confirm("Insert this transcript into Reason for Visit?\n\n" + text)) {
      setStatus("Insert cancelled.");
      render();
      return;
    }
    if (fillField(target, text)) {
      flashField(target);
      setStatus("Transcript inserted into Reason for Visit.");
    } else {
      setStatus("Could not write into the Reason for Visit field.");
    }
    render();
  }

  /**
   * Write a value using the element's native setter.
   *
   * Assigning `.value` directly is invisible to frameworks that patch the
   * property, so the prototype setter is called and the usual events are
   * dispatched. The write is then read back, because a silent no-op write is
   * worse than a visible failure in a chart form.
   */
  function fillField(field, value) {
    try {
      field.focus();

      if (field.isContentEditable) {
        field.textContent = value;
      } else {
        var prototype = field instanceof window.HTMLTextAreaElement
          ? window.HTMLTextAreaElement.prototype
          : window.HTMLInputElement.prototype;
        var descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
        if (descriptor && descriptor.set) {
          descriptor.set.call(field, value);
        } else {
          field.value = value;
        }
      }

      field.dispatchEvent(new Event("input", { bubbles: true }));
      field.dispatchEvent(new Event("change", { bubbles: true }));
      field.dispatchEvent(new Event("blur", { bubbles: true }));

      var readBack = field.isContentEditable ? (field.textContent || "") : (field.value || "");
      return readBack === value;
    } catch (error) {
      console.error("Fill failed:", error);
      return false;
    }
  }

  function flashField(field) {
    field.classList.add("openemr-asr-written");
    window.setTimeout(function () {
      field.classList.remove("openemr-asr-written");
    }, 1600);
  }

  function highlightReasonTarget() {
    var target = window.OpenEMRASRScanner.getReasonTarget();
    if (target) {
      target.classList.add("openemr-asr-highlight");
    }
  }

  // -------------------------------------------------------------------------
  // Rendering
  // -------------------------------------------------------------------------

  function setStatus(message, showPulse) {
    state.status = message;
    state.showPulse = Boolean(showPulse);
    render();
  }

  function setTranscript(value) {
    state.transcript = value || "";
    if (state.ui) {
      state.ui.previewEl.value = state.transcript;
    }
  }

  function previewValue(value, limit) {
    var text = String(value == null ? "" : value).replace(/\s+/g, " ").trim();
    return text.length > limit ? text.slice(0, limit - 1) + "…" : text;
  }

  function escapeHtml(text) {
    return String(text == null ? "" : text).replace(/[&<>"']/g, function (character) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character];
    });
  }

  function confidenceClass(value) {
    if (value >= 0.85) { return "high"; }
    if (value >= 0.7) { return "mid"; }
    return "low";
  }

  function render() {
    if (!state.ui) {
      return;
    }
    var ui = state.ui;

    ui.statusEl.innerHTML =
      (state.showPulse ? '<span class="openemr-asr-pulse"></span>' : "") + escapeHtml(state.status);

    ui.card.classList.toggle("is-collapsed", Boolean(state.panelState.collapsed));
    ui.toggleButton.textContent = state.panelState.collapsed ? "+" : "−";
    ui.toggleButton.setAttribute(
      "aria-label", state.panelState.collapsed ? "Expand panel" : "Collapse panel");

    var hasTranscript = Boolean((state.transcript || "").trim());
    var stale = state.analysis && state.analyzedTranscript !== (state.transcript || "").trim();

    ui.recordButton.disabled = state.isRecording || state.isBusy;
    ui.stopButton.disabled = !state.isRecording;
    ui.analyzeButton.disabled = !hasTranscript || state.isBusy;
    ui.analyzeButton.textContent = stale ? "Re-analyze" : "Analyze";
    ui.reasonButton.disabled = !hasTranscript || state.isBusy;

    ui.serviceEl.innerHTML = renderServiceLine();
    ui.qualityEl.innerHTML = renderQuality();
    ui.staleEl.innerHTML = stale
      ? '<div class="openemr-asr-stale">Transcript changed since the last analysis. Re-analyze before inserting.</div>'
      : "";
    ui.resultsEl.innerHTML = renderResults();

    Array.prototype.forEach.call(
      ui.resultsEl.querySelectorAll('input[type="checkbox"][data-index]'),
      function (box) {
        box.addEventListener("change", function () {
          state.selected[box.getAttribute("data-index")] = box.checked;
          updateInsertButton();
        });
      }
    );

    updateInsertButton();
  }

  function updateInsertButton() {
    if (!state.ui) {
      return;
    }
    var count = state.resolved.filter(function (_item, index) {
      return state.selected[index];
    }).length;

    state.ui.insertButton.disabled = count === 0 || state.isBusy;
    state.ui.insertButton.textContent = count
      ? "Insert " + count + " field" + (count === 1 ? "" : "s")
      : "Insert selected";
    state.ui.insertButton.style.display = state.resolved.length ? "" : "none";
  }

  function renderServiceLine() {
    if (state.capabilities === null) {
      return '<span class="openemr-asr-dot offline"></span>Service offline — demo text only';
    }
    var layers = state.capabilities.layers || {};
    var degraded = Object.keys(layers).filter(function (key) {
      return layers[key].available === false;
    });
    var model = (state.capabilities.whisper || {}).model || "?";
    return '<span class="openemr-asr-dot online"></span>Service ready · Whisper ' +
      escapeHtml(model) +
      (degraded.length ? " · " + degraded.length + " layer(s) degraded" : "");
  }

  function renderQuality() {
    if (!state.asrQuality) {
      return "";
    }
    var quality = state.asrQuality;
    var percent = Math.round(quality.overall_confidence * 100);
    var klass = confidenceClass(quality.overall_confidence);
    var html =
      '<div class="openemr-asr-meter">' +
      '<div class="openemr-asr-meter-label">ASR confidence <b>' + percent + '%</b></div>' +
      '<div class="openemr-asr-bar"><i class="' + klass + '" style="width:' + percent + '%"></i></div>' +
      "</div>";

    if (quality.hallucination_risk === "high" || quality.hallucination_risk === "medium") {
      var count = (quality.summary || {}).hallucination_suspected_count || 0;
      html += '<div class="openemr-asr-alert high">' + count +
        " segment(s) look hallucinated. Re-listen before accepting.</div>";
    }
    return html;
  }

  function renderResults() {
    if (!state.analysis) {
      return "";
    }
    var analysis = state.analysis;
    var html = "";

    (analysis.warnings || []).forEach(function (warning) {
      html += '<div class="openemr-asr-alert ' + escapeHtml(warning.level) + '">' +
        escapeHtml(warning.message) + "</div>";
    });

    if (analysis.phi && analysis.phi.entities && analysis.phi.entities.length) {
      html += '<div class="openemr-asr-alert medium">Identifiers detected: ' +
        escapeHtml(analysis.phi.entities.map(function (entity) {
          return entity.type;
        }).join(", ")) + "</div>";
    }

    if (state.resolved.length) {
      html += '<div class="openemr-asr-section">Fields on this page</div>';
      state.resolved.forEach(function (item, index) {
        var mapping = item.mapping;
        var percent = Math.round((mapping.confidence || 0) * 100);
        var klass = confidenceClass(mapping.confidence || 0);
        var checked = state.selected[index] ? " checked" : "";
        var occupied = String(item.currentValue || "").trim();

        html +=
          '<label class="openemr-asr-field">' +
          '<input type="checkbox" data-index="' + index + '"' + checked + ">" +
          '<span class="openemr-asr-field-body">' +
          '<span class="openemr-asr-field-head">' +
          '<b>' + escapeHtml(item.description) + "</b>" +
          '<span class="openemr-asr-badge ' + klass + '">' + percent + "%</span>" +
          "</span>" +
          '<span class="openemr-asr-value">' + escapeHtml(previewValue(mapping.value, 90)) + "</span>" +
          '<span class="openemr-asr-meta">matched on ' + escapeHtml(item.strategy) +
          " · " + escapeHtml(String(item.matchedOn)) +
          (mapping.needs_review ? ' · <em class="warn">needs review</em>' : "") +
          (occupied ? ' · <em class="warn">will overwrite</em>' : "") +
          "</span></span></label>";
      });
    }

    if (state.unresolved.length) {
      html += '<div class="openemr-asr-section">Not on this page</div>' +
        '<div class="openemr-asr-muted">' +
        escapeHtml(state.unresolved.map(function (mapping) {
          return mapping.entity_type;
        }).join(", ")) + "</div>";
    }

    var codes = (analysis.icd10 || {}).candidates || [];
    if (codes.length) {
      html += '<div class="openemr-asr-section">Suggested diagnosis codes</div>';
      codes.slice(0, 4).forEach(function (code) {
        html += '<div class="openemr-asr-code">' +
          '<b>' + escapeHtml(code.code) + "</b> " +
          '<span class="openemr-asr-badge ' + confidenceClass(code.confidence) + '">' +
          Math.round(code.confidence * 100) + "%</span> " +
          escapeHtml(code.description) + "</div>";
      });
      html += '<div class="openemr-asr-muted">Candidates only — select and verify before billing.</div>';
    }

    if (analysis.timings_ms) {
      html += '<div class="openemr-asr-muted">Analysis took ' +
        escapeHtml(String(analysis.timings_ms.total)) + " ms locally.</div>";
    }

    return html;
  }

  // -------------------------------------------------------------------------
  // UI construction
  // -------------------------------------------------------------------------

  /**
   * Inject the panel stylesheet.
   *
   * Every rule that targets the panel is prefixed with the root ID. That is not
   * cosmetic: a content script lands inside a page whose own stylesheet knows
   * nothing about it, and OpenEMR (like most Bootstrap-based apps) styles bare
   * `input` and `textarea` selectors. A host rule such as `input{width:100%}`
   * will otherwise size this panel's checkboxes to the full row and collapse
   * the layout. The ID prefix plus an explicit control reset makes the panel
   * independent of whatever the host page declares.
   *
   * The two page-facing classes — highlight and written — are deliberately NOT
   * prefixed, because they decorate form fields out in the host document.
   */
  function injectStyles() {
    var ROOT = "#openemr-asr-demo-root";
    var rules = [
      // Panel shell
      ROOT + "{position:fixed;right:20px;bottom:20px;z-index:2147483647;" +
        "font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;font-size:13px;" +
        "line-height:1.5;width:" + PANEL_WIDTH + "px;max-width:calc(100vw - 24px);" +
        "text-align:left;box-sizing:border-box}",
      ROOT + " *{box-sizing:border-box}",

      // Neutralise host form styling on the panel's own controls.
      ROOT + " input,#openemr-asr-demo-root textarea,#openemr-asr-demo-root button{" +
        "font-family:inherit;margin:0;min-width:0;max-width:none;float:none;" +
        "display:inline-block;box-shadow:none}",
      ROOT + ' input[type="checkbox"]{width:14px;height:14px;flex:0 0 14px;' +
        "padding:0;border:0;background:none;appearance:auto;-webkit-appearance:checkbox;" +
        "accent-color:#38bdf8;cursor:pointer}",

      ROOT + " .openemr-asr-card{background:#0f172a;color:#e2e8f0;border-radius:14px;" +
        "overflow:hidden;box-shadow:0 18px 44px rgba(15,23,42,.34);" +
        "border:1px solid rgba(148,163,184,.28)}",
      ROOT + " .openemr-asr-card.is-collapsed .openemr-asr-body{display:none}",
      ROOT + " .openemr-asr-header{padding:12px 14px;background:linear-gradient(135deg,#1d4ed8,#0f766e);" +
        "display:flex;align-items:flex-start;justify-content:space-between;gap:10px;" +
        "cursor:move;user-select:none}",
      ROOT + " .openemr-asr-title{font-size:14px;font-weight:700;margin:0;color:#f8fafc}",
      ROOT + " .openemr-asr-subtitle{margin:3px 0 0;font-size:11.5px;color:#e0f2fe;opacity:.92}",
      ROOT + " .openemr-asr-toggle{border:0;border-radius:999px;width:26px;height:26px;" +
        "background:rgba(255,255,255,.18);color:#f8fafc;font-size:16px;line-height:1;" +
        "cursor:pointer;flex:0 0 26px;padding:0}",
      ROOT + " .openemr-asr-body{padding:13px;max-height:74vh;overflow-y:auto}",

      // Service line and status
      ROOT + " .openemr-asr-service{font-size:11px;color:#94a3b8;margin-bottom:8px;" +
        "display:flex;align-items:center;gap:6px}",
      ROOT + " .openemr-asr-dot{width:7px;height:7px;border-radius:999px;flex:0 0 7px}",
      ROOT + " .openemr-asr-dot.online{background:#22c55e}",
      ROOT + " .openemr-asr-dot.offline{background:#ef4444}",
      ROOT + " .openemr-asr-status{font-size:12px;color:#cbd5e1;margin-bottom:9px}",

      // Buttons
      ROOT + " .openemr-asr-controls,#openemr-asr-demo-root .openemr-asr-row{" +
        "display:flex;gap:7px;margin-bottom:9px}",
      ROOT + " .openemr-asr-row{margin:8px 0 0}",
      ROOT + " .openemr-asr-button{flex:1 1 0;width:auto;border:0;border-radius:9px;" +
        "padding:9px 10px;font-size:12.5px;font-weight:700;cursor:pointer;line-height:1.2}",
      ROOT + " .openemr-asr-button.primary{background:#22c55e;color:#052e16}",
      ROOT + " .openemr-asr-button.warn{background:#f97316;color:#fff}",
      ROOT + " .openemr-asr-button.accent{background:#38bdf8;color:#082f49}",
      ROOT + " .openemr-asr-button.secondary{background:#e2e8f0;color:#0f172a}",
      ROOT + " .openemr-asr-button.ghost{background:transparent;color:#e2e8f0;" +
        "border:1px solid rgba(226,232,240,.32)}",
      ROOT + " .openemr-asr-button:disabled{opacity:.5;cursor:not-allowed}",

      // Transcript box
      ROOT + " .openemr-asr-preview{width:100%;min-height:84px;border-radius:9px;" +
        "border:1px solid #475569;background:#020617;color:#f8fafc;padding:9px;" +
        "resize:vertical;font-size:12.5px;line-height:1.5}",

      // Confidence meter
      ROOT + " .openemr-asr-meter{margin:9px 0 6px}",
      ROOT + " .openemr-asr-meter-label{font-size:11px;color:#94a3b8;margin-bottom:4px}",
      ROOT + " .openemr-asr-bar{height:5px;border-radius:999px;background:#1e293b;overflow:hidden}",
      ROOT + " .openemr-asr-bar i{display:block;height:100%;border-radius:999px}",
      ROOT + " .openemr-asr-bar i.high{background:#22c55e}",
      ROOT + " .openemr-asr-bar i.mid{background:#facc15}",
      ROOT + " .openemr-asr-bar i.low{background:#ef4444}",

      // Alerts
      ROOT + " .openemr-asr-alert{font-size:11.5px;line-height:1.45;border-radius:8px;" +
        "padding:7px 9px;margin:6px 0;border-left:3px solid}",
      ROOT + " .openemr-asr-alert.high{background:rgba(239,68,68,.14);border-color:#ef4444;color:#fecaca}",
      ROOT + " .openemr-asr-alert.medium{background:rgba(250,204,21,.13);border-color:#facc15;color:#fde68a}",
      ROOT + " .openemr-asr-alert.info{background:rgba(56,189,248,.13);border-color:#38bdf8;color:#bae6fd}",
      ROOT + " .openemr-asr-stale{font-size:11.5px;border-radius:8px;padding:7px 9px;margin:6px 0;" +
        "background:rgba(250,204,21,.13);border-left:3px solid #facc15;color:#fde68a}",

      // Field suggestions
      ROOT + " .openemr-asr-section{font-size:10.5px;text-transform:uppercase;" +
        "letter-spacing:.08em;color:#64748b;font-weight:700;margin:11px 0 5px}",
      ROOT + " .openemr-asr-field{display:flex;gap:8px;align-items:flex-start;" +
        "padding:7px 8px;margin:0 0 5px;background:#111c33;border:1px solid #1e293b;" +
        "border-radius:8px;cursor:pointer;width:100%;font-weight:400;color:#e2e8f0}",
      ROOT + " .openemr-asr-field:hover{border-color:#334155}",
      ROOT + ' .openemr-asr-field input[type="checkbox"]{margin-top:2px}',
      ROOT + " .openemr-asr-field-body{min-width:0;flex:1 1 auto;display:block}",
      ROOT + " .openemr-asr-field-head{display:flex;align-items:center;gap:6px;" +
        "justify-content:space-between}",
      ROOT + " .openemr-asr-field-head b{font-size:12px;color:#e2e8f0;font-weight:700}",
      ROOT + " .openemr-asr-value{display:block;font-size:11.5px;color:#cbd5e1;" +
        "margin-top:3px;overflow-wrap:anywhere}",
      ROOT + " .openemr-asr-meta{display:block;font-size:10px;color:#64748b;margin-top:3px}",
      ROOT + " .openemr-asr-meta em.warn{color:#fbbf24;font-style:normal;font-weight:600}",
      ROOT + " .openemr-asr-badge{font-size:10px;font-weight:700;border-radius:999px;" +
        "padding:1px 6px;flex:0 0 auto;white-space:nowrap}",
      ROOT + " .openemr-asr-badge.high{background:rgba(34,197,94,.2);color:#86efac}",
      ROOT + " .openemr-asr-badge.mid{background:rgba(250,204,21,.2);color:#fde68a}",
      ROOT + " .openemr-asr-badge.low{background:rgba(239,68,68,.2);color:#fecaca}",

      // Codes and footnotes
      ROOT + " .openemr-asr-code{font-size:11.5px;color:#cbd5e1;padding:4px 0;" +
        "border-bottom:1px solid #1e293b}",
      ROOT + " .openemr-asr-code b{color:#e2e8f0;font-family:ui-monospace,Menlo,monospace}",
      ROOT + " .openemr-asr-muted{font-size:10.5px;color:#64748b;margin-top:5px;line-height:1.45}",
      ROOT + " .openemr-asr-pulse{display:inline-block;width:8px;height:8px;margin-right:6px;" +
        "border-radius:999px;background:#f43f5e;animation:openemr-asr-pulse 1.2s infinite;" +
        "vertical-align:middle}",

      // Page-facing decorations: intentionally unprefixed.
      ".openemr-asr-highlight{outline:3px solid #22c55e !important;outline-offset:2px}",
      ".openemr-asr-written{outline:3px solid #38bdf8 !important;outline-offset:2px}",

      "@keyframes openemr-asr-pulse{0%{box-shadow:0 0 0 0 rgba(244,63,94,.65)}" +
        "70%{box-shadow:0 0 0 11px rgba(244,63,94,0)}100%{box-shadow:0 0 0 0 rgba(244,63,94,0)}}",
      "@media (prefers-reduced-motion:reduce){" + ROOT + " .openemr-asr-pulse{animation:none}}",
      "@media (max-width:640px){" + ROOT + "{width:min(" + PANEL_WIDTH +
        "px,calc(100vw - 16px));right:8px;bottom:8px}}"
    ];

    var style = document.createElement("style");
    style.textContent = rules.join("\n");
    document.documentElement.appendChild(style);
  }

  function buildUI() {
    var root = document.createElement("div");
    root.id = "openemr-asr-demo-root";
    root.innerHTML = [
      '<div class="openemr-asr-card">',
      '  <div class="openemr-asr-header" data-role="drag-handle">',
      "    <div>",
      '      <p class="openemr-asr-title">OpenEMR Voice Capture</p>',
      '      <p class="openemr-asr-subtitle">Dictate, analyze, confirm, then fill.</p>',
      "    </div>",
      '    <button class="openemr-asr-toggle" data-role="toggle" aria-label="Collapse panel">−</button>',
      "  </div>",
      '  <div class="openemr-asr-body">',
      '    <div class="openemr-asr-service" data-role="service"></div>',
      '    <div class="openemr-asr-status" data-role="status"></div>',
      '    <div class="openemr-asr-controls">',
      '      <button class="openemr-asr-button primary" data-role="record">Start mic</button>',
      '      <button class="openemr-asr-button warn" data-role="stop" disabled>Stop</button>',
      "    </div>",
      '    <textarea class="openemr-asr-preview" data-role="preview" ',
      '      placeholder="Transcript appears here. You can edit it before analyzing."></textarea>',
      '    <div data-role="quality"></div>',
      '    <div class="openemr-asr-row">',
      '      <button class="openemr-asr-button accent" data-role="analyze" disabled>Analyze</button>',
      '      <button class="openemr-asr-button ghost" data-role="demo">Demo text</button>',
      "    </div>",
      '    <div data-role="stale"></div>',
      '    <div data-role="results"></div>',
      '    <div class="openemr-asr-row">',
      '      <button class="openemr-asr-button secondary" data-role="insert" style="display:none">Insert selected</button>',
      "    </div>",
      '    <div class="openemr-asr-row">',
      '      <button class="openemr-asr-button ghost" data-role="reason" disabled>Insert transcript into Reason for Visit</button>',
      "    </div>",
      "  </div>",
      "</div>"
    ].join("");

    document.body.appendChild(root);

    function pick(role) {
      return root.querySelector('[data-role="' + role + '"]');
    }

    state.ui = {
      root: root,
      card: root.querySelector(".openemr-asr-card"),
      dragHandle: pick("drag-handle"),
      toggleButton: pick("toggle"),
      serviceEl: pick("service"),
      statusEl: pick("status"),
      qualityEl: pick("quality"),
      staleEl: pick("stale"),
      resultsEl: pick("results"),
      previewEl: pick("preview"),
      recordButton: pick("record"),
      stopButton: pick("stop"),
      analyzeButton: pick("analyze"),
      demoButton: pick("demo"),
      insertButton: pick("insert"),
      reasonButton: pick("reason")
    };

    state.ui.previewEl.addEventListener("input", function () {
      state.transcript = state.ui.previewEl.value;
      render();
    });
    state.ui.recordButton.addEventListener("click", startRecording);
    state.ui.stopButton.addEventListener("click", stopRecording);
    state.ui.analyzeButton.addEventListener("click", analyzeTranscript);
    state.ui.insertButton.addEventListener("click", insertSelectedFields);
    state.ui.reasonButton.addEventListener("click", insertIntoReasonOnly);
    state.ui.demoButton.addEventListener("click", function () {
      state.asrQuality = null;
      setTranscript(DEMO_TRANSCRIPT);
      setStatus("Demo transcript loaded. Click Analyze to see the clinical layers.");
    });
    state.ui.toggleButton.addEventListener("click", function (event) {
      event.stopPropagation();
      state.panelState.collapsed = !state.panelState.collapsed;
      persistPanelState();
      render();
    });

    setupDragging();
    render();
  }

  // -------------------------------------------------------------------------
  // Panel position
  // -------------------------------------------------------------------------

  function setupDragging() {
    var handle = state.ui.dragHandle;
    var root = state.ui.root;
    var dragging = false;
    var offsetX = 0;
    var offsetY = 0;

    handle.addEventListener("pointerdown", function (event) {
      if (event.button !== 0) {
        return;
      }
      dragging = true;
      var rect = root.getBoundingClientRect();
      offsetX = event.clientX - rect.left;
      offsetY = event.clientY - rect.top;
      handle.setPointerCapture(event.pointerId);
      event.preventDefault();
    });

    handle.addEventListener("pointermove", function (event) {
      if (!dragging) {
        return;
      }
      applyPanelPosition({ left: event.clientX - offsetX, top: event.clientY - offsetY }, false);
    });

    function finish(event) {
      if (!dragging) {
        return;
      }
      dragging = false;
      if (handle.hasPointerCapture && handle.hasPointerCapture(event.pointerId)) {
        handle.releasePointerCapture(event.pointerId);
      }
      persistPanelState();
    }

    handle.addEventListener("pointerup", finish);
    handle.addEventListener("pointercancel", finish);
  }

  function applyPanelPosition(position, persist) {
    var root = state.ui.root;
    var width = root.offsetWidth || PANEL_WIDTH;
    var height = root.offsetHeight || 260;
    var left = Math.max(4, Math.min(position.left, window.innerWidth - width - 4));
    var top = Math.max(4, Math.min(position.top, window.innerHeight - Math.min(height, 120) - 4));

    root.style.left = left + "px";
    root.style.top = top + "px";
    root.style.right = "auto";
    root.style.bottom = "auto";

    state.panelState.position = { left: left, top: top };
    if (persist) {
      persistPanelState();
    }
  }

  function applySavedPanelState() {
    var position = state.panelState.position;
    if (position && typeof position.left === "number" && typeof position.top === "number") {
      applyPanelPosition(position, false);
    }
  }

  function loadPanelState() {
    try {
      var raw = window.localStorage.getItem(PANEL_STATE_KEY);
      var parsed = raw ? JSON.parse(raw) : {};
      return {
        collapsed: Boolean(parsed.collapsed),
        position: parsed.position || null
      };
    } catch (error) {
      return { collapsed: false, position: null };
    }
  }

  function persistPanelState() {
    try {
      window.localStorage.setItem(PANEL_STATE_KEY, JSON.stringify(state.panelState));
    } catch (error) {
      /* storage unavailable (private window); position simply is not remembered */
    }
  }
})();
