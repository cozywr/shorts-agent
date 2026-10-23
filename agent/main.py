"""Daily run: write a parody script, voice it, draw it, edit it, upload it.

    python -m agent.main            # full run, uploads to YouTube
    python -m agent.main --dry-run  # makes the video but does not upload
"""
import argparse
import json
from datetime import date
from pathlib import Path

import yaml

from agent import script_writer, uploader, video, visuals, voices

ROOT = Path(__file__).resolve().parent.parent


def run(dry_run: bool) -> None:
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    history_file = ROOT / "history.json"
    history = json.loads(history_file.read_text())

    workdir = ROOT / "output" / date.today().isoformat()
    workdir.mkdir(parents=True, exist_ok=True)

    used = [f"{h['source']}: {h['scene']}" for h in history["scenes"]]
    script = script_writer.write_script(config, used)
    (workdir / "script.json").write_text(json.dumps(script, indent=2))
    print(f"Scene: {script['source']} - {script['scene']}")

    for i, shot in enumerate(script["shots"]):
        voice_id = config["characters"][shot["speaker"]]["voice_id"]
        shot["audio"] = voices.speak(shot["line"], voice_id, workdir / f"line_{i:02}.mp3")
        shot["image"] = visuals.draw(shot, config, workdir / f"shot_{i:02}.png")
        print(f"  shot {i + 1}/{len(script['shots'])} ready")

    v = config["video"]
    final = video.assemble(script["shots"], workdir, workdir / "short.mp4", v["max_seconds"], v["pause_between_lines"])
    print(f"Video: {final}")

    if dry_run:
        return
    url = uploader.upload(final, script, config)
    print(f"Uploaded: {url}")

    history["scenes"].append({"date": date.today().isoformat(), "source": script["source"],
                              "scene": script["scene"], "url": url})
    history_file.write_text(json.dumps(history, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    run(parser.parse_args().dry_run)
