"""Draws one vertical cartoon frame per shot."""
import base64
import os
from pathlib import Path

import requests

URL = "https://api.openai.com/v1/images/generations"
EDIT_URL = "https://api.openai.com/v1/images/edits"


def build_prompt(shot: dict, config: dict, safe: bool = False) -> str:
    chars = config["characters"]
    cast = "; ".join(f"{chars[c]['name']}: {chars[c]['look']}" for c in shot["characters"])
    speaker = chars[shot["speaker"]]["name"]
    # The safe version drops the scene description, which is what usually trips the image safety filter
    # (parodies of crime movies mention bosses, threats, weapons...).
    scene = "a bright, friendly cartoon room" if safe else shot["setting"]
    return (
        f"{config['style']}. Family-friendly. Characters in frame: {cast}. "
        f"Scene: {scene}. {speaker} is in the foreground, facing the viewer, with a clearly visible mouth, closed."
    )


def _request(prompt: str, config: dict) -> requests.Response:
    images = config.get("images", {})
    return requests.post(
        URL,
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        json={"model": images.get("model", "gpt-image-2"), "prompt": prompt,
              "size": "1024x1536", "quality": images.get("quality", "medium"), "n": 1},
        timeout=300,
    )


def _error(resp: requests.Response) -> str:
    try:
        err = resp.json()["error"]
        return f"{resp.status_code} {err.get('code') or err.get('type')}: {err.get('message')}"
    except (ValueError, KeyError, TypeError):
        return f"{resp.status_code}: {resp.text[:500]}"


def _is_safety_block(resp: requests.Response) -> bool:
    text = _error(resp).lower()
    return "moderation" in text or "safety" in text


def draw(shot: dict, config: dict, out: Path) -> Path:
    resp = _request(build_prompt(shot, config), config)
    if resp.status_code == 400 and _is_safety_block(resp):
        print(f"  image blocked by the safety filter ({_error(resp)}), retrying with a simpler scene")
        resp = _request(build_prompt(shot, config, safe=True), config)
    if not resp.ok:
        raise RuntimeError(f"OpenAI image request failed: {_error(resp)}")
    out.write_bytes(base64.b64decode(resp.json()["data"][0]["b64_json"]))
    return out


def draw_mouth_open(shot: dict, config: dict, closed: Path, out: Path) -> Path | None:
    """Redraws the shot with the speaker's mouth open, for lip flaps. Returns None if it can't,
    so a failed edit leaves a still frame instead of stopping the whole run."""
    c = config["characters"][shot["speaker"]]
    images = config.get("images", {})
    prompt = (
        "Keep this image exactly the same: same characters, poses, colors, background, framing and art style. "
        f"Change only one thing: {c['name']} ({c['look']}) now has their mouth wide open, mid-word, as if talking. "
        "Do not change anyone else."
    )
    data_url = "data:image/png;base64," + base64.b64encode(closed.read_bytes()).decode()
    resp = requests.post(
        EDIT_URL,
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        json={"model": images.get("model", "gpt-image-2"), "images": [{"image_url": data_url}],
              "prompt": prompt, "size": "1024x1536", "quality": images.get("quality", "medium"), "n": 1},
        timeout=300,
    )
    if not resp.ok:
        print(f"  couldn't draw the talking frame ({_error(resp)}), using a still frame for this shot")
        return None
    out.write_bytes(base64.b64decode(resp.json()["data"][0]["b64_json"]))
    return out
