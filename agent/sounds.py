"""Cartoon sound effects and the happy background music, made once with ElevenLabs and then
kept in assets/ (the workflow commits them), so every video sounds the same and costs nothing extra."""
import os
from pathlib import Path

import requests

API = "https://api.elevenlabs.io/v1"
ROOT = Path(__file__).resolve().parent.parent
SFX_DIR = ROOT / "assets" / "sfx"
MUSIC_DIR = ROOT / "assets" / "music"

SFX = {
    "boing": ("Cartoon spring boing sound effect, bouncy and funny", 1.0),
    "pop": ("Cartoon bubble pop sound, short and cute", 0.5),
    "whoosh": ("Fast cartoon whoosh swish, quick", 0.7),
    "ding": ("Bright cheerful ding bell, like a correct answer in a kids game show", 1.0),
    "drumroll": ("Short snare drum roll ending with a cymbal crash", 2.2),
    "slide_whistle": ("Cartoon slide whistle going up, funny", 1.2),
    "splat": ("Cartoon splat, funny squishy", 0.6),
    "bonk": ("Cartoon bonk on the head, funny wooden knock", 0.6),
    "honk": ("Silly clown bicycle horn honk honk", 0.9),
    "tada": ("Short cartoon ta-da fanfare with trumpets, triumphant and silly", 1.5),
    "record_scratch": ("Vinyl record scratch, comedic stop", 0.8),
    "kids_wow": ("Group of children saying wooow, amazed and delighted", 1.5),
    "kids_laugh": ("Group of children giggling and laughing happily", 2.0),
    "zip": ("Cartoon character zipping away fast, zip sound", 0.8),
    "boom": ("Deep cinematic bass boom impact, dramatic, short", 1.2),
    "sting": ("Short suspense string sting, dramatic reveal", 1.5),
    "heartbeat": ("Tense heartbeat thumping, two beats", 1.4),
    "clock": ("Fast clock ticking, tense countdown", 1.5),
    "alarm": ("Short electronic warning alarm beeping", 1.2),
    "crowd_gasp": ("Small crowd gasping in shock, oooh", 1.2),
    "crickets": ("Awkward silence with crickets chirping, comedic", 1.8),
}
NAMES = list(SFX) + ["none"]

MUSIC = {
    "kids": ("happy-loop.mp3", "Bouncy, playful, upbeat instrumental music for a kids cartoon: ukulele, xylophone, "
                               "hand claps and whistling, silly and happy, steady tempo, no vocals, loops smoothly"),
    "young_adults": ("what-if-loop.mp3", "Curious, slightly tense lo-fi hip hop beat for a science explainer: soft "
                                         "drums, deep bass, mysterious synth plucks, steady tempo, no vocals, loops smoothly"),
}


def _headers() -> dict:
    return {"xi-api-key": os.environ["ELEVENLABS_API_KEY"]}


def _generate(text: str, seconds: float, loop: bool = False) -> bytes:
    body = {"text": text, "duration_seconds": seconds, "prompt_influence": 0.6}
    if loop:
        body["loop"] = True
    resp = requests.post(f"{API}/sound-generation", headers=_headers(), json=body, timeout=180)
    if resp.status_code == 400 and loop:  # older models don't know "loop"
        body.pop("loop")
        resp = requests.post(f"{API}/sound-generation", headers=_headers(), json=body, timeout=180)
    resp.raise_for_status()
    return resp.content


def effect(name: str) -> Path | None:
    """The sound file for an effect name, made the first time it's needed. None for "none" or on errors."""
    if name not in SFX:
        return None
    out = SFX_DIR / f"{name}.mp3"
    if out.exists():
        return out
    try:
        prompt, seconds = SFX[name]
        data = _generate(prompt, seconds)
    except Exception as err:  # a missing sound effect shouldn't stop the video
        print(f"Couldn't make the {name} sound: {err}")
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print(f"Made the {name} sound effect")
    return out


def music(audience: str = "kids") -> Path | None:
    """The background music loop for this audience, made the first time it's needed."""
    name, prompt = MUSIC.get(audience, MUSIC["kids"])
    music_file = MUSIC_DIR / name
    if music_file.exists():
        return music_file
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    try:
        resp = requests.post(f"{API}/music", headers=_headers(), timeout=300,
                             json={"prompt": prompt, "music_length_ms": 60000, "force_instrumental": True})
        resp.raise_for_status()
        data = resp.content
        print("Made the background music")
    except Exception as err:
        print(f"Music API didn't work ({err}); making a sound-effect loop instead")
        try:
            data = _generate(prompt, 30, loop=True)
        except Exception as err2:
            print(f"Couldn't make background music: {err2}")
            return None
    music_file.write_bytes(data)
    return music_file
