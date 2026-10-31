"""Gives the channel its own ElevenLabs narrator voice and reads the story with word timings."""
import base64
import json
import os
import re
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


def _add_from_library(owner_id: str, voice_id: str, name: str) -> str:
    """Adds a Voice Library voice to the account (needed before it can speak) and returns its id."""
    resp = requests.post(f"{API}/voices/add/{owner_id}/{voice_id}", headers=_headers(),
                         json={"new_name": name}, timeout=120)
    if resp.status_code == 400 and "already" in resp.text.lower():
        return voice_id
    resp.raise_for_status()
    return resp.json()["voice_id"]


def ensure_narrator(config: dict, voices_file: Path, which: str = "narrator") -> str:
    """Returns the voice id for the narrator, or for one of config's extra_voices (e.g. "creepy"):
    a picked voice (voice_id), or one designed from its description.
    A new voice is set up whenever the choice in config.yaml changes."""
    if which == "narrator":
        n = config["narrator"]
    elif which in (config.get("extra_voices") or {}):
        n = config["extra_voices"][which]
    else:
        raise SystemExit(f"The story asks for voice {which!r}, but config.yaml has no voice by that name.")
    if not n.get("voice_id") and not n.get("voice"):
        raise SystemExit(f"The {which!r} voice hasn't been picked yet: set its voice_id in config.yaml.")
    if n.get("voice_id") and not n.get("library_owner_id"):
        return n["voice_id"]
    source = f"library:{n['library_owner_id']}/{n['voice_id']}" if n.get("voice_id") else n["voice"]
    voices = json.loads(voices_file.read_text()) if voices_file.exists() else {}
    saved = voices.get(which)
    if not isinstance(saved, dict) or saved.get("voice") != source:
        if n.get("voice_id"):
            voice_id = _add_from_library(n["library_owner_id"], n["voice_id"], f"Shorts - {n['name']}")
            print(f"Added the {which} voice from the Voice Library")
        else:
            voice_id = _design(f"Shorts - {n['name']}", n["voice"])
            print(f"Designed a new {which} voice")
        voices[which] = {"id": voice_id, "voice": source}
        voices_file.write_text(json.dumps(voices, indent=2) + "\n")
    return voices[which]["id"]


def say_as(text: str, config: dict) -> str:
    """Swaps written shorthand for how it should be read aloud (narrator.say_as in config.yaml)."""
    for written, spoken in (config["narrator"].get("say_as") or {}).items():
        text = re.sub(rf"(?<!\w){re.escape(written)}(?!\w)", spoken, text)
    return text


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
