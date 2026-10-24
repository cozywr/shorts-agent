"""Gives each character its own ElevenLabs voice and turns lines into speech with it."""
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


def ensure_voices(config: dict, voices_file: Path) -> dict[str, str]:
    """Returns {character id: voice id}, designing any voice that doesn't exist yet."""
    voices = json.loads(voices_file.read_text()) if voices_file.exists() else {}
    for cid, c in config["characters"].items():
        if cid not in voices:
            voices[cid] = _design(f"Shorts - {c['name']}", c["voice"])
            print(f"Designed a new voice for {c['name']}")
            voices_file.write_text(json.dumps(voices, indent=2) + "\n")
    return voices


def speak(text: str, voice_id: str, out: Path) -> Path:
    resp = requests.post(
        f"{API}/text-to-speech/{voice_id}",
        headers={**_headers(), "accept": "audio/mpeg"},
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=120,
    )
    resp.raise_for_status()
    out.write_bytes(resp.content)
    return out
