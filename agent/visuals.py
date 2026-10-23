"""Draws one vertical cartoon frame per shot."""
import base64
import os
from pathlib import Path

import requests

URL = "https://api.openai.com/v1/images/generations"


def build_prompt(shot: dict, config: dict) -> str:
    chars = config["characters"]
    cast = "; ".join(f"{chars[c]['name']}: {chars[c]['look']}" for c in shot["characters"])
    speaker = chars[shot["speaker"]]["name"]
    return (
        f"{config['style']}. Characters in frame: {cast}. "
        f"Scene: {shot['setting']}. {speaker} is speaking, shown in the foreground."
    )


def draw(shot: dict, config: dict, out: Path) -> Path:
    resp = requests.post(
        URL,
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        json={"model": "gpt-image-1", "prompt": build_prompt(shot, config), "size": "1024x1536", "quality": "medium", "n": 1},
        timeout=300,
    )
    resp.raise_for_status()
    out.write_bytes(base64.b64decode(resp.json()["data"][0]["b64_json"]))
    return out
