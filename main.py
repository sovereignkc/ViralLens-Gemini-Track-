"""ViralLens — Gemini analyzes viral YouTube videos and generates fresh ideas.
Run: ./run.sh   (reads GEMINI_API_KEY, falls back to GEMINI_PAID_API_KEY / GEMINI_FREE_API_KEY)
"""
import asyncio, hashlib, json, os, re
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent
CACHE = ROOT / "cache"; CACHE.mkdir(exist_ok=True)
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
# tried in order on 503/429/timeout — busy models are common during hackathons
FALLBACKS = list(dict.fromkeys(["gemini-3.5-flash", "gemini-3.7-flash", "gemini-3-flash-preview", MODEL]))
YT_KEY = os.environ.get("YOUTUBE_API_KEY")
KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_PAID_API_KEY") or os.environ.get("GEMINI_FREE_API_KEY")
client = genai.Client(api_key=KEY) if KEY else None


# ---------------------------------------------------------------- schemas
class Moment(BaseModel):
    timestamp: str = Field(description="mm:ss in the video")
    note: str


class Section(BaseModel):
    summary: str
    moments: list[Moment]


class VideoAnalysis(BaseModel):
    hook: Section = Field(description="What happens in the first 5 seconds and why it stops the scroll")
    structure_pacing: Section = Field(description="Beat-by-beat structure, cut frequency, pacing changes")
    format: Section = Field(description="Format/genre: talking head, listicle, challenge, tutorial, etc.")
    emotional_trigger: Section = Field(description="Primary emotion(s) exploited: curiosity, FOMO, awe, humor...")
    title_thumbnail: Section = Field(description="Title and thumbnail pattern; infer from title text and opening frames")
    why_viral: Section = Field(description="Most likely reasons it went viral")


class Idea(BaseModel):
    title: str
    hook_script: str = Field(description="Word-for-word script for the first 5 seconds, with on-screen action")
    outline: list[str]
    borrowed_pattern: str = Field(description="Which element of the viral pattern this borrows and from which video")


class Audience(BaseModel):
    age_range: str
    interests: list[str]
    why_they_watch: str
    where_they_hang_out: list[str] = Field(description="Platforms/communities this audience likely uses")
    evidence: list[str] = Field(description="What in the videos (with mm:ss) suggests this")


class PostSlot(BaseModel):
    day: str = Field(description="e.g. 'Week 1 · Tue'")
    idea_index: int = Field(description="1-5, which idea to post")
    platform: str = Field(description="YouTube long-form, Short, TikTok, Reels...")
    action: str = Field(description="What to post, incl. recycling hooks as Shorts")


class PatternReport(BaseModel):
    viral_pattern: str = Field(description="One-paragraph shared formula across the videos")
    shared_elements: list[str]
    audience: Audience = Field(description="INFERRED audience profile from the videos only — not real analytics")
    ideas: list[Idea] = Field(description="Exactly 5 ideas")
    calendar: list[PostSlot] = Field(description="2-week posting plan, 6-8 slots")


class HumanScore(BaseModel):
    idea_index: int
    score: int = Field(description="1-10, would this feel made by a real human creator?")
    flags: list[str] = Field(description="Exact AI-sounding phrases or generic choices; empty if none")
    reason: str


class AuthCheck(BaseModel):
    scores: list[HumanScore]


ANALYZE_SYS = ("You are a short-form and YouTube growth strategist who reverse-engineers viral videos. "
               "Watch the video carefully. Be specific and concrete; cite real mm:ss timestamps you observed. "
               "Never invent content you did not see or hear.")
ANALYZE_PROMPT = "Video title: {title}\nChannel: {channel}\nBreak this video down into the requested JSON."
TIERS = {
    "starting": "Starting out (0–1K subs): one person, a phone, natural light, free editing apps, under 2 hours to film. "
                "No guests, no locations they'd need permission for, no budget. Lean on personality and honesty.",
    "growing": "Growing (1K–100K subs): solo or a friend helping, a decent mic and camera, can do small props, "
               "simple outdoor shoots and occasional collabs. ~1 day per video.",
    "established": "Established (100K+): small crew, editor, budget for props/travel/guests, can do series and stunts.",
}
IDEAS_SYS = """You are a creative director who writes like a real creator, not a marketer.
Find the shared viral pattern across the breakdowns and adapt it to this creator's niche, tier and real life.

Rules:
- Ideas must be fresh (not copies) and REALISTIC for the creator's tier and equipment.
- Build every idea around the creator's own story details. Use specific personal details, numbers and real stakes
  (money, grades, embarrassment, a deadline) — never generic "you".
- Hooks are written the way a person actually talks out loud: contractions, fragments, a little messy. Must fit in 5 seconds.
- BANNED: "in today's fast-paced world", "game-changer", "unlock", "level up", "elevate", "dive in", "journey",
  "secret sauce", "hacks that will change your life", "you won't believe", "ultimate guide", emoji spam,
  numbered-listicle filler, and any sentence that could appear in a press release.
- The audience profile is INFERRED from the videos only. Be honest and say what's uncertain.
- Calendar: a realistic 2-week plan for this tier, including recycling the strongest hook as a Short."""
AUTH_SYS = """You are a skeptical viewer who has seen a thousand AI-generated video ideas. For each idea, score 1-10
"would this feel like a real human made it?" 10 = unmistakably a real person's life; 1 = generic AI slop.
Flag the exact phrases that sound AI-written or generic, and say why in one blunt sentence. Be harsh; most AI ideas
deserve 4-7."""
THINKING = {"analyze": types.ThinkingLevel.LOW, "ideas": types.ThinkingLevel.MEDIUM, "auth": types.ThinkingLevel.LOW}


# ---------------------------------------------------------------- helpers
def video_id(url: str) -> str | None:
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


async def oembed(url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10) as h:
            r = await h.get("https://www.youtube.com/oembed", params={"url": url, "format": "json"})
            if r.status_code == 200:
                d = r.json(); return {"title": d.get("title", ""), "channel": d.get("author_name", "")}
    except httpx.HTTPError:
        pass
    return {"title": "", "channel": ""}


async def generate(timeout: float, models: list[str] | None = None, **kw):
    """generate_content with model fallback. Busy/slow model -> next model immediately.
    Hard cap: the whole chain never takes more than ~1.5x `timeout`. Returns (response, model_used)."""
    loop = asyncio.get_running_loop(); deadline = loop.time() + timeout * 1.5
    last = None
    for model in models or FALLBACKS:
        left = deadline - loop.time()
        if left < 5:
            break
        try:
            return await asyncio.wait_for(client.aio.models.generate_content(model=model, **kw), timeout=min(timeout, left)), model
        except Exception as e:
            last = e; msg = str(e)
            if not (isinstance(e, asyncio.TimeoutError) or any(c in msg for c in ("402", "503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "500"))):
                raise
    raise last or asyncio.TimeoutError("Gemini took too long")


async def find_videos(about: str, n: int = 3) -> tuple[list[str], str]:
    """Find popular videos for the creator's niche. YouTube Data API if a key is set, else Gemini + Google Search."""
    if YT_KEY:
        q = re.split(r"\s[—–-]\s|[,.;:]", about)[0][:80]
        try:  # turn "Study tips — I'm a broke student who lifts" into a good search query
            r0, _ = await generate(15, contents=f"Write a 2-5 word YouTube search query for popular videos in this creator's niche. Reply with only the query.\nCreator: {about}",
                                   config=types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)))
            q = (r0.text or "").strip().strip('"').splitlines()[0][:80] or q
        except Exception:
            pass
        async with httpx.AsyncClient(timeout=15) as h:
            r = await h.get("https://www.googleapis.com/youtube/v3/search", params={
                "part": "snippet", "q": q, "type": "video", "order": "viewCount", "maxResults": n,
                "videoDuration": "medium", "relevanceLanguage": "en", "key": YT_KEY})
            r.raise_for_status()
            return [f"https://www.youtube.com/watch?v={i['id']['videoId']}" for i in r.json().get("items", [])], f'YouTube search "{q}" (top by views)'
    resp, _ = await generate(60, contents=(
        f"A creator describes themselves: \"{about}\". Use Google Search to find {n} real, highly-viewed YouTube videos "
        "in their niche that they could learn from (3-15 min preferred). Reply with one full youtube.com/watch URL per line, nothing else."),
        config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]))
    ids = list(dict.fromkeys(re.findall(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})", resp.text or "")))
    return [f"https://www.youtube.com/watch?v={i}" for i in ids[:n]], "Gemini + Google Search"


def _cache(kind: str, key: str) -> Path:
    return CACHE / f"{kind}_{hashlib.sha1(key.encode()).hexdigest()[:16]}.json"


def _err(e: Exception) -> str:
    s = str(e)
    if "402" in s or "credits are depleted" in s: return "Gemini credits depleted (402) — top up at ai.studio/projects"
    if "429" in s: return "Gemini quota/rate limit hit (429)"
    if isinstance(e, asyncio.TimeoutError): return "Gemini took too long — try again or paste a shorter video"
    return f"{type(e).__name__}: {s[:200]}"


async def analyze(url: str, meta: dict) -> dict:
    vid = video_id(url)
    p = _cache("video", vid or url)
    if p.exists():
        return {**json.loads(p.read_text()), "cached": True}
    if not client:
        raise RuntimeError("no Gemini API key set")
    resp, used = await generate(
        100,
        contents=types.Content(parts=[
            types.Part(file_data=types.FileData(file_uri=f"https://www.youtube.com/watch?v={vid}" if vid else url)),
            types.Part(text=ANALYZE_PROMPT.format(**meta))]),
        config=types.GenerateContentConfig(
            system_instruction=ANALYZE_SYS, temperature=0.4, response_mime_type="application/json",
            response_schema=VideoAnalysis, thinking_config=types.ThinkingConfig(thinking_level=THINKING["analyze"]),
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_LOW))
    out = {"analysis": json.loads(resp.text), "model": used, "usage": resp.usage_metadata.model_dump() if resp.usage_metadata else None}
    p.write_text(json.dumps(out))
    return out


def _cfg(kind, sys, temp, schema):
    return types.GenerateContentConfig(system_instruction=sys, temperature=temp, response_mime_type="application/json",
                                       response_schema=schema, thinking_config=types.ThinkingConfig(thinking_level=THINKING[kind]))


async def ideas(niche: str, tier: str, story: str, videos: list[dict]) -> dict:
    payload = json.dumps([{"title": v["title"], "channel": v["channel"], "analysis": v["analysis"]} for v in videos])
    p = _cache("ideas", "|".join([niche.lower().strip(), tier, story.strip(), payload]))
    if p.exists():
        return json.loads(p.read_text())
    prompt = (f"Creator niche: {niche}\nCreator tier: {TIERS.get(tier, TIERS['starting'])}\n"
              f"Your story (the creator's real life — build ideas around this): {story or '(not given — still be specific)'}\n\n"
              f"Video breakdowns:\n{payload}\n\nReturn the viral pattern, inferred audience, exactly 5 ideas and the calendar.")
    resp, used = await generate(80, contents=prompt, config=_cfg("ideas", IDEAS_SYS, 0.9, PatternReport))
    out = {**json.loads(resp.text), "model": used}
    try:  # authenticity pass — optional, never blocks the ideas
        r2, _ = await generate(40, contents="Ideas:\n" + json.dumps(
            [{"idea_index": i + 1, **d} for i, d in enumerate(out["ideas"])]), config=_cfg("auth", AUTH_SYS, 0.2, AuthCheck))
        out["authenticity"] = json.loads(r2.text)["scores"]
    except Exception as e:
        out["authenticity_error"] = _err(e)
    p.write_text(json.dumps(out))
    return out


# ---------------------------------------------------------------- sample mode (clearly labeled in UI)
def sample_analysis(title: str) -> dict:
    s = lambda summary, *m: {"summary": summary, "moments": [{"timestamp": t, "note": n} for t, n in m]}
    return {
        "hook": s("Opens mid-action with a bold claim on screen before any intro.", ("00:00", "Bold text claim + fast zoom"), ("00:03", "Promise of payoff")),
        "structure_pacing": s("Problem → 3 escalating beats → reveal. Cuts every ~2s early, slower at the payoff.", ("00:10", "Beat 1"), ("00:35", "Beat 2"), ("01:05", "Reveal")),
        "format": s("Face-cam listicle with B-roll overlays.", ("00:05", "List framing introduced")),
        "emotional_trigger": s("Curiosity gap plus mild FOMO.", ("00:02", "Open loop created"), ("01:05", "Loop closed")),
        "title_thumbnail": s(f"Title '{title or 'this video'}' uses a specific number + outcome; thumbnail likely a reaction face + 3-word text.", ("00:00", "Opening frame mirrors thumbnail")),
        "why_viral": s("Instant hook, tight open loop, and a satisfying, shareable payoff.", ("01:05", "Shareable moment")),
    }


def sample_ideas(niche: str) -> dict:
    mk = lambda t, h, o, b: {"title": t, "hook_script": h, "outline": o, "borrowed_pattern": b}
    return {"viral_pattern": f"Bold on-screen claim in second one, an open curiosity loop, three escalating beats, then a shareable payoff — adapted to {niche}.",
            "shared_elements": ["Claim before intro", "Open loop", "Escalating beats", "Fast early cuts", "Shareable payoff"],
            "audience": {"age_range": "18–24 (sample)", "interests": ["sample"], "why_they_watch": "Sample mode — Gemini unavailable.",
                         "where_they_hang_out": ["YouTube"], "evidence": []},
            "calendar": [{"day": f"Week 1 · {d}", "idea_index": i + 1, "platform": "YouTube", "action": "Post idea"} for i, d in enumerate(["Tue", "Fri"])],
            "ideas": [mk(f"I tried the #{i} {niche} trick for 7 days", f"(Fast zoom) \"This {niche} trick sounds fake — day 7 proved it isn't.\"",
                         ["Claim", "Day 1 setup", "Day 4 twist", "Day 7 result", "CTA"], "Claim-first hook + open loop") for i in range(1, 6)]}


# ---------------------------------------------------------------- API
app = FastAPI(title="ViralLens")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/health")
async def health():
    """Fast: one 8s ping on a light model. Never walks the fallback chain."""
    if not client:
        return {"ok": False, "model": MODEL, "error": "no Gemini API key set"}
    return {"ok": True, "model": FALLBACKS[0], "agent": bool(YT_KEY)}  # no network: never blocks the page


# ---------------------------------------------------------------- live voice coach
class CoachReply(BaseModel):
    say: str = Field(description="What you say out loud: 1-3 short, natural spoken sentences. No markdown, no lists.")
    rewrite_index: int = Field(0, description="1-5 if you rewrote an idea this turn, else 0")
    rewrite: Idea | None = None


COACH_SYS = """You are ViralLens, a live voice creative coach talking with a creator out loud.
You can see their profile and the analysis results (viral pattern, 5 ideas, scores, video breakdowns) in the context.
Talk like a real friend who's great at YouTube: short, warm, specific, a bit funny. 1-3 sentences per turn, because this
is spoken aloud. Ask one follow-up question when useful. Reference specific timestamps or ideas by number.
If they ask you to change, rewrite or make an idea more human, return the full rewritten idea in `rewrite` with
`rewrite_index`, and say briefly what you changed. Never use the banned AI clichés (game-changer, level up, dive in, unlock...)."""


class ChatReq(BaseModel):
    messages: list[dict]
    context: dict = {}


@app.post("/api/chat")
async def chat(req: ChatReq):
    if not client:
        raise HTTPException(503, "no Gemini key")
    convo = "\n".join(f"{m.get('role', 'user').upper()}: {m.get('text', '')}" for m in req.messages[-12:])
    try:
        resp, used = await generate(25, models=FALLBACKS, contents=f"CONTEXT:\n{json.dumps(req.context)[:30000]}\n\nCONVERSATION:\n{convo}\n\nReply as ViralLens.",
                                    config=types.GenerateContentConfig(system_instruction=COACH_SYS, temperature=0.8,
                                        response_mime_type="application/json", response_schema=CoachReply,
                                        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)))
        return {**json.loads(resp.text), "model": used}
    except Exception as e:
        return {"say": "Sorry, my connection to Gemini hiccuped. Say that again?", "error": _err(e)}


class RunReq(BaseModel):
    about: str = Field(description="Who the creator is + niche, in their own words")
    urls: list[str] = []
    tier: str = "starting"


def _sse(obj):
    return f"data: {json.dumps(obj, default=str)}\n\n"


@app.post("/api/run")
async def api_run(req: RunReq):
    about = req.about.strip()[:500]
    urls = [u for u in re.split(r"[\s,]+", " ".join(req.urls)) if video_id(u)][:3]
    if not about:
        raise HTTPException(400, "Tell us what you make first")

    async def gen():
        nonlocal urls
        if not urls:
            yield _sse({"type": "step", "id": "find", "text": "Finding viral videos in your niche…"})
            try:
                urls, how = await find_videos(about)
                yield _sse({"type": "step", "id": "find", "done": True, "text": f"Found {len(urls)} videos via {how}"})
            except Exception as e:
                urls = []
                yield _sse({"type": "step", "id": "find", "error": True, "text": f"Couldn't auto-find videos ({_err(e)})"})
            if not urls:
                yield _sse({"type": "need_urls", "text": "Paste 1–3 YouTube links of videos you love and hit go again."})
                return
        metas = await asyncio.gather(*(oembed(u) for u in urls))
        yield _sse({"type": "step", "id": "watch", "text": f"Gemini is watching {len(urls)} video{'s' if len(urls) > 1 else ''} (sees the visuals, hears the audio)…"})

        async def one(u, m):
            base = {"url": u, "video_id": video_id(u), **m}
            try:
                return {**base, **(await analyze(u, m)), "sample": False}
            except Exception as e:
                return {**base, "analysis": sample_analysis(m["title"]), "sample": True, "error": _err(e)}

        videos = []
        for fut in asyncio.as_completed([one(u, m) for u, m in zip(urls, metas)]):
            v = await fut; videos.append(v)
            yield _sse({"type": "video", "video": v})
        yield _sse({"type": "step", "id": "watch", "done": True, "text": f"Watched {len(videos)} video{'s' if len(videos) > 1 else ''}"})
        yield _sse({"type": "step", "id": "ideas", "text": "Finding the shared pattern and writing ideas for your life…"})
        real = [v for v in videos if not v["sample"]]
        try:
            if not real:
                raise RuntimeError(videos[0].get("error", "no successful analyses"))
            report, sample = await ideas(about, req.tier, about, real), False
        except Exception as e:
            report, sample = {**sample_ideas(about), "error": _err(e)}, True
        yield _sse({"type": "step", "id": "ideas", "done": True, "text": "Ideas written + human-checked"})
        yield _sse({"type": "report", "report": report, "report_sample": sample, "about": about, "tier": req.tier})
        yield _sse({"type": "done"})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


# ---------------------------------------------------------------- AGENT MODE: Gemini decides what to do via function calling
AGENT_SYS = """You are ViralLens, an autonomous research agent for YouTube creators. The creator only told you their niche,
tier and story. Your job: find what's working in their niche yourself, then deliver 5 human-feeling ideas.

Plan (adapt as needed):
1. search_videos with 1-2 good queries for their niche (short, like a viewer would type).
2. get_stats on the results; prefer OUTLIERS: high views relative to channel subscribers (outlier_ratio), recent-ish, not mega-celebrities.
3. analyze_video on exactly 3 picks (call them in one turn). If one fails, you may analyze one replacement.
4. write_ideas once.
5. For EVERY idea scoring below 7, call rewrite_idea with specific feedback — all of them in the SAME turn (parallel).
   Repeat once more only for ideas still below 7.
6. Finish with a 2-3 sentence spoken-style summary of what you found and why you picked those videos.
Before each tool call, write one short sentence about what you're doing and why."""

TOOL_DECLS = [
    {"name": "search_videos", "description": "Search YouTube for the most-viewed videos matching a query.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "max_results": {"type": "integer"}}, "required": ["query"]}},
    {"name": "get_stats", "description": "Views, likes, upload date, channel subscribers and outlier_ratio (views / subscribers) for videos.",
     "parameters": {"type": "object", "properties": {"video_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["video_ids"]}},
    {"name": "analyze_video", "description": "Gemini watches the video and returns a timestamped breakdown (hook, pacing, format, emotion, title, why viral).",
     "parameters": {"type": "object", "properties": {"video_id": {"type": "string"}}, "required": ["video_id"]}},
    {"name": "write_ideas", "description": "Write the viral pattern, inferred audience, 5 ideas and calendar from all analyzed videos, then score each idea 1-10 for 'feels human'.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "rewrite_idea", "description": "Rewrite one idea (1-5) using feedback, then re-score it.",
     "parameters": {"type": "object", "properties": {"index": {"type": "integer"}, "feedback": {"type": "string"}}, "required": ["index", "feedback"]}},
]


async def yt(path: str, **params):
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.get(f"https://www.googleapis.com/youtube/v3/{path}", params={**params, "key": YT_KEY})
        r.raise_for_status(); return r.json()


class AgentState:
    def __init__(self, about, tier):
        self.about, self.tier = about, tier
        self.videos: dict[str, dict] = {}   # analyzed
        self.seen: dict[str, dict] = {}     # search results / stats
        self.report: dict | None = None


async def t_search(st, query, max_results=10):
    d = await yt("search", part="snippet", q=query, type="video", order="viewCount", maxResults=min(int(max_results or 10), 15),
                 relevanceLanguage="en", videoDuration="medium")
    out = []
    for i in d.get("items", []):
        v = {"video_id": i["id"]["videoId"], "title": i["snippet"]["title"], "channel": i["snippet"]["channelTitle"],
             "published": i["snippet"]["publishedAt"][:10]}
        st.seen.setdefault(v["video_id"], {}).update(v); out.append(v)
    return {"query": query, "count": len(out), "videos": out}


async def t_stats(st, video_ids):
    ids = [i for i in video_ids if re.fullmatch(r"[A-Za-z0-9_-]{11}", i)][:25]
    vd = await yt("videos", part="statistics,snippet", id=",".join(ids))
    chans = {i["snippet"]["channelId"] for i in vd.get("items", [])}
    cd = await yt("channels", part="statistics", id=",".join(chans)) if chans else {"items": []}
    subs = {c["id"]: int(c["statistics"].get("subscriberCount", 0) or 0) for c in cd.get("items", [])}
    out = []
    for i in vd.get("items", []):
        views = int(i["statistics"].get("viewCount", 0)); sub = subs.get(i["snippet"]["channelId"], 0)
        v = {"video_id": i["id"], "title": i["snippet"]["title"], "channel": i["snippet"]["channelTitle"],
             "views": views, "likes": int(i["statistics"].get("likeCount", 0) or 0), "published": i["snippet"]["publishedAt"][:10],
             "channel_subs": sub, "outlier_ratio": round(views / max(sub, 1), 2)}
        st.seen.setdefault(v["video_id"], {}).update(v); out.append(v)
    return {"videos": sorted(out, key=lambda v: -v["outlier_ratio"])}


async def t_analyze(st, video_id):
    url = f"https://www.youtube.com/watch?v={video_id}"
    meta = await oembed(url)
    try:
        r = await analyze(url, meta); sample = False
    except Exception as e:
        r, sample = {"analysis": sample_analysis(meta["title"]), "error": _err(e)}, True
    v = {"url": url, "video_id": video_id, **meta, **r, "sample": sample, "stats": st.seen.get(video_id, {})}
    if not sample:
        st.videos[video_id] = v
    return v


async def score(ideas_list):
    r, _ = await generate(40, contents="Ideas:\n" + json.dumps([{"idea_index": i + 1, **d} for i, d in enumerate(ideas_list)]),
                          config=_cfg("auth", AUTH_SYS, 0.2, AuthCheck))
    return json.loads(r.text)["scores"]


async def t_write(st):
    if not st.videos:
        return {"error": "analyze at least one video first"}
    st.report = await ideas(st.about, st.tier, st.about, list(st.videos.values()))
    st.report.setdefault("authenticity", [])
    return {"ideas": [{"index": i + 1, "title": d["title"], "score": next((a["score"] for a in st.report["authenticity"] if a["idea_index"] == i + 1), None),
                       "flags": next((a["flags"] for a in st.report["authenticity"] if a["idea_index"] == i + 1), [])}
                      for i, d in enumerate(st.report["ideas"])]}


async def t_rewrite(st, index, feedback):
    if not st.report:
        return {"error": "call write_ideas first"}
    i = int(index) - 1
    old = st.report["ideas"][i]
    r, _ = await generate(40, contents=(f"Creator: {st.about}\nTier: {TIERS.get(st.tier, TIERS['starting'])}\nViral pattern: {st.report['viral_pattern']}\n"
                                        f"Original idea: {json.dumps(old)}\nFeedback: {feedback}\nRewrite this ONE idea so it feels unmistakably human."),
                          config=_cfg("ideas", IDEAS_SYS, 0.9, Idea))
    new = json.loads(r.text); st.report["ideas"][i] = new
    sc = (await score([new]))[0]; sc["idea_index"] = i + 1
    st.report["authenticity"] = [a for a in st.report["authenticity"] if a["idea_index"] != i + 1] + [sc]
    return {"index": i + 1, "title": new["title"], "score": sc["score"], "flags": sc["flags"]}


TOOL_FNS = {"search_videos": t_search, "get_stats": t_stats, "analyze_video": t_analyze, "write_ideas": t_write, "rewrite_idea": t_rewrite}


def _brief(name, res):
    """Short, human-readable result for the live log; full result still goes to the model."""
    if "error" in res: return f"error: {res['error']}"
    if name == "search_videos": return f"found {res['count']} videos for “{res['query']}”"
    if name == "get_stats":
        top = res["videos"][:3]
        return "top outliers: " + "; ".join(f"{v['title'][:40]} ({v['views']:,} views, {v['channel_subs']:,} subs, ×{v['outlier_ratio']})" for v in top)
    if name == "analyze_video": return f"watched “{res.get('title', '')[:60]}”" + (" (failed)" if res.get("sample") else "")
    if name in ("write_ideas",): return "scores: " + ", ".join(f"#{x['index']} {x['score']}/10" for x in res["ideas"])
    if name == "rewrite_idea": return f"idea #{res['index']} → {res['score']}/10: {res['title']}"
    return ""


def _for_model(name, res):
    if name == "analyze_video":  # keep the model's context small
        return {"video_id": res["video_id"], "title": res.get("title"), "ok": not res.get("sample"),
                "hook": res["analysis"]["hook"]["summary"], "why_viral": res["analysis"]["why_viral"]["summary"]}
    return res


class AgentReq(BaseModel):
    about: str
    tier: str = "starting"


@app.post("/api/agent")
async def api_agent(req: AgentReq):
    about = req.about.strip()[:500]
    if not about:
        raise HTTPException(400, "Tell us what you make first")
    if not YT_KEY:
        raise HTTPException(400, "Agent mode needs YOUTUBE_API_KEY")
    st = AgentState(about, req.tier)

    async def gen():
        tools = [types.Tool(function_declarations=[types.FunctionDeclaration(**d) for d in TOOL_DECLS])]
        cfg = types.GenerateContentConfig(system_instruction=AGENT_SYS, tools=tools, temperature=0.4,
                                          thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                                          automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        contents = [types.Content(role="user", parts=[types.Part(text=f"Creator: {about}\nTier: {TIERS.get(req.tier, TIERS['starting'])}\nGo.")])]
        models = FALLBACKS
        yield _sse({"type": "agent", "kind": "start", "text": "Agent online. Planning research…"})
        try:
            for turn in range(14):
                resp, used = await generate(60, models=models, contents=contents, config=cfg)
                models = [used]  # stick to one model so thought signatures stay valid
                cand = resp.candidates[0].content
                contents.append(cand)
                for p in cand.parts or []:
                    if p.text and not getattr(p, "thought", False):
                        yield _sse({"type": "agent", "kind": "think", "text": p.text.strip()})
                calls = resp.function_calls or []
                if not calls:
                    break
                for c in calls:
                    yield _sse({"type": "agent", "kind": "call", "name": c.name, "args": dict(c.args or {})})
                results = await asyncio.gather(*(TOOL_FNS[c.name](st, **dict(c.args or {})) if c.name in TOOL_FNS
                                                 else asyncio.sleep(0, {"error": "unknown tool"}) for c in calls), return_exceptions=True)
                parts = []
                for c, r in zip(calls, results):
                    if isinstance(r, Exception):
                        r = {"error": _err(r)}
                    yield _sse({"type": "agent", "kind": "result", "name": c.name, "text": _brief(c.name, r)})
                    if c.name == "analyze_video" and "video_id" in r:
                        yield _sse({"type": "video", "video": r})
                    if c.name in ("write_ideas", "rewrite_idea") and st.report:
                        yield _sse({"type": "report", "report": st.report, "report_sample": False})
                    parts.append(types.Part.from_function_response(name=c.name, response=_for_model(c.name, r)))
                contents.append(types.Content(role="user", parts=parts))
        except Exception as e:
            yield _sse({"type": "agent", "kind": "error", "text": f"Agent error: {_err(e)}"})
        if st.report:
            yield _sse({"type": "report", "report": st.report, "report_sample": False})
        yield _sse({"type": "done"})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
