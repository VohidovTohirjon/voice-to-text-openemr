/**
 * OpenEMR voice capture panel.
 *
 * Flow:
 *   record  -> POST /transcribe        transcript + per-segment ASR confidence
 *   analyze -> POST /analyze           SOAP, vitals, meds, ICD-10, PHI, warnings
 *   select  -> operator ticks fields   nothing is pre-accepted that needs review
 *   review  -> inline list of changes  old value next to new value, nothing written yet
 *   insert  -> confirm -> fill         each write is verified, and can be undone
 *
 * The panel never writes to the form without an explicit confirmation step,
 * and any suggestion the service marked `needs_review` starts unticked.
 *
 * Runs unchanged in two places: as a Chrome content script against a local
 * OpenEMR, and as an ordinary page script on the hosted demo, where
 * window.__OPENEMR_ASR_API_BASE points at an in-browser engine.
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
  // page cannot reach this in the real extension: it only takes effect in the
  // validation fixtures and the hosted demo, which load these files as
  // ordinary page scripts.
  var API_BASE = (typeof window.__OPENEMR_ASR_API_BASE === "string" &&
                  window.__OPENEMR_ASR_API_BASE) || "http://127.0.0.1:8000";
  var DEMO_TRANSCRIPT =
    "Patient reports headache and mild fever for two days. She denies chest pain. " +
    "On examination temperature 38.0 degrees, blood pressure 148 over 92, pulse 96. " +
    "Impression is likely viral upper respiratory infection with uncontrolled hypertension. " +
    "Plan is acetaminophen 500 mg, continue lisinopril 10 mg daily, follow up in one week.";
  var PANEL_STATE_KEY = "openemr-asr-panel-state";
  var PANEL_WIDTH = 380;
  var MAX_RECORD_SECONDS = 90;
  var MOBILE_QUERY = "(max-width: 640px)";

  // Entity names the service uses, in words a clinician would say.
  var ENTITY_LABELS = {
    blood_pressure_systolic: "BP systolic",
    blood_pressure_diastolic: "BP diastolic",
    heart_rate: "Pulse",
    respiratory_rate: "Respiration",
    oxygen_saturation: "Oxygen saturation",
    medication: "Medications"
  };

  var state = {
    transcript: "",
    analyzedTranscript: null,
    analysis: null,
    resolved: [],
    unresolved: [],
    selected: {},
    done: {},
    view: "capture",
    review: null,
    undo: null,
    notice: null,
    isRecording: false,
    isBusy: false,
    status: "Looking for the encounter form...",
    showPulse: false,
    mediaRecorder: null,
    stream: null,
    audioChunks: [],
    recordStartedAt: 0,
    recordTimer: null,
    asrQuality: null,
    capabilities: null,
    capabilitiesLoading: true,
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

  /**
   * Clinical form pages, by path.
   *
   * Deliberately narrow. OpenEMR's main tab shell (/interface/main/tabs/) is a
   * chrome page with a demographics search box, and the panel has no business
   * there - it belongs on the encounter and its forms, which OpenEMR loads into
   * an iframe whose own URL is one of the paths below.
   *
   * /patient_file/ on its own is NOT enough: it also covers demographics,
   * documents and billing.
   *
   * The hosted demo page is not an OpenEMR URL, so it opts in explicitly.
   */
  function isRelevantPage() {
    if (window.__OPENEMR_ASR_ANY_PAGE === true) {
      return true;
    }
    var path = window.location.pathname || "";
    return (
      path.indexOf("/forms/") >= 0 ||
      path.indexOf("/newpatient/") >= 0 ||
      path.indexOf("/newGroupEncounter/") >= 0 ||
      path.indexOf("/patient_file/encounter/") >= 0
    );
  }

  function boot() {
    // Page type is checked FIRST. Checking for a fillable field first meant any
    // page with a text box qualified, which put the panel on OpenEMR's calendar
    // tab because of its demographics search field.
    if (!isRelevantPage()) {
      return;
    }
    if (window.OpenEMRASRScanner.hasClinicalTarget()) {
      initialize();
      return;
    }

    var timeoutId = null;
    var observer = new MutationObserver(function () {
      if (!window.OpenEMRASRScanner.hasClinicalTarget()) {
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

  function isMobile() {
    return Boolean(window.matchMedia && window.matchMedia(MOBILE_QUERY).matches);
  }

  // -------------------------------------------------------------------------
  // Service
  // -------------------------------------------------------------------------

  function loadCapabilities() {
    state.capabilitiesLoading = true;
    render();
    fetch(API_BASE + "/capabilities")
      .then(function (response) {
        return response.ok ? response.json() : null;
      })
      .then(function (data) {
        state.capabilities = data;
        state.capabilitiesLoading = false;
        render();
      })
      .catch(function () {
        state.capabilities = null;
        state.capabilitiesLoading = false;
        setStatus("The speech service is not reachable. Demo text still works.");
      });
  }

  function requestTranscription(audioBlob) {
    var formData = new FormData();
    formData.append("file", audioBlob, "encounter-recording.webm");

    return fetch(API_BASE + "/transcribe", { method: "POST", body: formData })
      .then(function (response) {
        if (!response.ok) {
          return response.json().then(
            function (body) { throw new Error(body.detail || ("Transcription failed: " + response.status)); },
            function () { throw new Error("Transcription failed with status " + response.status); }
          );
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
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
      setStatus("This browser cannot record audio here. Type, paste or use Demo text.");
      return;
    }

    navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
      var recorder = new MediaRecorder(stream);
      state.audioChunks = [];
      state.stream = stream;
      state.mediaRecorder = recorder;
      state.isRecording = true;
      state.notice = null;

      recorder.addEventListener("dataavailable", function (event) {
        if (event.data && event.data.size > 0) {
          state.audioChunks.push(event.data);
        }
      });
      recorder.addEventListener("stop", handleRecordingStopped);
      recorder.start();
      startRecordTimer();
      setStatus("Recording. Speak now, then press Stop.", true);
    }).catch(function (error) {
      console.error("Microphone error:", error);
      setStatus("Microphone access was denied. You can still type, paste or use Demo text.");
    });
  }

  function stopRecording() {
    if (!state.mediaRecorder || state.mediaRecorder.state === "inactive") {
      return;
    }
    state.isRecording = false;
    stopRecordTimer();
    state.mediaRecorder.stop();
    setStatus("Transcribing audio...");
  }

  function startRecordTimer() {
    state.recordStartedAt = Date.now();
    updateRecordTimer();
    state.recordTimer = window.setInterval(function () {
      updateRecordTimer();
      if ((Date.now() - state.recordStartedAt) / 1000 >= MAX_RECORD_SECONDS) {
        stopRecording();
      }
    }, 500);
  }

  function stopRecordTimer() {
    if (state.recordTimer) {
      window.clearInterval(state.recordTimer);
      state.recordTimer = null;
    }
    if (state.ui) {
      state.ui.timerEl.textContent = "";
    }
  }

  function updateRecordTimer() {
    if (!state.ui) {
      return;
    }
    var seconds = Math.floor((Date.now() - state.recordStartedAt) / 1000);
    var label = Math.floor(seconds / 60) + ":" + ("0" + (seconds % 60)).slice(-2);
    state.ui.timerEl.textContent = label + " / " + Math.floor(MAX_RECORD_SECONDS / 60) + ":" +
      ("0" + (MAX_RECORD_SECONDS % 60)).slice(-2);
  }

  function handleRecordingStopped() {
    var blob = new Blob(state.audioChunks, { type: state.mediaRecorder && state.mediaRecorder.mimeType || "audio/webm" });
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
      // The operator's own text stays untouched: replacing it with sample text
      // after a failure would put words in a chart that nobody dictated.
      console.error("Transcription error:", error);
      state.asrQuality = null;
      setStatus("Transcription failed: " + error.message + " Type or paste the text instead.");
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
    stopRecordTimer();
    state.isRecording = false;
    state.mediaRecorder = null;
    state.stream = null;
    state.audioChunks = [];
  }

  // -------------------------------------------------------------------------
  // Analysis
  // -------------------------------------------------------------------------

  function resetResults() {
    state.analysis = null;
    state.analyzedTranscript = null;
    state.resolved = [];
    state.unresolved = [];
    state.selected = {};
    state.done = {};
    state.view = "capture";
    state.review = null;
    state.undo = null;
    state.notice = null;
  }

  function analyzeTranscript() {
    var transcript = (state.transcript || "").trim();
    if (!transcript) {
      return;
    }

    state.isBusy = true;
    state.view = "capture";
    state.review = null;
    state.notice = null;
    state.undo = null;
    setStatus("Analyzing transcript...");

    requestAnalysis(transcript).then(function (analysis) {
      state.analysis = analysis;
      state.analyzedTranscript = transcript;
      state.done = {};

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
          ? "Found " + count + " field" + (count === 1 ? "" : "s") + " to fill. Tick what you want, then review."
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
  // Review and insert
  // -------------------------------------------------------------------------

  function readField(field) {
    return field.isContentEditable ? (field.textContent || "") : (field.value || "");
  }

  function selectedCount() {
    return state.resolved.filter(function (_item, index) {
      return state.selected[index];
    }).length;
  }

  /** Step one: show exactly what would change. Nothing is written here. */
  function openReview() {
    var items = [];
    state.resolved.forEach(function (item, index) {
      if (state.selected[index]) {
        items.push({
          index: index,
          field: item.field,
          description: item.description,
          value: String(item.mapping.value),
          previous: readField(item.field)
        });
      }
    });

    if (!items.length) {
      setStatus("Nothing ticked. Select at least one field to insert.");
      return;
    }
    state.review = { items: items };
    state.view = "review";
    state.notice = null;
    setStatus("Check the changes below. Nothing is written until you confirm.");
  }

  function openReasonReview() {
    var target = window.OpenEMRASRScanner.getReasonTarget();
    var text = (state.transcript || "").trim();
    if (!target) {
      setStatus("No Reason for Visit field on this page.");
      return;
    }
    if (!text) {
      return;
    }
    state.review = {
      items: [{
        index: null,
        field: target,
        description: "Reason for visit",
        value: text,
        previous: readField(target)
      }]
    };
    state.view = "review";
    state.notice = null;
    setStatus("Check the change below. Nothing is written until you confirm.");
  }

  function closeReview() {
    state.view = "capture";
    state.review = null;
    setStatus(state.resolved.length
      ? "Tick what you want, then review."
      : "Ready. Record audio, or paste a transcript and analyze it.");
  }

  /** Step two: write, verify each write, and keep what is needed to undo. */
  function commitReview() {
    var items = (state.review && state.review.items) || [];
    var undo = [];
    var failed = [];

    items.forEach(function (item) {
      if (!document.contains(item.field)) {
        failed.push(item.description + " (no longer on the page)");
        return;
      }
      var before = readField(item.field);
      if (fillField(item.field, item.value)) {
        undo.push({ field: item.field, previous: before, index: item.index, description: item.description });
        if (item.index !== null) {
          state.done[item.index] = true;
          state.selected[item.index] = false;
        }
        flashField(item.field);
      } else {
        failed.push(item.description);
      }
    });

    state.undo = undo.length ? undo : null;
    state.view = "capture";
    state.review = null;

    if (failed.length) {
      state.notice = {
        kind: "warn",
        text: "Wrote " + undo.length + " field" + (undo.length === 1 ? "" : "s") +
          ". Could not write: " + failed.join(", ") + "."
      };
    } else {
      state.notice = {
        kind: "ok",
        text: "Inserted " + undo.length + " field" + (undo.length === 1 ? "" : "s") + " into the form."
      };
    }
    // On a phone the sheet covers the form, so fold it away and bring the first
    // filled field into view: seeing the result is the point of the insert.
    if (isMobile() && undo.length) {
      state.panelState.collapsed = true;
      window.setTimeout(function () { locateField(undo[0].field, true); }, 150);
    }
    setStatus("Done. Check the form, then save it as usual.");
  }

  function undoInsert() {
    if (!state.undo) {
      return;
    }
    var restored = 0;
    state.undo.forEach(function (entry) {
      if (document.contains(entry.field) && fillField(entry.field, entry.previous)) {
        restored += 1;
        flashField(entry.field);
        if (entry.index !== null) {
          delete state.done[entry.index];
          state.selected[entry.index] = true;
        }
      }
    });
    state.undo = null;
    state.notice = { kind: "info", text: "Undone. Restored " + restored + " field" + (restored === 1 ? "" : "s") + "." };
    setStatus("Restored the previous values.");
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
      field.focus({ preventScroll: true });

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

      return readField(field) === value;
    } catch (error) {
      console.error("Fill failed:", error);
      return false;
    }
  }

  function flashField(field) {
    field.classList.add("openemr-asr-written");
    window.setTimeout(function () {
      field.classList.remove("openemr-asr-written");
    }, 1800);
  }

  /** Scroll the real form field into view and pulse it, so the operator can see where a value goes. */
  function locateField(field, scroll) {
    if (!field || !document.contains(field)) {
      return;
    }
    if (scroll) {
      var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      field.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
    }
    field.classList.add("openemr-asr-locate");
    window.setTimeout(function () {
      field.classList.remove("openemr-asr-locate");
    }, scroll ? 1600 : 900);
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

  function sentenceCase(text) {
    var value = String(text || "").trim();
    return value ? value.charAt(0).toUpperCase() + value.slice(1) : "";
  }

  var ACRONYMS = /\b(bp|hr|spo2|bmi|ecg|ekg|icd|icd-10)\b/gi;

  /** Field labels come from the page in lower case; keep medical acronyms upper case. */
  function fieldTitle(text) {
    return sentenceCase(text).replace(ACRONYMS, function (match) {
      return match.toUpperCase();
    });
  }

  function entityLabel(name) {
    var key = String(name || "");
    return ENTITY_LABELS[key] || fieldTitle(key.replace(/_/g, " "));
  }

  function render() {
    if (!state.ui) {
      return;
    }
    var ui = state.ui;
    var inReview = state.view === "review";

    ui.statusEl.innerHTML =
      (state.showPulse ? '<span class="openemr-asr-pulse"></span>' : "") + escapeHtml(state.status);

    ui.card.classList.toggle("is-collapsed", Boolean(state.panelState.collapsed));
    ui.subtitleEl.textContent = state.panelState.collapsed && state.notice
      ? state.notice.text
      : "Dictate, review, then fill.";
    ui.toggleButton.setAttribute("aria-expanded", state.panelState.collapsed ? "false" : "true");
    ui.toggleButton.setAttribute(
      "aria-label", state.panelState.collapsed ? "Expand panel" : "Collapse panel");

    var hasTranscript = Boolean((state.transcript || "").trim());
    var stale = state.analysis && state.analyzedTranscript !== (state.transcript || "").trim();

    ui.captureEl.hidden = inReview;
    ui.reviewEl.hidden = !inReview;

    ui.recordButton.disabled = state.isRecording || state.isBusy;
    ui.recordButton.classList.toggle("is-live", state.isRecording);
    ui.stopButton.disabled = !state.isRecording;
    ui.analyzeButton.disabled = !hasTranscript || state.isBusy || state.isRecording;
    ui.analyzeButton.textContent = state.isBusy && !state.isRecording && !state.analysis
      ? "Working..." : (stale ? "Re-analyze" : "Analyze");

    ui.serviceEl.innerHTML = renderServiceLine();
    ui.qualityEl.innerHTML = renderQuality();
    ui.noticeEl.innerHTML = renderNotice();
    ui.staleEl.innerHTML = stale
      ? '<div class="openemr-asr-alert medium">Transcript changed since the last analysis. Re-analyze before inserting.</div>'
      : "";
    ui.resultsEl.innerHTML = renderResults();
    ui.reviewEl.innerHTML = inReview ? renderReview() : "";

    renderFooter(stale, hasTranscript);
  }

  function renderFooter(stale, hasTranscript) {
    var ui = state.ui;
    var inReview = state.view === "review";
    var count = inReview ? ((state.review && state.review.items) || []).length : selectedCount();
    var reasonAvailable = Boolean(window.OpenEMRASRScanner.getReasonTarget());
    var showInsert = inReview || state.resolved.length > 0;
    var showReason = !inReview && reasonAvailable;

    ui.footerEl.hidden = !(showInsert || showReason);
    ui.backButton.hidden = !inReview;
    ui.insertButton.hidden = !showInsert;
    ui.reasonButton.hidden = !showReason;

    ui.insertButton.disabled = count === 0 || state.isBusy || (!inReview && Boolean(stale));
    ui.insertButton.textContent = inReview
      ? "Insert " + count + " field" + (count === 1 ? "" : "s")
      : (count ? "Review " + count + " field" + (count === 1 ? "" : "s") : "Tick a field to insert");
    ui.reasonButton.disabled = !hasTranscript || state.isBusy;
  }

  function renderServiceLine() {
    if (state.capabilitiesLoading) {
      return '<span class="openemr-asr-dot loading"></span>Starting the analysis engine...';
    }
    if (state.capabilities === null) {
      return '<span class="openemr-asr-dot offline"></span>Service offline. Demo text only';
    }
    var layers = state.capabilities.layers || {};
    var degraded = Object.keys(layers).filter(function (key) {
      return layers[key].available === false;
    });
    var whisper = state.capabilities.whisper || {};
    var hosted = state.capabilities.deployment && state.capabilities.deployment.mode === "hosted";
    var html = '<span class="openemr-asr-dot online"></span>' +
      (hosted ? "Online demo" : "Service ready") + " · Whisper " + escapeHtml(whisper.model || "?") +
      (degraded.length ? " · " + degraded.length + " layer(s) degraded" : "");
    if (hosted && state.capabilities.deployment.note) {
      html += '<div class="openemr-asr-fineprint">' + escapeHtml(state.capabilities.deployment.note) + "</div>";
    }
    return html;
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

  function renderNotice() {
    if (!state.notice) {
      return "";
    }
    var notice = state.notice;
    var icon = notice.kind === "ok" ? "✓" : (notice.kind === "warn" ? "!" : "i");
    return '<div class="openemr-asr-notice ' + escapeHtml(notice.kind) + '" role="status">' +
      '<span class="openemr-asr-notice-icon" aria-hidden="true">' + icon + "</span>" +
      '<span class="openemr-asr-notice-text">' + escapeHtml(notice.text) + "</span>" +
      (state.undo ? '<button type="button" class="openemr-asr-link" data-action="undo">Undo</button>' : "") +
      '<button type="button" class="openemr-asr-link quiet" data-action="dismiss" aria-label="Dismiss">×</button>' +
      "</div>";
  }

  var LOCATE_ICON =
    '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">' +
    '<circle cx="8" cy="8" r="3.2" fill="none" stroke="currentColor" stroke-width="1.5"/>' +
    '<path d="M8 1v3M8 12v3M1 8h3M12 8h3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>';

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
      html += '<div class="openemr-asr-section"><span>Fill this form</span>' +
        '<span class="openemr-asr-section-actions">' +
        '<button type="button" class="openemr-asr-link" data-action="select-all">All</button>' +
        '<button type="button" class="openemr-asr-link" data-action="select-none">None</button>' +
        "</span></div>";

      state.resolved.forEach(function (item, index) {
        var mapping = item.mapping;
        var percent = Math.round((mapping.confidence || 0) * 100);
        var klass = confidenceClass(mapping.confidence || 0);
        var checked = state.selected[index];
        var occupied = String(readField(item.field) || "").trim();
        var chips = "";

        if (state.done[index]) {
          chips += '<span class="openemr-asr-chip ok">Inserted</span>';
        } else {
          chips += occupied
            ? '<span class="openemr-asr-chip warn" title="' + escapeHtml(previewValue(occupied, 120)) +
              '">Replaces existing text</span>'
            : '<span class="openemr-asr-chip">Empty field</span>';
          if (mapping.needs_review) {
            chips += '<span class="openemr-asr-chip warn">Check first</span>';
          }
        }

        html +=
          '<div class="openemr-asr-field' + (checked ? " is-checked" : "") + (state.done[index] ? " is-done" : "") +
          '" data-index="' + index + '" title="Matched by ' + escapeHtml(item.strategy) +
          ": " + escapeHtml(String(item.matchedOn)) + '">' +
          '<input type="checkbox" id="openemr-asr-f' + index + '" data-index="' + index + '"' +
          (checked ? " checked" : "") + ">" +
          '<label for="openemr-asr-f' + index + '" class="openemr-asr-field-main">' +
          '<span class="openemr-asr-field-head">' +
          "<b>" + escapeHtml(fieldTitle(item.description)) + "</b>" +
          '<span class="openemr-asr-badge ' + klass + '">' + percent + "%</span></span>" +
          '<span class="openemr-asr-value">' + escapeHtml(previewValue(mapping.value, 140)) + "</span>" +
          '<span class="openemr-asr-chips">' + chips + "</span>" +
          "</label>" +
          '<button type="button" class="openemr-asr-locatebtn" data-locate="' + index +
          '" aria-label="Show this field on the page" title="Show on page">' + LOCATE_ICON + "</button>" +
          "</div>";
      });
    }

    if (state.unresolved.length) {
      html += '<details class="openemr-asr-more"><summary>Also found, but not on this form (' +
        state.unresolved.length + ")</summary>" +
        '<div class="openemr-asr-tags">' +
        state.unresolved.map(function (mapping) {
          return '<span class="openemr-asr-tag">' + escapeHtml(entityLabel(mapping.entity_type)) + "</span>";
        }).join("") + "</div></details>";
    }

    var codes = (analysis.icd10 || {}).candidates || [];
    if (codes.length) {
      html += '<div class="openemr-asr-section"><span>Suggested diagnosis codes</span></div>';
      codes.slice(0, 4).forEach(function (code) {
        html += '<div class="openemr-asr-code">' +
          "<b>" + escapeHtml(code.code) + "</b>" +
          '<span class="openemr-asr-code-text">' + escapeHtml(code.description) + "</span>" +
          '<span class="openemr-asr-badge ' + confidenceClass(code.confidence) + '">' +
          Math.round(code.confidence * 100) + "%</span></div>";
      });
      html += '<div class="openemr-asr-muted">Suggestions only. Verify before billing.</div>';
    }

    if (analysis.timings_ms) {
      html += '<div class="openemr-asr-muted">Analysis took ' +
        escapeHtml(String(Math.round(analysis.timings_ms.total))) + " ms.</div>";
    }

    return html;
  }

  function renderReview() {
    var items = (state.review && state.review.items) || [];
    var html =
      '<div class="openemr-asr-review-head">' +
      "<b>Review before inserting</b>" +
      "<span>" + items.length + " change" + (items.length === 1 ? "" : "s") + "</span></div>";

    items.forEach(function (item, position) {
      var previous = String(item.previous || "").trim();
      html +=
        '<div class="openemr-asr-change" data-position="' + position + '">' +
        '<div class="openemr-asr-change-head"><b>' + escapeHtml(fieldTitle(item.description)) + "</b>" +
        '<button type="button" class="openemr-asr-locatebtn" data-locate-review="' + position +
        '" aria-label="Show this field on the page" title="Show on page">' + LOCATE_ICON + "</button></div>" +
        (previous
          ? '<div class="openemr-asr-old"><span>Replaces</span>' + escapeHtml(previewValue(previous, 160)) + "</div>"
          : "") +
        '<div class="openemr-asr-new"><span>' + (previous ? "With" : "Adds") + "</span>" +
        escapeHtml(previewValue(item.value, 400)) + "</div></div>";
    });

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
   * The page-facing classes (highlight, written, locate) are deliberately NOT
   * prefixed, because they decorate form fields out in the host document.
   */
  function injectStyles() {
    var ROOT = "#openemr-asr-demo-root";
    var rules = [
      // Panel shell
      ROOT + "{position:fixed;right:20px;bottom:20px;z-index:2147483647;" +
        "font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Arial,sans-serif;font-size:13px;" +
        "line-height:1.5;width:" + PANEL_WIDTH + "px;max-width:calc(100vw - 24px);" +
        "text-align:left;box-sizing:border-box;color-scheme:dark}",
      ROOT + " *{box-sizing:border-box}",
      ROOT + " [hidden]{display:none !important}",

      // Neutralise host form styling on the panel's own controls.
      ROOT + " input,#openemr-asr-demo-root textarea,#openemr-asr-demo-root button," +
        "#openemr-asr-demo-root summary{" +
        "font-family:inherit;margin:0;min-width:0;max-width:none;float:none;" +
        "box-shadow:none;text-transform:none;letter-spacing:normal}",
      ROOT + " button{display:inline-block;-webkit-appearance:none;appearance:none}",
      ROOT + ' input[type="checkbox"]{display:inline-block;width:16px;height:16px;flex:0 0 16px;' +
        "padding:0;border:0;background:none;appearance:auto;-webkit-appearance:checkbox;" +
        "accent-color:#38bdf8;cursor:pointer}",
      ROOT + " button:focus-visible,#openemr-asr-demo-root textarea:focus-visible," +
        '#openemr-asr-demo-root input[type="checkbox"]:focus-visible,#openemr-asr-demo-root summary:focus-visible{' +
        "outline:2px solid #7dd3fc;outline-offset:2px}",

      ROOT + " .openemr-asr-card{background:#0b1220;color:#e2e8f0;border-radius:16px;" +
        "overflow:hidden;box-shadow:0 24px 60px rgba(2,6,23,.45),0 0 0 1px rgba(148,163,184,.2);" +
        "display:flex;flex-direction:column;max-height:calc(100vh - 40px)}",
      ROOT + " .openemr-asr-card.is-collapsed .openemr-asr-main{display:none}",
      ROOT + " .openemr-asr-header{padding:12px 14px;background:linear-gradient(135deg,#1d4ed8,#0f766e);" +
        "display:flex;align-items:center;justify-content:space-between;gap:10px;" +
        "cursor:move;user-select:none;-webkit-user-select:none;touch-action:none}",
      ROOT + " .openemr-asr-title{font-size:14px;font-weight:700;margin:0;color:#f8fafc}",
      ROOT + " .openemr-asr-subtitle{margin:2px 0 0;font-size:11.5px;color:#e0f2fe;opacity:.92}",
      ROOT + " .openemr-asr-toggle{border:0;border-radius:999px;width:28px;height:28px;" +
        "background:rgba(255,255,255,.18);color:#f8fafc;font-size:16px;line-height:1;" +
        "cursor:pointer;flex:0 0 28px;padding:0;transition:background .15s}",
      ROOT + " .openemr-asr-toggle:hover{background:rgba(255,255,255,.3)}",

      ROOT + " .openemr-asr-main{display:flex;flex-direction:column;min-height:0;flex:1 1 auto}",
      ROOT + " .openemr-asr-scroll{padding:13px 13px 6px;overflow-y:auto;min-height:0;flex:1 1 auto;" +
        "max-height:min(62vh,560px);overscroll-behavior:contain;scrollbar-width:thin;" +
        "scrollbar-color:#334155 transparent}",

      // Service line and status
      ROOT + " .openemr-asr-service{font-size:11px;color:#94a3b8;margin-bottom:7px;" +
        "display:flex;align-items:center;gap:6px;flex-wrap:wrap}",
      ROOT + " .openemr-asr-dot{width:7px;height:7px;border-radius:999px;flex:0 0 7px}",
      ROOT + " .openemr-asr-dot.online{background:#22c55e}",
      ROOT + " .openemr-asr-dot.offline{background:#ef4444}",
      ROOT + " .openemr-asr-dot.loading{background:#facc15;animation:openemr-asr-blink 1s infinite}",
      ROOT + " .openemr-asr-fineprint{flex:1 0 100%;font-size:10.5px;line-height:1.45;color:#64748b}",
      ROOT + " .openemr-asr-status{font-size:12.5px;color:#cbd5e1;margin-bottom:10px;min-height:19px}",

      // Buttons
      ROOT + " .openemr-asr-controls{display:flex;gap:8px;margin-bottom:10px;align-items:center}",
      ROOT + " .openemr-asr-row{display:flex;gap:8px;margin:9px 0 0}",
      ROOT + " .openemr-asr-button{flex:1 1 0;width:auto;border:0;border-radius:10px;" +
        "min-height:38px;padding:9px 12px;font-size:13px;font-weight:700;cursor:pointer;line-height:1.2;" +
        "transition:background .15s,transform .1s,opacity .15s,box-shadow .15s}",
      ROOT + " .openemr-asr-button:active:not(:disabled){transform:scale(.98)}",
      ROOT + " .openemr-asr-button.primary{background:#22c55e;color:#052e16}",
      ROOT + " .openemr-asr-button.primary:hover:not(:disabled){background:#4ade80}",
      ROOT + " .openemr-asr-button.primary.is-live{background:#ef4444;color:#fff;" +
        "animation:openemr-asr-glow 1.4s infinite}",
      ROOT + " .openemr-asr-button.warn{background:#f97316;color:#fff}",
      ROOT + " .openemr-asr-button.accent{background:#38bdf8;color:#082f49}",
      ROOT + " .openemr-asr-button.accent:hover:not(:disabled){background:#7dd3fc}",
      ROOT + " .openemr-asr-button.go{background:#22c55e;color:#052e16;min-height:42px;font-size:13.5px}",
      ROOT + " .openemr-asr-button.go:hover:not(:disabled){background:#4ade80}",
      ROOT + " .openemr-asr-button.ghost{background:transparent;color:#e2e8f0;" +
        "border:1px solid rgba(226,232,240,.3)}",
      ROOT + " .openemr-asr-button.ghost:hover:not(:disabled){background:rgba(226,232,240,.08)}",
      ROOT + " .openemr-asr-button:disabled{opacity:.45;cursor:not-allowed}",
      ROOT + " .openemr-asr-timer{font-size:12px;color:#fca5a5;font-variant-numeric:tabular-nums;" +
        "min-width:64px;text-align:right}",
      ROOT + " .openemr-asr-link{background:none;border:0;padding:2px 4px;color:#7dd3fc;font-size:12px;" +
        "font-weight:600;cursor:pointer;border-radius:6px}",
      ROOT + " .openemr-asr-link:hover{background:rgba(125,211,252,.12)}",
      ROOT + " .openemr-asr-link.quiet{color:#94a3b8;font-size:15px;line-height:1}",
      ROOT + " .openemr-asr-textlink{background:none;border:0;padding:8px;color:#94a3b8;font-size:12px;" +
        "font-weight:600;cursor:pointer;width:100%;border-radius:8px}",
      ROOT + " .openemr-asr-textlink:hover:not(:disabled){color:#e2e8f0;background:rgba(148,163,184,.1)}",
      ROOT + " .openemr-asr-textlink:disabled{opacity:.4;cursor:not-allowed}",

      // Transcript box
      ROOT + " .openemr-asr-preview{display:block;width:100%;min-height:88px;border-radius:10px;" +
        "border:1px solid #334155;background:#020617;color:#f8fafc;padding:10px;" +
        "resize:vertical;font-size:13px;line-height:1.5;transition:border-color .15s}",
      ROOT + " .openemr-asr-preview:focus{border-color:#38bdf8;outline:none}",

      // Confidence meter
      ROOT + " .openemr-asr-meter{margin:10px 0 6px}",
      ROOT + " .openemr-asr-meter-label{font-size:11px;color:#94a3b8;margin-bottom:4px}",
      ROOT + " .openemr-asr-bar{height:5px;border-radius:999px;background:#1e293b;overflow:hidden}",
      ROOT + " .openemr-asr-bar i{display:block;height:100%;border-radius:999px;transition:width .4s ease}",
      ROOT + " .openemr-asr-bar i.high{background:#22c55e}",
      ROOT + " .openemr-asr-bar i.mid{background:#facc15}",
      ROOT + " .openemr-asr-bar i.low{background:#ef4444}",

      // Alerts and notices
      ROOT + " .openemr-asr-alert{font-size:12px;line-height:1.45;border-radius:9px;" +
        "padding:8px 10px;margin:7px 0;border-left:3px solid}",
      ROOT + " .openemr-asr-alert.high{background:rgba(239,68,68,.14);border-color:#ef4444;color:#fecaca}",
      ROOT + " .openemr-asr-alert.medium{background:rgba(250,204,21,.12);border-color:#facc15;color:#fde68a}",
      ROOT + " .openemr-asr-alert.info{background:rgba(56,189,248,.12);border-color:#38bdf8;color:#bae6fd}",
      ROOT + " .openemr-asr-notice{display:flex;align-items:center;gap:9px;border-radius:10px;" +
        "padding:9px 10px;margin:0 0 10px;font-size:12.5px;animation:openemr-asr-rise .25s ease}",
      ROOT + " .openemr-asr-notice.ok{background:rgba(34,197,94,.14);color:#bbf7d0}",
      ROOT + " .openemr-asr-notice.warn{background:rgba(250,204,21,.13);color:#fde68a}",
      ROOT + " .openemr-asr-notice.info{background:rgba(56,189,248,.13);color:#bae6fd}",
      ROOT + " .openemr-asr-notice-icon{width:20px;height:20px;border-radius:999px;flex:0 0 20px;" +
        "display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;" +
        "background:rgba(255,255,255,.14)}",
      ROOT + " .openemr-asr-notice-text{flex:1 1 auto;min-width:0}",

      // Sections and field cards
      ROOT + " .openemr-asr-section{display:flex;align-items:center;justify-content:space-between;" +
        "font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;" +
        "font-weight:700;margin:13px 0 6px}",
      ROOT + " .openemr-asr-section-actions{display:flex;gap:2px;text-transform:none;letter-spacing:0}",
      ROOT + " .openemr-asr-field{display:flex;gap:10px;align-items:flex-start;" +
        "padding:10px;margin:0 0 7px;background:#111a2e;border:1px solid #1e293b;" +
        "border-radius:11px;transition:border-color .15s,background .15s,opacity .2s}",
      ROOT + " .openemr-asr-field:hover{border-color:#334155;background:#13203a}",
      ROOT + " .openemr-asr-field.is-checked{border-color:rgba(56,189,248,.55);background:#0f2038}",
      ROOT + " .openemr-asr-field.is-done{opacity:.6}",
      ROOT + " .openemr-asr-field input[type=checkbox]{margin-top:2px}",
      ROOT + " .openemr-asr-field-main{flex:1 1 auto;min-width:0;display:block;cursor:pointer;" +
        "font-weight:400;color:#e2e8f0;margin:0;padding:0;width:auto}",
      ROOT + " .openemr-asr-field-head{display:flex;align-items:center;gap:8px;" +
        "justify-content:space-between}",
      ROOT + " .openemr-asr-field-head b{font-size:12.5px;color:#f1f5f9;font-weight:700}",
      ROOT + " .openemr-asr-value{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;" +
        "overflow:hidden;font-size:12px;color:#cbd5e1;margin-top:3px;overflow-wrap:anywhere}",
      ROOT + " .openemr-asr-chips{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}",
      ROOT + " .openemr-asr-chip{font-size:10.5px;font-weight:600;border-radius:999px;padding:1px 8px;" +
        "background:rgba(148,163,184,.14);color:#94a3b8;white-space:nowrap}",
      ROOT + " .openemr-asr-chip.warn{background:rgba(245,158,11,.16);color:#fcd34d}",
      ROOT + " .openemr-asr-chip.ok{background:rgba(34,197,94,.18);color:#86efac}",
      ROOT + " .openemr-asr-locatebtn{flex:0 0 28px;width:28px;height:28px;border-radius:8px;border:0;" +
        "background:transparent;color:#64748b;cursor:pointer;display:flex;align-items:center;" +
        "justify-content:center;padding:0;transition:background .15s,color .15s}",
      ROOT + " .openemr-asr-locatebtn:hover{background:rgba(56,189,248,.15);color:#7dd3fc}",
      ROOT + " .openemr-asr-badge{font-size:10.5px;font-weight:700;border-radius:999px;" +
        "padding:1px 7px;flex:0 0 auto;white-space:nowrap}",
      ROOT + " .openemr-asr-badge.high{background:rgba(34,197,94,.2);color:#86efac}",
      ROOT + " .openemr-asr-badge.mid{background:rgba(250,204,21,.2);color:#fde68a}",
      ROOT + " .openemr-asr-badge.low{background:rgba(239,68,68,.2);color:#fecaca}",

      // Values the form has no field for
      ROOT + " .openemr-asr-more{margin:6px 0 4px;font-size:12px;color:#94a3b8}",
      ROOT + " .openemr-asr-more summary{cursor:pointer;padding:4px 0;list-style:none;color:#94a3b8}",
      ROOT + " .openemr-asr-more summary::-webkit-details-marker{display:none}",
      ROOT + " .openemr-asr-more summary::before{content:'›';display:inline-block;margin-right:6px;" +
        "transition:transform .15s}",
      ROOT + " .openemr-asr-more[open] summary::before{transform:rotate(90deg)}",
      ROOT + " .openemr-asr-tags{display:flex;flex-wrap:wrap;gap:5px;padding:4px 0 2px}",
      ROOT + " .openemr-asr-tag{font-size:11px;border-radius:7px;padding:2px 8px;" +
        "background:#111a2e;border:1px solid #1e293b;color:#94a3b8}",

      // Diagnosis codes and footnotes
      ROOT + " .openemr-asr-code{display:flex;align-items:center;gap:8px;font-size:12px;color:#cbd5e1;" +
        "padding:6px 0;border-bottom:1px solid #1a2438}",
      ROOT + " .openemr-asr-code b{color:#f1f5f9;font-family:ui-monospace,Menlo,monospace;flex:0 0 auto;" +
        "min-width:46px}",
      ROOT + " .openemr-asr-code-text{flex:1 1 auto;min-width:0}",
      ROOT + " .openemr-asr-muted{font-size:10.5px;color:#64748b;margin-top:6px;line-height:1.45}",

      // Review step
      ROOT + " .openemr-asr-review-head{display:flex;align-items:baseline;justify-content:space-between;" +
        "margin:2px 0 10px}",
      ROOT + " .openemr-asr-review-head b{font-size:14px;color:#f1f5f9}",
      ROOT + " .openemr-asr-review-head span{font-size:11.5px;color:#94a3b8}",
      ROOT + " .openemr-asr-change{background:#111a2e;border:1px solid #1e293b;border-radius:11px;" +
        "padding:10px;margin:0 0 8px}",
      ROOT + " .openemr-asr-change-head{display:flex;align-items:center;justify-content:space-between;" +
        "margin-bottom:6px}",
      ROOT + " .openemr-asr-change-head b{font-size:12.5px;color:#f1f5f9}",
      ROOT + " .openemr-asr-old,#openemr-asr-demo-root .openemr-asr-new{font-size:12px;border-radius:8px;" +
        "padding:6px 9px;margin-top:5px;overflow-wrap:anywhere;line-height:1.45}",
      ROOT + " .openemr-asr-old{background:rgba(245,158,11,.1);color:#fcd34d;text-decoration:line-through;" +
        "text-decoration-color:rgba(252,211,77,.45)}",
      ROOT + " .openemr-asr-new{background:rgba(34,197,94,.1);color:#bbf7d0}",
      ROOT + " .openemr-asr-old span,#openemr-asr-demo-root .openemr-asr-new span{display:block;" +
        "font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;opacity:.75;" +
        "text-decoration:none}",

      // Sticky action bar
      ROOT + " .openemr-asr-footer{flex:0 0 auto;padding:10px 13px calc(10px + env(safe-area-inset-bottom,0px));" +
        "border-top:1px solid #1a2438;background:#0b1220}",
      ROOT + " .openemr-asr-footer .openemr-asr-row{margin:0}",
      ROOT + " .openemr-asr-footer .openemr-asr-textlink{margin-top:4px}",

      ROOT + " .openemr-asr-pulse{display:inline-block;width:8px;height:8px;margin-right:6px;" +
        "border-radius:999px;background:#f43f5e;animation:openemr-asr-pulse 1.2s infinite;" +
        "vertical-align:middle}",

      // Page-facing decorations: intentionally unprefixed.
      ".openemr-asr-highlight{outline:3px solid #22c55e !important;outline-offset:2px;" +
        "transition:outline-color .2s}",
      ".openemr-asr-written{outline:3px solid #38bdf8 !important;outline-offset:2px;" +
        "background-color:rgba(56,189,248,.1) !important;transition:background-color .6s,outline-color .3s}",
      ".openemr-asr-locate{outline:3px solid #f59e0b !important;outline-offset:3px;" +
        "box-shadow:0 0 0 6px rgba(245,158,11,.2) !important;transition:box-shadow .25s}",

      "@keyframes openemr-asr-pulse{0%{box-shadow:0 0 0 0 rgba(244,63,94,.65)}" +
        "70%{box-shadow:0 0 0 11px rgba(244,63,94,0)}100%{box-shadow:0 0 0 0 rgba(244,63,94,0)}}",
      "@keyframes openemr-asr-glow{0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,.55)}" +
        "50%{box-shadow:0 0 0 7px rgba(239,68,68,0)}}",
      "@keyframes openemr-asr-blink{50%{opacity:.35}}",
      "@keyframes openemr-asr-rise{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}",
      "@media (prefers-reduced-motion:reduce){" + ROOT + " *{animation:none !important;" +
        "transition:none !important}}",

      // Phones: a bottom sheet instead of a floating card, with touch-sized controls.
      "@media " + MOBILE_QUERY + "{" +
        ROOT + "{left:0 !important;right:0 !important;top:auto !important;bottom:0 !important;" +
          "width:100% !important;max-width:none !important}" +
        ROOT + " .openemr-asr-card{border-radius:18px 18px 0 0;max-height:88vh;" +
          "max-height:88dvh;box-shadow:0 -10px 40px rgba(2,6,23,.5)}" +
        ROOT + " .openemr-asr-header{cursor:pointer;touch-action:auto;padding:14px 16px}" +
        ROOT + " .openemr-asr-scroll{max-height:none}" +
        ROOT + " .openemr-asr-button{min-height:46px;font-size:14px}" +
        ROOT + " .openemr-asr-button.go{min-height:48px}" +
        ROOT + " .openemr-asr-preview{font-size:16px}" +
        ROOT + " .openemr-asr-locatebtn{flex-basis:36px;width:36px;height:36px}" +
        ROOT + ' input[type="checkbox"]{width:20px;height:20px;flex-basis:20px}' +
      "}"
    ];

    var style = document.createElement("style");
    style.textContent = rules.join("\n");
    document.documentElement.appendChild(style);
  }

  function buildUI() {
    var root = document.createElement("div");
    root.id = "openemr-asr-demo-root";
    root.setAttribute("role", "region");
    root.setAttribute("aria-label", "Voice capture");
    root.innerHTML = [
      '<div class="openemr-asr-card">',
      '  <div class="openemr-asr-header" data-role="drag-handle">',
      "    <div>",
      '      <p class="openemr-asr-title">OpenEMR Voice Capture</p>',
      '      <p class="openemr-asr-subtitle" data-role="subtitle">Dictate, review, then fill.</p>',
      "    </div>",
      '    <button type="button" class="openemr-asr-toggle" data-role="toggle" aria-label="Collapse panel" aria-expanded="true">⌄</button>',
      "  </div>",
      '  <div class="openemr-asr-main">',
      '    <div class="openemr-asr-scroll" data-role="scroll">',
      '      <div class="openemr-asr-service" data-role="service"></div>',
      '      <div class="openemr-asr-status" data-role="status" aria-live="polite"></div>',
      '      <div data-role="notice"></div>',
      '      <div data-role="capture">',
      '        <div class="openemr-asr-controls">',
      '          <button type="button" class="openemr-asr-button primary" data-role="record">Start mic</button>',
      '          <button type="button" class="openemr-asr-button warn" data-role="stop" disabled>Stop</button>',
      '          <span class="openemr-asr-timer" data-role="timer" aria-hidden="true"></span>',
      "        </div>",
      '        <textarea class="openemr-asr-preview" data-role="preview" aria-label="Transcript" ',
      '          placeholder="The transcript appears here. You can edit it before analyzing."></textarea>',
      '        <div data-role="quality"></div>',
      '        <div class="openemr-asr-row">',
      '          <button type="button" class="openemr-asr-button accent" data-role="analyze" disabled>Analyze</button>',
      '          <button type="button" class="openemr-asr-button ghost" data-role="demo">Demo text</button>',
      "        </div>",
      '        <div data-role="stale"></div>',
      '        <div data-role="results"></div>',
      "      </div>",
      '      <div data-role="review" hidden></div>',
      "    </div>",
      '    <div class="openemr-asr-footer" data-role="footer" hidden>',
      '      <div class="openemr-asr-row">',
      '        <button type="button" class="openemr-asr-button ghost" data-role="back" hidden>Back</button>',
      '        <button type="button" class="openemr-asr-button go" data-role="insert" hidden>Review fields</button>',
      "      </div>",
      '      <button type="button" class="openemr-asr-textlink" data-role="reason" hidden>',
      "        Put the whole transcript in Reason for Visit instead</button>",
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
      subtitleEl: pick("subtitle"),
      scrollEl: pick("scroll"),
      serviceEl: pick("service"),
      statusEl: pick("status"),
      noticeEl: pick("notice"),
      captureEl: pick("capture"),
      reviewEl: pick("review"),
      timerEl: pick("timer"),
      qualityEl: pick("quality"),
      staleEl: pick("stale"),
      resultsEl: pick("results"),
      previewEl: pick("preview"),
      recordButton: pick("record"),
      stopButton: pick("stop"),
      analyzeButton: pick("analyze"),
      demoButton: pick("demo"),
      footerEl: pick("footer"),
      backButton: pick("back"),
      insertButton: pick("insert"),
      reasonButton: pick("reason")
    };

    var ui = state.ui;

    ui.previewEl.addEventListener("input", function () {
      state.transcript = ui.previewEl.value;
      render();
    });
    ui.recordButton.addEventListener("click", startRecording);
    ui.stopButton.addEventListener("click", stopRecording);
    ui.analyzeButton.addEventListener("click", analyzeTranscript);
    ui.backButton.addEventListener("click", closeReview);
    ui.insertButton.addEventListener("click", function () {
      if (state.view === "review") {
        commitReview();
      } else {
        openReview();
      }
    });
    ui.reasonButton.addEventListener("click", openReasonReview);
    ui.demoButton.addEventListener("click", function () {
      resetResults();
      state.asrQuality = null;
      setTranscript(DEMO_TRANSCRIPT);
      setStatus("Demo transcript loaded. Press Analyze to see the clinical layers.");
    });

    ui.toggleButton.addEventListener("click", function (event) {
      event.stopPropagation();
      toggleCollapsed();
    });
    // On a phone the whole header is the handle, because there is nothing to drag.
    ui.dragHandle.addEventListener("click", function (event) {
      if (isMobile() && event.target !== ui.toggleButton) {
        toggleCollapsed();
      }
    });

    // One set of listeners for everything the results and review lists render.
    ui.scrollEl.addEventListener("change", function (event) {
      var box = event.target;
      if (box && box.matches && box.matches('input[type="checkbox"][data-index]')) {
        var index = box.getAttribute("data-index");
        state.selected[index] = box.checked;
        var card = box.closest(".openemr-asr-field");
        if (card) {
          card.classList.toggle("is-checked", box.checked);
        }
        renderFooter(
          state.analysis && state.analyzedTranscript !== (state.transcript || "").trim(),
          Boolean((state.transcript || "").trim())
        );
      }
    });
    ui.scrollEl.addEventListener("click", function (event) {
      var button = event.target.closest && event.target.closest("button");
      if (!button) {
        return;
      }
      var action = button.getAttribute("data-action");
      if (action === "undo") {
        undoInsert();
      } else if (action === "dismiss") {
        state.notice = null;
        state.undo = null;
        render();
      } else if (action === "select-all" || action === "select-none") {
        state.resolved.forEach(function (_item, index) {
          if (!state.done[index]) {
            state.selected[index] = action === "select-all";
          }
        });
        render();
      } else if (button.hasAttribute("data-locate")) {
        var item = state.resolved[Number(button.getAttribute("data-locate"))];
        locateField(item && item.field, true);
      } else if (button.hasAttribute("data-locate-review")) {
        var change = state.review && state.review.items[Number(button.getAttribute("data-locate-review"))];
        locateField(change && change.field, true);
      }
    });
    // Hovering a card previews where it will land, without moving the page.
    ui.scrollEl.addEventListener("mouseover", function (event) {
      var card = event.target.closest && event.target.closest(".openemr-asr-field");
      if (card && !card.contains(event.relatedTarget)) {
        var item = state.resolved[Number(card.getAttribute("data-index"))];
        locateField(item && item.field, false);
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && state.view === "review") {
        closeReview();
      }
    });

    setupDragging();
    render();
  }

  function toggleCollapsed() {
    state.panelState.collapsed = !state.panelState.collapsed;
    persistPanelState();
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
      if (event.button !== 0 || isMobile() || (event.target.closest && event.target.closest("button"))) {
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
    // A phone gets a bottom sheet: it starts folded so the form is visible, and
    // a position saved on a desktop would be meaningless there.
    if (isMobile()) {
      if (!state.panelState.saved) {
        state.panelState.collapsed = true;
      }
      return;
    }
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
        position: parsed.position || null,
        saved: Boolean(raw)
      };
    } catch (error) {
      return { collapsed: false, position: null, saved: false };
    }
  }

  function persistPanelState() {
    state.panelState.saved = true;
    try {
      window.localStorage.setItem(PANEL_STATE_KEY, JSON.stringify(state.panelState));
    } catch (error) {
      /* storage unavailable (private window); position simply is not remembered */
    }
  }
})();
