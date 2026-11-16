import re

def get_transcript(video_id: str, languages=("en", "en-US", "en-GB", "hi", "es", "pt", "fr", "de")):
    """Returns [{'text','start','dur'}, ...] with timestamps in seconds. [] if unavailable."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi as T
    except ImportError:
        return []
    raw = None
    try:                                   # v1.x API
        api = T()
        raw = api.fetch(video_id, languages=list(languages)).to_raw_data()
    except AttributeError:                 # legacy static API
        try:
            raw = T.get_transcript(video_id, languages=list(languages))
        except Exception:
            return []
    except Exception:                      # captions disabled / blocked / none in languages
        return []
    segs = []
    for seg in raw:
        txt = (seg.get("text") or "").replace("\n", " ").strip()
        if txt:
            segs.append({"text": txt,
                         "start": float(seg.get("start", 0)),
                         "dur": float(seg.get("duration", 2.0))})
    return segs

def timed_lines(segs):
    return "\n".join(f"[{s['start']:7.1f}s] {s['text']}" for s in segs)

def sentences_with_times(segs):
    """Split segments into sentences, spreading each segment's time across its sentences."""
    out = []
    for s in segs:
        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", s["text"]) if p.strip()]
        step = s["dur"] / max(1, len(parts))
        for i, p in enumerate(parts):
            out.append({"text": p, "start": s["start"] + i * step, "dur": step})
    return out
