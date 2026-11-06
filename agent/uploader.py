"""Uploads the finished Short with the YouTube Data API, using a stored OAuth refresh token."""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def publish_time(yt: dict, now: datetime | None = None) -> str | None:
    """The next publish time from config (at least 30 minutes away), as UTC for the API."""
    times = yt.get("publish_times") or []
    if not times:
        return None
    tz = ZoneInfo(yt.get("timezone", "America/New_York"))
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    slots = []
    for day in (0, 1):
        for t in times:
            h, m = map(int, t.split(":"))
            slot = (now + timedelta(days=day)).replace(hour=h, minute=m, second=0, microsecond=0)
            if slot - now >= timedelta(minutes=30):
                slots.append(slot)
    return min(slots).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def upload(video: Path, script: dict, config: dict) -> str:
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    youtube = build("youtube", "v3", credentials=creds)
    yt = config["youtube"]
    title = script["title"] if "#shorts" in script["title"].lower() else f"{script['title']} #Shorts"
    body = {
        "snippet": {
            "title": title[:100],
            "description": f"{script['description']}\n\n{yt.get('hashtags', '#Shorts')}",
            "tags": script.get("tags", [])[:15],
            "categoryId": yt["category_id"],
        },
        "status": {"privacyStatus": yt["privacy"], "selfDeclaredMadeForKids": yt.get("made_for_kids", True),
                   "containsSyntheticMedia": False},
    }
    when = None
    if os.environ.get("PUBLISH_AT", "").lower() == "now":  # public the moment it's uploaded
        body["status"]["privacyStatus"] = "public"
    elif os.environ.get("PUBLISH_AT"):  # a hand-started run that should still go public, e.g. "20:00"
        when = publish_time({**yt, "publish_times": [os.environ["PUBLISH_AT"]]})
    elif os.environ.get("PUBLISH_ON_SCHEDULE") == "true":
        when = publish_time(yt)
    if when:  # YouTube keeps it private and makes it public by itself at this time
        body["status"].update({"privacyStatus": "private", "publishAt": when})
        print(f"Will go public at {when} (UTC)")
    request = youtube.videos().insert(
        part="snippet,status", body=body,
        media_body=MediaFileUpload(str(video), mimetype="video/mp4", resumable=True),
    )
    response = None
    while response is None:
        _, response = request.next_chunk()
    return f"https://youtube.com/shorts/{response['id']}"
