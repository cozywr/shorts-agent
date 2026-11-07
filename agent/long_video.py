"""The weekly long video (about 10 minutes, widescreen 16:9): one "what if" story in chapters, with
the same stickman, narrator, painted places, music and sound effects as the Shorts.

    python -m agent.long_video              # full run, uploads to YouTube
    python -m agent.long_video --dry-run    # makes the video but does not upload
    python -m agent.long_video --topic "what if you never slept again"
"""
import os

os.environ["VIDEO_FORMAT"] = "wide"   # must be set before the drawing code is imported

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import yaml

from agent import cinematic, fact_writer, sounds, uploader, video, voices
from agent.main import YOUTUBE_SECRETS, narration_text

ROOT = Path(__file__).resolve().parent.parent
PIECE_CHARS = 2500   # the voice reads at most this much at a time


def _pieces(scenes: list[dict]) -> list[list[int]]:
    """Groups scene numbers into pieces for the voice: whole chapters, split if a chapter is too long."""
    groups, current, size = [], [], 0
    for i, sc in enumerate(scenes):
        n = len(sc["narration"]) + 1
        new_chapter = current and sc.get("chapter") != scenes[current[-1]].get("chapter")
        if current and (new_chapter or size + n > PIECE_CHARS):
            groups.append(current)
            current, size = [], 0
        current.append(i)
        size += n
    if current:
        groups.append(current)
    return groups


def _stamp(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60}:{s % 60:02}"


def run(dry_run: bool, topic: str | None = None, script_file: str | None = None) -> None:
    missing = [name for name in YOUTUBE_SECRETS if not os.environ.get(name)]
    if missing and not dry_run:
        sys.exit(f"Can't upload to YouTube: these secrets aren't set yet: {', '.join(missing)}.")
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    lv = config.get("long_video") or {}
    history_file = ROOT / "history.json"
    history = json.loads(history_file.read_text())
    history.setdefault("long", [])

    workdir = ROOT / "output" / f"long-{date.today().isoformat()}"
    workdir.mkdir(parents=True, exist_ok=True)

    # Don't let the long video use up the voice characters the daily Shorts need.
    left = voices.characters_left()
    needed = lv.get("max_words", 1500) * 7 + lv.get("keep_for_shorts", 25000)
    if left is not None and left < needed:
        sys.exit(f"Only {left:,} ElevenLabs characters left this month; the long video needs about "
                 f"{needed - lv.get('keep_for_shorts', 25000):,} and the Shorts need the rest. Skipping this week.")

    if script_file:
        script = json.loads(Path(script_file).read_text())
    else:
        used = [h["summary"] for h in history["long"]] + [h["summary"] for h in history.get("facts", [])][-30:]
        script = fact_writer.write_long(config, used, topic or lv.get("next_topic") or None)
    (workdir / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False))
    scenes = script["scenes"]
    text, starts = narration_text(scenes)
    print(f"Long video: {script['summary']} ({len(text.split())} words, {len(scenes)} scenes, "
          f"{len(script['chapters'])} chapters)")
    print("Fact-check: " + ("; ".join(script.get("fact_check") or []) or "no changes needed"))
    for i, sc in enumerate(scenes, 1):
        if sc.get("chapter_title"):
            print(f"  -- {sc['chapter_title']}")
        print(f"  {i}. [{sc['headline']}] {sc['narration']}")

    voice_id = voices.ensure_narrator(config, ROOT / "voices.json")
    for sc in scenes:
        sc["narration"] = voices.say_as(sc["narration"], config)
    groups = _pieces(scenes)
    parts = [narration_text([scenes[i] for i in g])[0] for g in groups]
    alignment, said = voices.speak_parts(parts, voice_id, workdir / "narration.mp3", config["narrator"])
    for g, part, was_said in zip(groups, parts, said):
        if was_said != part:   # that piece was read without the [direction] tags
            for i in g:
                scenes[i]["narration"] = voices.TAG.sub("", scenes[i]["narration"]).strip()
    text, starts = narration_text(scenes)

    effects = [sounds.effect(sc.get("sfx", "none")) for sc in scenes]
    music = sounds.music(config["facts"].get("audience", "kids")) if config["video"].get("music_volume", 0) > 0 else None
    settings = {**config["video"], "max_seconds": lv.get("max_seconds", 780), "fps": lv.get("fps", 30),
                "workers": lv.get("workers", -1), "music_volume": lv.get("music_volume", config["video"].get("music_volume", 0.1))}
    final = video.assemble(scenes, starts, workdir / "narration.mp3", alignment, workdir,
                           workdir / "long.mp4", settings, effects, music)
    print(f"Video: {final} ({video.duration(final) / 60:.1f} minutes)")

    # chapter timestamps for the description, from when each chapter's first word is said
    char_starts = alignment["character_start_times_seconds"]
    speed = settings.get("used_speed", 1.0)
    script["chapter_times"] = []
    for n, ch in enumerate(script["chapters"], 1):
        first = next(i for i, sc in enumerate(scenes) if sc.get("chapter") == n)
        at = 0.0 if n == 1 else char_starts[min(starts[first], len(char_starts) - 1)] / speed
        script["chapter_times"].append(f"{_stamp(at)} {ch['title'].title()}")
    thumb = cinematic.thumbnail(scenes[0], script.get("thumbnail_text") or script["title"], str(workdir.parent),
                                workdir / "thumbnail.jpg")
    script["scenes"] = scenes
    (workdir / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False))
    print("Chapters:\n  " + "\n  ".join(script["chapter_times"]))

    if dry_run:
        return
    url = uploader.upload(final, script, config, long=True, thumbnail=thumb)
    print(f"Uploaded: {url}")
    history["long"].append({"date": date.today().isoformat(), "topic": script["topic"],
                            "summary": script["summary"], "url": url})
    history_file.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--script", default=os.environ.get("SCRIPT_FILE") or None)
    parser.add_argument("--topic", default=os.environ.get("TOPIC") or None)
    args = parser.parse_args()
    run(args.dry_run, args.topic, args.script)
