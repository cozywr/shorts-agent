"""Asks Claude to write today's fun fact as a short stickman cartoon script."""
import json

import anthropic

from agent.animation import BACKGROUNDS, POSES

PROMPT = """You write scripts for a YouTube Shorts channel of fun facts for kids aged 5 to 10.
Each video is a short cartoon: a friendly stickman host in a red cap tells the fact while it
appears as big pictures (emoji) behind him, with a cheerful narrator reading the script.

{topic}
Rules:
- The fact must be TRUE, well established and easy to check (the kind of thing found in a
  children's encyclopedia or from NASA, National Geographic Kids, a museum). No myths,
  no "scientists think maybe" claims, no made-up numbers. If you're not sure, pick another fact.
- Super fun and friendly: simple words a 6-year-old understands, short sentences, lots of
  wonder ("Whoa!", "Guess what?"). Nothing scary, gross, violent, sad or unsafe to copy.
  No brands, real people, or asking kids for personal information.
- {min_words}-{max_words} words in total (about 40 seconds read aloud), split into 4 to 6 scenes.
- Scene 1 is the hook: a question or a surprising claim that makes kids want to know more.
  The middle scenes explain it in tiny steps, with one more amazing detail.
  The last scene is a happy wrap-up ending with "Now you know!" or similar.
- Each scene's narration is one or two short sentences, written exactly as it should be spoken
  (numbers in words when that reads better, no emoji, no abbreviations).
- headline: 1 to 4 big words shown at the top of the scene (e.g. "THREE HEARTS!"). Can be empty.
- emojis: 1 to 4 standard emoji that show what the narrator is talking about right now
  (e.g. ["🐙"] or ["❤️", "❤️", "❤️"]). Only common, single emoji that every phone has;
  no flags, no skin tones, no people with jobs, no combined emoji.
- background: one of {backgrounds} (pick what fits the topic; changing it mid-video is fine).
- pose: what the stickman does, one of {poses}.
  explain = talking with his hands, point = points at the pictures, think = hand on chin,
  surprised = jumps back amazed, cheer/jump/dance = very excited, shrug = "who knew?".
  Vary the poses from scene to scene.
- Don't repeat any of these earlier topics: {used}

Reply with the script as JSON."""

TOPIC_ANY = "Pick a fresh topic: animals, space, the human body, nature, weather, oceans, dinosaurs, food or how things work."
TOPIC_GIVEN = "Today's topic: {topic}"

SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string", "description": "A few words, e.g. 'octopus hearts'"},
        "summary": {"type": "string", "description": "One sentence stating the fact, to avoid repeats"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "narration": {"type": "string"},
                    "headline": {"type": "string"},
                    "emojis": {"type": "array", "items": {"type": "string"}},
                    "background": {"type": "string", "enum": BACKGROUNDS},
                    "pose": {"type": "string", "enum": POSES},
                },
                "required": ["narration", "headline", "emojis", "background", "pose"],
                "additionalProperties": False,
            },
        },
        "title": {"type": "string", "description": "Fun YouTube title under 70 characters, may use one emoji, ends with #Shorts"},
        "description": {"type": "string", "description": "1-2 friendly sentences for parents and kids"},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "5-10 tags"},
    },
    "required": ["topic", "summary", "scenes", "title", "description", "tags"],
    "additionalProperties": False,
}


def write_fact(config: dict, used: list[str], topic: str | None = None) -> dict:
    s = config["facts"]
    prompt = PROMPT.format(
        topic=TOPIC_GIVEN.format(topic=topic) if topic else TOPIC_ANY,
        min_words=s["min_words"],
        max_words=s["max_words"],
        backgrounds=", ".join(BACKGROUNDS),
        poses=", ".join(POSES),
        used="; ".join(used[-80:]) or "none yet",
    )
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    resp = client.messages.create(
        model=s["model"],
        max_tokens=16000,
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    if resp.stop_reason != "end_turn":
        raise RuntimeError(f"Script request stopped early: {resp.stop_reason}")
    script = json.loads(next(b.text for b in resp.content if b.type == "text"))
    script["scenes"] = [sc for sc in script["scenes"] if sc["narration"].strip()][:7]
    for sc in script["scenes"]:
        sc["emojis"] = sc["emojis"][:4] or ["⭐"]
    if len(script["scenes"]) < 2:
        raise RuntimeError("The script came back with too few scenes.")
    return script
