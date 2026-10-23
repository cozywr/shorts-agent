"""Asks Claude to pick a famous scene and write a short parody of it for our original characters."""
import json

import anthropic

PROMPT = """You write scripts for a YouTube Shorts channel that re-enacts famous movie and TV scenes
as cartoon parodies performed by our own ORIGINAL characters:

{cast}

Pick one instantly recognizable scene from a famous movie or TV show and write a parody of it
starring these characters. Rules:
- It's a parody: keep the scene's setup and dramatic beats, but rewrite the dialogue as jokes that fit
  our characters (e.g. the stakes become snacks, bedtime, a missing sock). Never copy more than a few
  words of the original dialogue.
- Never mention, describe or imitate the real actors or real show characters.
- {min_shots}-{max_shots} shots, one spoken line per shot, at most {max_words} words in total.
- Land a punchline in the final shot.
- Do NOT use any of these scenes again: {used}

Reply with JSON only, no prose, in exactly this shape:
{{
  "source": "Show or movie title",
  "scene": "Short name of the famous scene",
  "title": "YouTube title under 80 characters, ends with #Shorts",
  "description": "1-2 sentence description, says it is a parody with original characters",
  "tags": ["5-10 tags"],
  "shots": [
    {{"speaker": "character id", "line": "spoken line",
      "characters": ["ids visible in the shot"],
      "setting": "where the shot takes place and what is happening, one sentence"}}
  ]
}}"""


def write_script(config: dict, used_scenes: list[str]) -> dict:
    cast = "\n".join(
        f"- id `{cid}`: {c['name']}, {c['look']}. Personality: {c['personality']}"
        for cid, c in config["characters"].items()
    )
    s = config["script"]
    prompt = PROMPT.format(
        cast=cast,
        min_shots=s["min_shots"],
        max_shots=s["max_shots"],
        max_words=s["max_words"],
        used=", ".join(used_scenes) or "none yet",
    )
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    resp = client.messages.create(
        model=s["model"],
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    script = json.loads(text[text.index("{") : text.rindex("}") + 1])
    _validate(script, config)
    return script


def _validate(script: dict, config: dict) -> None:
    ids = set(config["characters"])
    for shot in script["shots"]:
        if shot["speaker"] not in ids:
            raise ValueError(f"Unknown speaker {shot['speaker']!r} in script")
        shot["characters"] = [c for c in shot.get("characters", []) if c in ids] or [shot["speaker"]]
