"""Gives the channel its own ElevenLabs narrator voice and reads the story with word timings."""
import base64
import json
import os
import re
import subprocess
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
    # Emoji can't be read aloud and show up as empty boxes in the captions.
    return re.sub(r" ?[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]+", "", text)


TAG = re.compile(r"\s*\[[a-z ]{2,20}\]")


def speak(text: str, voice_id: str, out: Path, settings: dict | None = None) -> dict:
    """Saves the speech to `out` and returns ElevenLabs' per-character timing for the text that was read.
    With the expressive eleven_v3 model, directions like [excited] or [giggles] are acted out;
    other models (or if v3 fails) get the text without them."""
    settings = settings or {}
    model = settings.get("model", "eleven_multilingual_v2")
    attempts = [(model, text)] if model == "eleven_v3" else []
    attempts.append(("eleven_multilingual_v2" if model == "eleven_v3" else model, TAG.sub("", text).strip()))
    last = None
    for model_id, said in attempts:
        if model_id == "eleven_v3":
            voice_settings = {"stability": 0.0}        # v3's most expressive "creative" setting
        else:
            voice_settings = {"stability": settings.get("stability", 0.3),
                              "similarity_boost": 0.8, "style": settings.get("style", 0.6)}
        resp = requests.post(
            f"{API}/text-to-speech/{voice_id}/with-timestamps",
            headers=_headers(),
            json={"text": said, "model_id": model_id, "voice_settings": voice_settings},
            timeout=300,
        )
        if resp.ok:
            data = resp.json()
            out.write_bytes(base64.b64decode(data["audio_base64"]))
            print(f"Voice: {model_id}")
            return {**data["alignment"], "text": said}
        last = resp
        print(f"{model_id} didn't work ({resp.status_code}: {resp.text[:200]})")
    last.raise_for_status()


def characters_left() -> int | None:
    """Characters left on the ElevenLabs plan this month, or None if the key can't tell us."""
    try:
        resp = requests.get(f"{API}/user/subscription", headers=_headers(), timeout=60)
        resp.raise_for_status()
        sub = resp.json()
        print(f"ElevenLabs plan: {sub.get('tier')}, {sub['character_count']:,} of {sub['character_limit']:,} "
              "characters used this month")
        return sub["character_limit"] - sub["character_count"]
    except Exception as err:
        print(f"Couldn't check the ElevenLabs plan: {err}")
        return None


def speak_parts(parts: list[str], voice_id: str, out: Path, settings: dict | None = None) -> tuple[dict, list[str]]:
    """Reads a long narration in pieces (the voice models only take a few thousand characters at a time)
    and joins them into one audio file with one set of timings. Also returns what was actually read for
    each piece (the [direction] tags are dropped for a piece that fell back to the older model)."""
    from agent.video import duration   # here to keep voices importable on its own
    pieces, said, chars, starts, ends = [], [], [], [], []
    offset = 0.0
    for n, text in enumerate(parts):
        piece = out.with_name(f"{out.stem}-{n}.mp3")
        a = speak(text, voice_id, piece, settings)
        if chars:   # the space between pieces
            chars.append(" ")
            starts.append(offset)
            ends.append(offset)
        chars += a["characters"]
        starts += [t + offset for t in a["character_start_times_seconds"]]
        ends += [t + offset for t in a["character_end_times_seconds"]]
        offset += duration(piece)
        pieces.append(piece)
        said.append(a["text"])
    listing = out.with_name(f"{out.stem}-parts.txt")
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in pieces))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c:a", "libmp3lame", "-q:a", "2", str(out)], check=True)
    return {"characters": chars, "character_start_times_seconds": starts, "character_end_times_seconds": ends,
            "text": " ".join(said)}, said
