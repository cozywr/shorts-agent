"""Turns the scenes and the narration into the finished Short: the stickman cartoon, the voice,
and big word-by-word captions that light up as each word is said."""
import json
import re
import subprocess
from pathlib import Path

from agent import animation

FPS = 30
MAX_SPEEDUP = 1.2    # a script that runs long is read up to 20% faster before anything gets cut
TAIL = 0.8           # seconds the last picture stays up after the voice ends
CHUNK_WORDS = 3
CHUNK_CHARS = 18
FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


def _run(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def duration(path: Path) -> float:
    out = _run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path))
    return float(json.loads(out)["format"]["duration"])


def words(alignment: dict) -> list[dict]:
    """Groups ElevenLabs' per-character timings into words."""
    chars = alignment["characters"]
    starts, ends = alignment["character_start_times_seconds"], alignment["character_end_times_seconds"]
    out, current = [], None
    for i, ch in enumerate(chars):
        if ch.isspace():
            current = None
            continue
        if current is None:
            current = {"text": "", "start": starts[i]}
            out.append(current)
        current["text"] += ch
        current["end"] = ends[i]
    # voice directions like [excited] or [giggles] are acted out, not shown
    return [w for w in out if not re.fullmatch(r"\[[^\]]*\]?[.,!?]*|[^\[]*\]", w["text"])]


def _chunks(all_words: list[dict]) -> list[list[dict]]:
    chunks, current = [], []
    for w in all_words:
        current.append(w)
        text = " ".join(x["text"] for x in current)
        if len(current) >= CHUNK_WORDS or len(text) >= CHUNK_CHARS or w["text"][-1] in ".,!?;:":
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


def _ass_time(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}"


def captions(all_words: list[dict], speed: float, out: Path) -> Path:
    """Karaoke captions: each word turns yellow as it's said."""
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,Fredoka,96,&H003CE1FF,&H00FFFFFF,&H00341E22,&H64000000,-1,0,0,0,100,100,1,0,1,9,5,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    chunks = _chunks(all_words)
    lines = []
    for n, chunk in enumerate(chunks):
        start = chunk[0]["start"] / speed
        end = chunk[-1]["end"] / speed
        if n + 1 < len(chunks):
            nxt = chunks[n + 1][0]["start"] / speed
            if nxt - end < 0.5:
                end = nxt
        text, t = "", start
        for w in chunk:
            gap = max(0.0, w["start"] / speed - t)
            dur = max(0.01, w["end"] / speed - w["start"] / speed)
            word = w["text"].upper().replace("{", "").replace("}", "").replace("\\", "")
            text += f"{{\\k{int(round(gap * 100))}}}" if gap > 0.005 else ""
            text += f"{{\\k{int(round(dur * 100))}}}{word} "
            t = w["end"] / speed
        pop = r"{\pos(540,1610)\fscx118\fscy118\t(0,90,\fscx100\fscy100)}"
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Word,,0,0,0,,{pop}{text.strip()}\n")
    out.write_text(header + "".join(lines))
    return out


def assemble(scenes: list[dict], starts: list[int], narration: Path, alignment: dict,
             workdir: Path, out: Path, settings: dict, effects: list[Path | None] | None = None,
             music: Path | None = None) -> Path:
    """`starts[i]` is the character in the narration where scene i begins. `effects[i]` is the
    sound effect played as scene i starts, and `music` loops quietly under everything."""
    max_seconds = settings["max_seconds"]
    base_speed = settings.get("speed", 1.0)
    spoken = duration(narration)
    speed = min(max(spoken / (max_seconds - TAIL), base_speed), max(base_speed, MAX_SPEEDUP))
    length = min(spoken / speed + TAIL, max_seconds)

    char_starts = alignment["character_start_times_seconds"]
    scene_times = [0.0] + [char_starts[min(c, len(char_starts) - 1)] / speed - 0.1 for c in starts[1:]]
    subs = captions(words(alignment), speed, workdir / "captions.ass")
    mouth = animation.mouth_track(alignment, speed)

    # Audio: the voice, plus each scene's sound effect at its start, plus the music underneath.
    inputs, mix = ["-i", str(narration)], []
    voice = f"[1:a]atempo={speed:.4f},apad[voice]" if speed != 1 else "[1:a]apad[voice]"
    parts = [voice]
    n = 2
    for i, sfx in enumerate(effects or []):
        if sfx is None or i >= len(scenes):
            continue
        at = max(0.0, scene_times[i]) + (0.75 if scenes[i]["pose"] == "faint" else 0.05)
        inputs += ["-i", str(sfx)]
        ms = int(at * 1000)
        parts.append(f"[{n}:a]volume={settings.get('effects_volume', 0.6)},adelay={ms}|{ms}[s{n}]")
        mix.append(f"[s{n}]")
        n += 1
    if music:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        fade = max(0.0, length - 1.5)
        parts.append(f"[{n}:a]volume={settings.get('music_volume', 0.12)},afade=t=out:st={fade:.2f}:d=1.5[m]")
        mix.append("[m]")
    if mix:
        parts.append(f"[voice]{''.join(mix)}amix=inputs={len(mix) + 1}:duration=first:normalize=0[a]")
    else:
        parts[0] = parts[0].replace("[voice]", "[a]")
    audio = ";".join(parts)
    video = (f"[0:v]subtitles=filename='{subs}':fontsdir='{FONT_DIR}',format=yuv420p[v]")
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{animation.W}x{animation.H}", "-r", str(FPS), "-i", "-",
         *inputs, "-filter_complex", f"{video};{audio}", "-map", "[v]", "-map", "[a]",
         "-t", f"{length:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS),
         "-c:a", "aac", "-ar", "44100", "-ac", "2", "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE)
    cache = str(workdir.parent)
    frames = int(length * FPS)
    i = 0
    for f in range(frames):
        t = f / FPS
        while i + 1 < len(scenes) and t >= scene_times[i + 1]:
            i += 1
        frame = animation.render_frame(scenes[i], scenes[i - 1] if i else None, t - scene_times[i], t,
                                       mouth(t), cache)
        proc.stdin.write(frame.tobytes())
        if f % (FPS * 10) == 0:
            print(f"Drawing {t:.0f}s / {length:.0f}s")
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed while making the video")
    return out
