"""Uploads a video an earlier run already made (e.g. a dry run you liked) instead of making a new one.

    python -m tools.upload_saved saved/   # folder with the earlier run's output (short.mp4 + script.json,
                                          # or the weekly long.mp4 + script.json + thumbnail.jpg)
"""
import json
import sys
from datetime import date
from pathlib import Path

import yaml

from agent import uploader

ROOT = Path(__file__).resolve().parent.parent


def main(folder: Path) -> None:
    found = list(folder.rglob("short.mp4")) or list(folder.rglob("long.mp4"))
    video = found[0]
    long = video.name == "long.mp4"
    script = json.loads((video.parent / "script.json").read_text())
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    print(f"Uploading: {script['title']}")
    url = uploader.upload(video, script, config, long=long, thumbnail=video.parent / "thumbnail.jpg" if long else None)
    print(f"Uploaded: {url}")
    history_file = ROOT / "history.json"
    history = json.loads(history_file.read_text())
    history.setdefault("long" if long else "facts", []).append({"date": date.today().isoformat(), "topic": script["topic"],
                                            "summary": script["summary"], "url": url})
    history_file.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n")
    if script.get("planned_topic"):
        from agent.main import remove_planned_topic
        remove_planned_topic(script["planned_topic"])


if __name__ == "__main__":
    main(Path(sys.argv[1]))
