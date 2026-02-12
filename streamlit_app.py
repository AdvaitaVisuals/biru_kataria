
import streamlit as st
import requests
import json
import os
from datetime import datetime

# ============================================================
# PREMIUM CONFIG & AESTHETICS
# ============================================================
st.set_page_config(
    page_title="BIRU_BHAI | Enterprise Studio",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium Glassmorphism Look
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>
    /* Global Styles */
    * { font-family: 'Outfit', sans-serif; }
    .main { background: linear-gradient(135deg, #0f172a 0%, #020617 100%); color: #f8fafc; }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: rgba(15, 23, 42, 0.8) !important;
        backdrop-filter: blur(10px);
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    /* Card Component */
    .premium-card {
        background: rgba(30, 41, 59, 0.5);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .premium-card:hover { border-color: #38bdf8; transform: translateY(-2px); }
    
    /* Gradient Text */
    .gradient-text {
        background: linear-gradient(90deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
    }
    
    /* Buttons */
    .stButton>button {
        background: linear-gradient(90deg, #0ea5e9, #6366f1) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 600 !important;
        transition: opacity 0.2s !important;
    }
    .stButton>button:hover { opacity: 0.9 !important; }

    /* Custom scrollbar */
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: #0f172a; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# UTILITIES
# ============================================================
DEFAULT_API_BASE = "https://biru-kataria.vercel.app" 
API_BASE = st.sidebar.text_input("Backend API Config", value=DEFAULT_API_BASE)

def api_get(endpoint):
    try: return requests.get(f"{API_BASE}{endpoint}", timeout=5).json()
    except: return None

def api_post(endpoint, json_data=None, files=None):
    try: return requests.post(f"{API_BASE}{endpoint}", json=json_data, files=files, timeout=120)
    except Exception as e: return f"Error: {e}"

# ============================================================
# SIDEBAR NAVIGATION
# ============================================================
with st.sidebar:
    st.markdown("<h1 class='gradient-text'>BIRU_BHAI</h1>", unsafe_allow_html=True)
    st.caption("Solo Creator OS v1.2.0 • Phase: Active")
    
    st.divider()
    
    nav = st.radio(
        "CORE MODULES",
        [
            "🏠 Dashboard",
            "📤 Ingest Content",
            "🎬 Video Clips",
            "📝 Transcription",
            "🧠 AI Strategy",
            "📅 Scheduling",
            "📊 Audience Insights",
            "📈 Engagement Analytics",
            "📱 WhatsApp Agent"
        ],
        index=0
    )
    
    st.divider()
    try:
        health = requests.get(f"{API_BASE}/health", timeout=2).json()
        if health:
            st.success("🟢 System Online")
        else:
            st.error("🔴 Backend Disconnected")
    except:
        st.error("🔴 Connection Failed")
        if st.button("Retry Link"):
            st.rerun()

# ============================================================
# ROUTING LOGIC
# ============================================================

if nav == "🏠 Dashboard":
    st.markdown("<h1 class='gradient-text'>System Intelligence Overview</h1>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Viral Projects", "12", "+2")
    with c2: st.metric("Clips Generated", "148", "+15")
    with c3: st.metric("Engagement Index", "92%", "+4%")
    with c4: st.metric("AI Tokens Used", "4.2M", "Eco-mode")
    
    st.markdown("""
    <div class='premium-card'>
        <h3>🔥 Trending Strategy</h3>
        <p>Your Haryana-style persona is resonating with 18-24 demographics. 
        <b>Strategy Recommendation:</b> Increase split-screen focus in Finance niches.</p>
    </div>
    """, unsafe_allow_html=True)

elif nav == "📤 Ingest Content":
    st.markdown("<h1 class='gradient-text'>Content Hybrid Ingest</h1>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📁 Heavy Upload")
        up = st.file_uploader("Drop master footage", type=["mp4", "mov"])
        if up and st.button("Initialize Processing"):
            with st.spinner("Uploading to Biru Cloud..."):
                resp = api_post("/assets/upload", files={"file": (up.name, up.getvalue())})
                if isinstance(resp, requests.Response) and resp.status_code == 201:
                    st.success("Bhai, uploading done. Agents are working!")
    with c2:
        st.subheader("🌐 Remote Link")
        yt_url = st.text_input("YouTube / Cloud Link")
        if yt_url and st.button("Fetch & Analyze"):
            resp = api_post("/assets/youtube", json_data={"url": yt_url})
            if isinstance(resp, requests.Response) and resp.status_code == 201:
                st.success("Biru Bhai is fetching the master link. System Paad denge!")

elif nav == "🎬 Video Clips":
    st.markdown("<h1 class='gradient-text'>Viral Library</h1>", unsafe_allow_html=True)
    assets = api_get("/assets") or []
    if not assets:
        st.info("No projects in the pipeline yet.")
    else:
        for asset in assets[:5]:
            with st.expander(f"📦 {asset['title']} | Status: {asset['status']}"):
                detail = api_get(f"/assets/{asset['id']}")
                if detail and detail.get('clips'):
                    for clip in detail['clips']:
                        st.markdown(f"<div class='premium-card'>", unsafe_allow_html=True)
                        cc1, cc2 = st.columns([2, 3])
                        with cc1:
                            if "http" in str(clip['file_path']):
                                st.video(clip['file_path'])
                        with cc2:
                            st.write(f"**Viral Score: {clip['virality_score']*10:.1f}/10**")
                            st.write(f"Duration: {clip['duration']}s")
                            st.button("Post to Reels", key=f"p_{clip['id']}")
                        st.markdown("</div>", unsafe_allow_html=True)

elif nav == "📝 Transcription":
    st.markdown("<h1 class='gradient-text'>Global Transcription Engine</h1>", unsafe_allow_html=True)
    st.write("Automatically extracts dialogue and translates to Haryanvi-English mix.")
    assets = api_get("/assets") or []
    for asset in assets[:5]:
        detail = api_get(f"/assets/{asset['id']}")
        if detail and detail.get('clips'):
            st.subheader(f"Project: {asset['title']}")
            for i, clip in enumerate(detail['clips']):
                st.text_area(f"Clip #{i+1} Transcript", clip.get('transcription', "Processing..."), height=100)

elif nav == "🧠 AI Strategy":
    st.markdown("<h1 class='gradient-text'>Wisdom Extract (AI Summarizer)</h1>", unsafe_allow_html=True)
    sum_url = st.text_input("Enter YouTube URL for instant wisdom")
    if st.button("Generate Strategy"):
        with st.spinner("Biru Bhai is watching... 🚬"):
            resp = api_post("/assets/youtube/summary", json_data={"url": sum_url})
            if isinstance(resp, requests.Response) and resp.status_code == 200:
                st.markdown(resp.json().get("summary", "No data"))

elif nav == "📂 Scheduling" or nav == "📅 Scheduling":
    st.markdown("<h1 class='gradient-text'>Content Calendar</h1>", unsafe_allow_html=True)
    st.info("Agent #9 (Scheduler) is coming soon. Currently managed by Biru Bhai manually.")
    st.image("https://images.unsplash.com/photo-1506784983877-45594efa4cbe?auto=format&fit=crop&q=80&w=1000", caption="Future Roadmap")

elif nav == "📊 Audience Insights":
    st.markdown("<h1 class='gradient-text'>Deep Demographic Analysis</h1>", unsafe_allow_html=True)
    st.markdown("""
    <div class='premium-card'>
        <h3>👥 Top Audience: Haryana, Delhi, Toronto</h3>
        <p>Engagement is highest between <b>9 PM - 11 PM IST</b>.</p>
    </div>
    """, unsafe_allow_html=True)

elif nav == "📱 WhatsApp Agent":
    st.markdown("<h1 class='gradient-text'>WhatsApp Agent Monitor</h1>", unsafe_allow_html=True)
    msgs = api_get("/whatsapp/messages") or []
    for m in msgs:
        st.markdown(f"""
        <div class='premium-card'>
            <b>From: {m['sender']}</b> | {m['timestamp'][:19]}<br>
            <p style='color: #cbd5e1'>Bhai: {m['message']}</p>
            <p style='color: #38bdf8'>Biru Bhai: {m['response'] or '...Thinking...'}</p>
        </div>
        """, unsafe_allow_html=True)

else:
    st.title(nav)
    st.write("Module logic initialization in progress...")

st.divider()
st.caption("BIRU_BHAI — The Solo Creator OS | Designed for the 1%ers.")
