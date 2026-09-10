/**
 * DOM field scanner.
 *
 * Two jobs:
 *
 *   getReasonTarget()      the original single-target path — find the encounter
 *                          form's "Reason for Visit" textarea.
 *
 *   resolveFieldMappings() the analysis path — take the field_mappings the ASR
 *                          service returns and locate a DOM element for each.
 *
 * Resolution is deliberately ordered from most to least reliable, and every
 * result records HOW it was found so the confirmation UI can show the operator
 * whether a field was matched on its real name or merely inferred from a label.
 */
(function () {
  var STRATEGY = {
    NAME: "name-attribute",
    ID: "id-attribute",
    LABEL: "label-text",
    PLACEHOLDER: "placeholder-text",
    ARIA: "aria-label"
  };

  function normalizeText(value) {
    return (value || "").toLowerCase().replace(/\s+/g, " ").trim();
  }

  function getAssociatedLabel(field) {
    if (field.id) {
      var explicit = document.querySelector('label[for="' + CSS.escape(field.id) + '"]');
      if (explicit) {
        return explicit.textContent || "";
      }
    }
    var wrapping = field.closest("label");
    return wrapping ? wrapping.textContent || "" : "";
  }

  function getNearbyLegend(field) {
    var fieldset = field.closest("fieldset");
    if (!fieldset) {
      return "";
    }
    var legend = fieldset.querySelector("legend");
    return legend ? legend.textContent || "" : "";
  }

  function isOwnUi(field) {
    return Boolean(field.closest && field.closest("#openemr-asr-demo-root"));
  }

  function isWritable(field) {
    if (!field || field.disabled || field.readOnly || isOwnUi(field)) {
      return false;
    }
    if (field.type && ["hidden", "submit", "button", "password", "file"].indexOf(field.type) >= 0) {
      return false;
    }
    // An element with no layout box cannot be shown to the operator for review.
    return Boolean(field.offsetParent || field.getClientRects().length);
  }

  function allWritableFields() {
    var selector = 'textarea, input[type="text"], input[type="number"], ' +
                   'input:not([type]), [contenteditable="true"]';
    return Array.prototype.slice.call(document.querySelectorAll(selector)).filter(isWritable);
  }

  function describeField(field) {
    var label = normalizeText(getAssociatedLabel(field));
    var legend = normalizeText(getNearbyLegend(field));
    var placeholder = normalizeText(field.placeholder);
    var fallback = normalizeText(field.name || field.id || field.tagName);
    return label || legend || placeholder || fallback || "text field";
  }

  /**
   * Locate the DOM element for one field mapping.
   *
   * openemr_fields carry the real name/id attributes from the OpenEMR form
   * tables, so they are tried first and exactly. field_labels are human-facing
   * words and are only used when the attribute lookup finds nothing, because
   * substring matching on visible text is much easier to get wrong.
   */
  function resolveField(mapping) {
    var writable = allWritableFields();
    var i;
    var candidate;

    var exactNames = mapping.openemr_fields || [];
    for (i = 0; i < exactNames.length; i += 1) {
      candidate = writable.filter(function (field) {
        return field.name === exactNames[i];
      })[0];
      if (candidate) {
        return { field: candidate, strategy: STRATEGY.NAME, matchedOn: exactNames[i], confidence: 1.0 };
      }
    }

    for (i = 0; i < exactNames.length; i += 1) {
      candidate = writable.filter(function (field) {
        return field.id === exactNames[i];
      })[0];
      if (candidate) {
        return { field: candidate, strategy: STRATEGY.ID, matchedOn: exactNames[i], confidence: 0.95 };
      }
    }

    var labels = mapping.field_labels || [];
    var best = null;

    writable.forEach(function (field) {
      var labelText = normalizeText(getAssociatedLabel(field));
      var legendText = normalizeText(getNearbyLegend(field));
      var placeholderText = normalizeText(field.placeholder);
      var ariaText = normalizeText(field.getAttribute("aria-label"));

      labels.forEach(function (needle) {
        var target = normalizeText(needle);
        if (!target) {
          return;
        }

        var strategy = null;
        var score = 0;

        // An exact label match is far stronger evidence than a substring hit.
        if (labelText === target || legendText === target) {
          strategy = STRATEGY.LABEL;
          score = 0.9;
        } else if (labelText.indexOf(target) >= 0 || legendText.indexOf(target) >= 0) {
          strategy = STRATEGY.LABEL;
          score = 0.7;
        } else if (ariaText.indexOf(target) >= 0) {
          strategy = STRATEGY.ARIA;
          score = 0.65;
        } else if (placeholderText.indexOf(target) >= 0) {
          strategy = STRATEGY.PLACEHOLDER;
          score = 0.6;
        }

        // Longer needles are more specific: "reason for visit" beats "reason".
        score += Math.min(0.08, target.length / 400);

        if (strategy && (!best || score > best.confidence)) {
          best = { field: field, strategy: strategy, matchedOn: needle, confidence: score };
        }
      });
    });

    return best;
  }

  /**
   * Resolve every mapping the service returned.
   * Each field is claimed at most once; the highest-confidence mapping wins.
   */
  function resolveFieldMappings(mappings) {
    var claimed = [];
    var resolved = [];
    var unresolved = [];

    (mappings || []).slice().sort(function (a, b) {
      return (b.confidence || 0) - (a.confidence || 0);
    }).forEach(function (mapping) {
      var hit = resolveField(mapping);
      if (!hit) {
        unresolved.push(mapping);
        return;
      }
      if (claimed.indexOf(hit.field) >= 0) {
        unresolved.push(mapping);
        return;
      }
      claimed.push(hit.field);
      resolved.push({
        mapping: mapping,
        field: hit.field,
        strategy: hit.strategy,
        matchedOn: hit.matchedOn,
        domConfidence: Math.min(1, hit.confidence),
        description: describeField(hit.field),
        currentValue: hit.field.isContentEditable
          ? (hit.field.textContent || "")
          : (hit.field.value || "")
      });
    });

    return { resolved: resolved, unresolved: unresolved };
  }

  // ---- original single-target path -----------------------------------------

  function isValidReasonTarget(field) {
    if (!field || isOwnUi(field)) {
      return false;
    }
    return field.matches('textarea[name="reason"], textarea#reason');
  }

  function getReasonTarget() {
    var byName = document.querySelector('textarea[name="reason"]');
    if (isValidReasonTarget(byName)) {
      return byName;
    }
    var byId = document.querySelector("textarea#reason");
    if (isValidReasonTarget(byId)) {
      return byId;
    }
    return null;
  }

  /** True when this page has anything worth offering the panel for. */
  function hasFillableFields() {
    return Boolean(getReasonTarget()) || allWritableFields().length > 0;
  }

  window.OpenEMRASRScanner = {
    STRATEGY: STRATEGY,
    getReasonTarget: getReasonTarget,
    isValidReasonTarget: isValidReasonTarget,
    resolveField: resolveField,
    resolveFieldMappings: resolveFieldMappings,
    allWritableFields: allWritableFields,
    describeField: describeField,
    hasFillableFields: hasFillableFields
  };
})();
