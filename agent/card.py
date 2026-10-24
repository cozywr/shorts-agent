"""Draws the Reddit-style post card shown while the title is read."""
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
WIDTH, PAD, RADIUS = 940, 48, 40


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(f"{FONT_DIR}/DejaVuSans{'-Bold' if bold else ''}.ttf", size)


def draw(title: str, channel: str, out: Path) -> Path:
    name_font, title_font, small_font = _font(40), _font(54), _font(34, bold=False)
    lines = textwrap.wrap(title, width=26)
    line_h = 70
    avatar = 96
    height = PAD + avatar + 36 + line_h * len(lines) + 30 + 40 + PAD

    img = Image.new("RGBA", (WIDTH, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, WIDTH - 1, height - 1), radius=RADIUS, fill=(255, 255, 255, 255))

    d.ellipse((PAD, PAD, PAD + avatar, PAD + avatar), fill=(255, 112, 32, 255))
    initial = channel[:1].upper()
    d.text((PAD + avatar / 2, PAD + avatar / 2), initial, font=_font(52), fill="white", anchor="mm")
    d.text((PAD + avatar + 24, PAD + avatar / 2), channel, font=name_font, fill=(20, 20, 20), anchor="lm")

    y = PAD + avatar + 36
    for line in lines:
        d.text((PAD, y), line, font=title_font, fill=(10, 10, 10))
        y += line_h
    d.text((PAD, y + 30), "♥ 99+      ↳ Reply      ↗ Share", font=small_font, fill=(120, 120, 120))
    img.save(out)
    return out
