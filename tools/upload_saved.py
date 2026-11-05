"""Uploads a video an earlier run already made (e.g. a dry run you liked) instead of making a new one.

    python -m tools.upload_saved saved/   # folder with the earlier run's output (short.mp4 + script.json)
"""
import json
import sys
from datetime import date
from pathlib import Path

import yaml

from agent import uploader

ROOT = Path(__file__).resolve().parent.parent


def main(folder: Path) -> None:
    video = next(folder.rglob("short.mp4"))
    script = json.loads((video.parent / "script.json").read_text())
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    print(f"Uploading: {script['title']}")
    url = uploader.upload(video, script, config)
    print(f"Uploaded: {url}")
    history_file = ROOT / "history.json"
    history = json.loads(history_file.read_text())
    history.setdefault("facts", []).append({"date": date.today().isoformat(), "topic": script["topic"],
                                            "summary": script["summary"], "url": url})
    history_file.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
