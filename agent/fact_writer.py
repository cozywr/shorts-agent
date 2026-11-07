"""Asks Claude to write today's video as a short stickman cartoon script, in one of two styles
(facts.audience in config.yaml):
  kids         silly fun facts for ages 5-10
  young_adults "What would happen if...?" scenarios for ages 16-30, with real science and dry humor
"""
import json

import anthropic

from agent.animation import BACKGROUNDS, POSES
from agent.sounds import NAMES as SOUNDS

KIDS_PROMPT = """You write scripts for a super fun YouTube Shorts cartoon channel for kids aged 5 to 10.
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

WHAT_IF_PROMPT = """You write scripts for a viral YouTube Shorts channel for people aged 16 to 30.
Each video is a stick-figure animation of ONE big curious question, followed all the way to its
conclusion while a deadpan narrator explains what REALLY happens. Rotate between these kinds:
- "What would happen if you...?" survival and body scenarios, where the stickman is "you":
  "What if you stopped sleeping?", "How long could you survive on the Moon?",
  "What happens to your body if you drink only coffee for a week?"
- Impossible-premise stories about one guy (the stickman): "What if your reaction time was ten
  times faster than everyone else's?", "What if you could hear everyone's thoughts?",
  "What if you woke up and gravity was half as strong?" Tell it as a tiny story with a twist ending,
  using real science where it matters.
- Psychology and habits, explained with humor: "Why you procrastinate", "Why you remember
  embarrassing moments at 3 a.m.", "What doomscrolling does to your brain". Real research, no jargon.

{topic}
What makes it work:
- Scene 1 is the hook and decides whether anyone keeps watching. In ONE short breath (under 15
  words) ask the question AND tease the wildest consequence: "What if you stopped sleeping? By day
  three, you'd be seeing things." No intro, no "hey guys". Its headline is the question in 2-5 words
  ("NO SLEEP?"), its sfx is boom or sting, and the stickman reacts big (surprised, scared or point).
- Walk through it in escalating stages with time or level markers (Hour 1, Day 3, Week 2, Minus 40
  degrees...). Each stage gets worse, weirder or more surprising than the last.
- The facts are REAL science, medicine, physics, history or psychology, specific and checkable
  (NASA, medical sources, encyclopedias). No myths, no made-up numbers. If you're not sure, leave it out.
- Dry, sarcastic, relatable humor for teens and twenty-somethings: deadpan one-liners, ironic
  understatement, jokes about school, work, rent, sleep schedules, phones, the gym, group chats.
  The stickman suffers comically (faints, panics, gives up). Funny, never cruel.
- End on a twist or punchline, then one short line that makes people comment: a question
  ("Would you last past day two? Be honest.") or asking for the next "what if" in the comments.
- Advertiser-friendly: no gore or graphic injuries (keep danger cartoonish and implied),
  no self-harm or suicide, no drugs, alcohol or vaping, no sexual content, no slurs or insults
  about groups, no real people or brands, nothing people could copy to hurt themselves.
  Don't present dangerous challenges as a good idea.

Format:
- {min_words}-{max_words} spoken words in total (about 45-55 seconds), split into 6 to 8 scenes.
- narration: exactly what the narrator says. Numbers in words where it reads better, no emoji.
  You may add up to three voice directions per video, each ONE word in square brackets:
  [sarcastic], [sighs], [laughs], [whispers], [gasps], [deadpan].
- headline: the stage marker or a 1-4 word punch at the top of the scene ("DAY 3", "HOUR 17",
  "BRAIN: OFFLINE"). Use stage markers for the stages.
- shout: what the stickman says in a comic speech bubble, 1-3 words ("NOPE.", "WHY?!", "I'M FINE"),
  or empty. Use it in about half the scenes.
- emojis: 1 to 4 standard emoji showing what's happening (e.g. ["☕", "🧠"]). Only common single
  emoji every phone has: no flags, skin tones or combined emoji.
- background: one of {backgrounds}. Pick what fits; changing it between scenes is fine.
- pose: one of {poses}.
  explain = talking with his hands, point = points at the pictures, think = hand on chin,
  surprised = jumps back, cheer/jump/dance = excited, shrug = "whatever", wave = waves,
  faint = collapses flat on his back, spin = flips in the air, run = runs back and forth in a panic,
  laugh = can't stop laughing, scared = shaking with his arms up.
  Never the same pose twice in a row; save faint/run/scared for the big moments.
- stat: the key real number of the scene, shown huge on screen and counting up as it's said:
  "0.25 S", "47%", "11,000 M", "-40°C", "3 DAYS", "600,000 STEPS". Only a number the narration of
  that scene actually says, with a short unit. Use it in 2 to 4 scenes for the most striking numbers,
  otherwise empty. A scene with a stat uses at most 2 emojis.
- sfx: the sound at the start of the scene, one of {sounds}. Dramatic ones (boom, sting, heartbeat,
  clock, alarm, crowd_gasp, crickets, record_scratch) fit this channel best. Use "none" sometimes.
- Don't repeat any of these earlier topics: {used}

Reply with the script as JSON."""

PROMPTS = {"kids": KIDS_PROMPT, "young_adults": WHAT_IF_PROMPT}
TOPIC_ANY = {
    "kids": "Pick a fresh, wacky topic: weird animals, the silly human body, space, dinosaurs, food, nature or how things work.",
    "young_adults": "Pick a fresh idea: your body pushed to the limit, space, the ocean, extreme weather, "
                    "history, a superpower or impossible premise, technology, or a psychology/habits question.",
}
TOPIC_GIVEN = "Today's topic: {topic}"

SCHEMA = {
    "type": "object",
    "properties": {
        "topic": {"type": "string", "description": "A few words, e.g. 'octopus hearts'"},
        "summary": {"type": "string", "description": "One sentence stating the topic and main fact, to avoid repeats"},
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
                    "stat": {"type": "string"},
                },
                "required": ["narration", "headline", "emojis", "background", "pose", "shout", "sfx", "stat"],
                "additionalProperties": False,
            },
        },
        "title": {"type": "string", "description": "Catchy YouTube title under 70 characters that makes the audience click, may use one emoji, ends with #Shorts"},
        "description": {"type": "string", "description": "1-2 sentences for the YouTube description"},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "5-10 tags"},
    },
    "required": ["topic", "summary", "scenes", "title", "description", "tags"],
    "additionalProperties": False,
}


def write_fact(config: dict, used: list[str], topic: str | None = None) -> dict:
    s = config["facts"]
    audience = s.get("audience", "kids")
    prompt = PROMPTS[audience].format(
        topic=TOPIC_GIVEN.format(topic=topic) if topic else TOPIC_ANY[audience],
        min_words=s["min_words"],
        max_words=s["max_words"],
        backgrounds=", ".join(BACKGROUNDS),
        poses=", ".join(POSES),
        sounds=", ".join(SOUNDS),
        used="; ".join(used[-80:]) or "none yet",
    )
    script = _ask(s, prompt, SCHEMA)
    script["scenes"] = [sc for sc in script["scenes"] if sc["narration"].strip()][:8]
    for sc in script["scenes"]:
        sc["emojis"] = sc["emojis"][:4] or ["⭐"]
    if len(script["scenes"]) < 2:
        raise RuntimeError("The script came back with too few scenes.")
    return fact_check(s, script)


def _ask(s: dict, prompt: str, schema: dict) -> dict:
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    resp = client.messages.create(
        model=s["model"],
        max_tokens=16000,
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": prompt}],
    )
    if resp.stop_reason != "end_turn":
        raise RuntimeError(f"Script request stopped early: {resp.stop_reason}")
    return json.loads(next(b.text for b in resp.content if b.type == "text"))


CHECK_PROMPT = """You are the fact-checker for a YouTube Shorts channel. Below is the narration of today's
video, one line per scene. Check every factual claim (numbers, times, causes, effects, history, names).
Jokes, exaggerated reactions and obvious sarcasm are fine and are not claims.

- If a claim is wrong, outdated, a common myth, or stated with more certainty than the evidence allows,
  rewrite just that part so it's accurate (use "about", "can", "up to" where the real answer varies).
- If a claim can't be fixed simply, remove it and keep the sentence flowing.
- Keep the style, the jokes, the voice directions in [brackets], and roughly the same length per scene.
- Don't change scenes that are already accurate.

Topic: {summary}

{lines}

Reply as JSON: the narration for every scene in the same order (same number of scenes: {n}),
the on-screen number for every scene (keep it, fix it to match your corrected narration, or empty
it if the number is gone), and a short note for each change you made (empty list if nothing needed fixing)."""

CHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "narrations": {"type": "array", "items": {"type": "string"}},
        "stats": {"type": "array", "items": {"type": "string"}},
        "changes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["narrations", "stats", "changes"],
    "additionalProperties": False,
}


def fact_check(s: dict, script: dict) -> dict:
    """A second, separate pass that fixes or removes shaky claims before anything is voiced."""
    scenes = script["scenes"]
    lines = "\n".join(f"Scene {i + 1}: {sc['narration']}" + (f"  [on-screen number: {sc['stat']}]" if sc.get("stat") else "")
                      for i, sc in enumerate(scenes))
    try:
        result = _ask(s, CHECK_PROMPT.format(summary=script["summary"], lines=lines, n=len(scenes)), CHECK_SCHEMA)
    except Exception as err:  # the check failing shouldn't stop the day's video
        print(f"Fact-check didn't run: {err}")
        script["fact_check"] = ["not run"]
        return script
    if len(result["narrations"]) == len(scenes):
        for sc, text in zip(scenes, result["narrations"]):
            if text.strip():
                sc["narration"] = text.strip()
    if len(result.get("stats", [])) == len(scenes):
        for sc, stat in zip(scenes, result["stats"]):
            sc["stat"] = stat.strip()
    script["fact_check"] = result["changes"]
    return script
