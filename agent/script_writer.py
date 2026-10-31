"""Asks Claude to write an original Reddit-style story for the narrator to read."""
import json

import anthropic

PROMPT = """You write narration for a YouTube Shorts "Reddit story time" channel. Each video is a made-up
story told like a viral Reddit post, read aloud by a narrator over video game footage.

{idea}
Rules:
- The story is ORIGINAL fiction. Never retell or copy a real Reddit post, news story or real person.
- First person, casual, like someone typing a post ("So this happened last week...").
- The post title is the hook and is read aloud first: make it impossible to scroll past
  (e.g. "Am I wrong for...", "My sister tried to...", "Today I messed up by..."). Under 100 characters.
- The story is {min_words}-{max_words} words: hook in the first sentence, drama that escalates,
  and a satisfying twist or payoff at the end. You may end with a short question that gets viewers commenting.
- Advertiser-friendly: no sexual content, graphic violence, self-harm, drugs, slurs, swearing,
  or real brands and people. Petty drama, family feuds, roommates, coworkers, weddings, neighbours,
  and harmless revenge all work great.
- Everything is read aloud, so write it as it should be spoken: no abbreviations like AITA or TIFU,
  no emojis, hashtags or edit notes.
- Don't repeat any of these earlier stories: {used}

Reply with the finished story as JSON."""

IDEA_ANY = "Come up with a fresh story idea."
IDEA_GIVEN = "Write a story based on this idea: {idea}"

# Structured outputs constrain the reply to this schema, so quotes in the story can't break the JSON.
STORY_SCHEMA = {
    "type": "object",
    "properties": {
        "post_title": {"type": "string", "description": "The Reddit-style post title, read aloud as the hook"},
        "story": {"type": "string", "description": "The post body, read aloud after the title"},
        "summary": {"type": "string", "description": "One sentence describing the story, to avoid repeats"},
        "title": {"type": "string", "description": "YouTube title under 80 characters, ends with #Shorts"},
        "description": {"type": "string", "description": "1-2 sentence YouTube description"},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "5-10 tags"},
    },
    "required": ["post_title", "story", "summary", "title", "description", "tags"],
    "additionalProperties": False,
}


DESCRIBE_PROMPT = """Here is a story for a YouTube Shorts "Reddit story time" channel, read aloud over
video game footage. Don't change the story. Write the YouTube details for it.

Post title: {post_title}

{story}

Reply as JSON."""

DESCRIBE_SCHEMA = {
    "type": "object",
    "properties": {k: STORY_SCHEMA["properties"][k] for k in ("summary", "title", "description", "tags")},
    "required": ["summary", "title", "description", "tags"],
    "additionalProperties": False,
}


def _ask(config: dict, prompt: str, schema: dict) -> dict:
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    resp = client.messages.create(
        model=config["story"]["model"],
        max_tokens=16000,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": prompt}],
    )
    if resp.stop_reason != "end_turn":
        raise RuntimeError(f"Story request stopped early: {resp.stop_reason}")
    return json.loads(next(b.text for b in resp.content if b.type == "text"))


def describe(config: dict, post_title: str, story: str) -> dict:
    """YouTube title, description, tags and a summary for a story someone wrote themselves."""
    return _ask(config, DESCRIBE_PROMPT.format(post_title=post_title, story=story), DESCRIBE_SCHEMA)


def write_story(config: dict, used: list[str], idea: str | None = None) -> dict:
    s = config["story"]
    prompt = PROMPT.format(
        idea=IDEA_GIVEN.format(idea=idea) if idea else IDEA_ANY,
        min_words=s["min_words"],
        max_words=s["max_words"],
        used="; ".join(used[-50:]) or "none yet",
    )
    return _ask(config, prompt, STORY_SCHEMA)
