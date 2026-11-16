import json, re
from .transcript import timed_lines, sentences_with_times

SYSTEM_PROMPT = """You are an expert short-form video strategist and editor. You find the most viral,
self-contained moments in a long video for YouTube Shorts / Instagram Reels / TikTok.
Rules:
- Use ONLY the timestamps shown in the transcript (the [123.4s] markers).
- Each clip must stand alone: it must make sense without the rest of the video, open with a strong
  hook, and end on a payoff, punchline, or clear takeaway.
- Prefer emotional peaks, hot takes, surprising facts, stories, conflict, laughter, "aha" moments.
- Clip length must be about the requested seconds (+/-20%).
- Score each moment 0-100 on hook strength, emotion, curiosity, and shareability.
Respond ONLY with JSON:
{"moments":[{"start":<float seconds>,"end":<float seconds>,"score":<int 0-100>,
"hook":"<the opening line or hook idea>","title":"<punchy title, max 60 chars>",
"reason":"<one sentence: why this can go viral>"}]}"""

HOOKS = ["secret", "truth about", "nobody", "most people", "here's why", "here is why", "the reason",
         "mistake", "never do", "always", "actually", "imagine", "what if", "story", "listen",
         "warning", "stop doing", "problem", "lesson", "rule", "million", "billion", "thousand",
         "dollars", "$", "%", "failed", "failure", "success", "best", "worst", "biggest", "first",
         "shocking", "crazy", "insane", "weird", "funny", "hilarious", "prove", "proof", "learn",
         "how to", "why you", "what happens", "changed my life", "blew my mind", "plot twist",
         "life hack", "tip", "trick", "turns out", "found out", "realize"]

def select_moments(client, model, meta, segs, target_len, count):
    """Public entry: AI agent if available, heuristic otherwise, evenly spaced as last resort."""
    duration = meta.get("duration") or 600
    cands = []
    if client is not None and segs:
        try:
            cands = _ai_candidates(client, model, meta, segs, target_len)
        except Exception:
            cands = []
        if cands and len(cands) < count:
            cands += _heuristic_candidates(segs, duration, target_len)
    elif segs:
        cands = _heuristic_candidates(segs, duration, target_len)
    return _pick(cands, count, duration)

def _ai_candidates(client, model, meta, segs, target_len):
    lines = timed_lines(segs)
    chunks = _chunk_lines(lines, max_chars=12000, max_chunks=8)
    out = []
    for chunk in chunks:
        resp = client.chat.completions.create(
            model=model,
            temperature=0.4,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _user_prompt(meta, chunk, target_len)},
            ],
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        for m in data.get("moments", []):
            try:
                m["start"] = _snap(float(m["start"]), segs)
                m["end"] = float(m["end"])
                m["score"] = int(m.get("score") or 60)
                m["title"] = (m.get("title") or m.get("hook") or "Clip")[:70]
                m["reason"] = m.get("reason") or ""
                out.append(m)
            except (TypeError, ValueError, KeyError):
                continue
    return out

def _user_prompt(meta, chunk, target_len):
    return (f'VIDEO: "{meta["title"]}" by {meta["channel"]} ({int(meta["duration"])}s total)\n'
            f'DESCRIPTION: {meta["description"][:600]}\n\n'
            f"TRANSCRIPT WITH TIMESTAMPS (seconds):\n{chunk}\n\n"
            f"TASK: Pick the 6 most viral, self-contained moments in THIS portion. "
            f"Each clip is about {target_len} seconds. Return ONLY JSON per the schema.")

def _chunk_lines(lines, max_chars=12000, max_chunks=8):
    chunks, cur = [], ""
    for ln in lines.split("\n"):
        if cur and len(cur) + len(ln) + 1 > max_chars:
            chunks.append(cur)
            if len(chunks) >= max_chunks:
                return chunks
            cur = ln
        else:
            cur = f"{cur}\n{ln}" if cur else ln
    if cur and len(chunks) < max_chunks:
        chunks.append(cur)
    return chunks

def _snap(t, segs):
    if not segs:
        return t
    return min(segs, key=lambda s: abs(s["start"] - t))["start"]

def _score_window(text):
    t = text.lower()
    score = 30
    score += min(sum(1 for h in HOOKS if h in t), 6) * 7
    score += min(t.count("?"), 3) * 4
    score += min(t.count("!"), 2) * 2
    if "[laughter]" in t or "laughs" in t:
        score += 5
    if re.search(r"\d", t):
        score += 3
    if any(h in " ".join(t.split()[:4]) for h in HOOKS):
        score += 10
    return min(100, score)

def _heuristic_candidates(segs, duration, target_len):
    sents = sentences_with_times(segs)
    cands = []
    for i in range(len(sents)):
        start, end, text, j = sents[i]["start"], sents[i]["start"], "", i
        while j < len(sents) and (sents[j]["start"] + sents[j]["dur"] - start) < target_len * 1.15:
            text += " " + sents[j]["text"]
            end = sents[j]["start"] + sents[j]["dur"]
            j += 1
        if end - start < target_len * 0.55:
            continue
        cands.append({"start": start, "end": end, "score": _score_window(text),
                      "hook": sents[i]["text"][:80], "title": sents[i]["text"][:60],
                      "reason": "High-engagement segment detected by heuristic engine."})
    return cands

def _pick(cands, count, duration):
    cleaned = []
    for c in cands:
        s = max(0.0, min(float(c.get("start", 0)), duration - 3))
        e = max(s + 5.0, min(float(c.get("end", s + 5)), duration))
        if e - s >= 5:
            cleaned.append({**c, "start": s, "end": e})
    cleaned.sort(key=lambda c: -int(c.get("score", 60)))
    picked = []
    for c in cleaned:
        if all(min(c["end"], p["end"]) - max(c["start"], p["start"])
               <= 0.25 * min(c["end"] - c["start"], p["end"] - p["start"]) for p in picked):
            picked.append(c)
        if len(picked) >= count:
            break
    if len(picked) < count:  # fill gaps with evenly spaced clips
        step = (duration - 30) / max(1, count)
        for i in range(count):
            if len(picked) >= count:
                break
            s = min(i * step, max(0.0, duration - 31))
            if all(min(s + 30, p["end"]) - max(s, p["start"]) <= 2 for p in picked):
                picked.append({"start": s, "end": s + 30, "score": 50, "hook": "",
                               "title": f"Highlight {i + 1}",
                               "reason": "Evenly spaced segment (no AI/heuristic candidate)."})
    return picked[:count]
