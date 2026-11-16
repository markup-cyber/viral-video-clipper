import os
import yt_dlp

def fetch_metadata(url: str) -> dict:
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        "id": info.get("id") or "",
        "title": info.get("title") or "Untitled",
        "channel": info.get("channel") or info.get("uploader") or "",
        "duration": float(info.get("duration") or 0),
        "description": (info.get("description") or "")[:4000],
        "view_count": int(info.get("view_count") or 0),
        "tags": info.get("tags") or [],
    }

def download_video(url: str, dest_dir: str, max_height=1080, cookies_file=None) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    opts = {
        "format": (f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]"
                   f"/best[height<={max_height}][ext=mp4]/best[height<={max_height}]/best"),
        "outtmpl": os.path.join(dest_dir, "source.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "concurrent_fragment_downloads": 4,
    }
    if cookies_file:
        opts["cookiefile"] = cookies_file
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.extract_info(url, download=True)
    for ext in ("mp4", "mkv", "webm"):
        p = os.path.join(dest_dir, f"source.{ext}")
        if os.path.exists(p):
            return p
    raise RuntimeError("Download finished but the output file was not found.")
