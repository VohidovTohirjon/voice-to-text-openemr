# Voice-to-Text OpenEMR (ASR Prototype)

## Overview
This is a simple prototype for adding voice-to-text into OpenEMR using a local ASR model.

## What I did so far
- Set up Whisper locally for speech-to-text
- Recorded audio using FFmpeg
- Built a Python script (`transcribe.py`) to convert speech → text
- Tested with a clinical-style example input
- Added a basic API (`api.py`) for future integration
- Added a Chrome extension MVP that can call the local API and fill OpenEMR fields after confirmation

## Example
Input (speech):  
"Patient report headache and mild fever for two days."

Output (text):  
Patient report headache and mild fever for two days.

## How to run
```bash
ffmpeg -f avfoundation -i ":1" -t 6 test.wav
python transcribe.py test.wav
```

## Run the local API

From `asr/`:

```bash
pip install -r requirements.txt
uvicorn api:app --host 127.0.0.1 --port 8000
```

The extension posts recorded audio to:

```text
http://127.0.0.1:8000/transcribe
```
