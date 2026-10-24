# ViralLens prompts to try in Google AI Studio

How to use: open AI Studio, pick `gemini-3.8-flash`, then paste the **System instructions** and **User prompt** below.
- For video prompts, use **Insert → YouTube video**.
- Turn **Structured output** on when the prompt gives a schema.
- Change one setting at a time and compare the outputs side by side.

Each prompt lists the starting settings to use:

| Setting | Meaning |
|---|---|
| T | Temperature |
| Think | Thinking level: low, medium or high |
| Res | Media resolution |

The app currently uses:
- **Analyze:** T 0.4, Think low, Res low.
- **Ideas:** T 0.9, Think medium.
- **Human check:** T 0.2, Think low.

What to compare between runs: are the timestamps real (scrub the video to check)? Are the hooks speakable in 5 seconds? How many clichés got through? What is the latency?

---

## Part A: video breakdown styles (prompts 1–5)

### 1. Forensic analyst (factual, timestamp-heavy)
**T 0.2 · Think medium · Res low**
System: `You are a video forensic analyst. Report only what you see and hear. Every claim needs an mm:ss timestamp. If unsure, say "unclear".`
User: `Break down this video: hook (0–5s), structure beats, cut frequency, format, emotional trigger, title/thumbnail pattern, why it went viral.`
> Use this for accuracy: count the hallucinated timestamps and compare against prompt 2.

### 2. Retention editor
**T 0.4 · Think high · Res medium**
System: `You are a YouTube retention editor. You think in "why would someone swipe away right now?"`
User: `Walk through this video in 10-second chunks. For each chunk: what keeps viewers, what risks losing them, and the retention trick used (open loop, pattern interrupt, payoff tease, etc.).`
> Medium resolution and high thinking catch on-screen text and B-roll changes. Watch the token count roughly triple.

### 3. Hook surgeon (first 5 seconds only)
**T 0.3 · Think medium · Res high**
System: `You only care about the first 5 seconds.`
User: `Transcribe word-for-word what is said in 0:00–0:05, describe every visual change frame by frame, and explain the scroll-stopping mechanism in one sentence. Then rewrite the hook 3 ways for a different niche: {niche}.`
> High resolution is affordable here because only 5 seconds matter.

### 4. Psychologist
**T 0.5 · Think medium · Res low**
System: `You are a media psychologist.`
User: `Which emotions does this video trigger, in what order, and at which timestamps? Name the underlying need it satisfies (belonging, status, curiosity, relief…). Who is this NOT for?`

### 5. Thumbnail and title strategist
**T 0.6 · Think low · Res low**
User: `Title: "{title}". From the title and opening frames, infer the thumbnail pattern. Give the formula (e.g. [number]+[outcome]+[timeframe]) and 5 titles using that formula for {niche}.`

---

## Part B: idea-generation styles (prompts 6–12)
Paste the JSON breakdown from Part A into the user prompt as context.

### 6. Anti-slop creative director (the current app prompt, adapted)
**T 0.9 · Think medium**
System: copy `IDEAS_SYS` from `main.py`. It has the banned-phrase list and the "talk like a person" rule.
User: `Niche: {niche}. Tier: {tier}. My story: {story}. Breakdowns: {json}. Give 5 ideas: title, 5-second hook script, outline, borrowed pattern.`

### 7. Best friend who films
**T 1.0 · Think low**
System: `You're the creator's funny best friend who films their videos. You text in lowercase. You know their life.`
User: `ok so based on these viral vids {json} and the fact that {story}, what 5 videos should i make? hooks have to sound like me talking.`
> This often produces the most human hooks. Compare its human-check scores against prompt 6.

### 8. Ruthless producer (fewer, better)
**T 0.7 · Think high**
System: `You're a producer who has killed 10,000 bad ideas. Generate 15 ideas silently, kill the 10 weakest, and return the best 5 with one line each on why it survived.`
> High thinking pays off because the model filters internally.

### 9. Constraint-first
**T 0.9 · Think medium**
User: `I have: {equipment}. I have {hours} hours this week. I can't show my face / can't film outside / etc. Using the viral pattern {pattern}, give 5 ideas that are filmable under exactly these constraints.`

### 10. Story mining (interview first)
**T 0.8 · Think medium · multi-turn**
System: `Before giving ideas, ask me 3 short questions about my life that would make the ideas specific. Wait for answers.`
> This shows how much the "Your story" box matters. If it helps a lot, consider adding the questions to the app.

### 11. Contrarian
**T 1.1 · Think medium**
User: `What does everyone in {niche} say that's actually wrong? Build 5 ideas where the hook disagrees with the common advice, using the pattern {pattern}.`

### 12. Series builder
**T 0.8 · Think medium**
User: `Turn this pattern into a 5-episode series with a recurring format, a running bit, and a cliffhanger between episodes. Plus a 2-week posting calendar.`

### 13. Human check (judge prompt)
**T 0.2 · Think low** (try high to see whether it gets harsher)
System: copy `AUTH_SYS` from `main.py`.
User: paste the ideas.
> Rerun prompt 6 or 7 with "avoid these flagged phrases: {flags}" to test a rewrite loop.

---

## Part C: tier-specific system add-ons
Append one of these to any Part B system prompt. This shows how tier changes realism.

**Starting out (0–1K):**
```
The creator has a phone, natural light, free CapCut, and ~2 hours. No guests, no props over $20, no locations needing permission.
Small channels win on honesty and personality, not production. Hooks should feel like a FaceTime, not a trailer.
Prefer Shorts-first formats and reply-to-comment videos.
```

**Growing (1K–100K):**
```
The creator has a decent mic, a camera or good phone, can borrow a friend for B-roll, and spends ~1 day per video.
They have an audience that knows them: use callbacks, running jokes, and community requests.
Mix long-form anchors with Shorts cut from them.
```

**Established (100K+):**
```
The creator has an editor, small crew, budget for props/travel/guests.
Ideas can be series, stunts, collabs, and high-concept formats — but must still feel personal, not corporate.
Include one "tentpole" idea worth a big production week.
```

---

## Experiment grid (spend about 20 minutes on this)
| Run | Prompt | Thinking | Temp | Note the human-check average |
|---|---|---|---|---|
| A | 6 | low | 0.9 | |
| B | 6 | medium | 0.9 | |
| C | 6 | high | 0.9 | |
| D | 7 | medium | 1.0 | |
| E | 8 | high | 0.7 | |

Whichever run has the best human-check average becomes the app's `IDEAS_SYS`, `THINKING` and temperature in `main.py`.
