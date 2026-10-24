# Daily story-time Shorts agent

Every day this agent:

1. **Writes a story** (Claude): an original, made-up story in the style of a viral Reddit post,
   with a hook title and a twist. Never a copy of a real post.
2. **Narrates it** with the channel's own AI narrator voice (ElevenLabs), with word-by-word timing.
3. **Edits the Short** (ffmpeg): a random slice of *your own* gameplay recordings, cropped to
   1080x1920, a post card with the title at the start, then big captions that pop in word by word.
   Under 60 seconds.
4. **Uploads it** to your channel through the YouTube Data API.

It runs on a schedule in GitHub Actions, so nothing needs to stay on in your house.

## One-time setup

### 1. API keys
| Secret name | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `ELEVENLABS_API_KEY` | elevenlabs.io → Profile → API key (Starter plan is enough) |

The narrator voice is designed automatically on the first run and saved in `voices.json`
(see `narrator` in `config.yaml` to change it).

### 2. Gameplay clips
Use gameplay **you recorded yourself** (other people's footage can get your videos claimed or taken down).
Longer recordings are best: each video uses a random ~1 minute slice. Landscape or vertical both work.

1. In the repo on GitHub, click **Releases** (right-hand side) → **Create a new release**
   (or **Draft a new release**).
2. Click **Choose a tag**, type `gameplay`, and click **Create new tag: gameplay on publish**.
3. Title it `gameplay`.
4. Drag your video files (mp4, mov, mkv, webm) into the box that says *Attach binaries*.
   Each file can be up to 2 GB. Wait until every file finishes uploading.
5. Click **Publish release**.

To add more later: open the release, click the pencil (Edit), drag more files in, and click **Update release**.
Small clips (under 25 MB) can also go in a `gameplay/` folder in the repo instead.

### 3. YouTube access
1. In console.cloud.google.com create a project and enable **YouTube Data API v3**.
2. Under **OAuth consent screen** choose *External* and add yourself as a test user. Then publish
   the app ("In production") so the sign-in doesn't expire after 7 days.
3. Under **Credentials** create an **OAuth client ID** of type *Desktop app* and download the JSON.
4. On your computer run `python tools/get_youtube_token.py path/to/that.json`, sign in with the
   Google account that owns the channel, and it prints three values.

### 4. Add the secrets
In the GitHub repo go to **Settings → Secrets and variables → Actions** and add the two API keys and
`YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`.
Never paste them in a chat or commit them.

## Running it
- **Test without posting:** Actions tab → *Daily Short* → *Run workflow*. *Dry run* is ticked by default.
  Type an idea in the *Story idea* box (e.g. `a roommate who labels every single grape`) or leave it
  empty and Claude comes up with one. The finished video is attached to the run under *Artifacts*.
- **Daily:** it runs automatically at 16:00 UTC. Change the `cron` line in
  `.github/workflows/daily-short.yml` to pick another time.

## Private vs public
Uploads start as **private** (`youtube.privacy` in `config.yaml`), so you can watch each one in
YouTube Studio and press Publish. YouTube also keeps API uploads private until your Google Cloud
project passes their free API compliance audit (search "YouTube API Services audit and quota
extension form"). Once it passes and you like the output, set `privacy: public` and it's fully hands-off.
Each upload is marked as containing AI-generated content and says in the description that the story is fiction.

## Run locally
```
pip install -r requirements.txt   # also needs ffmpeg and the DejaVu fonts
mkdir gameplay && cp ~/my-recording.mp4 gameplay/
export ANTHROPIC_API_KEY=... ELEVENLABS_API_KEY=...
python -m agent.main --dry-run    # video lands in output/<date>/short.mp4
```
