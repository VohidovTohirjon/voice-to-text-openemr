# Week 3 Test Matrix

| Area | Test | Expected Result | Owner |
| --- | --- | --- | --- |
| OpenEMR login | Refresh/login screen behavior | Extension stays hidden and does not log repeatedly | Tokhirjon |
| OpenEMR encounter | Field detection | Extension appears only when `textarea[name="reason"]` / `#reason` exists | Tokhirjon |
| OpenEMR encounter | Fill behavior | Transcript inserts into Reason for Visit only | Tokhirjon |
| OpenEMR encounter | Other field safety | Date/select/issue fields are not modified | Tokhirjon |
| Extension UI | Drag | Panel can be moved and does not block the form | Tokhirjon |
| Extension UI | Persist position | Saved panel position restores on reload | Tokhirjon |
| Extension UI | Collapse | Collapse/expand state persists on reload | Tokhirjon |
| Generic form | Contact reason page | Extension activates and fills local reason textarea | Tokhirjon |
| Generic form | Intake reason page | Extension activates and fills local reason textarea | Tokhirjon |
| Negative form | No reason field page | Extension stays hidden | Tokhirjon |
| ASR API | API running | Browser recording sends audio to local API | Andy/Tokhirjon |
| ASR API | API unavailable | Extension uses demo text fallback | Tokhirjon |

## Report Notes

- Current scope is an MVP validation pass, not production QA.
- The extension intentionally targets Reason for Visit only.
- OpenEMR save validation is separate from extension DOM insertion.
