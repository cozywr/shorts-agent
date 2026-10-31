"""Daily run: take your next story (or write one), narrate it, lay it over gameplay with captions, upload it.

    python -m agent.main            # full run, uploads to YouTube
    python -m agent.main --dry-run  # makes the video but does not upload
    python -m agent.main --idea "a roommate who labels every single grape"
"""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import yaml

from agent import card, gameplay, script_writer, stories, uploader, video, voices

ROOT = Path(__file__).resolve().parent.parent


YOUTUBE_SECRETS = ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")


def run(dry_run: bool, idea: str | None = None) -> None:
    # Check before spending money on the story and voice.
    missing = [name for name in YOUTUBE_SECRETS if not os.environ.get(name)]
    if missing and not dry_run:
        sys.exit(f"Can't upload to YouTube: these secrets aren't set yet: {', '.join(missing)}. "
                 "Add them (README step 3-4) or run with dry run ticked.")

    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    history_file = ROOT / "history.json"
    history = json.loads(history_file.read_text())
    history.setdefault("stories", [])

    workdir = ROOT / "output" / date.today().isoformat()
    workdir.mkdir(parents=True, exist_ok=True)

    own = stories.next_story(ROOT)
    if not own and not config["story"].get("auto_write", True):
        sys.exit("No stories left in the stories folder. Add one (see stories/README.md) and run again.")

    downloads = ROOT / "gameplay-download"  # kept out of output/ so big clips don't go in the video download
    downloads.mkdir(exist_ok=True)
    clip = gameplay.pick(ROOT, downloads, config["gameplay"]["release_tag"])
    print(f"Gameplay: {clip.name}")

    if own:
        post_title, body = stories.read(own)
        story = {"post_title": post_title, "story": body, **script_writer.describe(config, post_title, body)}
        print(f"Using your story {own.name}")
    else:
        story = script_writer.write_story(config, [h["summary"] for h in history["stories"]], idea)
    (workdir / "story.json").write_text(json.dumps(story, indent=2))
    print(f"Story: {story['post_title']} ({len(story['story'].split())} words)")

    voice_id = voices.ensure_narrator(config, ROOT / "voices.json")
    spoken_title = voices.say_as(story["post_title"], config)
    narration_text = f"{spoken_title}\n\n{voices.say_as(story['story'], config)}"
    alignment = voices.speak(narration_text, voice_id, workdir / "narration.mp3")

    post_card = None
    if config["card"].get("show", True):
        post_card = card.draw(story["post_title"], config["card"]["channel_name"], workdir / "card.png")
    final = video.assemble(clip, workdir / "narration.mp3", alignment, len(spoken_title), post_card,
                           workdir, workdir / "short.mp4", config["video"], gameplay.good_parts(clip, config))
    print(f"Video: {final}")

    if dry_run:
        return
    url = uploader.upload(final, story, config)
    print(f"Uploaded: {url}")

    if own:
        stories.mark_used(own)
    history["stories"].append({"date": date.today().isoformat(), "post_title": story["post_title"],
                               "summary": story["summary"], "url": url})
    history_file.write_text(json.dumps(history, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--idea", default=os.environ.get("IDEA") or None,
                        help='e.g. "a roommate who labels every single grape"; empty lets Claude pick')
    args = parser.parse_args()
    run(args.dry_run, args.idea)
