import json, re
from collections import Counter

KW_SYSTEM = """You are a YouTube growth strategist. For each clip, produce SEO metadata that
maximizes reach on YouTube Shorts, Instagram Reels and TikTok.
- Mix broad high-volume keywords with specific long-tail keywords.
- Titles: max 70 chars, front-load the main keyword, create curiosity.
- Always include #shorts in hashtags.
Respond ONLY with JSON:
{"clips":[{"index":<int>,"title":"...","keywords":["...12-15"],"hashtags":["#...8-10"],
"description":"<=200 chars, hook + 3 hashtags"}]}"""

STOP = set("the a an and or but if then so of to in on for with at by from as is are was were be "
           "been being it its this that these those you your i we they he she them our their what "
           "how why when who which will would can could should just like get got go going know "
           "really very about there here than more most some any all no not do does did done have "
           "has had said says".split())

def generate(client, model, meta, clips):
    """clips: list of dicts with 'index','title','text'. Returns {index: {title,keywords,...}}."""
    if client is not None:
        try:
            payload = [{"index": c["index"], "clip_title": c.get("title", ""),
                        "transcript_excerpt": c["text"][:900]} for c in clips]
            user = {"video_title": meta["title"], "channel": meta["channel"],
                    "video_tags": meta["tags"][:15], "clips": payload}
            resp = client.chat.completions.create(
                model=model, temperature=0.5, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": KW_SYSTEM},
                          {"role": "user", "content": json.dumps(user)}])
            data = json.loads(resp.choices[0].message.content or "{}")
            return {int(c["index"]): c for c in data.get("clips", []) if "index" in c}
        except Exception:
            pass
    return {c["index"]: heuristic_keywords(meta, c["text"], c.get("title", "")) for c in clips}

def heuristic_keywords(meta, text, clip_title):
    words = re.findall(r"[a-zA-Z']{3,}", (meta["title"] + " " + meta["description"] + " " + text).lower())
    words = [w for w in words if w not in STOP]
    uni, bi = Counter(words), Counter(f"{a} {b}" for a, b in zip(words, words[1:]))
    kws = [w for w, _ in uni.most_common(10)] + [b for b, _ in bi.most_common(6)]
    tags = [f"#{w.capitalize()}" for w, _ in uni.most_common(6)] + ["#shorts", "#viral", "#fyp", "#trending"]
    return {"title": (clip_title or meta["title"])[:70], "keywords": kws[:15],
            "hashtags": list(dict.fromkeys(tags))[:10],
            "description": (f"{meta['title']} #shorts")[:200]}
