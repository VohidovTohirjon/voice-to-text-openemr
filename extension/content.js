(function () {
  if (window.__openemrAsrDemoLoaded) {
    return;
  }

  if (shouldAbortForCurrentPage()) {
    return;
  }

  window.__openemrAsrDemoLoaded = true;

  var API_URL = "http://127.0.0.1:8000/transcribe";
  var DEMO_TRANSCRIPT = "Patient reports headache and mild fever for two days.";
  var PANEL_STATE_KEY = "openemr-asr-demo-panel-state";
  var DEFAULT_OFFSET = 20;
  var PANEL_WIDTH = 320;
  var state = {
    target: null,
    transcript: "",
    isRecording: false,
    status: "Looking for the encounter field...",
    mediaRecorder: null,
    stream: null,
    audioChunks: [],
    showPulse: false,
    ui: null,
    panelState: loadPanelState(),
    targetObserver: null
  };

  waitForValidTarget(initializeWhenReady);

  function initializeWhenReady(targetField) {
    if (state.ui) {
      state.target = makeTarget(targetField);
      highlightTarget(targetField);
      setStatus("Ready to capture audio for Reason for Visit.");
      return;
    }

    state.target = makeTarget(targetField);
    injectStyles();
    buildUI();
    applySavedPanelState();
    highlightTarget(targetField);
    setStatus("Ready to capture audio for Reason for Visit.");
    startFieldWatcher();
  }

  function shouldAbortForCurrentPage() {
    var path = window.location.pathname || "";
    return path.includes("/interface/login/");
  }

  function isRelevantPage() {
    var path = window.location.pathname || "";
    return (
      path.includes("/encounter/") ||
      path.includes("/forms/") ||
      path.includes("/newpatient/") ||
      path.includes("/newGroupEncounter/")
    );
  }

  function waitForValidTarget(callback) {
    var immediateTarget = findReasonTarget();
    if (immediateTarget) {
      callback(immediateTarget);
      return;
    }

    if (!isRelevantPage()) {
      return;
    }

    var timeoutId = null;
    var observer = new MutationObserver(function () {
      var targetField = findReasonTarget();
      if (!targetField) {
        return;
      }

      observer.disconnect();
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
      callback(targetField);
    });

    observer.observe(document.documentElement, {
      childList: true,
      subtree: true
    });

    timeoutId = window.setTimeout(function () {
      observer.disconnect();
    }, 10000);
  }

  function findReasonTarget() {
    var byName = document.querySelector('textarea[name="reason"]');
    if (isValidReasonTarget(byName)) {
      return byName;
    }

    var byId = document.querySelector("#reason");
    if (isValidReasonTarget(byId)) {
      return byId;
    }

    return null;
  }

  function makeTarget(field) {
    return {
      field: field,
      description: "Reason for Visit"
    };
  }

  function injectStyles() {
    var style = document.createElement("style");
    style.textContent = [
      "#openemr-asr-demo-root { position: fixed; right: 20px; bottom: 20px; z-index: 2147483647; font-family: Arial, sans-serif; width: 320px; max-width: calc(100vw - 24px); }",
      ".openemr-asr-card { background: #0f172a; color: #e2e8f0; border-radius: 14px; box-shadow: 0 18px 40px rgba(15, 23, 42, 0.28); overflow: hidden; border: 1px solid rgba(148, 163, 184, 0.25); backdrop-filter: blur(8px); }",
      ".openemr-asr-card.is-collapsed .openemr-asr-body { display: none; }",
      ".openemr-asr-header { padding: 12px 14px; background: linear-gradient(135deg, #1d4ed8, #0f766e); display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; cursor: move; user-select: none; }",
      ".openemr-asr-heading { min-width: 0; }",
      ".openemr-asr-title { font-size: 14px; font-weight: 700; margin: 0; }",
      ".openemr-asr-subtitle { margin: 4px 0 0; font-size: 12px; opacity: 0.88; }",
      ".openemr-asr-toggle { border: 0; border-radius: 999px; width: 28px; height: 28px; background: rgba(255, 255, 255, 0.16); color: #f8fafc; font-size: 18px; line-height: 1; cursor: pointer; flex-shrink: 0; }",
      ".openemr-asr-body { padding: 14px; }",
      ".openemr-asr-status { font-size: 12px; color: #cbd5e1; margin-bottom: 10px; line-height: 1.4; }",
      ".openemr-asr-controls { display: flex; gap: 8px; margin-bottom: 10px; }",
      ".openemr-asr-button { flex: 1; border: 0; border-radius: 10px; padding: 10px 12px; font-size: 13px; font-weight: 700; cursor: pointer; }",
      ".openemr-asr-button.primary { background: #22c55e; color: #052e16; }",
      ".openemr-asr-button.warn { background: #f97316; color: white; }",
      ".openemr-asr-button.secondary { background: #e2e8f0; color: #0f172a; }",
      ".openemr-asr-button.ghost { background: transparent; color: #e2e8f0; border: 1px solid rgba(226, 232, 240, 0.3); }",
      ".openemr-asr-button:disabled { opacity: 0.55; cursor: not-allowed; }",
      ".openemr-asr-preview { width: 100%; min-height: 96px; box-sizing: border-box; border-radius: 10px; border: 1px solid #475569; background: #020617; color: #f8fafc; padding: 10px; resize: vertical; font-size: 13px; line-height: 1.45; }",
      ".openemr-asr-row { display: flex; gap: 8px; margin-top: 10px; }",
      ".openemr-asr-target { margin-top: 10px; font-size: 12px; color: #94a3b8; }",
      ".openemr-asr-pulse { display: inline-block; width: 9px; height: 9px; margin-right: 6px; border-radius: 999px; background: #f43f5e; box-shadow: 0 0 0 rgba(244, 63, 94, 0.6); animation: openemr-asr-pulse 1.2s infinite; vertical-align: middle; }",
      ".openemr-asr-highlight { outline: 3px solid #22c55e !important; outline-offset: 2px; transition: outline-color 0.2s ease; }",
      "@media (max-width: 640px) { #openemr-asr-demo-root { width: min(320px, calc(100vw - 16px)); right: 8px; bottom: 8px; } }",
      "@keyframes openemr-asr-pulse { 0% { box-shadow: 0 0 0 0 rgba(244, 63, 94, 0.65); } 70% { box-shadow: 0 0 0 12px rgba(244, 63, 94, 0); } 100% { box-shadow: 0 0 0 0 rgba(244, 63, 94, 0); } }"
    ].join("\n");
    document.documentElement.appendChild(style);
  }

  function buildUI() {
    var root = document.createElement("div");
    root.id = "openemr-asr-demo-root";

    root.innerHTML = [
      '<div class="openemr-asr-card">',
      '  <div class="openemr-asr-header" data-role="drag-handle">',
      '    <div class="openemr-asr-heading">',
      '      <p class="openemr-asr-title">OpenEMR Voice Demo</p>',
      '      <p class="openemr-asr-subtitle">Record, edit, and confirm before inserting into the encounter form.</p>',
      "    </div>",
      '    <button class="openemr-asr-toggle" data-role="toggle" aria-label="Collapse voice panel">-</button>',
      "  </div>",
      '  <div class="openemr-asr-body">',
      '    <div class="openemr-asr-status" data-role="status"></div>',
      '    <div class="openemr-asr-controls">',
      '      <button class="openemr-asr-button primary" data-role="record">Start mic</button>',
      '      <button class="openemr-asr-button warn" data-role="stop" disabled>Stop</button>',
      "    </div>",
      '    <textarea class="openemr-asr-preview" data-role="preview" placeholder="Transcript preview appears here. You can edit it before inserting."></textarea>',
      '    <div class="openemr-asr-row">',
      '      <button class="openemr-asr-button secondary" data-role="fill" disabled>Insert into form</button>',
      '      <button class="openemr-asr-button ghost" data-role="mock">Use demo text</button>',
      "    </div>",
      '    <div class="openemr-asr-target" data-role="target"></div>',
      "  </div>",
      "</div>"
    ].join("");

    document.body.appendChild(root);

    var card = root.querySelector(".openemr-asr-card");
    var dragHandle = root.querySelector('[data-role="drag-handle"]');
    var toggleButton = root.querySelector('[data-role="toggle"]');
    var statusEl = root.querySelector('[data-role="status"]');
    var targetEl = root.querySelector('[data-role="target"]');
    var previewEl = root.querySelector('[data-role="preview"]');
    var recordButton = root.querySelector('[data-role="record"]');
    var stopButton = root.querySelector('[data-role="stop"]');
    var fillButton = root.querySelector('[data-role="fill"]');
    var mockButton = root.querySelector('[data-role="mock"]');

    previewEl.addEventListener("input", function () {
      state.transcript = previewEl.value;
      syncButtons();
    });

    recordButton.addEventListener("click", startRecording);
    stopButton.addEventListener("click", stopRecording);
    fillButton.addEventListener("click", confirmAndFill);
    mockButton.addEventListener("click", function () {
      setTranscript(DEMO_TRANSCRIPT);
      setStatus("Demo transcript loaded. Review it, then insert it into the form.");
    });
    toggleButton.addEventListener("click", function (event) {
      event.stopPropagation();
      toggleCollapsed();
    });

    state.ui = {
      root: root,
      card: card,
      dragHandle: dragHandle,
      toggleButton: toggleButton,
      statusEl: statusEl,
      targetEl: targetEl,
      previewEl: previewEl,
      recordButton: recordButton,
      stopButton: stopButton,
      fillButton: fillButton,
      mockButton: mockButton
    };

    setupDragging();
    render();
  }

  function setStatus(message, showPulse) {
    state.status = message;
    state.showPulse = !!showPulse;
    render();
  }

  function setTranscript(value) {
    state.transcript = value || "";
    state.ui.previewEl.value = state.transcript;
    syncButtons();
  }

  function render() {
    if (!state.ui) {
      return;
    }

    state.ui.statusEl.innerHTML = (state.showPulse ? '<span class="openemr-asr-pulse"></span>' : "") + escapeHtml(state.status);
    state.ui.targetEl.textContent = state.target
      ? "Target field: " + state.target.description
      : "Target field: not available";
    state.ui.card.classList.toggle("is-collapsed", !!state.panelState.collapsed);
    state.ui.toggleButton.textContent = state.panelState.collapsed ? "+" : "-";
    state.ui.toggleButton.setAttribute(
      "aria-label",
      state.panelState.collapsed ? "Expand voice panel" : "Collapse voice panel"
    );
    syncButtons();
  }

  function syncButtons() {
    if (!state.ui) {
      return;
    }

    state.ui.recordButton.disabled = state.isRecording;
    state.ui.stopButton.disabled = !state.isRecording;
    state.ui.fillButton.disabled = !state.target || !state.transcript.trim();
  }

  function startFieldWatcher() {
    var observer = new MutationObserver(function () {
      var nextTarget = findReasonTarget();
      if (!nextTarget) {
        if (state.target && !document.contains(state.target.field)) {
          clearHighlight();
          state.target = null;
          syncButtons();
          setStatus("Waiting for the encounter field to appear...");
        }
        return;
      }

      if (!state.target || state.target.field !== nextTarget) {
        state.target = makeTarget(nextTarget);
        highlightTarget(nextTarget);
        setStatus("Ready to capture audio for Reason for Visit.");
      }
    });

    observer.observe(document.documentElement, {
      childList: true,
      subtree: true
    });

    state.targetObserver = observer;
  }

  async function startRecording() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus("Browser microphone capture is unavailable here. Use demo text for the report demo.");
      return;
    }

    try {
      var stream = await navigator.mediaDevices.getUserMedia({ audio: true });
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
      setStatus("Recording... speak now, then press Stop.", true);
      render();
    } catch (error) {
      console.error("Microphone error:", error);
      setStatus("Microphone access failed. You can still use demo text and show the fill workflow.");
    }
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

  async function handleRecordingStopped() {
    try {
      var blob = new Blob(state.audioChunks, { type: "audio/webm" });
      var transcript = await requestTranscription(blob);
      setTranscript(transcript);
      setStatus("Transcript ready. Edit it if needed, then insert it into the form.");
    } catch (error) {
      console.error("Transcription error:", error);
      setTranscript(DEMO_TRANSCRIPT);
      setStatus("Local ASR API was unavailable, so demo text was loaded instead.");
    } finally {
      cleanupRecording();
      render();
    }
  }

  async function requestTranscription(audioBlob) {
    var formData = new FormData();
    formData.append("file", audioBlob, "openemr-demo-recording.webm");

    var response = await fetch(API_URL, {
      method: "POST",
      body: formData
    });

    if (!response.ok) {
      throw new Error("Transcription request failed with status " + response.status);
    }

    var data = await response.json();

    if (!data || !data.transcription) {
      throw new Error("Transcription response did not include text.");
    }

    return data.transcription;
  }

  function cleanupRecording() {
    if (state.stream) {
      state.stream.getTracks().forEach(function (track) {
        track.stop();
      });
    }

    state.isRecording = false;
    state.mediaRecorder = null;
    state.stream = null;
    state.audioChunks = [];
  }

  function confirmAndFill() {
    if (!state.transcript.trim()) {
      return;
    }

    var targetField = getPreferredTargetField();

    if (!targetField) {
      setStatus("Could not find the Reason for Visit field. Refresh the encounter page and try again.");
      console.warn("Could not find textarea[name='reason'] at insert time.");
      return;
    }

    var accepted = window.confirm(
      "Insert this transcript into Reason for Visit?\n\n" + state.transcript.trim()
    );

    if (!accepted) {
      setStatus("Insert cancelled. You can keep editing the transcript preview.");
      return;
    }

    var inserted = fillField(targetField, state.transcript.trim());

    if (inserted) {
      setStatus("Transcript inserted into Reason for Visit.");
      return;
    }

    setStatus("The transcript could not be inserted into the target field.");
    console.warn("Insert failed: textarea value did not match expected text.");
  }

  function fillField(field, value) {
    field.focus();

    if (field.matches("textarea")) {
      var textareaSetter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype,
        "value"
      ).set;
      textareaSetter.call(field, value);
    } else if (field.matches("input")) {
      var inputSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        "value"
      ).set;
      inputSetter.call(field, value);
    } else if (field.isContentEditable) {
      field.textContent = value;
    } else {
      field.value = value;
    }

    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.dispatchEvent(new Event("change", { bubbles: true }));
    field.dispatchEvent(new Event("blur", { bubbles: true }));

    return readFieldValue(field) === value;
  }

  function getPreferredTargetField() {
    var preferredField = findReasonTarget();

    if (preferredField) {
      state.target = makeTarget(preferredField);
      highlightTarget(preferredField);
      render();
      return preferredField;
    }

    if (
      state.target &&
      state.target.field &&
      document.contains(state.target.field) &&
      isValidReasonTarget(state.target.field)
    ) {
      return state.target.field;
    }

    return null;
  }

  function isValidReasonTarget(field) {
    if (!field) {
      return false;
    }

    if (field.classList && field.classList.contains("openemr-asr-preview")) {
      return false;
    }

    return field.matches('textarea[name="reason"], textarea#reason');
  }

  function readFieldValue(field) {
    if (field.isContentEditable) {
      return field.textContent || "";
    }

    return field.value || "";
  }

  function highlightTarget(field) {
    clearHighlight();
    field.classList.add("openemr-asr-highlight");
  }

  function clearHighlight() {
    var previous = document.querySelectorAll(".openemr-asr-highlight");
    previous.forEach(function (node) {
      node.classList.remove("openemr-asr-highlight");
    });
  }

  function setupDragging() {
    var dragHandle = state.ui.dragHandle;
    var root = state.ui.root;
    var toggleButton = state.ui.toggleButton;
    var dragState = null;

    dragHandle.addEventListener("pointerdown", function (event) {
      if (event.target === toggleButton) {
        return;
      }

      dragState = {
        pointerId: event.pointerId,
        offsetX: event.clientX - root.getBoundingClientRect().left,
        offsetY: event.clientY - root.getBoundingClientRect().top
      };

      dragHandle.setPointerCapture(event.pointerId);
    });

    dragHandle.addEventListener("pointermove", function (event) {
      if (!dragState || dragState.pointerId !== event.pointerId) {
        return;
      }

      var nextLeft = event.clientX - dragState.offsetX;
      var nextTop = event.clientY - dragState.offsetY;
      applyPanelPosition({
        left: nextLeft,
        top: nextTop
      }, true);
    });

    dragHandle.addEventListener("pointerup", finishDragging);
    dragHandle.addEventListener("pointercancel", finishDragging);

    function finishDragging(event) {
      if (!dragState || dragState.pointerId !== event.pointerId) {
        return;
      }

      dragHandle.releasePointerCapture(event.pointerId);
      dragState = null;
      persistPanelState();
    }
  }

  function toggleCollapsed() {
    state.panelState.collapsed = !state.panelState.collapsed;
    persistPanelState();
    render();
  }

  function applySavedPanelState() {
    var position = sanitizePanelPosition(state.panelState.position);
    if (position) {
      applyPanelPosition(position, false);
    } else {
      resetPanelPosition();
    }

    render();
  }

  function applyPanelPosition(position, persist) {
    var sanitized = sanitizePanelPosition(position);
    if (!sanitized || !state.ui) {
      resetPanelPosition();
      return;
    }

    state.ui.root.style.left = sanitized.left + "px";
    state.ui.root.style.top = sanitized.top + "px";
    state.ui.root.style.right = "auto";
    state.ui.root.style.bottom = "auto";
    state.panelState.position = sanitized;

    if (persist) {
      persistPanelState();
    }
  }

  function resetPanelPosition() {
    if (!state.ui) {
      return;
    }

    state.ui.root.style.left = "auto";
    state.ui.root.style.top = "auto";
    state.ui.root.style.right = DEFAULT_OFFSET + "px";
    state.ui.root.style.bottom = DEFAULT_OFFSET + "px";
    state.panelState.position = null;
    persistPanelState();
  }

  function sanitizePanelPosition(position) {
    if (!position || typeof position.left !== "number" || typeof position.top !== "number") {
      return null;
    }

    var rootWidth = state.ui ? state.ui.root.offsetWidth : PANEL_WIDTH;
    var rootHeight = state.ui ? state.ui.root.offsetHeight : 220;
    var maxLeft = Math.max(DEFAULT_OFFSET, window.innerWidth - rootWidth - DEFAULT_OFFSET);
    var maxTop = Math.max(DEFAULT_OFFSET, window.innerHeight - rootHeight - DEFAULT_OFFSET);

    if (
      position.left < 0 ||
      position.top < 0 ||
      position.left > window.innerWidth - DEFAULT_OFFSET ||
      position.top > window.innerHeight - DEFAULT_OFFSET
    ) {
      return null;
    }

    return {
      left: clamp(position.left, DEFAULT_OFFSET, maxLeft),
      top: clamp(position.top, DEFAULT_OFFSET, maxTop)
    };
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function loadPanelState() {
    try {
      var raw = window.localStorage.getItem(PANEL_STATE_KEY);
      if (!raw) {
        return {
          position: null,
          collapsed: false
        };
      }

      var parsed = JSON.parse(raw);
      return {
        position: parsed && parsed.position ? parsed.position : null,
        collapsed: !!(parsed && parsed.collapsed)
      };
    } catch (_error) {
      return {
        position: null,
        collapsed: false
      };
    }
  }

  function persistPanelState() {
    try {
      window.localStorage.setItem(PANEL_STATE_KEY, JSON.stringify(state.panelState));
    } catch (_error) {
      // Ignore localStorage write failures for demo mode.
    }
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
})();
