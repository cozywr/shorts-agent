"""Downloads preview clips of female narrator voices from ElevenLabs so you can pick one by ear.

Run by the "Voice samples" workflow. The clips land in output/voice-samples/, numbered,
with voices.txt listing each number's voice_id and library_owner_id for config.yaml.
"""
import os
import re
from pathlib import Path

import requests

API = "https://api.elevenlabs.io/v1"
HEADERS = {"xi-api-key": os.environ["ELEVENLABS_API_KEY"]}
OUT = Path("output/voice-samples")


def _library(use_case: str, count: int) -> list[dict]:
    params = {"gender": "female", "language": "en", "use_cases": use_case, "page_size": count,
              "sort": "trending"}
    resp = requests.get(f"{API}/shared-voices", headers=HEADERS, params=params, timeout=60)
    if resp.status_code >= 400:  # fall back to the default order if this sort isn't accepted
        params.pop("sort")
        resp = requests.get(f"{API}/shared-voices", headers=HEADERS, params=params, timeout=60)
    resp.raise_for_status()
    return [{"name": v["name"], "voice_id": v["voice_id"], "owner": v.get("public_owner_id", ""),
             "preview": v.get("preview_url"), "about": v.get("description") or ""}
            for v in resp.json()["voices"]]


def _premade() -> list[dict]:
    resp = requests.get(f"{API}/voices", headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return [{"name": v["name"], "voice_id": v["voice_id"], "owner": "", "preview": v.get("preview_url"),
             "about": v.get("description") or ""}
            for v in resp.json()["voices"]
            if v.get("category") == "premade" and (v.get("labels") or {}).get("gender") == "female"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    seen, picks = set(), []
    for voice in _library("narrative_story", 8) + _library("social_media", 6) + _premade():
        if voice["voice_id"] not in seen and voice["preview"]:
            seen.add(voice["voice_id"])
            picks.append(voice)
    lines = []
    for i, v in enumerate(picks, 1):
        name = re.sub(r"[^\w -]+", "", v["name"])[:40].strip()
        audio = requests.get(v["preview"], timeout=60)
        if not audio.ok:
            continue
        (OUT / f"{i:02} - {name}.mp3").write_bytes(audio.content)
        lines.append(f"{i:02} - {v['name']}\n    voice_id: {v['voice_id']}\n"
                     f"    library_owner_id: {v['owner']}\n    {v['about'][:150]}\n")
    (OUT / "voices.txt").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
