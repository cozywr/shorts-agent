"""Gives the channel its own ElevenLabs narrator voice and reads the story with word timings."""
import base64
import json
import os
from pathlib import Path

import requests

API = "https://api.elevenlabs.io/v1"


def _headers() -> dict:
    return {"xi-api-key": os.environ["ELEVENLABS_API_KEY"]}


def _design(name: str, description: str) -> str:
    """Designs a brand-new voice from a text description and saves it to the account."""
    resp = requests.post(f"{API}/text-to-voice/design", headers=_headers(),
                         json={"voice_description": description, "auto_generate_text": True}, timeout=300)
    resp.raise_for_status()
    generated_id = resp.json()["previews"][0]["generated_voice_id"]
    resp = requests.post(f"{API}/text-to-voice", headers=_headers(),
                         json={"voice_name": name, "voice_description": description,
                               "generated_voice_id": generated_id}, timeout=120)
    resp.raise_for_status()
    return resp.json()["voice_id"]


def ensure_narrator(config: dict, voices_file: Path) -> str:
    """Returns the narrator's voice id, designing the voice on the first run."""
    n = config["narrator"]
    if n.get("voice_id"):
        return n["voice_id"]
    voices = json.loads(voices_file.read_text()) if voices_file.exists() else {}
    if "narrator" not in voices:
        voices["narrator"] = _design(f"Shorts - {n['name']}", n["voice"])
        print("Designed a new narrator voice")
        voices_file.write_text(json.dumps(voices, indent=2) + "\n")
    return voices["narrator"]


def speak(text: str, voice_id: str, out: Path) -> dict:
    """Saves the speech to `out` and returns ElevenLabs' per-character timing for the text."""
    resp = requests.post(
        f"{API}/text-to-speech/{voice_id}/with-timestamps",
        headers=_headers(),
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=300,
    )
    resp.raise_for_status()
    data = resp.json()
    out.write_bytes(base64.b64decode(data["audio_base64"]))
    return data["alignment"]
