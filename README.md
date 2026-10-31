# Daily story-time Shorts agent

Every day this agent:

1. **Takes your next story** from the `stories/` folder, word for word (see "Adding your stories").
   If `story.auto_write` is on in `config.yaml` and you've run out, Claude writes an original one instead.
2. **Narrates it** with the channel's own AI narrator voice (ElevenLabs), with word-by-word timing.
3. **Edits the Short** (ffmpeg): a random slice of *your own* gameplay recordings, cropped to
   1080x1920, a post card with the title at the start, then big captions that pop in word by word.
   Up to 3 minutes.
4. **Uploads it** to your channel through the YouTube Data API.

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

After uploading a new recording, list the parts that are real gameplay under `gameplay.good_parts`
in `config.yaml` (minutes:seconds), so menus and end screens never show. Unlisted clips skip
their first and last minute.

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

## Adding your stories
1. Open the repo on GitHub and click into the **stories** folder.
2. Click **Add file → Create new file**.
3. Name it ending in `.txt`, e.g. `01-roommate-cake.txt` (stories are used in name order).
4. Type the **title on the first line**, then the story on the lines below it.
5. Click **Commit changes**, then **Commit changes** again.

Each story is posted once, then moves to `stories/used/`. A test (dry) run doesn't use it up.

## Running it
- **Test without posting:** Actions tab → *Daily Short* → *Run workflow*. *Dry run* is ticked by default.
  It uses your next story. The finished video is attached to the run under *Artifacts*.
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
