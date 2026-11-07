"""The "cinematic" look: a black silhouette stickman and silhouette props in front of glowing,
layered skies, with depth (far layers fade into the light), slow camera push-ins, parallax drift,
cross-fades between scenes, film grain and a vignette.

Uses the same scene script and stickman poses as animation.py, so either look can be picked in config.yaml.
"""
import math
import os
import random
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from agent.animation import (BOX_H, BOX_W, FOOT_Y, HEAD_R, LOWER_ARM, NECK, SHAKY, SHIN, SPINE, THIGH,
                             UPPER_ARM, W, H, _ease, _lerp, _mix, _vec, blend, emoji_image, pose)

FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
GROUND = 1500
HOST_X = 330
SIL = (12, 11, 20)
PAD = 700          # extra width on each scenery layer, for the slow sideways drift

# sky top, sky middle, horizon, glow colour, light: (kind, x, y, radius)
LOOKS = {
    "sky":        ((30, 36, 88), (226, 112, 96), (255, 200, 128), (255, 190, 120), ("sun", 640, 1180, 150)),
    "desert":     ((52, 26, 74), (228, 92, 64), (255, 172, 92), (255, 150, 80), ("sun", 560, 1250, 190)),
    "forest":     ((34, 62, 84), (112, 162, 164), (214, 226, 206), (240, 240, 210), ("sun", 760, 980, 90)),
    "snow":       ((26, 44, 96), (112, 152, 206), (222, 232, 246), (230, 240, 255), ("sun", 700, 1150, 110)),
    "night":      ((6, 8, 26), (22, 30, 74), (64, 72, 132), (190, 200, 255), ("moon", 760, 520, 95)),
    "space":      ((4, 4, 12), (16, 12, 44), (64, 30, 96), (160, 120, 255), ("planet", 790, 610, 210)),
    "underwater": ((40, 150, 196), (22, 108, 152), (30, 92, 130), (150, 230, 255), ("rays", 540, -100, 0)),
    "city":       ((22, 22, 66), (196, 86, 108), (255, 168, 116), (255, 170, 120), ("sun", 520, 1240, 170)),
    "bedroom":    ((14, 18, 40), (26, 32, 64), (38, 44, 82), (190, 205, 255), ("window", 790, 760, 0)),
    "lab":        ((8, 26, 34), (16, 52, 62), (26, 74, 82), (120, 255, 230), ("screen", 540, 640, 0)),
}

# Scenery layers, far to near: (shape, how dark 0-1, height above ground, drift speed px/s)
LAYERS = {
    "sky":        [("hills", 0.45, 330, 2), ("hills", 0.72, 190, 5), ("hills", 1.0, 70, 9)],
    "desert":     [("dunes", 0.42, 300, 2), ("dunes", 0.7, 170, 5), ("dunes", 1.0, 60, 9)],
    "forest":     [("pines", 0.35, 520, 2), ("pines", 0.62, 380, 4), ("pines", 1.0, 240, 8)],
    "snow":       [("mountains", 0.4, 700, 1), ("mountains", 0.68, 420, 4), ("hills", 1.0, 70, 9)],
    "night":      [("mountains", 0.5, 420, 1), ("hills", 0.75, 200, 4), ("hills", 1.0, 70, 8)],
    "space":      [("craters", 1.0, 60, 6)],
    "underwater": [("rocks", 0.35, 260, 2), ("kelp", 0.55, 460, 4), ("rocks", 1.0, 40, 8)],
    "city":       [("skyline", 0.42, 760, 2), ("skyline", 0.7, 470, 4), ("street", 1.0, 30, 9)],
    "bedroom":    [("room", 1.0, 0, 0)],
    "lab":        [("desk", 1.0, 0, 0)],
}


def _font(size: int, weight: str = "ExtraBold") -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / f"Montserrat-{weight}.ttf"), size)


def _gradient3(top, mid, bottom, height=H, width=W) -> Image.Image:
    col = Image.new("RGB", (1, height))
    split = int(height * 0.62)
    for y in range(height):
        if y < split:
            c = _mix(top, mid, (y / split) ** 1.2)
        else:
            c = _mix(mid, bottom, (y - split) / (height - split))
        col.putpixel((0, y), c)
    return col.resize((width, height))


def _glow(radius: int, color, strength: float = 1.0) -> Image.Image:
    size = radius * 6
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, (r, a) in enumerate([(2.6, 40), (1.9, 70), (1.4, 110)]):
        rr = radius * r
        d.ellipse((size / 2 - rr, size / 2 - rr, size / 2 + rr, size / 2 + rr), fill=(*color, int(a * strength)))
    return img.filter(ImageFilter.GaussianBlur(radius * 0.7))


def _noise_line(rnd: random.Random, width: int, base: float, amp: float, waves: int = 4) -> list[float]:
    phases = [(rnd.uniform(0, 6.28), rnd.uniform(0.6, 1.8) * (k + 1)) for k in range(waves)]
    out = []
    for x in range(0, width + 20, 20):
        y = base
        for k, (ph, f) in enumerate(phases):
            y += amp / (k + 1) * math.sin(x / width * math.pi * 2 * f + ph)
        out.append(y)
    return out


def _layer(kind: str, shape: str, depth: float, height: int, seed: int) -> Image.Image:
    """One silhouette scenery layer, coloured to fade into the horizon light when far away."""
    top, mid, horizon, glow, _ = LOOKS[kind]
    color = _mix(horizon, SIL, depth) if depth < 1 else SIL
    w = W + PAD
    img = Image.new("RGBA", (w, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rnd = random.Random(f"{kind}{shape}{seed}")
    base = GROUND - height
    if shape in ("hills", "dunes", "street", "craters"):
        amp = {"hills": 60, "dunes": 90, "street": 0, "craters": 14}[shape]
        line = _noise_line(rnd, w, base, amp, 3 if shape == "dunes" else 4)
        d.polygon([(0, H)] + [(i * 20, y) for i, y in enumerate(line)] + [(w, H)], fill=color)
        if shape == "street":
            for x in range(0, w, 260):
                d.rectangle((x, base - 260, x + 10, base), fill=color)
                d.rectangle((x - 40, base - 268, x + 50, base - 252), fill=color)
    elif shape == "mountains":
        pts, x = [(0, H)], 0
        while x < w + 200:
            peak = base - rnd.randint(0, int(height * 0.6))
            pts += [(x, base + rnd.randint(0, 40)), (x + rnd.randint(120, 220), peak)]
            x += rnd.randint(260, 420)
        pts += [(w, base), (w, H)]
        d.polygon(pts, fill=color)
    elif shape == "pines":
        d.rectangle((0, GROUND - 60, w, H), fill=color)
        x = -40
        while x < w:
            th = height * rnd.uniform(0.55, 1.0)
            half = th * 0.2
            d.polygon([(x, GROUND - 40 - th), (x - half, GROUND - 30), (x + half, GROUND - 30)], fill=color)
            x += rnd.randint(50, 120)
    elif shape == "skyline":
        d.rectangle((0, GROUND - 20, w, H), fill=color)
        x = 0
        while x < w:
            bw, bh = rnd.randint(90, 200), int(height * rnd.uniform(0.35, 1.0))
            d.rectangle((x, GROUND - bh, x + bw, GROUND), fill=color)
            if rnd.random() < 0.3:
                d.rectangle((x + bw / 2 - 4, GROUND - bh - 70, x + bw / 2 + 4, GROUND - bh), fill=color)
            if depth < 0.6:  # a few lit windows on the far buildings
                for wy in range(GROUND - bh + 30, GROUND - 30, 46):
                    for wx in range(x + 14, x + bw - 20, 30):
                        if rnd.random() < 0.18:
                            d.rectangle((wx, wy, wx + 12, wy + 18), fill=_mix(glow, (255, 255, 255), 0.3))
            x += bw + rnd.randint(0, 14)
    elif shape == "rocks":
        line = _noise_line(rnd, w, base, 50, 5)
        d.polygon([(0, H)] + [(i * 20, y) for i, y in enumerate(line)] + [(w, H)], fill=color)
    elif shape == "kelp":
        for _ in range(18):
            x, hh, ph = rnd.randint(0, w), height * rnd.uniform(0.5, 1.0), rnd.uniform(0, 6)
            pts = [(x + 26 * math.sin(k / 3 + ph), GROUND - k * hh / 12) for k in range(13)]
            d.line(pts, fill=color, width=rnd.randint(12, 22), joint="curve")
    elif shape == "room":
        d.rectangle((0, GROUND, w, H), fill=SIL)
        # bed, nightstand, lamp
        d.rounded_rectangle((640, GROUND - 160, 1180, GROUND), 24, fill=SIL)
        d.rounded_rectangle((640, GROUND - 230, 700, GROUND - 120), 14, fill=SIL)
        d.rectangle((70, GROUND - 210, 220, GROUND), fill=SIL)
        d.polygon([(105, GROUND - 330), (185, GROUND - 330), (205, GROUND - 260), (85, GROUND - 260)], fill=SIL)
        d.rectangle((140, GROUND - 260, 150, GROUND - 210), fill=SIL)
    elif shape == "desk":
        d.rectangle((0, GROUND, w, H), fill=SIL)
        d.rectangle((560, GROUND - 260, 1120, GROUND - 230), fill=SIL)
        for x in (590, 1080):
            d.rectangle((x, GROUND - 230, x + 20, GROUND), fill=SIL)
        for x, hh in ((660, 120), (720, 170), (790, 90)):  # beakers
            d.rounded_rectangle((x, GROUND - 260 - hh, x + 44, GROUND - 260), 10, fill=SIL)
    return img


@lru_cache(maxsize=None)
def _sky(kind: str) -> Image.Image:
    top, mid, horizon, glow, light = LOOKS[kind]
    img = _gradient3(top, mid, horizon).convert("RGBA")
    rnd = random.Random(kind)
    lk, lx, ly, lr = light
    d = ImageDraw.Draw(img)
    if kind in ("night", "space"):
        for _ in range(160):
            x, y, r = rnd.randint(0, W), rnd.randint(0, GROUND - 200), rnd.choice([1, 1, 2, 2, 3])
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 240, rnd.randint(120, 255)))
    if kind == "space":
        neb = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        nd = ImageDraw.Draw(neb)
        for _ in range(6):
            x, y, r = rnd.randint(0, W), rnd.randint(200, 1100), rnd.randint(200, 380)
            nd.ellipse((x - r, y - r * 0.6, x + r, y + r * 0.6), fill=(*rnd.choice([(120, 60, 200), (60, 90, 220), (200, 70, 150)]), 50))
        img.alpha_composite(neb.filter(ImageFilter.GaussianBlur(90)))
    if lk in ("sun", "moon", "planet"):
        g = _glow(lr, glow, 1.0 if lk != "moon" else 0.7)
        img.alpha_composite(g, (int(lx - g.width / 2), int(ly - g.height / 2)))
        d = ImageDraw.Draw(img)
        if lk == "sun":
            d.ellipse((lx - lr, ly - lr, lx + lr, ly + lr), fill=_mix(glow, (255, 250, 230), 0.6))
        elif lk == "moon":
            d.ellipse((lx - lr, ly - lr, lx + lr, ly + lr), fill=(240, 240, 255))
            d.ellipse((lx - lr + 40, ly - lr - 10, lx + lr + 40, ly + lr - 10), fill=_mix(top, mid, 0.3))
        else:
            planet = Image.new("RGBA", (lr * 2, lr * 2), (0, 0, 0, 0))
            pd = ImageDraw.Draw(planet)
            pd.ellipse((0, 0, lr * 2, lr * 2), fill=(150, 110, 210))
            for i in range(5):   # soft bands
                y = lr * 2 * (0.2 + i * 0.15)
                pd.rectangle((0, y, lr * 2, y + lr * 0.12), fill=(120, 90, 190))
            shadow = Image.new("L", planet.size, 0)
            ImageDraw.Draw(shadow).ellipse((-lr * 0.55, lr * 0.35, lr * 1.6, lr * 2.6), fill=235)
            shadow = shadow.filter(ImageFilter.GaussianBlur(lr * 0.18))
            dark = Image.new("RGBA", planet.size, (20, 12, 36, 255))
            planet = Image.composite(dark, planet, shadow)
            mask = Image.new("L", planet.size, 0)
            ImageDraw.Draw(mask).ellipse((0, 0, lr * 2, lr * 2), fill=255)
            img.paste(planet, (lx - lr, ly - lr), mask)
    elif lk == "rays":
        rays = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        rd = ImageDraw.Draw(rays)
        for _ in range(7):
            x = rnd.randint(-200, W)
            rd.polygon([(x, 0), (x + 120, 0), (x + 420, 1500), (x + 220, 1500)], fill=(200, 245, 255, 40))
        img.alpha_composite(rays.filter(ImageFilter.GaussianBlur(30)))
    elif lk == "window":
        win = (lx - 190, ly - 260, lx + 190, ly + 230)
        light_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(light_img)
        ld.polygon([(win[0], win[3]), (win[2], win[3]), (win[2] - 160, GROUND + 300), (win[0] - 420, GROUND + 300)],
                   fill=(*glow, 45))
        img.alpha_composite(light_img.filter(ImageFilter.GaussianBlur(24)))
        d = ImageDraw.Draw(img)
        d.rectangle(win, fill=(70, 90, 160))
        d.ellipse((lx + 40, ly - 200, lx + 140, ly - 100), fill=(240, 240, 255))
        d.rectangle(win, outline=SIL, width=22)
        d.line((lx, win[1], lx, win[3]), fill=SIL, width=16)
        d.line((win[0], ly - 15, win[2], ly - 15), fill=SIL, width=16)
    elif lk == "screen":
        g = _glow(260, glow, 0.6)
        img.alpha_composite(g, (int(lx - g.width / 2), int(ly - g.height / 2)))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((lx - 360, ly - 220, lx + 360, ly + 200), 18, fill=(30, 90, 96), outline=SIL, width=16)
        for i in range(6):
            d.line((lx - 300, ly - 160 + i * 60, lx - 300 + rnd.randint(200, 600), ly - 160 + i * 60),
                   fill=(*glow, 160), width=10)
    return img


@lru_cache(maxsize=None)
def _layers(kind: str) -> list[tuple[Image.Image, float]]:
    return [(_layer(kind, shape, depth, height, i), speed) for i, (shape, depth, height, speed)
            in enumerate(LAYERS.get(kind, LAYERS["sky"]))]


@lru_cache(maxsize=None)
def _bloom(kind: str) -> Image.Image:
    """The bright parts of the sky, blurred wide: the light spills and glows like a camera lens."""
    sky = _sky(kind).convert("L").point(lambda v: max(0, v - 150) * 2)
    glow = sky.resize((W // 8, H // 8), Image.BILINEAR).filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BILINEAR)
    out = Image.new("RGBA", (W, H), tuple(_mix(LOOKS[kind][3], (255, 255, 255), 0.3)) + (0,))
    out.putalpha(glow)
    return out


PAINTED = Path(__file__).resolve().parent.parent / "assets" / "backgrounds"


@lru_cache(maxsize=None)
def _painted_list(kind: str) -> tuple[str, ...]:
    return tuple(sorted(str(p) for p in PAINTED.glob(f"{kind}-*.jpg")))


@lru_cache(maxsize=8)
def _painted(path: str) -> Image.Image:
    img = Image.open(path).convert("RGBA").resize((W + 80, H + 40), Image.LANCZOS)
    shade = Image.new("L", (1, 256))   # darken the bottom a little so captions and the ground read well
    for y in range(256):
        shade.putpixel((0, y), int(max(0, (y - 170) / 86) ** 1.5 * 150))
    dark = Image.new("RGBA", img.size, (8, 6, 14, 0))
    dark.putalpha(shade.resize(img.size, Image.BILINEAR))
    img.alpha_composite(dark)
    return img


def _scene_background(kind: str, t: float, variant: int = 0) -> Image.Image:
    painted = _painted_list(kind)
    if painted:   # a painted place from the library, drifting slowly sideways
        img = _painted(painted[variant % len(painted)])
        x = int(40 + 36 * math.sin(t * 0.12))
        frame = img.crop((x, 20, x + W, 20 + H))
        _particles(frame, kind, t)
        return frame
    frame = _sky(kind).copy()
    _particles(frame, kind, t)
    for img, speed in _layers(kind):
        x = -int((PAD / 2 + math.sin(t * 0.05) * 0 + t * speed) % PAD) if speed else 0
        frame.alpha_composite(img, (0, 0), (-x, 0, -x + W, H))
    # shallow depth of field: the scenery is slightly soft so the sharp stickman stands out
    frame = frame.resize((W // 2, H // 2), Image.BILINEAR).filter(ImageFilter.GaussianBlur(1.6)).resize((W, H), Image.BILINEAR)
    frame.alpha_composite(_bloom(kind))
    return frame


def _particles(frame: Image.Image, kind: str, t: float) -> None:
    d = ImageDraw.Draw(frame)
    rnd = random.Random(kind + "p")
    if kind in ("sky", "desert", "city", "forest", "bedroom", "lab"):   # dust floating in the light
        for i in range(26):
            x0, y0 = rnd.randint(0, W), rnd.randint(300, GROUND)
            x = (x0 + t * rnd.uniform(4, 14)) % W
            y = y0 + 20 * math.sin(t * 0.6 + i)
            a = int(60 + 50 * math.sin(t * 1.3 + i))
            d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 245, 220, max(0, a)))
    elif kind in ("night", "space"):
        for i in range(30):
            x, y = rnd.randint(0, W), rnd.randint(0, GROUND - 300)
            a = int(140 + 110 * math.sin(t * rnd.uniform(1, 3) + i))
            d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 255, 255, max(0, a)))
    elif kind == "snow":
        for i in range(70):
            x0, sp, r = rnd.randint(0, W), rnd.randint(40, 110), rnd.uniform(2, 6)
            y = (rnd.randint(0, H) + t * sp) % H
            x = x0 + 18 * math.sin(t + i)
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 200))
    elif kind == "underwater":
        for i in range(24):
            x0, sp, r = rnd.randint(0, W), rnd.randint(40, 110), rnd.randint(4, 12)
            y = GROUND - ((rnd.randint(0, 1500) + t * sp) % 1500)
            x = x0 + 12 * math.sin(t * 2 + i)
            d.ellipse((x - r, y - r, x + r, y + r), outline=(200, 240, 255, 150), width=3)


# ---------------------------------------------------------------- silhouettes

SS = 2
CAP = (214, 58, 48)
# what he wears; config.yaml video.outfit overrides any of these
OUTFIT = {"hat": "cap", "hat_color": CAP, "top": "none", "top_color": (60, 110, 200), "pants_color": None,
          "scarf": None, "glasses": False}
EYE = (246, 244, 236)


def _face(d, hc, r, face, k, skin=SIL):
    """Simple eyes and mouth, looking the way he faces, so you can read how he feels.
    White on a dark face; dark with a white sparkle on a light face."""
    ex = [hc[0] + r * 0.12, hc[0] + r * 0.56]
    ey = hc[1] + r * 0.05
    w = 4 * k
    light = sum(skin) / 3 > 110
    EYE, PUPIL = ((40, 32, 44), (255, 255, 255)) if light else (globals()["EYE"], SIL)
    if face == "dizzy":
        for x in ex:
            e = r * 0.13
            d.line((x - e, ey - e, x + e, ey + e), fill=EYE, width=w)
            d.line((x - e, ey + e, x + e, ey - e), fill=EYE, width=w)
    elif face in ("joy", "laugh"):
        for x in ex:
            e = r * 0.15
            d.arc((x - e, ey - e * 0.6, x + e, ey + e * 1.2), 200, 340, fill=EYE, width=w)
    elif face == "think":
        for x in ex:
            d.line((x - r * 0.13, ey, x + r * 0.13, ey), fill=EYE, width=w)
        d.line((ex[1] - r * 0.16, ey - r * 0.3, ex[1] + r * 0.16, ey - r * 0.38), fill=EYE, width=w)  # raised brow
    else:
        big = 1.35 if face == "wow" else 1.0
        for x in ex:
            e = r * 0.13 * big
            d.ellipse((x - e * 0.8, ey - e, x + e * 0.8, ey + e), fill=EYE)
            pe = e * (0.32 if light else 0.45)
            px, py = (x + e * 0.2, ey - e * 0.35) if light else (x + e * 0.25, ey + pe * 0.4)
            d.ellipse((px - pe, py - pe, px + pe, py + pe), fill=PUPIL)
    mx, my = hc[0] + r * 0.38, hc[1] + r * 0.5
    if face == "wow":
        m = r * 0.12
        d.ellipse((mx - m * 0.8, my - m, mx + m * 0.8, my + m), outline=EYE, width=w)
    elif face == "laugh":
        m = r * 0.2
        d.chord((mx - m, my - m, mx + m, my + m), 0, 180, fill=EYE)
    elif face in ("happy", "joy"):
        m = r * 0.17
        d.arc((mx - m, my - m * 1.2, mx + m, my + m * 0.6), 20, 160, fill=EYE, width=w)
    elif face == "think":
        d.line((mx - r * 0.1, my, mx + r * 0.12, my - r * 0.04), fill=EYE, width=w)


def _limb(d, start, upper, lower, l1, l2, width, upper_fill=SIL, lower_fill=SIL):
    x1, y1 = start[0] + _vec(upper, l1)[0], start[1] + _vec(upper, l1)[1]
    x2, y2 = x1 + _vec(upper + lower, l2)[0], y1 + _vec(upper + lower, l2)[1]
    d.line((start, (x1, y1)), fill=upper_fill, width=width)
    d.line(((x1, y1), (x2, y2)), fill=lower_fill, width=width)
    for (x, y), f in ((start, upper_fill), ((x2, y2), lower_fill), ((x1, y1), upper_fill)):
        d.ellipse((x - width / 2, y - width / 2, x + width / 2, y + width / 2), fill=f)


def draw_silhouette(p: dict) -> Image.Image:
    k = SS
    img = Image.new("RGBA", (BOX_W * k, BOX_H * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lw = 30 * k

    def leg_drop(leg):
        return _vec(leg[0], THIGH)[1] + _vec(leg[0] + leg[1], SHIN)[1]
    drop = max(leg_drop(p["ll"]), leg_drop(p["rl"]))
    hip = (BOX_W / 2 * k, (FOOT_Y - drop - p["lift"]) * k)
    lean = p["lean"]
    neck = (hip[0] + _vec(180 - lean, SPINE)[0] * k, hip[1] + _vec(180 - lean, SPINE)[1] * k)
    shoulder = (hip[0] + _vec(180 - lean, SPINE - 20)[0] * k, hip[1] + _vec(180 - lean, SPINE - 20)[1] * k)
    o = OUTFIT
    top, tc = o.get("top", "none"), tuple(o.get("top_color", (60, 110, 200)))
    pants = tuple(o["pants_color"]) if o.get("pants_color") else SIL
    for leg in ("ll", "rl"):
        _limb(d, hip, p[leg][0], p[leg][1], THIGH * k, SHIN * k, lw, pants, pants)
        if o.get("boots"):   # chunky boots on the lower third of each shin
            kx = hip[0] + _vec(p[leg][0], THIGH * k)[0]
            ky = hip[1] + _vec(p[leg][0], THIGH * k)[1]
            ang = p[leg][0] + p[leg][1]
            a1 = (kx + _vec(ang, SHIN * k * 0.6)[0], ky + _vec(ang, SHIN * k * 0.6)[1])
            a2 = (kx + _vec(ang, SHIN * k * 1.02)[0], ky + _vec(ang, SHIN * k * 1.02)[1])
            boot = tuple(o["boots"])
            d.line((a1, a2), fill=boot, width=int(lw * 1.45))
            d.ellipse((a2[0] - lw * 0.7, a2[1] - lw * 0.55, a2[0] + lw * 1.1, a2[1] + lw * 0.55), fill=boot)
    d.line((hip, neck), fill=SIL, width=lw)
    tilt = p["tilt"]
    hc = (neck[0] + _vec(180 - lean + tilt, NECK + HEAD_R)[0] * k, neck[1] + _vec(180 - lean + tilt, NECK + HEAD_R)[1] * k)
    r = HEAD_R * k
    if top == "hoodie":   # the hood, bunched up behind his neck
        d.ellipse((hc[0] - r * 1.15, hc[1] + r * 0.35, hc[0] + r * 0.55, hc[1] + r * 1.25), fill=_mix(tc, (0, 0, 0), 0.3))
    if top != "none":
        waist = (hip[0] + _vec(180 - lean, 18)[0] * k, hip[1] + _vec(180 - lean, 18)[1] * k)
        d.line((waist, shoulder), fill=tc, width=int(lw * 1.9))
        for pt in (waist, shoulder):
            d.ellipse((pt[0] - lw * 0.95, pt[1] - lw * 0.95, pt[0] + lw * 0.95, pt[1] + lw * 0.95), fill=tc)
        if top == "jacket":   # open front showing the shirt underneath
            inner = tuple(o.get("shirt_color") or _mix(tc, (0, 0, 0), 0.55))
            d.line((waist, shoulder), fill=inner, width=int(lw * 0.7))
    if o.get("belt"):
        bx, byy = hip[0] + _vec(180 - lean, 22)[0] * k, hip[1] + _vec(180 - lean, 22)[1] * k
        d.rectangle((bx - lw * 1.0, byy - lw * 0.3, bx + lw * 1.0, byy + lw * 0.3), fill=(24, 22, 28))
        d.rectangle((bx - lw * 0.35, byy - lw * 0.38, bx + lw * 0.35, byy + lw * 0.38), outline=(214, 218, 228), width=3 * k)
    sleeve = tc if top != "none" else SIL
    lower_sleeve = tc if top in ("hoodie", "jacket") else SIL
    for arm in ("la", "ra"):
        _limb(d, shoulder, p[arm][0], p[arm][1], UPPER_ARM * k, LOWER_ARM * k, lw, sleeve, lower_sleeve)
    d.line((neck, hc), fill=SIL, width=lw)
    if o.get("necklace"):
        silver = (214, 218, 228)
        d.arc((neck[0] - r * 0.45, neck[1] - r * 0.3, neck[0] + r * 0.45, neck[1] + r * 0.75), 20, 160, fill=silver, width=3 * k)
        cx, cy = neck[0] + r * 0.02, neck[1] + r * 0.75
        d.line((cx, cy - r * 0.02, cx, cy + r * 0.42), fill=silver, width=4 * k)
        d.line((cx - r * 0.1, cy + r * 0.08, cx + r * 0.1, cy + r * 0.08), fill=silver, width=4 * k)
    if o.get("fur"):
        fc = tuple(o["fur"])
        rnd = random.Random(3)
        for i in range(34):   # a fluffy collar of little tufts all around the neck and shoulders
            a = 2 * math.pi * i / 34
            rr = r * (0.7 + rnd.uniform(0, 0.2))
            x, y = neck[0] + rr * math.cos(a) * 1.1, neck[1] + rr * math.sin(a) * 0.38 + r * 0.25
            e = r * rnd.uniform(0.2, 0.3)
            d.ellipse((x - e, y - e, x + e, y + e), fill=_mix(fc, (255, 255, 255), rnd.uniform(0, 0.12)))
    if o.get("scarf"):
        sc = tuple(o["scarf"])
        d.line((neck[0] - r * 0.1, neck[1] - r * 0.1, neck[0] - r * 0.75, neck[1] + r * 0.9), fill=sc, width=int(lw * 0.9))
        d.ellipse((neck[0] - r * 0.6, neck[1] - r * 0.45, neck[0] + r * 0.6, neck[1] + r * 0.15), fill=sc)
    skin = tuple(o.get("skin") or SIL)
    d.ellipse((hc[0] - r, hc[1] - r, hc[0] + r, hc[1] + r), fill=skin)
    hat, hcol = o.get("hat", "cap"), tuple(o.get("hat_color", CAP))
    if hat == "cap":      # crown over the top of the head and a brim pointing the way he faces
        d.chord((hc[0] - r * 1.02, hc[1] - r * 1.04, hc[0] + r * 1.02, hc[1] + r * 0.9), 192, 348, fill=hcol)
        by = hc[1] - r * 0.42
        d.polygon([(hc[0] + r * 0.3, by - r * 0.1), (hc[0] + r * 1.45, by + r * 0.04), (hc[0] + r * 1.4, by + r * 0.2),
                   (hc[0] + r * 0.3, by + r * 0.16)], fill=_mix(hcol, (0, 0, 0), 0.25))
    elif hat == "beanie":
        d.chord((hc[0] - r * 1.05, hc[1] - r * 1.25, hc[0] + r * 1.05, hc[1] + r * 0.75), 180, 360, fill=hcol)
        d.rounded_rectangle((hc[0] - r * 1.08, hc[1] - r * 0.42, hc[0] + r * 1.08, hc[1] - r * 0.12), r * 0.12,
                            fill=_mix(hcol, (0, 0, 0), 0.2))
        d.ellipse((hc[0] - r * 0.2, hc[1] - r * 1.45, hc[0] + r * 0.2, hc[1] - r * 1.05), fill=hcol)
    elif hat == "headphones":
        d.arc((hc[0] - r * 1.12, hc[1] - r * 1.2, hc[0] + r * 1.12, hc[1] + r * 1.0), 190, 350, fill=(40, 40, 52), width=int(r * 0.2))
        d.rounded_rectangle((hc[0] - r * 0.6, hc[1] - r * 0.25, hc[0] - r * 0.15, hc[1] + r * 0.45), r * 0.15, fill=hcol)
    elif hat == "hair":   # long shaggy hair; the bangs are drawn after the face so they cover one eye
        pts = [(0.95, -0.35), (0.6, -1.18), (-0.2, -1.3), (-0.95, -0.98), (-1.28, -0.3), (-1.25, 0.95), (-1.02, 0.55),
               (-0.92, 1.15), (-0.68, 0.62), (-0.5, 1.02), (-0.32, 0.45), (-0.12, -0.38), (0.4, -0.58)]
        d.polygon([(hc[0] + r * x, hc[1] + r * y) for x, y in pts], fill=hcol)
    if o.get("glasses"):
        for x in (hc[0] + r * 0.12, hc[0] + r * 0.56):
            e = r * 0.24
            d.ellipse((x - e, hc[1] + r * 0.05 - e, x + e, hc[1] + r * 0.05 + e), outline=EYE, width=4 * k)
        d.line((hc[0] + r * 0.36, hc[1], hc[0] + r * 0.32, hc[1]), fill=EYE, width=4 * k)
    _face(d, hc, r, p.get("face", "happy"), k, skin)
    if hat == "hair":
        bangs = [(-0.15, -0.95), (0.7, -1.0), (1.18, -0.55), (1.08, 0.12), (0.9, -0.08), (0.78, 0.38), (0.6, 0.02),
                 (0.42, 0.34), (0.3, -0.12), (0.05, 0.02)]
        d.polygon([(hc[0] + r * x, hc[1] + r * y) for x, y in bangs], fill=hcol)
        shine = _mix(hcol, (255, 255, 255), 0.22)
        for x1, y1, x2, y2 in ((0.0, -0.95, 0.75, -0.3), (-0.6, -0.95, -1.0, 0.4), (0.35, -0.98, 0.95, -0.55)):
            d.line((hc[0] + r * x1, hc[1] + r * y1, hc[0] + r * x2, hc[1] + r * y2), fill=shine, width=3 * k)
    return img.reduce(k)


@lru_cache(maxsize=256)
def _prop_silhouette(emoji: str, size: int, cache_dir: str, kind: str = "sky") -> Image.Image | None:
    """The picture, colour-graded into the scene: darkened and tinted towards the shadows,
    lit from behind with a rim of the scene's light, and a soft glow so it reads against the sky."""
    img = emoji_image(emoji, cache_dir) or emoji_image("⭐", cache_dir)
    if img is None:
        return None
    scale = size / max(img.size)
    img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
    top, mid, horizon, glow, _ = LOOKS.get(kind, LOOKS["sky"])
    pad = 40
    alpha = img.getchannel("A")
    shade = Image.new("RGB", img.size, _mix(SIL, mid, 0.35))
    graded = Image.blend(img.convert("RGB"), shade, 0.42)
    canvas = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    halo = Image.new("RGBA", canvas.size, (*glow, 0))
    big_alpha = Image.new("L", canvas.size, 0)
    big_alpha.paste(alpha, (pad, pad))
    halo.putalpha(big_alpha.filter(ImageFilter.GaussianBlur(18)).point(lambda v: int(v * 0.55)))
    canvas.alpha_composite(halo)
    rim = Image.new("RGBA", canvas.size, (*_mix(glow, (255, 255, 255), 0.4), 0))
    rim_alpha = ImageChops.subtract(big_alpha, ImageChops.offset(big_alpha, 5, 6)).filter(ImageFilter.GaussianBlur(1.5))
    rim.putalpha(rim_alpha)
    body = graded.convert("RGBA")
    body.putalpha(alpha)
    canvas.alpha_composite(body, (pad, pad))
    canvas.alpha_composite(rim)
    return canvas


def _prop_layout(n: int):
    cx, cy = 760, 1010
    if n == 1:
        return [(cx, cy, 460)]
    if n == 2:
        return [(cx, cy - 190, 300), (cx, cy + 170, 300)]
    if n == 3:
        return [(cx, cy - 200, 270), (cx - 150, cy + 130, 270), (cx + 150, cy + 130, 270)]
    return [(cx - 140, cy - 160, 240), (cx + 140, cy - 160, 240), (cx - 140, cy + 160, 240), (cx + 140, cy + 160, 240)]


def _draw_props(frame, emojis, t, cache_dir, kind="sky"):
    emojis = emojis[:4]
    for i, (e, (x, y, size)) in enumerate(zip(emojis, _prop_layout(len(emojis)))):
        x01 = (t - 0.2 - i * 0.15) / 0.4
        if x01 <= 0:
            continue
        k = min(1.0, x01 * 2.5)                      # opacity
        img = _prop_silhouette(e, size, cache_dir, kind)
        if img is None:
            continue
        s = 0.4 + 0.6 * _out_back(x01)
        sprite = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.BILINEAR) if abs(s - 1) > 0.001 else img
        if k < 1:
            sprite = sprite.copy()
            sprite.putalpha(sprite.getchannel("A").point(lambda v, k=k: int(v * k)))
        bob = 10 * math.sin(t * 1.6 + i)
        frame.alpha_composite(sprite, (int(x - sprite.width / 2), int(y + bob - sprite.height / 2)))


# ---------------------------------------------------------------- text

@lru_cache(maxsize=64)
def _title_sprite(text: str) -> Image.Image:
    """Warm golden headline with a dark outline and a soft glow, like a movie title."""
    text = text.upper().strip()
    size = 112
    font = _font(size)
    while font.getlength(text) > 940 and size > 60:
        size -= 6
        font = _font(size)
    lines = [text]
    if font.getlength(text) > 940:
        words = text.split()
        half = len(words) // 2
        lines = [" ".join(words[:half]), " ".join(words[half:])]
    lh = int(size * 1.12)
    h = lh * len(lines) + 120
    mask = Image.new("L", (W, h), 0)
    stroke = Image.new("L", (W, h), 0)
    md, sd = ImageDraw.Draw(mask), ImageDraw.Draw(stroke)
    for i, line in enumerate(lines):
        y = 60 + lh * i + lh / 2
        md.text((W / 2, y), line, font=font, fill=255, anchor="mm")
        sd.text((W / 2, y), line, font=font, fill=255, anchor="mm", stroke_width=max(4, size // 16))
    grad = _gradient3((255, 247, 222), (255, 222, 150), (255, 172, 70), height=h, width=W).convert("RGBA")
    out = Image.new("RGBA", (W, h), (255, 150, 60, 0))
    out.putalpha(stroke.filter(ImageFilter.GaussianBlur(22)).point(lambda v: v * 150 // 255))   # glow
    edge = Image.new("RGBA", (W, h), (58, 28, 20, 0))
    edge.putalpha(stroke)
    out.alpha_composite(edge)
    grad.putalpha(mask)
    out.alpha_composite(grad)
    return out


@lru_cache(maxsize=1)
def _clock_face() -> Image.Image:
    r, k = 54, 3
    img = Image.new("RGBA", (r * 2 * k + 8 * k, r * 2 * k + 8 * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = img.width / 2
    d.ellipse((c - r * k, c - r * k, c + r * k, c + r * k), fill=(20, 18, 30, 200), outline=(240, 236, 226), width=5 * k)
    for i in range(12):
        a = math.radians(i * 30)
        r1, r2 = r * k * (0.72 if i % 3 else 0.62), r * k * 0.84
        d.line((c + r1 * math.sin(a), c - r1 * math.cos(a), c + r2 * math.sin(a), c - r2 * math.cos(a)),
               fill=(240, 236, 226), width=3 * k)
    return img.reduce(k)


def _draw_clock(frame, t):
    """A small ticking clock above time markers like DAY 3 or HOUR 17."""
    k = _out_back(min(1.0, t / 0.35))
    if k <= 0:
        return
    face = _clock_face().copy()
    d = ImageDraw.Draw(face)
    c = face.width / 2
    a = math.radians(t * 240)
    d.line((c, c, c + 40 * math.sin(a), c - 40 * math.cos(a)), fill=(255, 196, 90), width=5)
    d.line((c, c, c + 26 * math.sin(a / 12), c - 26 * math.cos(a / 12)), fill=(240, 236, 226), width=6)
    d.ellipse((c - 6, c - 6, c + 6, c + 6), fill=(255, 196, 90))
    if k < 0.999:
        face = face.resize((max(1, int(face.width * k)), max(1, int(face.height * k))), Image.BILINEAR)
    frame.alpha_composite(face, (int(W / 2 - face.width / 2), int(165 - face.height / 2)))


STAT_RE = re.compile(r"^([^\d\-+]*)([\-+]?)([\d,]*\.?\d+)(.*)$")


@lru_cache(maxsize=256)
def _stat_text_sprite(text: str, size: int) -> Image.Image:
    font = _font(size)
    tw = int(font.getlength(text)) + 40
    h = int(size * 1.4)
    mask = Image.new("L", (tw, h), 0)
    ImageDraw.Draw(mask).text((tw / 2, h / 2), text, font=font, fill=255, anchor="mm")
    grad = _gradient3((255, 250, 232), (255, 224, 150), (255, 176, 74), height=h, width=tw).convert("RGBA")
    grad.putalpha(mask)
    return grad


@lru_cache(maxsize=32)
def _stat_card(w: int, h: int) -> Image.Image:
    k = 2
    card = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 0, w * k - 1, h * k - 1), 34 * k, fill=(14, 12, 24, 190), outline=(255, 214, 140, 120), width=3 * k)
    return card.reduce(k)


def _draw_stat(frame, stat, t):
    """The scene's key number, huge, counting up from zero like a stopwatch."""
    stat = stat.strip().upper()
    if not stat or t < 0.25:
        return
    t -= 0.25
    m = STAT_RE.match(stat)
    k = _out_cubic(min(1.0, t / 1.1))
    unit = ""
    if m:
        pre, sign, num, unit = m.groups()
        decimals = len(num.split(".")[1]) if "." in num else 0
        value = float(num.replace(",", "")) * k
        shown = f"{value:,.{decimals}f}" if "," in num else f"{value:.{decimals}f}"
        big, big_final = f"{pre}{sign}{shown}", f"{pre}{sign}{num}"
    else:
        big = big_final = stat
    # short units (S, %, °C, M) stay full size; words (DAYS, STEPS) sit smaller beside the number
    word = len(unit.strip()) > 2
    size = 150
    def width(sz):
        return _font(sz).getlength(big_final + ("" if word else unit)) + (_font(int(sz * 0.42)).getlength(unit) + 20 if word else 0)
    while width(size) > 780 and size > 70:
        size -= 8
    num_spr = _stat_text_sprite(big + ("" if word else unit), size)
    unit_spr = _stat_text_sprite(unit.strip(), int(size * 0.42)) if word else None
    final_w = int(width(size))
    w, h = max(320, final_w + 110), int(size * 1.5)
    pop = _out_back(min(1.0, t / 0.35))
    card = _stat_card(w, h)
    glow = Image.new("RGBA", (w + 120, h + 120), (255, 160, 70, 0))
    gm = Image.new("L", glow.size, 0)
    ImageDraw.Draw(gm).rounded_rectangle((60, 60, 60 + w, 60 + h), 34, fill=int(110 * min(1.0, t / 0.3)))
    glow.putalpha(gm.filter(ImageFilter.GaussianBlur(26)))
    layer = Image.new("RGBA", glow.size, (0, 0, 0, 0))
    layer.alpha_composite(glow)
    layer.alpha_composite(card, (60, 60))
    x0 = 60 + (w - final_w) / 2 - 20
    layer.alpha_composite(num_spr, (int(x0), int(60 + h / 2 - num_spr.height / 2 - 6)))
    if unit_spr is not None:
        ux = x0 + _font(size).getlength(big_final) + 30
        layer.alpha_composite(unit_spr, (int(ux), int(60 + h / 2 - unit_spr.height / 2 + size * 0.18)))
    bar = int((w - 80) * k)   # a thin bar fills as it counts
    ImageDraw.Draw(layer).rounded_rectangle((100, 60 + h - 22, 100 + max(6, bar), 60 + h - 14), 4, fill=(255, 196, 90, 230))
    if pop < 0.999:
        layer = layer.resize((max(1, int(layer.width * pop)), max(1, int(layer.height * pop))), Image.BILINEAR)
    cx, cy = W / 2, 515
    frame.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))


TIME_WORDS = ("SECOND", "MINUTE", "HOUR", "DAY", "WEEK", "MONTH", "YEAR")


def _draw_title(frame, text, t):
    """The headline slams in: starts big, snaps down to size with a little overshoot."""
    if not text.strip() or t <= 0:
        return
    img = _title_sprite(text)
    k = min(1.0, t / 0.3)
    if k < 1:
        scale = 1.35 - 0.35 * _out_back(k)
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.BILINEAR)
        a = min(1.0, t / 0.12)
        img.putalpha(img.getchannel("A").point(lambda v: int(v * a)))
    frame.alpha_composite(img, (int((W - img.width) / 2), int(300 - img.height / 2)))
    if any(w in text.upper() for w in TIME_WORDS):
        _draw_clock(frame, t)


@lru_cache(maxsize=64)
def _pill_sprite(text: str) -> Image.Image:
    font = _font(54)
    tw = font.getlength(text.upper())
    w, h = int(tw + 70), 96
    img = Image.new("RGBA", (w, h + 26), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w, h), 48, fill=(255, 255, 255, 240))
    d.polygon([(w * 0.28, h - 2), (w * 0.42, h - 2), (w * 0.26, h + 24)], fill=(255, 255, 255, 240))
    d.text((w / 2, h / 2 + 2), text.upper(), font=font, fill=SIL, anchor="mm")
    return img


def _draw_pill(frame, text, t, x, base=690):
    if not text.strip() or t < 0.25 or t > 2.4:
        return
    k = min(_ease((t - 0.25) / 0.2), _ease((2.4 - t) / 0.25))
    img = _pill_sprite(text)
    if k < 1:
        img = img.copy()
        img.putalpha(img.getchannel("A").point(lambda v: int(v * k)))
    cx = max(img.width / 2 + 20, min(W - img.width / 2 - 20, x + 60))
    frame.alpha_composite(img, (int(cx - img.width / 2), int(base - img.height + (1 - k) * 15)))


# ---------------------------------------------------------------- finishing

@lru_cache(maxsize=1)
def _vignette() -> Image.Image:
    small = Image.new("L", (108, 192), 0)
    d = ImageDraw.Draw(small)
    for i in range(40):
        a = int(150 * (1 - i / 40) ** 2)
        d.rectangle((i, i * 1.6, 107 - i, 191 - i * 1.6), outline=a)
    mask = small.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(40))
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.putalpha(mask)
    return out


@lru_cache(maxsize=6)
def _grain(i: int) -> Image.Image:
    small = Image.frombytes("L", (540, 960), os.urandom(540 * 960)).resize((W, H), Image.NEAREST)
    out = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    out.putalpha(small.point(lambda v: v // 14))
    return out


def _camera(frame: Image.Image, zoom: float, dx: float, dy: float) -> Image.Image:
    a = 1 / zoom
    cx, cy = W / 2, H / 2
    return frame.transform((W, H), Image.AFFINE, (a, 0, cx - a * cx + dx, 0, a, cy - a * cy + dy),
                           resample=Image.BILINEAR)


def _rotate(man: Image.Image, angle: float, spin: bool, lift: float):
    pad = 420
    big = Image.new("RGBA", (man.width + pad * 2, man.height + pad), (0, 0, 0, 0))
    big.paste(man, (pad, pad))
    center = (pad + BOX_W / 2, pad + (FOOT_Y - 330 - lift if spin else FOOT_Y))
    return big.rotate(angle, resample=Image.BICUBIC, center=center), -pad, -pad


_last: dict[int, Image.Image] = {}
def _rim_lit(man: Image.Image, color) -> Image.Image:
    """Edge light from the scene's light (upper right), like a sunset catching his outline,
    plus a faint halo so he never disappears into a dark sky."""
    a = man.getchannel("A")
    shifted = ImageChops.offset(a, -6, 5)
    rim = ImageChops.subtract(a, shifted).filter(ImageFilter.GaussianBlur(1.2))
    small = a.resize((a.width // 4, a.height // 4), Image.BILINEAR).filter(ImageFilter.MaxFilter(5))
    halo = small.filter(ImageFilter.GaussianBlur(4)).resize(a.size, Image.BILINEAR).point(lambda v: v * 90 // 255)
    out = Image.new("RGBA", man.size, tuple(color) + (0,))
    out.putalpha(halo)
    out.alpha_composite(man)
    lit = Image.new("RGBA", man.size, tuple(_mix(color, (255, 255, 255), 0.35)) + (0,))
    lit.putalpha(rim.point(lambda v: min(255, v * 2)))
    out.alpha_composite(lit)
    return out


BLEND = 0.45   # seconds the stickman takes to move from one pose into the next


def _smooth(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _out_cubic(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def _out_back(x: float) -> float:
    """Overshoots a little and settles: things pop in instead of fading in."""
    x = max(0.0, min(1.0, x))
    c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def render_frame(scene: dict, prev_scene: dict | None, t_scene: float, t_total: float,
                 mouth_open: float, cache_dir: str) -> Image.Image:
    kind = scene["background"] if scene["background"] in LOOKS else "sky"
    variant = sum(map(ord, scene.get("headline", "") + scene.get("narration", "")[:40]))
    frame = _scene_background(kind, t_total, variant)
    _draw_props(frame, scene.get("emojis") or [], t_scene, cache_dir, kind)

    p = pose(scene["pose"], t_total, t_scene)
    if prev_scene is not None and t_scene < BLEND:
        p = blend(pose(prev_scene["pose"], t_total, t_scene + 99), p, _smooth(t_scene / BLEND))
    man = draw_silhouette(p)
    if p.get("flip"):
        man = man.transpose(Image.FLIP_LEFT_RIGHT)
    man = _rim_lit(man, LOOKS[kind][3])
    x0, y0 = int(HOST_X - BOX_W / 2 + p["dx"]), int(GROUND + 8 - FOOT_Y)
    if p["rot"] % 360:
        man, ox, oy = _rotate(man, p["rot"], scene["pose"] == "spin", p["lift"])
        x0, y0 = x0 + ox, y0 + oy
    frame.alpha_composite(man, (max(0, x0), max(0, y0)), (max(0, -x0), max(0, -y0)))

    # camera: a slow eased push-in with a gentle drift, a punch-in at each cut, a bigger one to open
    # the video (the hook), and a short smooth jolt on big moments
    zoom = 1.0 + 0.05 * _smooth(min(1.0, t_scene / 7))
    if prev_scene is None:
        zoom += 0.28 * (1 - _out_cubic(min(1.0, t_scene / 0.8)))
    else:
        zoom += 0.06 * (1 - _out_cubic(min(1.0, t_scene / 0.45)))
    drift = 18 * math.sin(t_total * 0.35)
    shake = 0.0
    if scene["pose"] in SHAKY:
        when = 0.75 if scene["pose"] == "faint" else 0.0
        shake = 9 * max(0.0, 1 - abs(t_scene - when - 0.2) / 0.3) ** 2
    frame = _camera(frame, zoom, drift + shake * math.sin(t_total * 31), shake * math.cos(t_total * 23))

    # text sits on top of the camera move so it stays steady and sharp
    _draw_title(frame, scene.get("headline", ""), t_scene)
    _draw_stat(frame, scene.get("stat", ""), t_scene)
    _draw_pill(frame, scene.get("shout", ""), t_scene, HOST_X + p["dx"], 790 if scene.get("stat") else 690)
    frame.alpha_composite(_vignette())
    frame.alpha_composite(_grain(int(t_total * 24) % 6))
    out = frame.convert("RGB")

    # soft cross-fade from the last frame of the previous scene
    if prev_scene is not None and t_scene < 0.35 and id(prev_scene) in _last:
        out = Image.blend(_last[id(prev_scene)], out, _ease(t_scene / 0.35))
    else:
        _last[id(scene)] = out
    return out
