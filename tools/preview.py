"""Draws a video from a script file without any API keys, with silent fake narration,
to check how the cartoon looks.

    python tools/preview.py examples/octopus.json
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent import video  # noqa: E402
from agent.main import narration_text  # noqa: E402


def fake_alignment(text: str, per_char: float = 0.065) -> dict:
    starts = [i * per_char for i in range(len(text))]
    return {"characters": list(text), "character_start_times_seconds": starts,
            "character_end_times_seconds": [s + per_char for s in starts]}


def main(script_file: str) -> None:
    script = json.loads(Path(script_file).read_text())
    text, starts = narration_text(script["scenes"])
    alignment = fake_alignment(text)
    workdir = ROOT / "output" / "preview"
    workdir.mkdir(parents=True, exist_ok=True)
    seconds = alignment["character_end_times_seconds"][-1]
    silence = workdir / "silence.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-t", f"{seconds:.2f}", str(silence)], check=True)
    out = video.assemble(script["scenes"], starts, silence, alignment, workdir, workdir / "preview.mp4",
                         {"max_seconds": 60, "speed": 1.0})
    print(out)


if __name__ == "__main__":
    main(sys.argv[1])
