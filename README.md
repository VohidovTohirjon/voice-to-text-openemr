# Voice-to-Text OpenEMR Integration

## Overview
This project explores adding voice-to-text functionality into OpenEMR using a local ASR (speech-to-text) system.

The goal is to allow clinicians to speak naturally and have their input automatically converted into structured text inside the encounter form.

## Project Structure
- `asr/` → Local speech-to-text prototype (Whisper-based)
- `openemr/` → OpenEMR integration (modified files only)

## What’s Working
- Audio recording and transcription using Whisper
- Example clinical speech converted into text
- Identification and modification of OpenEMR encounter form
- Placeholder added for AI-generated text insertion

## Notes
- Whisper is used as a baseline due to easy setup and fast testing
- Medical-specific models (like MedASR) are planned for future evaluation
- Only modified OpenEMR files are included (full repo is too large)

## Status
Working prototype (ASR side complete, integration in progress)
