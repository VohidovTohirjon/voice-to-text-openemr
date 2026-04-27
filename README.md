# Voice-to-Text OpenEMR Integration

## Overview
This project explores adding voice-to-text to OpenEMR using a local ASR system.

The goal is to let a clinician speak and insert the transcript into the encounter form.

## Project Structure
- `asr/` → Local speech-to-text prototype (Whisper-based)
- `openemr/` → OpenEMR integration (modified files only)
- `extension/` → Chrome extension source (MV3 content scripts and UI)
- `scripts/` → Lightweight npm pipeline helpers for building/watching the extension
- `validation/` → Week 3 validation checklist, test matrix, and local form fixtures
- `dist/extension/` → Generated unpacked extension build output

## What’s Working
- Audio recording and transcription using Whisper
- Example clinical speech converted into text
- Identification and modification of OpenEMR encounter form
- Placeholder added for AI-generated text insertion
- Chrome extension scans local pages for likely text-entry targets
- Extension prioritizes the OpenEMR `Reason for Visit` field
- Floating mic UI supports recording, transcript preview, confirm-before-fill, drag/move, and collapse
- Demo transcript fallback exists when microphone or API access is not available
- Extension stays inactive on irrelevant pages like the OpenEMR login screen

## Notes
- Whisper is used as a baseline due to easy setup and fast testing
- Medical-specific models (like MedASR) are planned for future evaluation
- Only modified OpenEMR files are included (full repo is too large)

## Status
Working prototype with local ASR and a demo-ready Chrome extension

## Extension Pipeline

This repo uses a lightweight npm pipeline around the current file-based extension.

From the project root:

```bash
npm run check
npm run build
npm run dev
```

- `npm run check` validates the extension scripts, manifest, and ASR API syntax
- `npm run build` copies the unpacked extension into `dist/extension/`
- `npm run dev` watches `extension/` and rebuilds `dist/extension/` automatically

## Quick Demo Flow

1. Start the ASR API:

```bash
cd asr
pip install -r requirements.txt
uvicorn api:app --host 127.0.0.1 --port 8000
```

2. In Chrome, open `chrome://extensions`, enable Developer Mode, and load the unpacked extension from:

```text
/Users/tokhirjon/asr_test/dist/extension
```

You can also load `/Users/tokhirjon/asr_test/extension` directly while developing, but `dist/extension` is the cleaner folder to show in a demo.

3. Open local OpenEMR in the browser and navigate to a page with the `Reason for Visit` field.

4. Use the floating extension panel to record audio or click `Use demo text`.

5. Optionally drag the panel out of the way or collapse it between steps.

6. Review the transcript preview and click `Insert into form` to place it into the detected OpenEMR textarea.

## Week 3 Validation

Week 3 work has started in `validation/`.

Run the local validation fixtures with:

```bash
npm run serve:validation
```

Then open:

```text
http://127.0.0.1:5173/contact-reason.html
http://127.0.0.1:5173/intake-reason.html
http://127.0.0.1:5173/no-reason-field.html
```

Use `validation/openemr-encounter-checklist.md` for the OpenEMR encounter page and `validation/test-matrix.md` for the Week 3 testing summary.
