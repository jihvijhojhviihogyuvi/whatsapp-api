import os
import sys
from google import genai


def try_stream(client: genai.Client, label: str) -> int:
    print(f"\n=== auth mode: {label}")
    candidates = [
        "gemma-4-26b-a4b-it-maas",
        "google/gemma-4-26b-a4b-it-maas",
        "publishers/google/models/gemma-4-26b-a4b-it-maas",
    ]

    last_error: Exception | None = None
    for model in candidates:
        print(f"\nTrying model: {model}")
        try:
            saw_text = False
            for chunk in client.models.generate_content_stream(
                model=model,
                contents="Reply with exactly STREAM_OK",
            ):
                text = chunk.text or ""
                if text:
                    saw_text = True
                    print(text, end="", flush=True)
            print()
            if saw_text:
                print(f"SUCCESS: stream worked with model='{model}'")
                return 0
            print(f"Model '{model}' returned no text chunks.")
        except Exception as exc:  # pragma: no cover
            last_error = exc
            print(f"ERROR for '{model}': {type(exc).__name__}: {exc}")
    if last_error:
        print(f"\nFinal error: {type(last_error).__name__}: {last_error}")
    return 1


def main() -> int:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    print(f"GEMINI_API_KEY set: {bool(key)}")
    print(f"GOOGLE_CLOUD_PROJECT: {project}")
    print(f"GOOGLE_CLOUD_LOCATION: {location}")

    if key:
        client = genai.Client(api_key=key)
        try:
            rc = try_stream(client, "gemini-api-key")
            if rc == 0:
                return 0
        finally:
            client.close()

    if project:
        client = genai.Client(vertexai=True, project=project, location=location)
        try:
            rc = try_stream(client, "vertex-ai")
            if rc == 0:
                return 0
        finally:
            client.close()

    print("\nNo working auth/model combo found.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
