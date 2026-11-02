"""Draws the cartoon: our stickman host acting out each scene in front of a bright background,
with the thing the fact is about shown as big emoji pictures and a headline at the top.

Everything is drawn with code, so the stickman looks exactly the same in every video.
"""
import math
import random
import re
import urllib.request
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
GROUND = 1440                      # y of the ground line the stickman stands on
HOST_X = 300                       # where the stickman stands
PROPS_CENTER = (745, 930)          # where the pictures go
FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Fredoka-Bold.ttf"
EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
EMOJI_PNG = "https://cdn.jsdelivr.net/gh/googlefonts/noto-emoji@v2.047/png/512/emoji_u{code}.png"

BACKGROUNDS = ["sky", "underwater", "space", "forest", "desert", "snow", "night", "lab"]
POSES = ["explain", "wave", "point", "think", "surprised", "cheer", "jump", "shrug", "walk", "dance"]

INK = (34, 34, 52)
CAP = (235, 64, 52)
CAP_DARK = (190, 40, 34)
SS = 2                             # the stickman is drawn at 2x and shrunk, for smooth edges


# ---------------------------------------------------------------- helpers

def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT), size)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _mix(c1, c2, t):
    return tuple(int(_lerp(a, b, t)) for a, b in zip(c1, c2))


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def _pop(t: float) -> float:
    """0 → overshoot → 1 over ~0.35s, for things popping in."""
    if t <= 0:
        return 0.0
    if t >= 0.35:
        return 1.0
    x = t / 0.35
    return 1 + 0.25 * math.sin(x * math.pi) - (1 - x) ** 3


def _gradient(top, bottom, height=H) -> Image.Image:
    col = Image.new("RGB", (1, height))
    for y in range(height):
        col.putpixel((0, y), _mix(top, bottom, y / (height - 1)))
    return col.resize((W, height))


# ---------------------------------------------------------------- backgrounds

def _cloud(scale: float = 1.0) -> Image.Image:
    w, h = int(360 * scale), int(170 * scale)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for cx, cy, r in [(0.25, 0.62, 0.22), (0.45, 0.42, 0.3), (0.68, 0.55, 0.25), (0.5, 0.7, 0.24)]:
        R = r * w * 0.75
        d.ellipse((cx * w - R, cy * h - R, cx * w + R, cy * h + R), fill=(255, 255, 255, 235))
    return img


def _hill_ground(d: ImageDraw.ImageDraw, color, dark):
    d.rectangle((0, GROUND, W, H), fill=color)
    d.ellipse((-300, GROUND - 120, 700, GROUND + 260), fill=color)
    d.ellipse((450, GROUND - 80, 1500, GROUND + 300), fill=_mix(color, dark, 0.25))
    d.rectangle((0, GROUND + 60, W, H), fill=color)
    d.line((0, GROUND + 60, W, GROUND + 60), fill=dark, width=0)


def _tree(d, x, base, h, color, trunk):
    d.rectangle((x - 14, base - h * 0.25, x + 14, base), fill=trunk)
    for i in range(3):
        top = base - h + i * h * 0.22
        half = h * (0.28 + i * 0.07)
        d.polygon([(x, top), (x - half, top + h * 0.42), (x + half, top + h * 0.42)], fill=color)


@lru_cache(maxsize=None)
def background(kind: str) -> Image.Image:
    """The still part of each background, drawn once."""
    rnd = random.Random(kind)
    if kind == "underwater":
        img = _gradient((64, 200, 230), (18, 70, 150))
        d = ImageDraw.Draw(img)
        for _ in range(7):
            x = rnd.randint(0, W)
            d.polygon([(x, 0), (x + 140, 0), (x + 260, 1300), (x + 200, 1300)], fill=_mix((64, 200, 230), (255, 255, 255), 0.12))
        d.rectangle((0, GROUND, W, H), fill=(240, 214, 150))
        d.ellipse((-200, GROUND - 50, 600, GROUND + 120), fill=(240, 214, 150))
        for x in (60, 980, 1040, 880):
            for k in range(5):
                y = GROUND - k * 70
                d.ellipse((x - 24 + (k % 2) * 18, y - 80, x + 24 + (k % 2) * 18, y), fill=(46, 160, 90))
    elif kind == "space":
        img = _gradient((14, 12, 48), (60, 30, 110))
        d = ImageDraw.Draw(img)
        d.ellipse((40, 560, 200, 720), fill=(255, 160, 80))
        d.ellipse((0, 620, 240, 660), outline=(255, 220, 160), width=8)
        d.rectangle((0, GROUND, W, H), fill=(170, 170, 190))
        d.ellipse((-200, GROUND - 60, 1300, GROUND + 140), fill=(170, 170, 190))
        for _ in range(9):
            x, y, r = rnd.randint(0, W), rnd.randint(GROUND + 40, H - 300), rnd.randint(20, 60)
            d.ellipse((x - r, y - r * 0.5, x + r, y + r * 0.5), fill=(140, 140, 165))
    elif kind == "forest":
        img = _gradient((150, 215, 255), (220, 245, 255))
        d = ImageDraw.Draw(img)
        for i, x in enumerate(range(-40, W + 80, 150)):
            _tree(d, x, GROUND - 40, 420 + (i % 3) * 70, (60, 150, 80), (120, 80, 50))
        for x in range(30, W, 230):
            _tree(d, x, GROUND + 10, 300, (40, 125, 65), (110, 70, 40))
        _hill_ground(d, (110, 200, 90), (60, 140, 50))
    elif kind == "desert":
        img = _gradient((255, 190, 120), (255, 235, 190))
        d = ImageDraw.Draw(img)
        d.ellipse((760, 180, 980, 400), fill=(255, 240, 150))
        d.ellipse((-400, GROUND - 200, 700, GROUND + 300), fill=(232, 180, 110))
        d.ellipse((400, GROUND - 160, 1500, GROUND + 300), fill=(240, 196, 120))
        d.rectangle((0, GROUND, W, H), fill=(245, 205, 130))
        green, x = (70, 160, 80), 990
        d.rounded_rectangle((x - 28, GROUND - 280, x + 28, GROUND + 10), 28, fill=green)
        d.rounded_rectangle((x - 95, GROUND - 150, x, GROUND - 115), 17, fill=green)
        d.rounded_rectangle((x - 95, GROUND - 230, x - 62, GROUND - 120), 17, fill=green)
        d.rounded_rectangle((x, GROUND - 190, x + 80, GROUND - 158), 16, fill=green)
        d.rounded_rectangle((x + 48, GROUND - 250, x + 80, GROUND - 165), 16, fill=green)
    elif kind == "snow":
        img = _gradient((170, 210, 245), (235, 245, 255))
        d = ImageDraw.Draw(img)
        d.polygon([(-100, GROUND), (250, 900), (600, GROUND)], fill=(210, 225, 245))
        d.polygon([(250, 900), (180, 1030), (320, 1030)], fill=(255, 255, 255))
        d.polygon([(450, GROUND), (850, 820), (1250, GROUND)], fill=(200, 215, 240))
        d.polygon([(850, 820), (770, 970), (930, 970)], fill=(255, 255, 255))
        d.rectangle((0, GROUND, W, H), fill=(250, 252, 255))
        d.ellipse((-200, GROUND - 60, 700, GROUND + 120), fill=(250, 252, 255))
    elif kind == "night":
        img = _gradient((20, 30, 80), (70, 60, 140))
        d = ImageDraw.Draw(img)
        d.ellipse((780, 180, 960, 360), fill=(255, 245, 200))
        d.ellipse((830, 160, 1000, 330), fill=_mix((20, 30, 80), (70, 60, 140), 0.1))
        _hill_ground(d, (40, 90, 70), (20, 50, 40))
    elif kind == "lab":
        img = _gradient((200, 190, 255), (235, 225, 255))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((120, 180, 960, 600), 24, fill=(50, 90, 70), outline=(150, 100, 60), width=18)
        d.line((180, 520, 420, 520), fill=(230, 240, 230), width=6)
        d.ellipse((820, 470, 900, 550), outline=(230, 240, 230), width=6)
        d.rectangle((0, GROUND, W, H), fill=(210, 170, 120))
        for x in range(0, W, 120):
            d.line((x, GROUND, x - 80, H), fill=(190, 150, 100), width=6)
    else:  # sky
        img = _gradient((110, 190, 255), (210, 238, 255))
        d = ImageDraw.Draw(img)
        d.ellipse((800, 140, 1000, 340), fill=(255, 220, 80))
        _hill_ground(d, (120, 210, 90), (70, 150, 50))
        for x in (90, 1000, 700):
            y = GROUND + 120 + (x % 7) * 20
            for a in range(0, 360, 72):
                dx, dy = 22 * math.cos(math.radians(a)), 22 * math.sin(math.radians(a))
                d.ellipse((x + dx - 16, y + dy - 16, x + dx + 16, y + dy + 16), fill=(255, 255, 255))
            d.ellipse((x - 14, y - 14, x + 14, y + 14), fill=(255, 200, 60))
    return img.convert("RGB")


def _animate_background(frame: Image.Image, kind: str, t: float) -> None:
    """Small moving things: clouds drift, bubbles rise, stars twinkle, snow falls."""
    d = ImageDraw.Draw(frame)
    rnd = random.Random(kind + "anim")
    if kind in ("sky", "forest"):
        for i in range(3):
            sp = 18 + i * 9
            x = (rnd.randint(0, W) + t * sp) % (W + 500) - 400
            y = 120 + i * 210 + rnd.randint(0, 60)
            frame.paste(_cloud_sprite(0.8 + 0.3 * (i % 2)), (int(x), int(y)), _cloud_sprite(0.8 + 0.3 * (i % 2)))
    elif kind == "underwater":
        for i in range(16):
            x0, sp, r = rnd.randint(0, W), rnd.randint(60, 140), rnd.randint(8, 22)
            y = GROUND - ((rnd.randint(0, 1500) + t * sp) % 1500)
            x = x0 + 14 * math.sin(t * 2 + i)
            d.ellipse((x - r, y - r, x + r, y + r), outline=(220, 245, 255), width=4)
    elif kind in ("space", "night"):
        for i in range(70):
            x, y = rnd.randint(0, W), rnd.randint(0, GROUND - 100)
            r = 2 + 3 * (0.5 + 0.5 * math.sin(t * rnd.uniform(1.5, 4) + i))
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 230))
    elif kind == "snow":
        for i in range(60):
            x0, sp, r = rnd.randint(0, W), rnd.randint(50, 120), rnd.randint(5, 11)
            y = (rnd.randint(0, H) + t * sp) % H
            x = x0 + 20 * math.sin(t + i)
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255))
    elif kind == "desert":
        x = (t * 40) % (W + 400) - 200
        frame.paste(_cloud_sprite(0.6), (int(x), 520), _cloud_sprite(0.6))


@lru_cache(maxsize=None)
def _cloud_sprite(scale: float) -> Image.Image:
    return _cloud(scale)


# ---------------------------------------------------------------- emoji pictures

def _codepoints(emoji: str) -> str:
    return "_".join(f"{ord(c):04x}" for c in emoji if ord(c) != 0xFE0F)


@lru_cache(maxsize=None)
def emoji_image(emoji: str, cache_dir: str = "") -> Image.Image | None:
    """A big, sharp picture of an emoji (Noto Emoji, Apache 2.0). Downloads the 512px version,
    or falls back to the emoji font. None if it can't be drawn."""
    code = _codepoints(emoji)
    cached = Path(cache_dir or ".") / "emoji" / f"{code}.png"
    if cached.exists():
        return Image.open(cached).convert("RGBA")
    try:
        with urllib.request.urlopen(EMOJI_PNG.format(code=code), timeout=20) as resp:
            data = resp.read()
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(data)
        return Image.open(cached).convert("RGBA")
    except Exception:
        pass
    try:
        font = ImageFont.truetype(EMOJI_FONT, 109)
    except OSError:
        return None
    img = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((80, 80), emoji, font=font, embedded_color=True, anchor="mm")
    box = img.getbbox()
    if not box or (box[2] - box[0]) < 40:
        return None
    return img.crop(box)


def _fit(img: Image.Image, size: int) -> Image.Image:
    scale = size / max(img.size)
    return img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)


def _prop_layout(n: int) -> list[tuple[float, float, int]]:
    cx, cy = PROPS_CENTER
    if n == 1:
        return [(cx, cy, 420)]
    if n == 2:
        return [(cx - 10, cy - 170, 280), (cx + 10, cy + 170, 280)]
    if n == 3:
        return [(cx, cy - 190, 250), (cx - 140, cy + 120, 250), (cx + 140, cy + 120, 250)]
    return [(cx - 135, cy - 150, 230), (cx + 135, cy - 150, 230), (cx - 135, cy + 150, 230), (cx + 135, cy + 150, 230)]


@lru_cache(maxsize=256)
def _sized(emoji: str, size: int, cache_dir: str) -> Image.Image | None:
    img = emoji_image(emoji, cache_dir)
    return _fit(img, size) if img else None


def _draw_props(frame: Image.Image, emojis: list[str], t: float, cache_dir: str) -> None:
    emojis = emojis[:4]
    for i, (e, (x, y, size)) in enumerate(zip(emojis, _prop_layout(len(emojis)))):
        s = _pop(t - 0.15 - i * 0.18)
        if s <= 0:
            continue
        img = _sized(e, size, cache_dir) or _sized("⭐", size, cache_dir)
        if img is None:
            continue
        bob = 16 * math.sin(t * 2.4 + i * 1.3)
        tilt = 5 * math.sin(t * 1.7 + i)
        sprite = img.rotate(tilt, resample=Image.BICUBIC, expand=True)
        if abs(s - 1) > 0.01:
            sprite = sprite.resize((max(1, int(sprite.width * s)), max(1, int(sprite.height * s))), Image.BILINEAR)
        frame.alpha_composite(sprite, (int(x - sprite.width / 2), int(y + bob - sprite.height / 2)))


# ---------------------------------------------------------------- headline

@lru_cache(maxsize=64)
def _headline_sprite(text: str) -> Image.Image:
    text = text.upper()
    size = 120
    while size > 60:
        font = _font(size)
        lines = _wrap(text, font, 960)
        if len(lines) <= 2:
            break
        size -= 8
    line_h = int(size * 1.08)
    img = Image.new("RGBA", (W, line_h * len(lines) + 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        y = 30 + line_h * i + line_h / 2
        d.text((W / 2, y + 10), line, font=font, fill=(0, 0, 0, 90), anchor="mm", stroke_width=14, stroke_fill=(0, 0, 0, 90))
        d.text((W / 2, y), line, font=font, fill=(255, 225, 60), anchor="mm", stroke_width=14, stroke_fill=INK)
    return img


def _wrap(text: str, font, width: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and font.getlength(trial) > width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur] if cur else lines


def _draw_headline(frame: Image.Image, text: str, t: float) -> None:
    if not text.strip():
        return
    s = _pop(t)
    if s <= 0:
        return
    img = _headline_sprite(text)
    sprite = img
    if abs(s - 1) > 0.01:
        sprite = sprite.resize((int(sprite.width * s), max(1, int(sprite.height * s))), Image.BILINEAR)
    frame.alpha_composite(sprite, (int(W / 2 - sprite.width / 2), int(330 - sprite.height / 2)))


# ---------------------------------------------------------------- the stickman

# Angles are in degrees from straight down: 0 points down, 90 to the right of the screen, 180 up.
# Each arm/leg is (upper angle, lower angle relative to upper).
UPPER_ARM, LOWER_ARM, THIGH, SHIN = 115, 105, 135, 135
SPINE, NECK, HEAD_R = 205, 26, 74


def pose(name: str, t: float) -> dict:
    s = math.sin
    p = {"la": (-25, -15), "ra": (25, 15), "ll": (-12, 0), "rl": (12, 0),
         "lift": 4 * s(t * 3), "lean": 0.0, "tilt": 0.0, "face": "happy", "look": 1.0}
    if name == "wave":
        p["ra"] = (150 + 18 * s(t * 9), 25 * s(t * 9 + 1))
        p["la"] = (-20, -10)
        p["tilt"] = 4
    elif name == "point":
        p["ra"] = (100 + 6 * s(t * 5), -5 + 4 * s(t * 5))
        p["la"] = (-45, 95)          # hand on hip
        p["lean"] = 4
    elif name == "think":
        p["ra"] = (35, 150)          # hand at chin
        p["la"] = (-30, 80)
        p["tilt"] = -8 + 3 * s(t * 1.5)
        p["face"] = "think"
        p["look"] = 0.3
    elif name == "surprised":
        jolt = max(0.0, 1 - t * 3)
        p["la"] = (-135 - 10 * s(t * 6), -20)
        p["ra"] = (135 + 10 * s(t * 6), 20)
        p["lift"] = 30 * jolt + 4 * s(t * 4)
        p["face"] = "wow"
    elif name == "cheer":
        b = abs(s(t * 5))
        p["la"] = (-160 + 15 * b, -10)
        p["ra"] = (160 - 15 * b, 10)
        p["lift"] = 40 * b
        p["ll"], p["rl"] = (-18 - 10 * b, 25 * b), (18 + 10 * b, -25 * b)
        p["face"] = "joy"
    elif name == "jump":
        b = abs(s(t * 3.6))
        p["lift"] = 150 * b
        p["la"] = (-150 * b - 20 * (1 - b), -10)
        p["ra"] = (150 * b + 20 * (1 - b), 10)
        p["ll"], p["rl"] = (-25 * b - 8, 60 * b), (25 * b + 8, -60 * b)
        p["face"] = "joy"
    elif name == "shrug":
        u = 0.5 + 0.5 * s(t * 4)
        p["la"] = (-55 - 10 * u, -95)
        p["ra"] = (55 + 10 * u, 95)
        p["lift"] = 6 * u
        p["tilt"] = 7
        p["face"] = "think"
    elif name == "walk":
        w = s(t * 7)
        p["ll"], p["rl"] = (28 * w, 15 * max(0.0, -w)), (-28 * w, 15 * max(0.0, w))
        p["la"], p["ra"] = (-30 * w - 8, -20), (30 * w + 8, 20)
        p["lift"] = 8 * abs(math.cos(t * 7))
    elif name == "dance":
        w = s(t * 6)
        p["la"] = (-110 - 40 * w, -50 * w)
        p["ra"] = (110 - 40 * w, 50 * w)
        p["ll"], p["rl"] = (-20 + 10 * w, 10), (20 + 10 * w, -10)
        p["lean"] = 8 * w
        p["face"] = "joy"
    else:  # explain: friendly talking gestures
        g = s(t * 2.6)
        p["ra"] = (55 + 20 * g, 55 + 15 * s(t * 3.1))
        p["la"] = (-30 - 8 * g, -40)
        p["tilt"] = 3 * s(t * 1.3)
    return p


def blend(a: dict, b: dict, k: float) -> dict:
    """Smoothly mixes two poses (k=0 → a, k=1 → b)."""
    out = dict(b)
    for key in ("la", "ra", "ll", "rl"):
        out[key] = (_lerp(a[key][0], b[key][0], k), _lerp(a[key][1], b[key][1], k))
    for key in ("lift", "lean", "tilt", "look"):
        out[key] = _lerp(a[key], b[key], k)
    out["face"] = a["face"] if k < 0.5 else b["face"]
    return out


def _vec(angle: float, length: float) -> tuple[float, float]:
    r = math.radians(angle)
    return math.sin(r) * length, math.cos(r) * length


BOX_W, BOX_H = 760, 1000            # area the stickman is drawn in (1x)
FOOT_Y = BOX_H - 40                 # feet sit here inside the box


def _limb(d, start, upper, lower, l1, l2, width):
    a = upper
    x1, y1 = start[0] + _vec(a, l1)[0], start[1] + _vec(a, l1)[1]
    b = upper + lower
    x2, y2 = x1 + _vec(b, l2)[0], y1 + _vec(b, l2)[1]
    d.line((start, (x1, y1), (x2, y2)), fill=INK, width=width, joint="curve")
    for x, y in (start, (x1, y1), (x2, y2)):
        r = width / 2
        d.ellipse((x - r, y - r, x + r, y + r), fill=INK)
    return x2, y2


def draw_stickman(p: dict, mouth_open: float, blink: bool) -> Image.Image:
    k = SS
    img = Image.new("RGBA", (BOX_W * k, BOX_H * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lw = 20 * k

    # Hip height comes from the legs so the feet stay on the ground.
    def leg_drop(leg):
        up, low = leg
        return _vec(up, THIGH)[1] + _vec(up + low, SHIN)[1]
    drop = max(leg_drop(p["ll"]), leg_drop(p["rl"]))
    hip = (BOX_W / 2 * k, (FOOT_Y - drop - p["lift"]) * k)

    # ground shadow (shrinks as we jump)
    sh = max(0.35, 1 - p["lift"] / 220)
    d.ellipse(((BOX_W / 2 - 110 * sh) * k, (FOOT_Y - 12) * k, (BOX_W / 2 + 110 * sh) * k, (FOOT_Y + 16) * k),
              fill=(0, 0, 0, 50))

    lean = p["lean"]
    neck = (hip[0] + _vec(180 - lean, SPINE)[0] * k, hip[1] + _vec(180 - lean, SPINE)[1] * k)
    shoulder = (hip[0] + _vec(180 - lean, SPINE - 20)[0] * k, hip[1] + _vec(180 - lean, SPINE - 20)[1] * k)

    for leg in ("ll", "rl"):
        _limb(d, hip, p[leg][0], p[leg][1], THIGH * k, SHIN * k, lw)
    d.line((hip, neck), fill=INK, width=lw)
    # left arm behind, right arm in front of the body
    _limb(d, shoulder, p["la"][0], p["la"][1], UPPER_ARM * k, LOWER_ARM * k, lw)
    _limb(d, shoulder, p["ra"][0], p["ra"][1], UPPER_ARM * k, LOWER_ARM * k, lw)

    # head
    tilt = p["tilt"]
    hc = (neck[0] + _vec(180 - lean + tilt, NECK + HEAD_R)[0] * k, neck[1] + _vec(180 - lean + tilt, NECK + HEAD_R)[1] * k)
    r = HEAD_R * k
    head = Image.new("RGBA", (int(r * 2 + 80 * k), int(r * 2 + 80 * k)), (0, 0, 0, 0))
    hd = ImageDraw.Draw(head)
    c = head.width / 2
    hd.ellipse((c - r, c - r, c + r, c + r), fill=(255, 255, 255), outline=INK, width=int(10 * k))
    look = 14 * p["look"] * k
    ex, ey = 24 * k, -8 * k
    for side in (-1, 1):
        x = c + side * ex + look
        if blink:
            hd.line((x - 11 * k, c + ey, x + 11 * k, c + ey), fill=INK, width=int(6 * k))
        elif p["face"] == "wow":
            hd.ellipse((x - 13 * k, c + ey - 17 * k, x + 13 * k, c + ey + 17 * k), fill=INK)
            hd.ellipse((x - 4 * k, c + ey - 11 * k, x + 4 * k, c + ey - 3 * k), fill="white")
        else:
            hd.ellipse((x - 10 * k, c + ey - 14 * k, x + 10 * k, c + ey + 14 * k), fill=INK)
            hd.ellipse((x - 2 * k, c + ey - 9 * k, x + 5 * k, c + ey - 2 * k), fill="white")
    # cheeks
    for side in (-1, 1):
        x = c + side * 46 * k + look * 0.6
        hd.ellipse((x - 13 * k, c + 14 * k, x + 13 * k, c + 28 * k), fill=(255, 150, 150))
    # mouth
    mx, my = c + look * 0.7, c + 30 * k
    if p["face"] == "wow" or mouth_open > 0.55:
        o = (0.6 + 0.6 * mouth_open) if p["face"] != "wow" else 1.2
        hd.ellipse((mx - 14 * k, my - 12 * k * o, mx + 14 * k, my + 14 * k * o), fill=(120, 30, 40), outline=INK, width=int(5 * k))
    elif mouth_open > 0.15 or p["face"] == "joy":
        hd.chord((mx - 26 * k, my - 18 * k, mx + 26 * k, my + 22 * k), 0, 180, fill=(120, 30, 40), outline=INK, width=int(5 * k))
    elif p["face"] == "think":
        hd.line((mx - 16 * k, my + 4 * k, mx + 14 * k, my - 2 * k), fill=INK, width=int(6 * k))
    else:
        hd.arc((mx - 24 * k, my - 20 * k, mx + 24 * k, my + 14 * k), 20, 160, fill=INK, width=int(6 * k))
    # the host's red cap, so he's recognisable in every video
    hd.chord((c - r * 0.98, c - r * 1.02, c + r * 0.98, c + r * 0.55), 180, 360, fill=CAP, outline=INK, width=int(8 * k))
    hd.rounded_rectangle((c + r * 0.2, c - r * 0.3, c + r * 1.45, c - r * 0.1), int(8 * k), fill=CAP_DARK, outline=INK, width=int(7 * k))
    hd.ellipse((c - 9 * k, c - r * 1.08, c + 9 * k, c - r * 0.9), fill=CAP_DARK)
    head = head.rotate(-tilt, resample=Image.BICUBIC, center=(c, c))
    img.alpha_composite(head, (int(hc[0] - c), int(hc[1] - c)))
    return img.reduce(k)


# ---------------------------------------------------------------- whole frames

def render_frame(scene: dict, prev_scene: dict | None, t_scene: float, t_total: float,
                 mouth_open: float, cache_dir: str) -> Image.Image:
    kind = scene["background"] if scene["background"] in BACKGROUNDS else "sky"
    frame = background(kind).convert("RGBA")
    _animate_background(frame, kind, t_total)

    _draw_props(frame, scene.get("emojis") or [], t_scene, cache_dir)
    _draw_headline(frame, scene.get("headline", ""), t_scene)

    p = pose(scene["pose"], t_total)
    if prev_scene is not None and t_scene < 0.3:
        p = blend(pose(prev_scene["pose"], t_total), p, _ease(t_scene / 0.3))
    blink = (t_total % 3.7) < 0.12
    man = draw_stickman(p, mouth_open, blink)
    frame.alpha_composite(man, (int(HOST_X - BOX_W / 2), int(GROUND + 30 - FOOT_Y)))
    return frame.convert("RGB")


VOWELS = set("aeiouyAEIOUY")


def mouth_track(alignment: dict, speed: float):
    """Returns f(t) → how open the mouth is (0-1) at time t, from which letter is being said."""
    chars = alignment["characters"]
    starts = [s / speed for s in alignment["character_start_times_seconds"]]
    ends = [e / speed for e in alignment["character_end_times_seconds"]]
    import bisect

    def f(t: float) -> float:
        i = bisect.bisect_right(starts, t) - 1
        if i < 0 or t > ends[i] + 0.05:
            return 0.0
        ch = chars[i]
        if ch in VOWELS:
            return 0.9
        if re.match(r"[A-Za-z]", ch):
            return 0.35
        return 0.0
    return f
