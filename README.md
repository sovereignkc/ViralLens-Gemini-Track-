# ViralLens

**ChatGPT waits for you to find the videos. ViralLens finds the outliers itself.**

ViralLens is a Gemini agent for YouTube creators. You type one sentence about yourself and what you make. The agent then:
1. Searches YouTube for videos in your niche.
2. Ranks the **outliers**: videos with high views relative to the channel's size.
3. **Watches** the top picks with Gemini's native video understanding.
4. Writes 5 video ideas built around your real life.
5. Has a skeptical second Gemini pass score each idea 1–10 for whether it feels human, and rewrites any idea that scores below 7.

Built for the **ACM AI "Five Nights with AI" hackathon, Track 3 (Best Use of Google Gemini)**.

## Features
- **Agent mode (default).** Gemini uses function calling to decide which tool to call and when: `search_videos`, `get_stats`, `analyze_video`, `write_ideas` and `rewrite_idea`. Every step streams live to the page.
- **Outlier detection.** Uses YouTube Data API v3 stats; outlier ratio = views ÷ channel subscribers.
- **Native video analysis.** Each YouTube URL is passed to Gemini as `file_data`. Gemini returns a timestamped breakdown: hook (first 5 seconds), structure and pacing, format, emotional trigger, title/thumbnail pattern, and why it went viral. Click a timestamp to jump the embedded player.
- **Ideas built for you.**
  - Three creator tiers: 📱 Just starting, 🎙️ Growing, 🎬 Big channel. Ideas stay realistic for that gear and time budget.
  - Your story feeds into every idea.
  - Common AI clichés are banned in the prompt.
- **"Feels human?" check.** Each idea gets a 1–10 score, with the exact AI-sounding phrases flagged and a reason.
- **2-week posting calendar** and an **inferred audience profile**. The profile is labelled as AI-inferred, not real analytics.
- **Paste-links mode.** Analyze up to 3 specific videos instead of searching.

## Quick start
Requirements: Python 3.10+, a Gemini API key, and a YouTube Data API v3 key.

```bash
git clone https://github.com/sovereignkc/ViralLens-Gemini-Track-.git
cd ViralLens-Gemini-Track-
cp .env.example .env      # then fill in both keys
./run.sh                  # creates .venv, installs requirements, starts the server
```
Open http://127.0.0.1:8000.

### Getting the keys
- **Gemini:** create a key at https://aistudio.google.com/apikey. If the project uses prepay billing, add credits; a spend cap alone isn't enough.
- **YouTube Data API v3:**
  1. In Google Cloud Console, enable **YouTube Data API v3**.
  2. Go to Credentials → Create credentials → **API key**. You need a standard key, which starts with `AIza`. Gemini's newer `AQ.` keys don't work with YouTube.
  3. Under API restrictions, make sure the key is allowed to use YouTube Data API v3.

Without a YouTube key the agent can't search, but paste-links mode still works.

### Manual run (without run.sh)
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export GEMINI_API_KEY=... YOUTUBE_API_KEY=...
.venv/bin/uvicorn main:app --port 8000
```

## How it works
```
one sentence + tier
      │
      ▼
Gemini agent (function calling loop, streamed to the page)
  ├─ search_videos(query)      → YouTube Data API search, ordered by views
  ├─ get_stats(video_ids)      → views, likes, date, subs, outlier ratio
  ├─ analyze_video(video_id)   → Gemini watches the video, returns timestamped JSON
  ├─ write_ideas()             → pattern, audience, 5 ideas, calendar + human scores
  └─ rewrite_idea(i, feedback) → rewrite and re-score until every idea is ≥ 7
```

| File | What it is |
|---|---|
| `main.py` | FastAPI backend: schemas, prompts, tools, agent loop, paste-links flow |
| `static/index.html` | Single-page UI (Tailwind) |
| `PROMPTS.md` | Prompt styles and settings to try in Google AI Studio |
| `DEMO.md` | 3-minute demo script and judge Q&A |

### Reliability
- **Fallback.** Every Gemini call has a timeout and falls through a list of models (`gemini-3.5-flash` → `3.7-flash` → `3-flash-preview` → `3.8-flash`) on 503, 429, 402 or a timeout.
- **Caching.** Video breakdowns and idea sets are saved to `cache/`, so repeat runs are fast.

### Settings
| Call | Temperature | Thinking level | Media resolution |
|---|---|---|---|
| Video analysis | 0.4 | low | low |
| Ideas | 0.9 | medium | – |
| Human check | 0.2 | low | – |
| Agent loop | 0.4 | low | – |

Set `GEMINI_MODEL` to override the default model.

## API
| Endpoint | Purpose |
|---|---|
| `POST /api/agent` `{about, tier}` | Agent mode (SSE stream) |
| `POST /api/run` `{about, urls[], tier}` | Paste-links mode (SSE stream) |
| `POST /api/chat` `{messages[], context}` | Voice/chat coach backend (experimental) |
| `GET /api/health` | Status |

## Notes
- The audience profile is inferred by Gemini from the videos. It is not channel analytics.
- A full agent run is roughly 100–150k tokens on a flash model.
