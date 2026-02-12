
import streamlit as st
import requests
import json
import time
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

st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>
    * { font-family: 'Outfit', sans-serif; }
    .main { background: linear-gradient(135deg, #0f172a 0%, #020617 100%); color: #f8fafc; }
    [data-testid="stSidebar"] {
        background-color: rgba(15, 23, 42, 0.8) !important;
        backdrop-filter: blur(10px);
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }
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
    .gradient-text {
        background: linear-gradient(90deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
    }
    .stButton>button {
        background: linear-gradient(90deg, #0ea5e9, #6366f1) !important;
        color: white !important; border: none !important;
        border-radius: 8px !important; padding: 0.5rem 1rem !important;
        font-weight: 600 !important; transition: opacity 0.2s !important;
    }
    .stButton>button:hover { opacity: 0.9 !important; }
    .step-done { color: #22c55e; font-weight: 600; }
    .step-running { color: #f59e0b; font-weight: 600; }
    .step-fail { color: #ef4444; font-weight: 600; }
    .step-pending { color: #64748b; }
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
    try: return requests.get(f"{API_BASE}{endpoint}", timeout=15).json()
    except: return None

def api_post(endpoint, json_data=None, files=None):
    try: return requests.post(f"{API_BASE}{endpoint}", json=json_data, files=files, timeout=120)
    except Exception as e: return f"Error: {e}"

# ============================================================
# SIDEBAR NAVIGATION
# ============================================================
with st.sidebar:
    st.markdown("<h1 class='gradient-text'>BIRU_BHAI</h1>", unsafe_allow_html=True)
    st.caption("Solo Creator OS v2.0 | 5-Step Pipeline Active")
    st.divider()
    nav = st.radio(
        "CORE MODULES",
        ["🏠 Dashboard", "🚀 Pipeline", "🎬 Video Clips", "🧠 AI Strategy", "📱 WhatsApp Agent"],
        index=0
    )
    st.divider()
    try:
        health = requests.get(f"{API_BASE}/health", timeout=2).json()
        st.success("🟢 System Online") if health else st.error("🔴 Backend Down")
    except:
        st.error("🔴 Connection Failed")
        if st.button("Retry"): st.rerun()

# ============================================================
# PIPELINE STEP RENDERER
# ============================================================
STEP_ICONS = {1: "📥", 2: "🎙️", 3: "🧠", 4: "✂️", 5: "📤"}
STEP_NAMES = {1: "Fetch Metadata", 2: "Transcribe Audio", 3: "AI Analysis", 4: "Generate Clips", 5: "Caption & Post"}

def render_pipeline_steps(steps):
    """Render 5-step pipeline progress."""
    for s in steps:
        num = s['step_number']
        icon = STEP_ICONS.get(num, "⚪")
        name = s['step_name']
        status = s['status']
        summary = s.get('result_summary', '')

        if status == "COMPLETED":
            st.markdown(f"<div class='premium-card'>{icon} <span class='step-done'>Step {num}: {name} — Done</span><br><small style='color:#94a3b8'>{summary or ''}</small></div>", unsafe_allow_html=True)
        elif status == "RUNNING":
            st.markdown(f"<div class='premium-card' style='border-color:#f59e0b'>{icon} <span class='step-running'>Step {num}: {name} — Running...</span></div>", unsafe_allow_html=True)
        elif status == "POLLING":
            st.markdown(f"<div class='premium-card' style='border-color:#f59e0b'>{icon} <span class='step-running'>Step {num}: {name} — Waiting for clips...</span></div>", unsafe_allow_html=True)
        elif status == "FAILED":
            err = s.get('error_message', 'Unknown error')
            st.markdown(f"<div class='premium-card' style='border-color:#ef4444'>{icon} <span class='step-fail'>Step {num}: {name} — Failed</span><br><small style='color:#ef4444'>{err}</small></div>", unsafe_allow_html=True)
        elif status == "SKIPPED":
            st.markdown(f"<div class='premium-card'>{icon} <span style='color:#94a3b8'>Step {num}: {name} — Skipped</span><br><small style='color:#64748b'>{summary or ''}</small></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='premium-card'>{icon} <span class='step-pending'>Step {num}: {name} — Pending</span></div>", unsafe_allow_html=True)

def render_asset_card(a):
    """Render a rich information card for a content asset."""
    status = a.get('status', 'PENDING')
    step = a.get('pipeline_step', 0)
    step_name = STEP_NAMES.get(step, "Initializing")
    
    # Progress visualization (colored icons)
    progress_html = ""
    for i in range(1, 6):
        if i < step: color = "#22c55e" # Done
        elif i == step: color = "#f59e0b" # Running
        else: color = "#475569" # Pending
        progress_html += f"<span style='color:{color}; margin-right:5px'>{STEP_ICONS.get(i, '⚪')}</span>"

    # Metadata extraction
    meta = a.get('meta_data', {})
    if isinstance(meta, str):
        try: meta = json.loads(meta)
        except: meta = {}
    
    duration = meta.get('duration_string') or meta.get('duration') or "N/A"
    
    html = f"""
    <div class="premium-card">
        <div style="display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center;">
                <div style="background: linear-gradient(135deg, #818cf8, #6366f1); width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; margin-right: 1rem; font-weight: 700; font-size: 1.2rem;">
                    {a['title'][0] if a.get('title') else 'B'}
                </div>
                <div>
                    <h4 style="margin:0; font-weight:700;">{a.get('title', 'Untitiled')}</h4>
                    <small style="color:#94a3b8">ID: #{a['id']} | {status} | Step {step}: {step_name}</small><br>
                    <div style="margin-top: 5px;">{progress_html}</div>
                </div>
            </div>
            <div style="text-align: right;">
                <small style="color:#64748b">Duration: {duration}</small>
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


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
        <h3>🔥 Pipeline v2.0 Active</h3>
        <p>5-Step AI Pipeline: Fetch → Transcribe → Analyze → Clip → Auto Post</p>
    </div>
    """, unsafe_allow_html=True)

    # Show recent assets
    assets = api_get("/assets") or []
    if assets:
        st.subheader("Recent Projects")
        for a in assets[:5]:
            render_asset_card(a)

elif nav == "🚀 Pipeline":
    st.markdown("<h1 class='gradient-text'>Content Pipeline</h1>", unsafe_allow_html=True)

    # URL Input
    yt_url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")

    if yt_url and st.button("Start Pipeline"):
        with st.spinner("Creating asset..."):
            resp = api_post("/assets/youtube", json_data={"url": yt_url})
            if isinstance(resp, requests.Response) and resp.status_code == 201:
                data = resp.json()
                st.session_state["pipeline_asset_id"] = data["id"]
                st.session_state["pipeline_running"] = True
                st.success(f"Asset created (ID: {data['id']}). Pipeline starting...")
                st.rerun()
            else:
                st.error(f"Failed to create asset: {resp}")

    # Active Pipeline Monitor
    if "pipeline_asset_id" in st.session_state:
        asset_id = st.session_state["pipeline_asset_id"]
        st.divider()
        st.subheader(f"Pipeline #{asset_id}")

        # Get current status
        status = api_get(f"/pipeline/{asset_id}/status")
        if status:
            # Show overall status
            overall = status.get("overall_status", "PENDING")
            title = status.get("title", "Processing...")
            st.markdown(f"**{title}** | Status: `{overall}`")

            # Progress bar
            steps = status.get("steps", [])
            completed = sum(1 for s in steps if s['status'] in ('COMPLETED', 'SKIPPED'))
            st.progress(completed / 5, text=f"Step {status.get('current_step', 0)} of 5")

            # Render steps
            render_pipeline_steps(steps)

            # Auto-advance logic
            if st.session_state.get("pipeline_running", False):
                current_step = status.get("current_step", 0)
                current_step_status = None
                for s in steps:
                    if s['step_number'] == current_step:
                        current_step_status = s['status']
                        break

                should_advance = (
                    overall not in ("READY", "FAILED") and
                    current_step_status in ("PENDING", "COMPLETED", "SKIPPED", "POLLING", None)
                )

                if should_advance and current_step <= 5:
                    with st.spinner(f"Running Step {current_step if current_step_status not in ('COMPLETED', 'SKIPPED') else current_step + 1}..."):
                        advance_resp = api_post(f"/pipeline/{asset_id}/advance")
                        if isinstance(advance_resp, requests.Response):
                            if advance_resp.status_code == 200:
                                time.sleep(1)
                                st.rerun()
                            else:
                                try:
                                    err = advance_resp.json().get("detail", "Unknown error")
                                except:
                                    err = advance_resp.text
                                st.error(f"Step failed: {err}")
                                st.session_state["pipeline_running"] = False
                        else:
                            st.error(f"Connection error: {advance_resp}")
                            st.session_state["pipeline_running"] = False

                elif overall == "READY":
                    st.session_state["pipeline_running"] = False
                    st.balloons()
                    st.success("Pipeline complete! All 5 steps done.")

                elif overall == "FAILED":
                    st.session_state["pipeline_running"] = False

            # Manual controls
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Retry / Continue"):
                    st.session_state["pipeline_running"] = True
                    st.rerun()
            with col2:
                if st.button("Refresh Status"):
                    st.rerun()
            with col3:
                if st.button("New Pipeline"):
                    del st.session_state["pipeline_asset_id"]
                    st.session_state["pipeline_running"] = False
                    st.rerun()
        else:
            st.error("Could not fetch pipeline status. Backend may be offline.")

    # Show past pipelines
    st.divider()
    st.subheader("Past Pipelines")
    assets = api_get("/assets") or []
    for a in assets[:10]:
        render_asset_card(a)
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("View", key=f"view_{a['id']}"):
                st.session_state["pipeline_asset_id"] = a['id']
                st.session_state["pipeline_running"] = False
                st.rerun()


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
                        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
                        cc1, cc2 = st.columns([2, 3])
                        with cc1:
                            if "http" in str(clip.get('file_path', '')):
                                st.video(clip['file_path'])
                        with cc2:
                            st.write(f"**Viral Score: {clip.get('virality_score', 0)*10:.1f}/10**")
                            st.write(f"Duration: {clip.get('duration', 0)}s")
                            if clip.get('transcription'):
                                try:
                                    caps = json.loads(clip['transcription'])
                                    st.write(f"IG: {caps.get('ig', 'N/A')}")
                                    st.write(f"YT: {caps.get('yt', 'N/A')}")
                                except:
                                    st.write(f"Caption: {clip['transcription'][:100]}")
                        st.markdown("</div>", unsafe_allow_html=True)
                else:
                    st.info("No clips generated yet.")


elif nav == "🧠 AI Strategy":
    st.markdown("<h1 class='gradient-text'>Wisdom Extract (AI Summarizer)</h1>", unsafe_allow_html=True)
    sum_url = st.text_input("Enter YouTube URL for instant wisdom")
    if st.button("Generate Strategy"):
        with st.spinner("Biru Bhai is watching..."):
            resp = api_post("/assets/youtube/summary", json_data={"url": sum_url})
            if isinstance(resp, requests.Response) and resp.status_code == 200:
                st.markdown(resp.json().get("summary", "No data"))

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
    st.write("Module initialization in progress...")

st.divider()
st.caption("BIRU_BHAI — The Solo Creator OS | Designed for the 1%ers.")
