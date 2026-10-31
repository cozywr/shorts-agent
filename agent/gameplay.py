"""Picks a random gameplay clip, from the repo's gameplay/ folder or from the "gameplay" GitHub release."""
import os
import random
from pathlib import Path

import requests

VIDEO_TYPES = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


def _is_video(name: str) -> bool:
    return Path(name).suffix.lower() in VIDEO_TYPES


def _release_assets(tag: str) -> list[dict]:
    """Video files attached to the release with this tag. Empty when not running on GitHub or no release."""
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not repo or not token:
        return []
    resp = requests.get(f"https://api.github.com/repos/{repo}/releases/tags/{tag}",
                        headers={"Authorization": f"Bearer {token}"}, timeout=60)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    return [a for a in resp.json()["assets"] if _is_video(a["name"])]


def _download(asset: dict, workdir: Path) -> Path:
    out = workdir / asset["name"]
    # requests drops the Authorization header when GitHub redirects to its file storage host.
    with requests.get(asset["url"], stream=True, timeout=600,
                      headers={"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
                               "Accept": "application/octet-stream"}) as resp:
        resp.raise_for_status()
        with out.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    return out


def pick(root: Path, workdir: Path, release_tag: str) -> Path:
    folder = root / "gameplay"
    clips: list[Path | dict] = [p for p in sorted(folder.iterdir()) if _is_video(p.name)] if folder.exists() else []
    clips += _release_assets(release_tag)
    if not clips:
        raise SystemExit("No gameplay clips found. Upload some videos to the 'gameplay' release "
                         "(README step 2) and run again.")
    clip = random.choice(clips)
    if isinstance(clip, Path):
        return clip
    print(f"Downloading gameplay clip {clip['name']}")
    return _download(clip, workdir)


def _seconds(stamp: str) -> float:
    total = 0.0
    for piece in stamp.strip().split(":"):
        total = total * 60 + float(piece)
    return total


def good_parts(clip: Path, config: dict) -> list[tuple[float, float]]:
    """The parts of this clip listed under gameplay.good_parts in config.yaml, as (start, end) seconds."""
    ranges = (config["gameplay"].get("good_parts") or {}).get(clip.name, [])
    return [tuple(_seconds(x) for x in r.split("-")) for r in ranges]
