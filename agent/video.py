"""Puts the narration over a random slice of gameplay, cropped to 1080x1920, with big word-by-word captions."""
import json
import random
import subprocess
from pathlib import Path

FPS = 30
MAX_SPEEDUP = 1.25   # a story that runs long is read up to 25% faster before anything gets cut
CHUNK_WORDS = 3      # captions show up to this many words at a time
CHUNK_CHARS = 16


def _run(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def _probe(path: Path) -> dict:
    return json.loads(_run("ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                           "-of", "json", str(path)))


def duration(path: Path) -> float:
    return float(_probe(path)["format"]["duration"])


def words(alignment: dict, start_char: int = 0) -> list[dict]:
    """Groups ElevenLabs' per-character timings into words, skipping characters before `start_char`."""
    chars = alignment["characters"]
    starts, ends = alignment["character_start_times_seconds"], alignment["character_end_times_seconds"]
    out, current = [], None
    for i in range(start_char, len(chars)):
        if chars[i].isspace():
            current = None
            continue
        if current is None:
            current = {"text": "", "start": starts[i]}
            out.append(current)
        current["text"] += chars[i]
        current["end"] = ends[i]
    return out


def _chunks(story_words: list[dict]) -> list[dict]:
    chunks, current = [], []
    for w in story_words:
        current.append(w)
        text = " ".join(x["text"] for x in current)
        if len(current) >= CHUNK_WORDS or len(text) >= CHUNK_CHARS or w["text"][-1] in ".,!?;:":
            chunks.append({"text": text, "start": current[0]["start"], "end": current[-1]["end"]})
            current = []
    if current:
        chunks.append({"text": " ".join(x["text"] for x in current),
                       "start": current[0]["start"], "end": current[-1]["end"]})
    # Hold each chunk until the next one starts, unless the narrator pauses.
    for a, b in zip(chunks, chunks[1:]):
        if b["start"] - a["end"] < 0.4:
            a["end"] = b["start"]
    return chunks


def _ass_time(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}"


def captions(story_words: list[dict], speed: float, out: Path) -> Path:
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,DejaVu Sans,100,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,8,4,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for c in _chunks(story_words):
        text = c["text"].upper().replace("{", "").replace("}", "").replace("\\", "")
        pop = r"{\fscx120\fscy120\t(0,90,\fscx100\fscy100)}"
        lines.append(f"Dialogue: 0,{_ass_time(c['start'] / speed)},{_ass_time(c['end'] / speed)},Word,,0,0,0,,"
                     f"{pop}{text}\n")
    out.write_text(header + "".join(lines))
    return out


def _slice_start(clip_seconds: float, length: float, parts: list[tuple[float, float]]) -> float | None:
    """Random start inside a part of the clip that is real gameplay, or None to loop the whole clip."""
    if not parts:
        edge = min(60.0, clip_seconds * 0.1)  # recordings usually start and end in menus
        parts = [(edge, clip_seconds - edge)]
    parts = [(a, min(b, clip_seconds)) for a, b in parts]
    fitting = [(a, b) for a, b in parts if b - a >= length]
    if fitting:
        a, b = random.choice(fitting)
        return random.uniform(a, b - length)
    if clip_seconds > length + 1:
        # No part is long enough for this story: start at the longest one and let it run on.
        a, b = max(parts, key=lambda p: p[1] - p[0])
        return min(a, clip_seconds - length - 1)
    return None


def assemble(gameplay: Path, narration: Path, alignment: dict, title_chars: int, card: Path,
             workdir: Path, out: Path, settings: dict, parts: list[tuple[float, float]] | None = None) -> Path:
    """Narration is the post title followed by the story; the card shows while the title is read.
    `parts` are the (start, end) seconds of the clip that are actual gameplay."""
    max_seconds = settings["max_seconds"]
    spoken = duration(narration)
    speed = min(max(spoken / max_seconds, 1.0), MAX_SPEEDUP)
    length = min(spoken / speed, max_seconds)

    title_end = alignment["character_end_times_seconds"][title_chars - 1] / speed
    subs = captions(words(alignment, title_chars), speed, workdir / "captions.ass")

    info = _probe(gameplay)
    clip_seconds = float(info["format"]["duration"])
    game_has_audio = any(s["codec_type"] == "audio" for s in info["streams"])
    start = _slice_start(clip_seconds, length, parts or [])
    if start is not None:
        print(f"Gameplay from {int(start) // 60}:{int(start) % 60:02}")
        game_in = ["-ss", f"{start:.2f}", "-i", str(gameplay)]
    else:
        game_in = ["-stream_loop", "-1", "-i", str(gameplay)]

    voice = f"[1:a]atempo={speed:.4f}[voice]" if speed > 1 else "[1:a]anull[voice]"
    volume = settings.get("gameplay_volume", 0)
    if volume and game_has_audio:
        audio = f"{voice};[0:a]volume={volume}[game];[voice][game]amix=inputs=2:duration=first:normalize=0[a]"
    else:
        audio = voice.replace("[voice]", "[a]")
    video = (f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps={FPS}[bg];"
             f"[bg][2:v]overlay=(W-w)/2:(H-h)/2:enable='lt(t,{title_end:.3f})'[withcard];"
             f"[withcard]subtitles=filename='{subs}'[v]")
    _run("ffmpeg", "-y", *game_in, "-i", str(narration), "-loop", "1", "-i", str(card),
         "-filter_complex", f"{video};{audio}", "-map", "[v]", "-map", "[a]", "-t", f"{length:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
         "-c:a", "aac", "-ar", "44100", "-ac", "2", "-movflags", "+faststart", str(out))
    return out
