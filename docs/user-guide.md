# User Guide

## What this prototype does

This project is a local voice-to-text prototype for OpenEMR. The Chrome extension can:

- record audio in the browser
- send audio to the local ASR API
- analyze transcript text into structured field suggestions
- preview the transcript before writing
- fill detected fields after confirmation

The main OpenEMR demo target is the `Reason for Visit` field, but the current extension can also test simple generic web forms that expose fillable text inputs or textareas.

## Setup

### 1. Start the ASR API

From `asr/`:

```bash
pip install -r requirements.txt
uvicorn api:app --host 127.0.0.1 --port 8000
```

Optional for the NLP extractor:

```bash
python -m spacy download en_core_web_sm
```

Optional for local LLM extraction:

```bash
ollama pull llama3.2:3b
```

The extension currently uses the spaCy/rule-based path by default.

### 2. Build the extension

From the project root:

```bash
npm run check
npm run build
```

### 3. Load the extension in Chrome

1. Open `chrome://extensions`
2. Turn on Developer Mode
3. Click `Load unpacked`
4. Select:

```text
/Users/tokhirjon/asr_test/dist/extension
```

## Basic flow

1. Open the local OpenEMR encounter page or a supported test form.
2. Wait for the floating panel to appear.
3. Click `Start mic` and record audio, or paste/edit transcript text manually.
4. Click `Analyze text` to generate field suggestions.
5. Review the suggested field fills.
6. Click `Insert into form`.
7. Confirm the fill operation in the dialog.

## Panel behavior

- The panel can be dragged by its header.
- Panel position is saved in localStorage.
- Collapse state is also saved in localStorage.
- If you edit the transcript manually after analysis, the extension asks you to analyze again for the latest field suggestions.

## Permissions and edge cases

- On the OpenEMR login page, the panel stays hidden.
- If no fillable text fields exist, the panel does not activate.
- If the microphone is denied, you can still use demo text or paste transcript text manually.
- If the API is unavailable, the extension falls back to a demo transcript path.

## Validation pages

Run local validation pages with:

```bash
npm run serve:validation
```

Then test:

```text
http://127.0.0.1:5173/contact-reason.html
http://127.0.0.1:5173/intake-reason.html
http://127.0.0.1:5173/no-reason-field.html
```

## Current limitations

- The project is still a prototype, not a production-ready OpenEMR plugin.
- OpenEMR save/validation behavior is separate from DOM field filling.
- Generic web-form support is best-effort and depends on visible labels/placeholders/name attributes.
