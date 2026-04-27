# Week 3 Validation

This folder starts the Week 3 validation work for the OpenEMR voice-to-text MVP.

## Goals

- Verify the extension stays hidden on the OpenEMR login page.
- Verify the extension appears on the encounter page when `textarea[name="reason"]` / `#reason` exists.
- Verify transcript preview stays editable before insert.
- Verify `Insert into form` writes only to the real Reason for Visit textarea.
- Check basic portability on simple local web forms.

## How to Run Local Form Fixtures

From the repo root:

```bash
npm run serve:validation
```

Then open:

```text
http://127.0.0.1:5173/contact-reason.html
http://127.0.0.1:5173/intake-reason.html
http://127.0.0.1:5173/no-reason-field.html
```

The first two pages intentionally include a `textarea` named `reason`, so the extension should activate there. The third page is a negative test and should not show the extension.

## Notes

This is a manual validation harness, not a full automated browser test suite. It is meant to give the team repeatable evidence for the Week 3 report.
