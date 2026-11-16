import os, glob, json, shutil, subprocess, tempfile
from .utils import ensure_ffmpeg

def probe(video_path):
    ensure_ffmpeg()
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height", "-of", "json", video_path]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    st = (json.loads(out.stdout or "{}").get("streams") or [{}])[0]
    return int(st.get("width") or 1920), int(st.get("height") or 1080)

def _even(n):
    return int(n) // 2 * 2

def face_crop_x(video_path, start, dur, src_w, src_h):
    """Sample frames across the clip, find the dominant face, return crop-x in source pixels."""
    try:
        import cv2, numpy as np
    except ImportError:
        return None
    tmpd = tempfile.mkdtemp(prefix="faces_")
    try:
        fps = max(0.25, 8 / max(dur, 1))
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}",
               "-i", video_path, "-vf", f"fps={fps:.3f},scale=480:-2", "-q:v", "5",
               os.path.join(tmpd, "f_%02d.jpg")]
        subprocess.run(cmd, capture_output=True, timeout=180)
        files = sorted(glob.glob(os.path.join(tmpd, "f_*.jpg")))
        if not files:
            return None
        cas = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        fracs = []
        for f in files:
            img = cv2.imread(f)
            if img is None:
                continue
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = cas.detectMultiScale(gray, 1.1, 5, minSize=(40, 40))
            if len(faces):
                x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
                fracs.append((x + w / 2) / img.shape[1])
        if not fracs:
            return None
        cx = float(np.median(fracs))
        cw = _even(src_h * 9 / 16)
        return max(0, min(int(cx * src_w - cw / 2), src_w - cw))
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)

def write_ass(segs_in_clip, clip_start, clip_dur, ass_path, play_res=(1080, 1920)):
    """Burn-in style captions: <=4-word cues, uppercase, bottom-center."""
    def ts(t):
        t = max(0.0, t)
        return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"
    events = []
    for seg in segs_in_clip:
        s0 = max(0.0, seg["start"] - clip_start)
        s1 = min(clip_dur, seg["start"] + seg.get("dur", 2.0) - clip_start)
        if s1 - s0 < 0.2:
            continue
        words, cues, cur = seg["text"].split(), [], []
        for w in words:
            cur.append(w)
            if len(cur) >= 4 or sum(len(x) + 1 for x in cur) > 24:
                cues.append(" ".join(cur)); cur = []
        if cur:
            cues.append(" ".join(cur))
        total = sum(len(c) for c in cues) or 1
        t = s0
        for c in cues:
            d = (s1 - s0) * len(c) / total
            events.append((t, min(t + d, s1), c.upper()))
            t += d
    header = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {play_res[0]}\nPlayResY: {play_res[1]}\n"
              "WrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
              "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
              "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
              "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
              "Style: Cap,Arial,58,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,-1,0,0,0,100,100,1,0,"
              "1,5,1,2,50,50,420,1\n\n[Events]\n"
              "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header)
        for a, b, txt in events:
            txt = txt.replace("{", "").replace("}", "").replace("\n", " ")
            f.write(f"Dialogue: 0,{ts(a)},{ts(b)},Cap,,0,0,0,,{txt}\n")

def make_clip(video_path, out_path, start, dur, mode="blur", captions=None, smart_crop=False):
    """mode: 'blur' = 9:16 with blurred bg | 'fill' = 9:16 face-crop fill | 'original'."""
    ensure_ffmpeg()
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    out_name = os.path.basename(out_path)
    ass_name = None
    if captions:
        ass_name = out_name.rsplit(".", 1)[0] + ".ass"
        write_ass(captions, start, dur, os.path.join(out_dir, ass_name))

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-ss", f"{start:.2f}", "-i", video_path, "-t", f"{dur:.2f}"]

    if mode == "blur":
        fc = ("[0:v]split=2[bgsrc][fgsrc];"
              "[bgsrc]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
              "gblur=sigma=20[bg];"
              "[fgsrc]scale=1080:-2:flags=bicubic[fg];"
              "[bg][fg]overlay=(W-w)/2:(H-h)/2")
        fc += f";[tmpo]ass={ass_name}[out]" if ass_name else "[out]"
        cmd += ["-filter_complex", fc, "-map", "[out]", "-map", "0:a:0?"]
    elif mode == "fill":
        src_w, src_h = probe(video_path)
        cw = _even(src_h * 9 / 16)
        x = face_crop_x(video_path, start, dur, src_w, src_h) if smart_crop else None
        if x is None:
            x = (src_w - cw) // 2
        vf = f"crop={cw}:{src_h}:{x}:0,scale=1080:1920:flags=bicubic"
        if ass_name:
            vf += f",ass={ass_name}"
        cmd += ["-vf", vf, "-map", "0:v:0", "-map", "0:a:0?"]
    else:
        vf = f"ass={ass_name}" if ass_name else None
        if vf:
            cmd += ["-vf", vf, "-map", "0:v:0", "-map", "0:a:0?"]
        else:
            cmd += ["-map", "0:v:0", "-map", "0:a:0?"]

    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart", out_name]
    proc = subprocess.run(cmd, cwd=out_dir, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for {out_name}:\n{proc.stderr[-800:]}")
