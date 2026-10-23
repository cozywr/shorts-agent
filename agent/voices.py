"""Turns each line into speech with the character's ElevenLabs voice."""
import os
from pathlib import Path

import requests

URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def speak(text: str, voice_id: str, out: Path) -> Path:
    resp = requests.post(
        URL.format(voice_id=voice_id),
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "accept": "audio/mpeg"},
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=120,
    )
    resp.raise_for_status()
    out.write_bytes(resp.content)
    return out
