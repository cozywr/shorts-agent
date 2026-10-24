"""Daily run: write a parody script, voice it, draw it, edit it, upload it.

    python -m agent.main            # full run, uploads to YouTube
    python -m agent.main --dry-run  # makes the video but does not upload
    python -m agent.main --scene "Breaking Bad, the I am the one who knocks scene"
"""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import yaml

from agent import script_writer, uploader, video, visuals, voices

ROOT = Path(__file__).resolve().parent.parent


YOUTUBE_SECRETS = ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")


def run(dry_run: bool, scene: str | None = None) -> None:
    # Check before spending money on the script, voices and images.
    missing = [name for name in YOUTUBE_SECRETS if not os.environ.get(name)]
    if missing and not dry_run:
        sys.exit(f"Can't upload to YouTube: these secrets aren't set yet: {', '.join(missing)}. "
                 "Add them (README step 3-4) or run with dry run ticked.")

    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    history_file = ROOT / "history.json"
    history = json.loads(history_file.read_text())

    workdir = ROOT / "output" / date.today().isoformat()
    workdir.mkdir(parents=True, exist_ok=True)

    used = [f"{h['source']}: {h['scene']}" for h in history["scenes"]]
    script = script_writer.write_script(config, used, scene)
    (workdir / "script.json").write_text(json.dumps(script, indent=2))
    print(f"Scene: {script['source']} - {script['scene']}")

    voice_ids = voices.ensure_voices(config, ROOT / "voices.json")
    for i, shot in enumerate(script["shots"]):
        shot["audio"] = voices.speak(shot["line"], voice_ids[shot["speaker"]], workdir / f"line_{i:02}.mp3")
        shot["image"] = visuals.draw(shot, config, workdir / f"shot_{i:02}.png")
        if config["video"].get("lip_flaps", True):
            shot["mouth_open"] = visuals.draw_mouth_open(shot, config, shot["image"], workdir / f"shot_{i:02}_open.png")
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
    parser.add_argument("--scene", default=os.environ.get("SCENE") or None,
                        help='e.g. "Breaking Bad, the I am the one who knocks scene"; empty lets Claude pick')
    args = parser.parse_args()
    run(args.dry_run, args.scene)
