"""Assembles frames + voice lines into a 1080x1920 Short with a slow zoom and burned-in captions."""
import subprocess
from pathlib import Path

FPS = 30


def _run(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def duration(path: Path) -> float:
    return float(_run("ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "csv=p=0", str(path)).strip())


def _segment(image: Path, audio: Path, seconds: float, out: Path) -> None:
    frames = int(seconds * FPS) + 1
    zoom = (
        "scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
        f"zoompan=z='min(zoom+0.0007,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s=1080x1920:fps={FPS}"
    )
    _run("ffmpeg", "-y", "-i", str(image), "-i", str(audio),
         "-filter_complex", f"[0:v]{zoom}[v];[1:a]apad[a]", "-map", "[v]", "-map", "[a]",
         "-t", f"{seconds:.3f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
         "-c:a", "aac", "-ar", "44100", "-ac", "2", str(out))


def _ts(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def assemble(shots: list[dict], workdir: Path, out: Path, max_seconds: float, pause: float) -> Path:
    """Each shot needs `image`, `audio` and `line`. Returns the finished video path."""
    segments, srt, t = [], [], 0.0
    for i, shot in enumerate(shots):
        seconds = duration(shot["audio"]) + pause
        seg = workdir / f"seg_{i:02}.mp4"
        _segment(shot["image"], shot["audio"], seconds, seg)
        segments.append(seg)
        srt.append(f"{i + 1}\n{_ts(t)} --> {_ts(t + seconds - pause)}\n{shot['line']}\n")
        t += seconds

    listing = workdir / "segments.txt"
    listing.write_text("".join(f"file '{s.resolve()}'\n" for s in segments))
    joined = workdir / "joined.mp4"
    _run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined))

    subs = workdir / "captions.srt"
    subs.write_text("\n".join(srt))
    style = ("FontName=DejaVu Sans,Fontsize=13,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
             "BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=80,MarginL=20,MarginR=20")
    _run("ffmpeg", "-y", "-i", str(joined), "-vf", f"subtitles={subs}:force_style='{style}'",
         "-t", str(max_seconds), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "copy", str(out))
    return out
