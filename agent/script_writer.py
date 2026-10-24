"""Asks Claude to pick a famous scene and write a short parody of it for our original characters."""
import json

import anthropic

PROMPT = """You write scripts for a YouTube Shorts channel that re-enacts famous movie and TV scenes
as cartoon parodies performed by our own ORIGINAL characters:

{cast}

{pick}
Rules:
- It's a parody: keep the scene's setup and dramatic beats, but rewrite the dialogue as jokes that fit
  our characters (e.g. the stakes become snacks, bedtime, a missing sock). Never copy more than a few
  words of the original dialogue.
- Never mention, describe or imitate the real actors or real show characters.
- {min_shots}-{max_shots} shots, one spoken line per shot, at most {max_words} words in total.
- Land a punchline in the final shot.
- Keep every shot's `setting` family-friendly and visual: no weapons, blood, drugs or crime props
  (an image safety filter rejects those). Swap them for silly stand-ins like snacks or toys.
- Do NOT use any of these scenes again: {used}

Reply with the finished script as JSON."""

# Structured outputs constrain the reply to this schema, so quotes in dialogue can't break the JSON.
SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "source": {"type": "string", "description": "Show or movie title"},
        "scene": {"type": "string", "description": "Short name of the famous scene"},
        "title": {"type": "string", "description": "YouTube title under 80 characters, ends with #Shorts"},
        "description": {"type": "string", "description": "1-2 sentences, says it is a parody with original characters"},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "5-10 tags"},
        "shots": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string", "description": "character id"},
                    "line": {"type": "string", "description": "spoken line"},
                    "characters": {"type": "array", "items": {"type": "string"},
                                   "description": "ids visible in the shot"},
                    "setting": {"type": "string",
                                "description": "where the shot takes place and what is happening, one sentence"},
                },
                "required": ["speaker", "line", "characters", "setting"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["source", "scene", "title", "description", "tags", "shots"],
    "additionalProperties": False,
}


PICK_ANY = ("Pick one instantly recognizable scene from a famous movie or TV show and write a parody of it\n"
            "starring these characters.")
PICK_GIVEN = ("Write a parody of this scene, starring these characters: {scene}\n"
              "Our cast always plays it: never use the real show's characters, even if named above.")


def write_script(config: dict, used_scenes: list[str], scene: str | None = None) -> dict:
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
        pick=PICK_GIVEN.format(scene=scene) if scene else PICK_ANY,
    )
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    resp = client.messages.create(
        model=s["model"],
        max_tokens=16000,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCRIPT_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    if resp.stop_reason != "end_turn":
        raise RuntimeError(f"Script request stopped early: {resp.stop_reason}")
    script = json.loads(next(b.text for b in resp.content if b.type == "text"))
    _validate(script, config)
    return script


def _validate(script: dict, config: dict) -> None:
    ids = set(config["characters"])
    for shot in script["shots"]:
        if shot["speaker"] not in ids:
            raise ValueError(f"Unknown speaker {shot['speaker']!r} in script")
        shot["characters"] = [c for c in shot.get("characters", []) if c in ids] or [shot["speaker"]]
