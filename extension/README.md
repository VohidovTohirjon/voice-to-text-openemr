# Chrome Extension MVP

This folder contains the Chrome extension MVP for the CSC 436 OpenEMR voice-to-text demo.

## What it does

- Injects into local `localhost` / `127.0.0.1` pages
- Activates only on relevant OpenEMR encounter/form pages
- Targets only the OpenEMR `Reason for Visit` textarea
- Shows a floating voice/transcript panel
- Records audio in-browser when microphone access is available
- Sends audio to the local ASR API at `http://127.0.0.1:8000/transcribe`
- Falls back to demo text if the local API is unavailable
- Requires confirmation before filling the selected field
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
