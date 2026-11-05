# Daily fun-fact Shorts for kids

Every day this agent:

1. **Writes a fun fact for kids** (ages 5-10) with Claude: true, easy to check, super friendly,
   split into 4-6 little scenes. Topics never repeat (`history.json`).
2. **Narrates it** with the channel's AI narrator voice (ElevenLabs), with word-by-word timing.
3. **Animates it**: our stickman host in a red cap acts out each scene (waving, pointing,
   jumping, thinking) in front of bright backgrounds (sky, underwater, space, forest, desert, snow,
   night, classroom), with the thing the fact is about shown as big pictures (Noto Emoji, Apache 2.0)
   and a headline at the top. His mouth moves as the narrator talks. Captions light up word by word.
   Everything is drawn by code, so the host looks the same in every video.
4. **Uploads it** to your channel, marked **Made for kids** (comments and personalised ads are off,
   as YouTube requires for kids' videos).

It runs on a schedule in GitHub Actions, so nothing needs to stay on in your house.

## One-time setup

### 1. API keys
| Secret name | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `ELEVENLABS_API_KEY` | elevenlabs.io → Profile → API key (Starter plan is enough) |

To pick the narrator by ear: Actions tab → **Voice samples** → **Run workflow**, then download
*voice-samples* from the finished run and listen. Put your favourite's `voice_id` and
`library_owner_id` (from `voices.txt`) under `narrator` in `config.yaml`.
Otherwise the narrator voice is designed automatically from its description in `config.yaml` (`narrator`)
and saved in `voices.json`. Change the description and a new voice is made on the next run.

### 2. YouTube access
1. In console.cloud.google.com create a project and enable **YouTube Data API v3**.
2. Under **OAuth consent screen** choose *External* and add yourself as a test user. Then publish
   the app ("In production") so the sign-in doesn't expire after 7 days.
3. Under **Credentials** create an **OAuth client ID** of type *Desktop app* and download the JSON.
4. On your computer run `python tools/get_youtube_token.py path/to/that.json`, sign in with the
   Google account that owns the channel, and it prints three values.

### 3. Add the secrets
In the GitHub repo go to **Settings → Secrets and variables → Actions** and add the two API keys and
`YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`.
Never paste them in a chat or commit them.

## Running it
- **Test without posting:** Actions tab → *Daily Short* → *Run workflow*. *Dry run* is ticked by default.
  Type a *Topic* to choose today's fact, or leave it empty. The finished video is attached to the run under *Artifacts*.
- **Twice a day:** it runs automatically at 11:00 and 19:00 UTC, and YouTube publishes each
  Short at the next time in `youtube.publish_times` in `config.yaml` (9am and 5pm Eastern).
  Change those times there, and the `cron` lines in `.github/workflows/daily-short.yml`
  so each run starts a few hours before its time.

## Private vs public
Uploads start as **private** (`youtube.privacy` in `config.yaml`), so you can watch each one in
YouTube Studio and press Publish. YouTube also keeps API uploads private until your Google Cloud
project passes their free API compliance audit (search "YouTube API Services audit and quota
extension form"). Once it passes and you like the output, set `privacy: public` and it's fully hands-off.

## Run locally
```
pip install -r requirements.txt   # also needs ffmpeg and the Noto Color Emoji font
export ANTHROPIC_API_KEY=... ELEVENLABS_API_KEY=...
python -m agent.main --dry-run --topic "why cats purr"   # video lands in output/<date>/short.mp4
python tools/preview.py examples/octopus.json            # silent preview, no API keys needed
```

Fonts: Fredoka and Montserrat (SIL Open Font License, `assets/fonts/OFL*.txt`).

Looks (`video.look`): `cinematic` draws silhouettes against glowing layered skies with slow camera push-ins,
cross-fades, film grain and a vignette (`agent/cinematic.py`); `cartoon` is the bright kids look (`agent/animation.py`).
Preview either without API keys: `python tools/preview.py examples/space.json cinematic`.
