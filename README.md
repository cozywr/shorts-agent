# Daily cartoon-parody Shorts agent

Every day this agent:

1. **Writes a parody** of a famous movie or TV scene (Claude picks one it hasn't done yet) starring our
   original characters: Pickle Pete, Big Mama Muffin, Sir Waddles and Zip (see `config.yaml`).
2. **Voices it** with each character's own AI voice (ElevenLabs).
3. **Draws each shot** as a vertical cartoon frame (OpenAI image generation).
   It also draws a second version with the speaker's mouth open, and the video flaps between
   the two in time with the voice, so the character visibly talks (`video.lip_flaps` in `config.yaml`).
4. **Edits the Short**: 1080x1920, slow zoom on each frame, captions, under 60 seconds (ffmpeg).
5. **Uploads it** to your channel through the YouTube Data API.

It runs on a schedule in GitHub Actions, so nothing needs to stay on in your house.

## One-time setup

### 1. API keys (each is a paid account; rough total ~$20–30/month for one Short a day)
| Secret name | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `OPENAI_API_KEY` | platform.openai.com → API keys |
| `ELEVENLABS_API_KEY` | elevenlabs.io → Profile → API key (Starter plan is enough) |

### 2. Character voices
Nothing to do. On the first run the agent designs a brand-new voice for each character in
ElevenLabs from the `voice` description in `config.yaml`, and saves their IDs in `voices.json`.
Your ElevenLabs API key needs the Text to Speech, Voices (write) and Voice Generation permissions.
To change a voice, edit its description and delete that character's line from `voices.json`.

### 3. YouTube access
1. In console.cloud.google.com create a project and enable **YouTube Data API v3**.
2. Under **OAuth consent screen** choose *External* and add yourself as a test user. Then publish
   the app ("In production") so the sign-in doesn't expire after 7 days.
3. Under **Credentials** create an **OAuth client ID** of type *Desktop app* and download the JSON.
4. On your computer run `python tools/get_youtube_token.py path/to/that.json`, sign in with the
   Google account that owns the channel, and it prints three values.

### 4. Add the secrets
In the GitHub repo go to **Settings → Secrets and variables → Actions** and add all six values:
the three API keys and `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`.
Never paste them in a chat or commit them.

## Running it
- **Test without posting:** Actions tab → *Daily Short* → *Run workflow* → tick *dry run*.
  The finished video is attached to the run under *Artifacts*.
- **Daily:** it runs automatically at 16:00 UTC. Change the `cron` line in
  `.github/workflows/daily-short.yml` to pick another time.

## Private vs public
Uploads start as **private** (`youtube.privacy` in `config.yaml`), so you can watch each one in
YouTube Studio and press Publish. YouTube also keeps API uploads private until your Google Cloud
project passes their free API compliance audit (search "YouTube API Services audit and quota
extension form"). Once it passes and you like the output, set `privacy: public` and it's fully hands-off.

## Run locally
```
pip install -r requirements.txt   # also needs ffmpeg
export ANTHROPIC_API_KEY=... OPENAI_API_KEY=... ELEVENLABS_API_KEY=...
python -m agent.main --dry-run    # video lands in output/<date>/short.mp4
```
