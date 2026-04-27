# OpenEMR Encounter Validation Checklist

Use this checklist on the local OpenEMR encounter/new patient form.

## Environment

- Browser: Chrome
- Extension loaded from: `/Users/tokhirjon/asr_test/dist/extension`
- OpenEMR target: local OpenEMR instance
- ASR API: `http://127.0.0.1:8000/transcribe`

## Tests

| Test | Expected Result | Pass/Fail | Notes |
| --- | --- | --- | --- |
| Open login page | Extension panel does not appear |  |  |
| Open encounter page | Extension panel appears after `Reason for Visit` field loads |  |  |
| Target field highlight | `textarea[name="reason"]` / `#reason` is highlighted |  |  |
| Demo text | `Use demo text` fills the transcript preview only |  |  |
| Edit preview | Transcript text can be edited before insert |  |  |
| Confirm insert | Confirmation dialog appears before writing to OpenEMR |  |  |
| Reason insert | Confirmed text appears in the Reason for Visit textarea |  |  |
| Other fields | Date, select boxes, and issue fields are not modified |  |  |
| Drag panel | Panel can be moved by dragging the header |  |  |
| Saved position | Panel position remains after page refresh |  |  |
| Collapse panel | Panel collapses and expands using the toggle |  |  |
| Saved collapse | Collapse state remains after page refresh |  |  |
| API fallback | If ASR API is off, demo text fallback still supports insert flow |  |  |

## Result Summary

Add screenshots or short notes here after manual testing:

- Login page result:
- Encounter page result:
- Insert result:
- Any failures:
