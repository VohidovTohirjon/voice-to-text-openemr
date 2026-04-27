(function () {
  function normalizeText(value) {
    return (value || "")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim();
  }

  function getAssociatedLabel(field) {
    if (!field.id) {
      return "";
    }

    var label = document.querySelector('label[for="' + CSS.escape(field.id) + '"]');
    return label ? label.textContent || "" : "";
  }

  function getNearbyLegend(field) {
    var fieldset = field.closest("fieldset");
    if (!fieldset) {
      return "";
    }

    var legend = fieldset.querySelector("legend");
    return legend ? legend.textContent || "" : "";
  }

  function getCandidateText(field) {
    var parts = [
      field.name,
      field.id,
      field.placeholder,
      field.getAttribute("aria-label"),
      field.getAttribute("title"),
      getAssociatedLabel(field),
      getNearbyLegend(field)
    ];

    return normalizeText(parts.filter(Boolean).join(" "));
  }

  function isTextEntryField(field) {
    if (!field || field.disabled || field.readOnly) {
      return false;
    }

    if (field.classList && field.classList.contains("openemr-asr-preview")) {
      return false;
    }

    if (!field.matches('textarea[name="reason"], textarea#reason')) {
      return false;
    }

    if (field.matches("textarea")) {
      return true;
    }

    return false;
  }

  function scoreField(field) {
    var text = getCandidateText(field);
    var score = 0;

    if (!text) {
      return score;
    }

    if (field.matches('textarea[name="reason"], textarea#reason')) {
      score += 120;
    }

    if (text.includes("reason for visit")) {
      score += 100;
    }

    if (text.includes("chief complaint")) {
      score += 60;
    }

    if (text.includes("reason")) {
      score += 30;
    }

    if (text.includes("visit")) {
      score += 20;
    }

    if (field.matches("textarea")) {
      score += 15;
    }

    if (field.closest("form")) {
      score += 5;
    }

    return score;
  }

  function describeField(field) {
    var label = normalizeText(getAssociatedLabel(field));
    var legend = normalizeText(getNearbyLegend(field));
    var placeholder = normalizeText(field.placeholder);
    var fallback = normalizeText(field.name || field.id || field.tagName);

    return label || legend || placeholder || fallback || "text field";
  }

  function scanCandidates() {
    var nodes = Array.from(
      document.querySelectorAll(
        'textarea, input[type="text"], input:not([type]), [contenteditable="true"]'
      )
    );

    return nodes
      .filter(isTextEntryField)
      .map(function (field) {
        return {
          field: field,
          score: scoreField(field),
          description: describeField(field),
          selectorHint: [field.tagName.toLowerCase(), field.name, field.id].filter(Boolean).join("#")
        };
      })
      .sort(function (a, b) {
        return b.score - a.score;
      });
  }

  function getBestCandidate() {
    var candidates = scanCandidates();
    return candidates.length ? candidates[0] : null;
  }

  window.OpenEMRASRScanner = {
    scanCandidates: scanCandidates,
    getBestCandidate: getBestCandidate
  };
})();
