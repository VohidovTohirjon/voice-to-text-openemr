# Week 3 Test Matrix

| Area | Test | Expected Result | Owner |
| --- | --- | --- | --- |
| OpenEMR login | Refresh/login screen behavior | Extension stays hidden and does not log repeatedly | Tokhirjon |
| OpenEMR encounter | Field detection | Extension appears only when `textarea[name="reason"]` / `#reason` exists | Tokhirjon |
| OpenEMR encounter | Fill behavior | Transcript inserts into Reason for Visit only | Tokhirjon |
| OpenEMR encounter | Field suggestions | Transcript analysis returns suggested field fills before insert | Tokhirjon |
| OpenEMR encounter | Other field safety | Date/select/issue fields are not modified | Tokhirjon |
| Extension UI | Drag | Panel can be moved and does not block the form | Tokhirjon |
| Extension UI | Persist position | Saved panel position restores on reload | Tokhirjon |
| Extension UI | Collapse | Collapse/expand state persists on reload | Tokhirjon |
| Extension UI | Active/inactive states | Header badge and status text reflect ready/review/recording states | Tokhirjon |
| Edge case | Mic denied | Clear fallback message appears and manual transcript flow still works | Tokhirjon |
| Edge case | No fields found | Extension stays hidden or inactive without repeated errors | Tokhirjon |
| Edge case | Transcript edited after analysis | Re-analysis path works and stale mappings are not silently reused | Tokhirjon |
| Generic form | Contact reason page | Extension activates and fills local reason textarea | Tokhirjon |
| Generic form | Intake reason page | Extension activates and fills local reason textarea | Tokhirjon |
| Negative form | No reason field page | Extension stays hidden | Tokhirjon |
| Generic form | Google Form | Extension injects and can analyze/fill compatible text fields | Tokhirjon |
| ASR API | API running | Browser recording sends audio to local API | Andy/Tokhirjon |
| ASR API | API unavailable | Extension uses demo text fallback | Tokhirjon |

## Report Notes

- Current scope is an MVP validation pass, not production QA.
- The extension intentionally targets Reason for Visit only.
- OpenEMR save validation is separate from extension DOM insertion.
