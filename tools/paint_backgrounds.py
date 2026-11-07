"""Paints the background library once with Google's image AI (about 3 cents a picture) and saves it
in assets/backgrounds/, where every video then reuses it for free.

    GEMINI_API_KEY=... python -m tools.paint_backgrounds        # paints what's missing
    VARIANTS=3 ONLY=city,lab python -m tools.paint_backgrounds  # just some places
    WIDE=true python -m tools.paint_backgrounds                 # 16:9 ones for the weekly long video
"""
import base64
import io
import json
import os
import sys
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "backgrounds"
API = "https://generativelanguage.googleapis.com/v1beta"
MODELS = ["gemini-nano-banana-2.1", "gemini-3.1-flash-image", "gemini-3.1-flash-lite-image"]

WIDE = os.environ.get("WIDE", "").lower() == "true"
SIZE = (1920, 1080) if WIDE else (1080, 1920)
ASPECT = "16:9" if WIDE else "9:16"

STYLE = ("Vertical 9:16 background art for a stick-figure animation. Stylized 2D digital painting, clean "
         "shapes, soft gradients, cinematic warm lighting with glowing light sources, gentle atmospheric haze "
         "and depth, rich but muted colours, like a high-quality modern animated explainer video. The ground "
         "or floor is a flat, open, uncluttered area across the bottom quarter of the picture, with the "
         "horizon or back wall around two-thirds of the way down, and empty space on the left side where a "
         "character will stand. No people, no characters, no animals, no text, no letters, no numbers, no logos.")

PLACES = {
    "sky": "a grassy hilltop under a huge golden-hour sky with soft glowing clouds",
    "underwater": "the deep ocean, light rays from the surface far above, coral and rocks on a sandy sea floor",
    "space": "outer space with a big ringed planet, a colourful nebula and stars, a grey rocky moon surface as the ground",
    "forest": "a misty pine forest clearing at sunrise with god rays through the trees",
    "desert": "rolling sand dunes at sunset with a huge low sun and a few cacti",
    "snow": "a snowy mountain plateau at blue twilight with snow falling and peaks behind",
    "night": "a quiet street at night under a full moon, warm street lamps glowing, houses with lit windows",
    "lab": "a science laboratory interior, a big window showing a sunset city skyline, benches with glassware and a microscope",
    "city": "a city street at golden hour, shopfronts with warm glowing windows, a cafe awning, street lamps",
    "bedroom": "a cozy bedroom at night lit by a desk lamp, a bed, a window with city lights, plain posters on the wall",
}


if WIDE:
    STYLE = STYLE.replace("Vertical 9:16", "Widescreen 16:9").replace(
        "the bottom quarter of the picture, with the horizon or back wall around two-thirds of the way down, "
        "and empty space on the left side",
        "the bottom fifth of the picture, with the horizon or back wall around three-quarters of the way down, "
        "and empty space on the left third")


def _find_image(obj):
    """Finds base64 image data anywhere in an API response."""
    if isinstance(obj, dict):
        mime = obj.get("mimeType") or obj.get("mime_type") or ""
        data = obj.get("data")
        if isinstance(data, str) and len(data) > 1000 and (mime.startswith("image") or obj.get("type") == "image"):
            return data
        for v in obj.values():
            found = _find_image(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_image(v)
            if found:
                return found
    return None


def paint(prompt: str, key: str) -> Image.Image:
    headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
    errors = []
    for model in MODELS:
        attempts = [
            (f"{API}/models/{model}:generateContent",
             {"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": ASPECT}}}),
            (f"{API}/interactions",
             {"model": model, "input": prompt, "response_format": {"type": "image", "aspect_ratio": ASPECT}}),
        ]
        for url, body in attempts:
            resp = requests.post(url, headers=headers, json=body, timeout=300)
            if resp.ok:
                data = _find_image(resp.json())
                if data:
                    return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")
                errors.append(f"{model} {url.rsplit('/', 1)[-1]}: no image in reply {json.dumps(resp.json())[:300]}")
            else:
                errors.append(f"{model} {url.rsplit('/', 1)[-1]}: {resp.status_code} {resp.text[:300]}")
    raise RuntimeError("\n".join(errors))


def fit(img: Image.Image) -> Image.Image:
    """Crops and scales to exactly SIZE (1080x1920, or 1920x1080 for wide)."""
    w, h = img.size
    target = SIZE[0] / SIZE[1]
    if w / h > target:
        nw = int(h * target)
        img = img.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / target)
        img = img.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return img.resize(SIZE, Image.LANCZOS)


def main() -> None:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY isn't set: add it as a GitHub secret first.")
    variants = int(os.environ.get("VARIANTS") or 3)
    only = [p.strip() for p in (os.environ.get("ONLY") or "").split(",") if p.strip()]
    OUT.mkdir(parents=True, exist_ok=True)
    made = 0
    for place, description in PLACES.items():
        if only and place not in only:
            continue
        for i in range(1, variants + 1):
            out = OUT / f"{'wide-' if WIDE else ''}{place}-{i}.jpg"
            if out.exists():
                continue
            prompt = f"{STYLE}\n\nThe place: {description}." + (" A different view and time of day from usual." if i > 1 else "")
            try:
                fit(paint(prompt, key)).save(out, quality=90)
            except Exception as err:
                print(f"Couldn't paint {place} #{i}:\n{err}")
                if made == 0:
                    sys.exit(1)   # the very first one failing means the key or model is wrong: stop, don't waste money
                continue
            made += 1
            print(f"Painted {out.name}")
    print(f"Done: {made} new backgrounds")


if __name__ == "__main__":
    main()
