"""
Field-Fill Mapping Layer
========================
Maps extracted entities to DOM form field semantic types.

Each mapping includes:
  - field_labels:    label/placeholder/aria-label keywords the DOM scanner should
                     match against (case-insensitive substring match)
  - openemr_fields:  Open-EMR-specific field name/id attribute values for direct
                     lookup (faster than generic label scanning)
  - needs_review:    True when confidence < REVIEW_THRESHOLD — surfaced in the
                     confirmation UI so the provider can verify before commit
"""

from typing import Any

# Confidence below this value triggers the "needs review" flag
REVIEW_THRESHOLD = 0.75

# ---------------------------------------------------------------------------
# Entity type → generic DOM label keywords
# ---------------------------------------------------------------------------
# Used by the content script to match against label text, placeholder, aria-label,
# name attribute, and surrounding context (case-insensitive contains).

ENTITY_TO_FIELD_LABELS: dict[str, list[str]] = {
    "name":            ["full name", "name", "patient name"],
    "first_name":      ["first name", "given name", "fname", "first"],
    "last_name":       ["last name", "surname", "family name", "lname", "last"],
    "email":           ["email", "e-mail", "email address"],
    "phone":           ["phone", "telephone", "mobile", "cell", "contact number"],
    "address":         ["address", "street address", "mailing address", "street"],
    "city":            ["city", "town"],
    "state":           ["state", "province"],
    "zip":             ["zip", "zip code", "postal code", "postal"],
    "date_of_birth":   ["date of birth", "dob", "birth date", "birthday"],
    "date":            ["date", "appointment date", "visit date"],
    "chief_complaint": ["chief complaint", "reason for visit", "presenting complaint", "cc"],
    "assessment":      ["assessment", "impression"],
    "plan":            ["plan", "treatment plan", "management"],
    "medication":      ["medication", "medications", "drug", "prescription"],
    "diagnosis":       ["diagnosis", "diagnoses", "icd"],
    "organization":    ["organization", "employer", "company", "facility"],
}

# ---------------------------------------------------------------------------
# Open-EMR specific field name/id overrides
# ---------------------------------------------------------------------------
# These match the actual `name` and `id` attributes in Open-EMR's encounter
# forms, bypassing the need for generic label inference on the primary target.

OPENEMR_FIELD_MAP: dict[str, list[str]] = {
    "first_name":      ["fname"],
    "last_name":       ["lname"],
    "date_of_birth":   ["dob", "patient_dob"],
    "email":           ["email"],
    "phone":           ["phone_home", "phone_cell"],
    "address":         ["street", "patient_address"],
    "city":            ["city"],
    "state":           ["state"],
    "zip":             ["postal_code", "zip"],
    "chief_complaint": ["reason", "cc", "reason_for_visit"],
    "assessment":      ["assessment"],
    "plan":            ["plan"],
    "medication":      ["medication", "medications"],
    "diagnosis":       ["diagnosis", "diagnosis_code"],
}


# ---------------------------------------------------------------------------
# Main mapping function
# ---------------------------------------------------------------------------


def map_entities_to_fields(entities: dict) -> list[dict[str, Any]]:
    """
    Convert extracted entity dict into a list of field-fill mappings.

    Args:
        entities: Output from extractor.extract_entities().
                  Expected shape: { entity_type: { value, confidence } }
                  Also accepts flat { entity_type: str } (e.g. raw LLM output).

    Returns:
        List of field mappings sorted by confidence (descending), each with:
          entity_type   — the extracted entity type
          value         — the text to write into the field
          confidence    — float 0.0–1.0
          field_labels  — DOM label/placeholder keywords to match
          openemr_fields — Open-EMR field name/id hints
          needs_review  — True if confidence < REVIEW_THRESHOLD
    """
    mappings: list[dict[str, Any]] = []

    for entity_type, entity_data in entities.items():
        # Skip internal meta keys (e.g. _fallback_reason)
        if entity_type.startswith("_"):
            continue

        if isinstance(entity_data, dict):
            value = str(entity_data.get("value", ""))
            confidence = float(entity_data.get("confidence", 0.0))
        else:
            value = str(entity_data)
            confidence = 0.70  # conservative default for flat LLM output

        mappings.append(
            {
                "entity_type": entity_type,
                "value": value,
                "confidence": confidence,
                "field_labels": ENTITY_TO_FIELD_LABELS.get(entity_type, [entity_type]),
                "openemr_fields": OPENEMR_FIELD_MAP.get(entity_type, []),
                "needs_review": confidence < REVIEW_THRESHOLD,
            }
        )

    mappings.sort(key=lambda m: m["confidence"], reverse=True)
    return mappings
