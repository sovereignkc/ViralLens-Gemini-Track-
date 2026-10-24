# ViralLens demo plan (target 3 minutes)

## Short answers
- **How many links?** Show **0 links in the main demo**, because the agent finds the videos itself. That is the pitch. Use paste-links mode only as a 15-second "it also works with your own links" moment, with **1 link that's already cached**.
- **All 3 tiers or just one?** Do **one live run on "📱 Just starting"**. It's the most relatable tier, and the phone-only constraint shows up clearly in the ideas. Mention the other tiers in one line ("switch to Big channel and it plans crew and budget shoots") but don't run them live, since each run takes about 70 seconds.

---

## Before judges arrive (10 minutes)
1. Run `./run.sh`, then hard refresh. The pill should read **"● Gemini agent ready"**.
2. **Warm-up run**: do one full agent run with the exact demo sentence. This caches the video breakdowns, so the live run is faster.
3. Paste-links mode: run **1 link** once so it replays instantly from the cache.
4. **Record the backup video** of a full run in case the network or Gemini fails during judging.
5. Check your AI Studio balance after one run so you know the cost per run.
6. Turn the screen brightness up, set zoom to 110–125%, and close other tabs.

---

## 3-minute script

**0:00 Hook (15s)**
> "Every creator asks 'what should I post?' and every AI tool gives the same generic answer. ChatGPT waits for you to find the videos. **ViralLens goes and finds the outliers itself.**"

**0:15 Input (15s)**: click a "Try:" chip, or type:
> `Math explainers — I'm a high school math teacher who skateboards`

Tier: 📱 Just starting. Click **Find my pattern ✦**.
> "That's all I give it: one sentence and my tier."

**0:30 Agent console (45s)**: narrate while it streams.
- "It's choosing its own search queries. Look, when one came back empty, it changed the query itself."
- "Now it pulls real YouTube stats and ranks **outliers**: views relative to channel size. A video with 11M views on a 1.5M-subscriber channel beats a celebrity channel."
- "Now **Gemini is actually watching the videos**. It sees the cuts, reads on-screen text and hears the audio, all from just the link. Most models can only read the title."

**1:15 Breakdowns (20s)**: click a timestamp in a video card.
> "Every claim has a timestamp. Click it and the player jumps to that moment. That's only possible because Gemini watched the video."

**1:35 Human check (35s)**: this is the strongest demo moment.
> "It wrote 5 ideas, then a **second skeptical Gemini pass** scored them. These scored 3, 4 and 5 because they sounded like AI. Watch: the agent **rewrites them by itself** until they score 7 or higher."

Point to the red ⚑ flags: "It even calls out the exact AI-sounding phrases."

**2:10 Ideas, calendar, audience (25s)**
- Read one hook out loud (it's written to be spoken).
- "Copy button: paste it straight into your notes."
- "A 2-week posting plan sized for a phone and one person."
- "Audience profile, which we **label as inferred**. We don't pretend it's real analytics."

**2:35 Paste-links mode (10s)**: "Already have a video in mind? Paste it." Use the cached link so it loads instantly.

**2:45 Close (15s)**
> "One sentence in. An agent that searches, ranks outliers, watches the videos, writes ideas and fixes its own AI-speak. Ideas built from what actually worked, plus your real life."

---

## Demo sentences (pick one, then warm it up)
| Niche sentence | Why it demos well |
|---|---|
| `Math explainers — I'm a high school math teacher who skateboards` | **Tested**: 7/5/6/4/3, then all rewritten to 8. Fun crossover. |
| `Budget cooking — I'm a single dad, 3 kids, $60/week` | **Tested**: emotional, very human ideas ("worried the card will decline"). |
| `Study tips — I'm a broke college student who lifts, failed orgo once` | **Tested**. Relatable to student judges. |
| `Gaming — I'm a nurse who streams after night shifts` | Untested. Unexpected combination. |
| `Fitness — I'm 52 and just started lifting` | Untested. Strong story. |
| `Personal finance — I'm 19 and paying off my mom's credit card` | Untested. High stakes, very human. |
| `Language learning — I'm learning Korean to talk to my grandma` | Untested. Heartwarming. |

Tip: specific numbers, a struggle or an odd combination produce the most human ideas and the biggest score jumps.

---

## Links for paste-links mode
These IDs were all confirmed working in testing:
| Video | Link | Use for |
|---|---|---|
| Rick Astley, Never Gonna Give You Up | https://www.youtube.com/watch?v=dQw4w9WgXcQ | **Already cached.** A fun "rickroll" moment that loads instantly. |
| Rodney Mullen, "Why this trick should be IMPOSSIBLE" (physics + skating) | https://www.youtube.com/watch?v=yFRPhi0jhGc | Math/skate niche |
| 3Blue1Brown, "The essence of calculus" | https://www.youtube.com/watch?v=WUvTyaaNkzM | Math explainers |
| "How to Study MORE in LESS TIME" | https://www.youtube.com/watch?v=Zff3rUY0iGg | Study tips |
| "How to STUDY so FAST it feels like CHEATING" | https://www.youtube.com/watch?v=9tDkkKDQWlg | Study tips |
| "$60 ALDI Haul & Weekly Meal Plan for Family of 4" | https://www.youtube.com/watch?v=NQ9uvPp4NyQ | Budget cooking (×5.8 outlier) |

For other videos, search YouTube yourself. **Pick videos under 10 minutes** (they process faster and cost less) and avoid music videos, which have little speech to analyze.

---

## Talking points for judges' questions
- **Why is this an agent and not a chatbot?** Gemini function calling chooses which of 5 tools to call and in what order (search, stats, watch, write, rewrite). It adapts its queries and stops only when all ideas score 7 or higher.
- **Why Gemini specifically?** Native YouTube video understanding (visuals and audio from a URL), structured JSON output, function calling and thinking levels, all in one model.
- **What is an outlier?** A video's views divided by its channel's subscribers. It surfaces formats that work *despite* channel size, which matters for small creators.
- **Isn't it just generating generic ideas?** No. AI clichés are banned in the prompt, ideas are built around the user's story, and a separate judge pass scores and flags anything AI-sounding.
- **Is the audience data real?** It's inferred and labelled that way on purpose. We chose honesty over fake analytics.
- **How reliable is it?** Every call has a timeout and falls back across 4 Gemini models. Video breakdowns are cached.
- **What does it cost?** A full run is roughly 150k tokens on flash, a few cents. Quote the real number from your balance check.
- **Roadmap**: connect your own channel through OAuth for real analytics, a live voice coach (the backend endpoint exists), thumbnail generation with Gemini image models, and weekly automatic trend scans.

## If something breaks
- **Agent errors or hangs**: say "live demos, right?" and paste the cached Rick Astley link, or play the backup video.
- **429/402 from Gemini**: check credits at ai.studio/projects.
- **Page dead or buttons don't respond**: hard refresh (Cmd+Shift+R).
