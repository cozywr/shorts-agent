"""Asks Claude to write today's fun fact as a short stickman cartoon script."""
import json

import anthropic

from agent.animation import BACKGROUNDS, POSES
from agent.sounds import NAMES as SOUNDS

PROMPT = """You write scripts for a super fun YouTube Shorts cartoon channel for kids aged 5 to 10.
Each video is a goofy cartoon: a silly stickman host in a red cap reacts to a jaw-dropping fun fact,
with big pictures (emoji), cartoon sound effects, comic speech bubbles and a very excited
cartoon narrator. Kids should LAUGH first and learn something by accident.

{topic}
What makes it fun:
- The first line grabs attention in under 2 seconds: a wild claim, a silly question or a dare
  ("Your burps could fill a bathtub? WAIT, WHAT?!", "Bet you can't lick your elbow!"). No slow intros.
- Pick facts kids find WEIRD, silly or a little gross-funny (boogers, burps, poop-eating rabbits,
  animals doing ridiculous things) or amazing (huge, tiny, super fast, super strong), and
  "try it right now!" facts kids can safely test (you can't hum while holding your nose).
- Make it a little story with jokes: the stickman tries something and fails, gets scared,
  faints from shock, runs away screaming, or laughs his head off. Use comedy beats: a build-up,
  a surprise, a reaction. Talk straight to the viewer ("Yes, YOU!").
- Over-the-top excitement and silliness, short punchy sentences, funny sounds in words
  ("Boing!", "Ewww!", "Whoooa!"). Simple words a 6-year-old understands.
- End with a funny twist or a quick challenge ("Go try it and don't tell your teacher!") and
  "Follow for more silly facts!".

Safety and truth:
- The fact must be TRUE and easy to check (kids' encyclopedias, NASA, National Geographic Kids,
  museums). No myths, no made-up numbers. Silly jokes around the fact are fine; the fact itself isn't.
- Nothing scary, mean, violent, sad, or dangerous to copy (no "try it" with fire, heights,
  holding breath for long, eating things, etc.). No brands, real people, or asking for personal info.

Format:
- {min_words}-{max_words} spoken words in total (about 35-45 seconds), split into 5 to 7 quick scenes.
- narration: exactly what the narrator says in that scene. Numbers in words where it reads better,
  no emoji. You may add up to two voice directions per video, each ONE word in square
  brackets: [excited], [giggles], [laughs], [gasps], [whispers], [shouts].
- headline: 1 to 4 big words at the top of the scene (e.g. "SNOT FACTORY!"). Can be empty.
- shout: what the stickman yells in a comic speech bubble, 1-3 words ("WHAAAT?!", "EWWW!",
  "NO WAY!", "HA HA!"), or empty. Use it in about half the scenes.
- emojis: 1 to 4 standard emoji showing what's being talked about right now
  (e.g. ["🐰", "💩"]). Only common single emoji every phone has: no flags, skin tones or combined emoji.
- background: one of {backgrounds}. Pick what fits; changing it between scenes is fun.
- pose: one of {poses}.
  explain = talking with his hands, point = points at the pictures, think = hand on chin,
  surprised = jumps back amazed, cheer/jump/dance = very excited, shrug = "who knew?",
  faint = faints flat on his back from shock, spin = flips in the air, run = runs back and forth
  in a panic, laugh = can't stop laughing, scared = shaking with his arms up, wave = waves at the viewer.
  Use the funny ones (faint, spin, run, laugh, scared) at the big moments, and never the same pose twice in a row.
- sfx: the cartoon sound at the start of the scene, one of {sounds}. Use "none" sometimes.
- Don't repeat any of these earlier topics: {used}

Reply with the script as JSON."""

TOPIC_ANY = "Pick a fresh, wacky topic: weird animals, the silly human body, space, dinosaurs, food, nature or how things work."
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
                    "shout": {"type": "string"},
                    "sfx": {"type": "string", "enum": SOUNDS},
                },
                "required": ["narration", "headline", "emojis", "background", "pose", "shout", "sfx"],
                "additionalProperties": False,
            },
        },
        "title": {"type": "string", "description": "Catchy, silly YouTube title under 70 characters that makes kids click, may use one emoji, ends with #Shorts"},
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
        sounds=", ".join(SOUNDS),
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
    script["scenes"] = [sc for sc in script["scenes"] if sc["narration"].strip()][:8]
    for sc in script["scenes"]:
        sc["emojis"] = sc["emojis"][:4] or ["⭐"]
    if len(script["scenes"]) < 2:
        raise RuntimeError("The script came back with too few scenes.")
    return script
