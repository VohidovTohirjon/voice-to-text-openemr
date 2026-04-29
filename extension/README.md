# Chrome Extension MVP

This folder contains the Chrome extension MVP for the CSC 436 OpenEMR voice-to-text demo.

## What it does

- Injects into local `localhost` / `127.0.0.1` pages
- Injects into Google Forms pages for portability testing
- Activates only on relevant OpenEMR encounter/form pages
- Prioritizes the OpenEMR `Reason for Visit` textarea and can map transcript entities to other form fields
- Shows a floating voice/transcript panel
- Records audio in-browser when microphone access is available
- Sends audio to the local ASR API and can call transcript extraction endpoints
- Falls back to demo text if the local API is unavailable
- Requires confirmation before filling selected fields
- Lets the user drag the panel and collapse it, with state saved in localStorage

## Files

- `manifest.json` - Manifest V3 config
- `scanner.js` - DOM field scanner and target ranking
- `content.js` - Floating UI, recording flow, transcript preview, and fill behavior

## Build / Run

From the repo root:

```bash
npm run check
npm run build
```

Load the unpacked extension from:

```text
/Users/tokhirjon/asr_test/dist/extension
```

For active development, `npm run dev` watches the `extension/` folder and rebuilds the output when files change.

## Notes

The source files stay in `extension/`. The generated unpacked build lives in `dist/extension/`.
