import os
import tempfile
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import whisper

app = FastAPI(title="ASR Prototype API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

model = whisper.load_model("base")


@app.get("/")
def root():
    return {"message": "ASR prototype API is running"}


@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename)[1] or ".wav"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_audio:
        contents = await file.read()
        temp_audio.write(contents)
        temp_path = temp_audio.name

    try:
        result = model.transcribe(temp_path)
        text = result["text"].strip()
        return {"transcription": text}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
