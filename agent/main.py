"""Daily run: write a fun fact for kids, voice it, animate the stickman host, upload it.

    python -m agent.main                          # full run, uploads to YouTube
    python -m agent.main --dry-run                # makes the video but does not upload
    python -m agent.main --topic "why cats purr"  # pick today's topic yourself
"""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import yaml

from agent import fact_writer, uploader, video, voices

ROOT = Path(__file__).resolve().parent.parent

YOUTUBE_SECRETS = ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")


def narration_text(scenes: list[dict]) -> tuple[str, list[int]]:
    """All the scenes' narration as one text, and the character where each scene starts."""
    text, starts = "", []
    for sc in scenes:
        if text:
            text += " "
        starts.append(len(text))
        text += sc["narration"].strip()
    return text, starts


def run(dry_run: bool, topic: str | None = None) -> None:
    # Check before spending money on the script and voice.
    missing = [name for name in YOUTUBE_SECRETS if not os.environ.get(name)]
    if missing and not dry_run:
        sys.exit(f"Can't upload to YouTube: these secrets aren't set yet: {', '.join(missing)}. "
                 "Add them (README step 3) or run with dry run ticked.")

    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    history_file = ROOT / "history.json"
    history = json.loads(history_file.read_text())
    history.setdefault("facts", [])

    workdir = ROOT / "output" / date.today().isoformat()
    workdir.mkdir(parents=True, exist_ok=True)

    script = fact_writer.write_fact(config, [h["summary"] for h in history["facts"]], topic)
    (workdir / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False))
    text, starts = narration_text(script["scenes"])
    print(f"Fact: {script['summary']} ({len(text.split())} words, {len(script['scenes'])} scenes)")

    voice_id = voices.ensure_narrator(config, ROOT / "voices.json")
    alignment = voices.speak(voices.say_as(text, config), voice_id, workdir / "narration.mp3")

    final = video.assemble(script["scenes"], starts, workdir / "narration.mp3", alignment,
                           workdir, workdir / "short.mp4", config["video"])
    print(f"Video: {final}")

    if dry_run:
        return
    url = uploader.upload(final, script, config)
    print(f"Uploaded: {url}")
    history["facts"].append({"date": date.today().isoformat(), "topic": script["topic"],
                             "summary": script["summary"], "url": url})
    history_file.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--topic", default=os.environ.get("TOPIC") or None,
                        help='e.g. "why cats purr"; empty lets Claude pick')
    args = parser.parse_args()
    run(args.dry_run, args.topic)
