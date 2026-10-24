"""Run once on your own computer to let the agent upload to your channel.

    pip install google-auth-oauthlib
    python tools/get_youtube_token.py path/to/client_secret.json

A browser window opens, you sign in to the Google account that owns the channel, and the script
prints a refresh token. Save it as the YOUTUBE_REFRESH_TOKEN secret. Don't paste it anywhere else.
"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

if __name__ == "__main__":
    secrets_file = sys.argv[1] if len(sys.argv) > 1 else "client_secret.json"
    flow = InstalledAppFlow.from_client_secrets_file(secrets_file, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    client = json.load(open(secrets_file))["installed"]
    print("\nAdd these three as GitHub repository secrets:\n")
    print(f"YOUTUBE_CLIENT_ID      = {client['client_id']}")
    print(f"YOUTUBE_CLIENT_SECRET  = {client['client_secret']}")
    print(f"YOUTUBE_REFRESH_TOKEN  = {creds.refresh_token}")
