import os, time, shutil, zipfile
from pathlib import Path
import streamlit as st

st.set_page_config(page_title="ViralClipper", page_icon="🎬", layout="wide")
st.title("🎬 ViralClipper")
st.caption("Paste a YouTube link → get 10 viral-ready short clips + keywords, all downloadable.")

# ---------- Sidebar ----------
with st.sidebar:
    st.header("⚙️ Settings")
    count = st.slider("Number of clips", 4, 12, 10)
    target_len = st.select_slider("Target clip length (seconds)", [15, 20, 30, 45, 60, 75, 90], 30)
    aspect = st.radio("Output format",
                      ["Vertical 9:16 (blurred bg)", "Vertical 9:16 (face-crop fill)", "Original"], 0)
    captions = st.checkbox("Burn-in captions", True)
    smart_crop = st.checkbox("Face-aware smart crop", True)
    st.divider()
    api_key = st.text_input("OpenAI API key (optional)", type="password",
                            help="Enables the AI viral agent + AI keywords. Leave empty to use the "
                                 "built-in heuristic engine.")
    model = st.text_input("OpenAI model", "gpt-4o-mini")
    cookies = st.text_input("cookies.txt path (advanced, optional)",
                            help="For age-restricted / member videos. Export with a browser extension.")

url = st.text_input("YouTube video URL", placeholder="https://www.youtube.com/watch?v=...")
go = st.button("🚀 Generate clips", type="primary", disabled=not url)

MODES = {"Vertical 9:16 (blurred bg)": "blur",
         "Vertical 9:16 (face-crop fill)": "fill",
         "Original": "original"}

def run_pipeline(url):
    from clipper.utils import extract_video_id, ensure_ffmpeg
    from clipper import downloader, transcript, virality, editor, keywords

    ensure_ffmpeg()
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Could not parse a YouTube video ID from that URL.")

    client = None
    if api_key.strip():
        from openai import OpenAI
        client = OpenAI(api_key=api_key.strip())

    work = Path("outputs") / f"{video_id}_{int(time.time())}"
    work.mkdir(parents=True, exist_ok=True)

    with st.status("Analyzing video…", expanded=True) as status:
        st.write("Fetching metadata…")
        meta = downloader.fetch_metadata(url)
        st.write(f"**{meta['title']}** — {meta['channel']} ({int(meta['duration'] // 60)} min)")
        st.write("Fetching transcript…")
        segs = transcript.get_transcript(video_id)
        if segs:
            st.write(f"Transcript OK ({len(segs)} segments).")
        else:
            st.warning("No transcript available → clips will be evenly spaced; keywords from "
                       "title/description only.")
        st.write("🤖 AI agent is scanning for the most viral moments…")
        moments = virality.select_moments(client, model, meta, segs, target_len, count)
        st.write(f"Selected {len(moments)} moments.")
        status.update(label="Viral moments selected ✔", state="complete")

    with st.spinner("Downloading source video… (this can take a minute)"):
        src = downloader.download_video(url, str(work), cookies_file=cookies.strip() or None)

    mode = MODES[aspect]
    clips = []
    bar = st.progress(0.0, text="Rendering clips…")
    for i, m in enumerate(moments, 1):
        start = max(0.0, min(float(m["start"]), max(0.0, meta["duration"] - 3)))
        dur = max(5.0, min(float(m["end"]) - start, 90.0))
        out = work / f"clip_{i:02d}.mp4"
        caps = ([s for s in segs
                 if s["start"] < start + dur and s["start"] + s.get("dur", 2) > start]
                if captions else None)
        editor.make_clip(src, str(out), start, dur, mode, captions=caps, smart_crop=smart_crop)
        clips.append({"index": i, "path": str(out), "start": start, "dur": dur,
                      "score": int(m.get("score", 60)), "hook": m.get("hook", ""),
                      "title": m.get("title", f"Clip {i}"), "reason": m.get("reason", ""),
                      "text": " ".join(s["text"] for s in (caps or []))[:1200]})
        bar.progress(i / len(moments), text=f"Rendered clip {i}/{len(moments)}")
    bar.progress(1.0, text="All clips rendered ✔")

    with st.spinner("Generating keywords & hashtags…"):
        kw_map = keywords.generate(client, model, meta, clips)

    return {"meta": meta, "clips": clips, "kw": kw_map, "work": str(work)}

def card(c, kw, best=False):
    k = kw.get(c["index"], {})
    st.video(c["path"], format="video/mp4")
    st.write(f"⏱️ {int(c['start'] // 60)}:{int(c['start'] % 60):02d}–"
             f"{int((c['start'] + c['dur']) // 60)}:{int((c['start'] + c['dur']) % 60):02d}  •  "
             f"🔥 Virality score **{c['score']}/100**")
    if c.get("reason"):
        st.caption(c["reason"])
    if k.get("title"):
        st.markdown(f"**Title:** {k['title']}")
    if k.get("keywords"):
        st.markdown("**Keywords:** " + "  ".join(f"`{x}`" for x in k["keywords"]))
    if k.get("hashtags"):
        st.markdown("**Hashtags:** " + " ".join(k["hashtags"]))
    if k.get("description"):
        st.caption("Description: " + k["description"])
    p = Path(c["path"])
    st.download_button("⬇️ Download this clip", p.read_bytes(),
                       file_name=f"{__import__('clipper.utils', fromlist=['slugify']).slugify(k.get('title') or c['title'])}.mp4",
                       key=f"dl_{c['index']}")

# ---------- Run ----------
if go:
    st.session_state.pop("results", None)
    try:
        st.session_state["results"] = run_pipeline(url)
    except Exception as e:
        st.error(f"Something went wrong: {e}")

results = st.session_state.get("results")
if results:
    clips = sorted(results["clips"], key=lambda c: -c["score"])
    kw = results["kw"]
    st.success(f"✅ Done! {len(clips)} clips saved in: {results['work']}")
    if st.button("📂 Open output folder in Explorer"):
        try:
            os.startfile(str(Path(results["work"]).resolve()))  # Windows
        except Exception:
            st.code(str(Path(results["work"]).resolve()))

    top = clips[0]
    st.subheader(f"🏆 #1 Most viral: {top['title']}")
    card(top, kw, best=True)

    st.divider()
    st.subheader("The rest of the pack")
    for rank, c in enumerate(clips[1:], start=2):
        with st.expander(f"#{rank} • {c['title']} — score {c['score']}"):
            card(c, kw)

    st.divider()
    zp = Path(results["work"]) / "all_clips.zip"
    if not zp.exists():
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for c in results["clips"]:
                z.write(c["path"], arcname=Path(c["path"]).name)
    st.download_button("⬇️ Download ALL clips (.zip)", zp.read_bytes(), file_name="viral_clips.zip")
