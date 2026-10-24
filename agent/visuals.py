"""Draws one vertical cartoon frame per shot."""
import base64
import os
from pathlib import Path

import requests

URL = "https://api.openai.com/v1/images/generations"


def build_prompt(shot: dict, config: dict, safe: bool = False) -> str:
    chars = config["characters"]
    cast = "; ".join(f"{chars[c]['name']}: {chars[c]['look']}" for c in shot["characters"])
    speaker = chars[shot["speaker"]]["name"]
    # The safe version drops the scene description, which is what usually trips the image safety filter
    # (parodies of crime movies mention bosses, threats, weapons...).
    scene = "a bright, friendly cartoon room" if safe else shot["setting"]
    return (
        f"{config['style']}. Family-friendly. Characters in frame: {cast}. "
        f"Scene: {scene}. {speaker} is speaking, shown in the foreground."
    )


def _request(prompt: str, config: dict) -> requests.Response:
    images = config.get("images", {})
    return requests.post(
        URL,
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        json={"model": images.get("model", "gpt-image-1"), "prompt": prompt,
              "size": "1024x1536", "quality": images.get("quality", "medium"), "n": 1},
        timeout=300,
    )


def _error(resp: requests.Response) -> str:
    try:
        err = resp.json()["error"]
        return f"{resp.status_code} {err.get('code') or err.get('type')}: {err.get('message')}"
    except (ValueError, KeyError, TypeError):
        return f"{resp.status_code}: {resp.text[:500]}"


def draw(shot: dict, config: dict, out: Path) -> Path:
    resp = _request(build_prompt(shot, config), config)
    if resp.status_code == 400:
        print(f"  image rejected ({_error(resp)}), retrying with a simpler scene")
        resp = _request(build_prompt(shot, config, safe=True), config)
    if not resp.ok:
        raise RuntimeError(f"OpenAI image request failed: {_error(resp)}")
    out.write_bytes(base64.b64decode(resp.json()["data"][0]["b64_json"]))
    return out
