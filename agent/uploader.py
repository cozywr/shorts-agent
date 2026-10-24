"""Uploads the finished Short with the YouTube Data API, using a stored OAuth refresh token."""
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


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
            "description": f"{script['description']}\n\nParody. All characters are original.\n#Shorts",
            "tags": script.get("tags", [])[:15],
            "categoryId": yt["category_id"],
        },
        "status": {"privacyStatus": yt["privacy"], "selfDeclaredMadeForKids": False},
    }
    request = youtube.videos().insert(
        part="snippet,status", body=body,
        media_body=MediaFileUpload(str(video), mimetype="video/mp4", resumable=True),
    )
    response = None
    while response is None:
        _, response = request.next_chunk()
    return f"https://youtube.com/shorts/{response['id']}"
