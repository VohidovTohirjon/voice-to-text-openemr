import sys
import whisper

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python transcribe.py <audio_file>")
        sys.exit(1)

    audio_file = sys.argv[1]

    model = whisper.load_model("base")
    result = model.transcribe(audio_file)
    text = result["text"].strip()

    print("\n--- TRANSCRIPTION ---")
    print(text)
    print("---------------------\n")

    with open("output.txt", "w", encoding="utf-8") as f:
        f.write(text + "\n")

if __name__ == "__main__":
    main()
