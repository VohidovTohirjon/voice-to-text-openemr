#!/bin/bash

echo "Recording 6 seconds of audio..."
ffmpeg -f avfoundation -i ":1" -t 6 test.wav -y

echo "Running transcription..."
python transcribe.py test.wav
