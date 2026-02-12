
import streamlit as st
import requests
import time
import os
import json

# ============================================================
# CONFIG & STYLE
# ============================================================
st.set_page_config(page_title="BIRU_BHAI | Studio", page_icon="🎬", layout="wide")

st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .stButton>button { width: 100%; border-radius: 8px; background-color: #4CAF50; color: white; font-weight: bold; }
    .clip-card { padding: 1rem; border-radius: 10px; background-color: #1e2130; border: 1px solid #30363d; margin-bottom: 1rem; }
    .caption-box { background-color: #0d1117; padding: 10px; border-radius: 5px; border: 1px dashed #4CAF50; font-family: monospace; }
</style>
""", unsafe_allow_html=True)

# Production Vercel URL (Update this with your actual Vercel domain)
DEFAULT_API_BASE = "https://biru-kataria.vercel.app" 
API_BASE = st.sidebar.text_input("Backend API URL", value=DEFAULT_API_BASE)

def get_health():
    try: return requests.get(f"{API_BASE}/health", timeout=3).json()
    except: return None

def get_assets():
    try: return requests.get(f"{API_BASE}/assets").json()
    except: return []

def get_asset_detail(asset_id):
    try: return requests.get(f"{API_BASE}/assets/{asset_id}").json()
    except: return None

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.title("🎬 BIRU_BHAI STUDIO")
    st.caption("v0.5.0 | 12-Agent System Active")
    st.divider()
    if get_health(): st.success("Studio Online")
    else: st.error("Backend Offline")
    
    st.info("🧠 **Decisions**: GPT-4o-Vision\n"
            "🗣️ **Voice**: Enabled via WhatsApp\n"
            "🖼️ **Frames**: Frame & Poster Agents")

# ============================================================
# HUB
# ============================================================
st.title("Main Studio Hub 🧬")

t_ingest, t_library, t_summarizer = st.tabs(["📲 Ingest Content", "🎥 Viral Library", "🧠 AI Summarizer"])

with t_ingest:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📤 Local Video")
        up = st.file_uploader("Upload", type=["mp4", "mov"])
        if up and st.button("Start AI Army"):
            with st.spinner("Uploading and triggers agents..."):
                resp = requests.post(f"{API_BASE}/assets/upload", files={"file": (up.name, up.getvalue())})
                if resp.status_code == 201: st.success(f"Task #{resp.json()['id']} Created!")
    with c2:
        st.subheader("🔗 YouTube Link")
        yt_url = st.text_input("Paste Link")
        if yt_url and st.button("Download & Process Link"):
            resp = requests.post(f"{API_BASE}/assets/youtube", json={"url": yt_url})
            if resp.status_code == 201: st.success("AI has taken control of the link.")

with t_summarizer:
    st.subheader("📝 YouTube AI Summarizer")
    st.write("Extract wisdom from any YouTube video in seconds.")
    
    sum_url = st.text_input("YouTube URL for Summary", key="sum_url")
    if sum_url and st.button("Generate AI Summary"):
        with st.spinner("Biru Bhai is watching the video... 🚬"):
            try:
                resp = requests.post(f"{API_BASE}/assets/youtube/summary", json={"url": sum_url})
                if resp.status_code == 200:
                    summary_text = resp.json().get("summary", "No summary found.")
                    st.markdown("### 📥 Viral Summary")
                    st.markdown(summary_text)
                else:
                    st.error(f"Error: {resp.text}")
            except Exception as e:
                st.error(f"Technical glitch: {e}")

with t_library:
    assets = get_assets()
    if not assets: st.write("No projects yet.")
    for asset in assets[:10]: # Show recent 10
        with st.expander(f"📦 PROJECT #{asset['id']} - {asset['title']} [{asset['status']}]"):
            detail = get_asset_detail(asset['id'])
            if detail:
                if detail['status'] == "PROCESSING":
                    st.info("🤖 AI Brain is 'seeing' the footage and choosing 10 viral clips...")
                    st.progress(0.4)
                elif detail['status'] == "READY":
                    clips = detail.get('clips', [])
                    for i, clip in enumerate(clips):
                        with st.container():
                            st.markdown(f"---")
                            cc1, cc2, cc3 = st.columns([1, 1, 1.5])
                            with cc1:
                                if clip.get('file_path'):
                                    # Logic to find the poster
                                    # Posters are named poster_{asset_id}_{start_time}.jpg
                                    poster_url = f"{API_BASE}/media/posters/poster_{asset['id']}_{int(clip['start_time'])}.jpg"
                                    st.image(poster_url, caption=f"AI Generated Poster #{i+1}")
                            with cc2:
                                st.write(f"**Viral Clip #{i+1}**")
                                st.write(f"🕒 {clip['start_time']}s - {clip['end_time']}s")
                                st.metric("Viral Score", f"{clip.get('virality_score',0)*10:.1f}/10")
                                
                                # Parse Captions
                                try:
                                    caps = json.loads(clip.get('transcription', '{}'))
                                    st.write("**Captions:**")
                                    st.caption(f"IG: {caps.get('ig', 'N/A')}")
                                    st.caption(f"YT: {caps.get('yt', 'N/A')}")
                                except: st.write(f"Reason: {clip.get('transcription')}")
                            with cc3:
                                if clip.get('file_path'):
                                    rel = clip['file_path'].replace("\\", "/").split("media/")[-1]
                                    st.video(f"{API_BASE}/media/{rel}")
                                    st.button("📲 Post to IG (Demo)", key=f"post_{clip['id']}")
                elif detail['status'] == "FAILED":
                    st.error(f"Error: {detail['error_message']}")

st.divider()
st.caption("BIRU_BHAI — The Solo Creator OS | Built for the 100M Views.")
