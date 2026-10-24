"""Asks Claude to pick a famous scene and write a short parody of it for our original characters."""
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

Submit the finished script with the submit_script tool."""

# Forcing a tool call makes the API hand back already-parsed JSON, so quotes in dialogue can't break it.
SCRIPT_TOOL = {
    "name": "submit_script",
    "description": "Submit the finished parody script.",
    "input_schema": {
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
                },
            },
        },
        "required": ["source", "scene", "title", "description", "tags", "shots"],
    },
}


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
        tools=[SCRIPT_TOOL],
        tool_choice={"type": "tool", "name": "submit_script"},
        messages=[{"role": "user", "content": prompt}],
    )
    script = next(b.input for b in resp.content if b.type == "tool_use")
    _validate(script, config)
    return script


def _validate(script: dict, config: dict) -> None:
    ids = set(config["characters"])
    for shot in script["shots"]:
        if shot["speaker"] not in ids:
            raise ValueError(f"Unknown speaker {shot['speaker']!r} in script")
        shot["characters"] = [c for c in shot.get("characters", []) if c in ids] or [shot["speaker"]]
