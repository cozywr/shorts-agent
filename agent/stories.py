"""Stories you write yourself: .txt files in stories/, read word for word, oldest file name first.

The first line of a file is the post title, everything after it is the story.
A first line like "voice: creepy" (before the title) reads the story with that voice from config.yaml.
After a real upload the file moves to stories/used/ so it isn't posted twice.
"""
from pathlib import Path


def next_story(root: Path) -> Path | None:
    folder = root / "stories"
    files = sorted(folder.glob("*.txt")) if folder.exists() else []
    return files[0] if files else None


def read(path: Path) -> tuple[str, str, str]:
    """Returns (title, story, voice), where voice is "narrator" unless the file asks for another."""
    lines = path.read_text(encoding="utf-8-sig").strip().splitlines()
    voice = "narrator"
    if lines and lines[0].lower().startswith("voice:"):
        voice = lines[0].split(":", 1)[1].strip().lower()
        lines = "\n".join(lines[1:]).strip().splitlines()
    title, body = lines[0].strip(), "\n".join(lines[1:]).strip()
    if not body:
        raise SystemExit(f"{path.name} only has one line. Put the title on the first line "
                         "and the story on the lines below it.")
    return title, body, voice


def mark_used(path: Path) -> None:
    used = path.parent / "used"
    used.mkdir(exist_ok=True)
    path.rename(used / path.name)
