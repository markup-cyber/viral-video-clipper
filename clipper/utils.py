import re
from shutil import which

def extract_video_id(url: str):
    """Accepts watch?v=, youtu.be/, shorts/, embed/ links or a raw 11-char ID."""
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([\w-]{11})", url)
    if m:
        return m.group(1)
    m = re.fullmatch(r"([\w-]{11})", url.strip())
    return m.group(1) if m else None

def ensure_ffmpeg():
    if which("ffmpeg") is None or which("ffprobe") is None:
        raise RuntimeError(
            "ffmpeg not found. Install it, then reopen the terminal:\n"
            "    winget install Gyan.FFmpeg"
        )

def slugify(s: str, maxlen=60):
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    return re.sub(r"[\s_-]+", "-", s)[:maxlen] or "clip"
