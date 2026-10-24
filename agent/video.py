"""Assembles frames + voice lines into a 1080x1920 Short with a slow zoom and burned-in captions."""
import array
import math
import subprocess
from pathlib import Path

FPS = 30
SAMPLE_RATE = 8000
FLAP_FRAMES = 3  # while talking, the mouth opens and closes every 3 frames (10 flaps a second)


def _run(*args: str) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def duration(path: Path) -> float:
    return float(_run("ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "csv=p=0", str(path)).strip())


def mouth_timeline(audio: Path, frames: int) -> list[bool]:
    """For each video frame, whether the speaker's mouth should be open."""
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(audio), "-ac", "1", "-ar", str(SAMPLE_RATE),
                          "-f", "s16le", "-"], check=True, capture_output=True).stdout
    samples = array.array("h", pcm[: len(pcm) // 2 * 2])
    per_frame = SAMPLE_RATE // FPS
    loudness = []
    for i in range(frames):
        chunk = samples[i * per_frame:(i + 1) * per_frame]
        loudness.append(math.sqrt(sum(x * x for x in chunk) / len(chunk)) if chunk else 0.0)
    threshold = max(max(loudness, default=0) * 0.15, 300)
    return [level > threshold and (i // FLAP_FRAMES) % 2 == 0 for i, level in enumerate(loudness)]


def _frames_input(closed: Path, mouth_open: Path, timeline: list[bool], listing: Path) -> list[str]:
    """ffmpeg concat-demuxer input that shows the open or closed frame for each run of the timeline."""
    lines, run_start = [], 0
    for i in range(1, len(timeline) + 1):
        if i == len(timeline) or timeline[i] != timeline[run_start]:
            frame = mouth_open if timeline[run_start] else closed
            lines.append(f"file '{frame.resolve()}'\nduration {(i - run_start) / FPS:.4f}\n")
            run_start = i
    lines.append(f"file '{closed.resolve()}'\n")  # concat ignores the last entry's duration
    listing.write_text("".join(lines))
    return ["-f", "concat", "-safe", "0", "-i", str(listing)]


def _segment(image: Path, audio: Path, seconds: float, out: Path, mouth_open: Path | None = None) -> None:
    frames = int(seconds * FPS) + 1
    fit = "scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,setsar=1,"
    if mouth_open:
        video_in = _frames_input(image, mouth_open, mouth_timeline(audio, frames), out.with_suffix(".txt"))
        # One output frame per input frame; `on` counts frames so the slow zoom keeps going across flaps.
        zoom = f"fps={FPS},{fit}zoompan=z='min(1+on*0.0007,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1"
    else:
        video_in = ["-i", str(image)]
        zoom = (f"{fit}zoompan=z='min(zoom+0.0007,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={frames}")
    _run("ffmpeg", "-y", *video_in, "-i", str(audio),
         "-filter_complex", f"[0:v]{zoom}:s=1080x1920:fps={FPS}[v];[1:a]apad[a]", "-map", "[v]", "-map", "[a]",
         "-t", f"{seconds:.3f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
         "-c:a", "aac", "-ar", "44100", "-ac", "2", str(out))


def _ts(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def assemble(shots: list[dict], workdir: Path, out: Path, max_seconds: float, pause: float) -> Path:
    """Each shot needs `image`, `audio` and `line`, and may have a `mouth_open` frame. Returns the video path."""
    segments, srt, t = [], [], 0.0
    for i, shot in enumerate(shots):
        seconds = duration(shot["audio"]) + pause
        seg = workdir / f"seg_{i:02}.mp4"
        _segment(shot["image"], shot["audio"], seconds, seg, shot.get("mouth_open"))
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
