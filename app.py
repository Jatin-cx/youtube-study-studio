"""
YouTube Study Studio AI - Ultra-Stable Multi-Device Web & Mobile App.
Optimized for 100% reliability on Mobile Phones, Tablets, and Desktop Browsers.
Features:
- Mobile-responsive video header with prominent duration badge.
- Instant in-memory result presentation (eliminates mobile disconnects and rerun bugs).
- Android Innertube client fallback to bypass cloud datacenter IP blocks.
- Gemini 3.5 Flash Lite multi-model failover for 1-3+ hour lectures.
- SQLite Database history with private user isolation.
"""

import os
import re
import uuid
from pathlib import Path
from dotenv import load_dotenv
import streamlit as st

from youtube_extractor import (
    get_video_metadata,
    get_playlist_videos,
    get_video_transcript,
    is_playlist_url,
    extract_video_id,
)
from notes_generator import generate_study_notes
from pdf_generator import create_study_pdf
from db_manager import (
    init_db,
    save_study_record,
    get_all_records,
    get_record_by_id,
    delete_record,
    get_db_stats
)
from google import genai

# Load backend environment variables (supports .env and Streamlit Cloud Secrets)
load_dotenv()
BACKEND_API_KEY = os.getenv("GEMINI_API_KEY", "")
if not BACKEND_API_KEY:
    try:
        BACKEND_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        pass

# Page Configuration: Mobile & Desktop responsive layout
st.set_page_config(
    page_title="LectureScribe Studio AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Output directory for generated PDFs
OUTPUT_DIR = Path("generated_notes")
OUTPUT_DIR.mkdir(exist_ok=True)

# Initialize database
init_db()

# User Private Session Isolation (Resilient across mobile and desktop)
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:12]

USER_ID = st.session_state.user_id


def sanitize_filename(name: str) -> str:
    """Sanitize strings for safe file paths."""
    sanitized = re.sub(r'[\\/*?:"<>|]', '', name)
    return sanitized.strip()[:60]


# ---------------- MOBILE & DESKTOP RESPONSIVE CSS ----------------
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', sans-serif;
}

.stApp {
    background-color: #F8FAFC;
}

/* Responsive Container Padding */
.block-container {
    padding-top: 14px !important;
    padding-bottom: 30px !important;
    padding-left: 20px !important;
    padding-right: 20px !important;
    max-width: 100% !important;
}

/* Sleek Top Bar */
.top-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 12px 20px;
    margin-bottom: 16px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
}

.brand-text {
    font-size: 19px;
    font-weight: 800;
    color: #1E293B;
    display: flex;
    align-items: center;
    gap: 8px;
}

.brand-badge {
    background: #EEF2FF;
    color: #4F46E5;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 6px;
}

/* Universal Cards */
.dash-card {
    background: white;
    border-radius: 14px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.04);
    padding: 18px 20px;
    margin-bottom: 16px;
}

/* Badges */
.video-badge {
    background: #EEF2FF;
    color: #4F46E5;
    font-weight: 600;
    font-size: 13px;
    padding: 4px 10px;
    border-radius: 6px;
    display: inline-block;
    margin-right: 6px;
    margin-bottom: 4px;
}

.duration-badge {
    background: #FEF3C7;
    color: #B45309;
    font-weight: 700;
    font-size: 13px;
    padding: 4px 10px;
    border-radius: 6px;
    display: inline-block;
    margin-right: 6px;
    margin-bottom: 4px;
}

/* Buttons */
.stButton>button {
    background: linear-gradient(135deg, #4F46E5 0%, #6366F1 100%) !important;
    color: white !important;
    font-weight: 700 !important;
    font-size: 15px !important;
    padding: 10px 24px !important;
    border-radius: 10px !important;
    border: none !important;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3) !important;
}

.stDownloadButton>button {
    background: linear-gradient(135deg, #059669 0%, #10B981 100%) !important;
    color: white !important;
    font-weight: 700 !important;
    font-size: 14px !important;
    padding: 8px 20px !important;
    border-radius: 8px !important;
    border: none !important;
}

/* Inputs */
.stTextInput>div>div>input {
    border-radius: 10px !important;
    font-size: 15px !important;
    padding: 10px 14px !important;
}

header[data-testid="stHeader"] {
    background: transparent;
}
footer {
    visibility: hidden;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Session State Initialization
if "active_record" not in st.session_state:
    st.session_state.active_record = None

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []


# =====================================================================
# SIDEBAR: SAVED SESSIONS & HISTORY LIBRARY
# =====================================================================
with st.sidebar:
    st.markdown("### 📚 Study Library")
    stats = get_db_stats(USER_ID)
    st.caption(f"**{stats['total_notes']}** Notes in your private library")

    if st.button("➕ New Study Session", width="stretch"):
        st.session_state.active_record = None
        st.session_state.chat_messages = []
        st.rerun()

    st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

    hist_search = st.text_input("🔍 Search History", placeholder="Topic or channel...", label_visibility="collapsed")
    records = get_all_records(USER_ID, hist_search)

    if not records:
        st.caption("No past sessions yet. Generate your first lecture notes!")
    else:
        for r in records:
            col_h1, col_h2 = st.columns([4, 1])
            with col_h1:
                label = f"📖 {r['title'][:26]}..." if len(r['title']) > 26 else f"📖 {r['title']}"
                if st.button(label, key=f"rec_btn_{r['id']}", width="stretch"):
                    full_r = get_record_by_id(r['id'], user_id=USER_ID)
                    if full_r:
                        st.session_state.active_record = full_r
                        st.session_state.chat_messages = []
                        st.rerun()
            with col_h2:
                if st.button("✕", key=f"rec_del_{r['id']}", help="Delete"):
                    delete_record(r['id'], user_id=USER_ID)
                    if st.session_state.active_record and st.session_state.active_record.get('id') == r['id']:
                        st.session_state.active_record = None
                    st.rerun()


# =====================================================================
# TOP APP BAR
# =====================================================================
st.markdown("""
<div class="top-nav">
    <div class="brand-text">
        <span>🎓</span>
        <span>LectureScribe AI</span>
        <span class="brand-badge">STUDIO</span>
    </div>
    <div style="font-size: 13px; color: #64748B;">
        Full Course Notes • AI Tutor Chat • Printable PDF
    </div>
</div>
""", unsafe_allow_html=True)


# =====================================================================
# MAIN STAGE: ACTIVE SESSION OR GENERATION INPUT
# =====================================================================

# CASE 1: Active Record Loaded
if st.session_state.active_record:
    rec = st.session_state.active_record

    # Header Banner of Active Lecture
    st.markdown(f"""
    <div class="dash-card" style="background: linear-gradient(135deg, #1E1B4B 0%, #312E81 50%, #4338CA 100%); color: white;">
        <h3 style="margin: 0 0 8px 0; color: white;">{rec['title']}</h3>
        <div>
            <span class="video-badge" style="background: rgba(255,255,255,0.2); color: white;">👤 {rec['channel']}</span>
            <span class="duration-badge">⏱️ {rec['duration']}</span>
            <span class="video-badge" style="background: rgba(255,255,255,0.2); color: white;">📅 {rec['created_at']}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Action Toolbar
    col_act1, col_act2, col_act3 = st.columns([1.5, 1.5, 2])
    with col_act1:
        if rec.get('pdf_blob'):
            st.download_button(
                label="⬇️ Download Study Guide PDF",
                data=rec['pdf_blob'],
                file_name=rec['pdf_filename'],
                mime="application/pdf",
                type="primary",
                width="stretch"
            )
        elif os.path.exists(rec.get('pdf_path', '')):
            with open(rec['pdf_path'], "rb") as pf:
                st.download_button(
                    label="⬇️ Download Study Guide PDF",
                    data=pf.read(),
                    file_name=rec['pdf_filename'],
                    mime="application/pdf",
                    type="primary",
                    width="stretch"
                )
    with col_act2:
        if st.button("➕ Generate Another Video", width="stretch"):
            st.session_state.active_record = None
            st.session_state.chat_messages = []
            st.rerun()

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # Interactive Workspace Tabs
    tab_notes, tab_chat, tab_quiz, tab_transcript = st.tabs([
        "📖 Comprehensive Notes",
        "💬 Chat with AI Lecture Tutor",
        "🎯 Flashcards & Quiz",
        "⏱️ Transcript"
    ])

    with tab_notes:
        st.markdown(rec['notes_markdown'])

    with tab_chat:
        st.markdown("##### 💬 Ask Your AI Tutor About This Lecture")
        st.caption("Ask questions, request simpler explanations, formula derivations, or exam tips based on what was taught in this video.")

        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if user_prompt := st.chat_input("Ask a question about this lecture..."):
            st.session_state.chat_messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            with st.chat_message("assistant"):
                with st.spinner("AI Tutor is answering..."):
                    try:
                        client = genai.Client(api_key=BACKEND_API_KEY)
                        system_tutor = f"""You are a friendly, encouraging academic tutor.
You have the full context of this lecture:
Title: {rec['title']}
Channel: {rec['channel']}

Lecture Notes:
{rec['notes_markdown']}

Lecture Transcript:
{rec.get('transcript_text', '')[:10000]}

Answer the student's question clearly, accurately, and conceptually based on the lecture material.
"""
                        resp = client.models.generate_content(
                            model="gemini-3.5-flash-lite",
                            contents=user_prompt,
                            config={"system_instruction": system_tutor}
                        )
                        tutor_reply = resp.text
                        st.markdown(tutor_reply)
                        st.session_state.chat_messages.append({"role": "assistant", "content": tutor_reply})
                    except Exception as e:
                        st.error(f"Error answering question: {str(e)}")

    with tab_quiz:
        st.markdown("##### 🎯 Self-Study & Active Recall Quiz")
        notes_txt = rec['notes_markdown']
        if "Comprehension Check" in notes_txt:
            st.markdown(notes_txt.split("Comprehension Check")[-1])
        elif "Quiz" in notes_txt:
            st.markdown(notes_txt.split("Quiz")[-1])
        else:
            st.info("Study notes are available in the first tab to review key concepts!")

    with tab_transcript:
        st.markdown("##### ⏱️ Full Timestamped Transcript")
        st.text_area("Transcript with Timestamps", value=rec.get('transcript_text', 'No transcript stored.'), height=450)


# CASE 2: No active session - Generation Screen
else:
    st.markdown("""
    <div class="dash-card">
        <h3 style="margin-top: 0; color: #1E293B; font-weight: 800;">🚀 Create Study Notes & PDF Guide</h3>
        <p style="color: #64748B; font-size: 14px; margin-bottom: 16px;">
            Paste any educational YouTube video or playlist link below. The AI will extract concepts, formulas, definitions, and format a publication-ready PDF.
        </p>
    """, unsafe_allow_html=True)

    url_col, opt_col = st.columns([3, 1.2])
    with url_col:
        url_input = st.text_input(
            "YouTube Video or Playlist URL:",
            placeholder="Paste URL here (e.g. https://www.youtube.com/watch?v=...)",
            label_visibility="collapsed"
        )
    with opt_col:
        detail_level = st.selectbox(
            "Study Notes Depth:",
            options=["Standard (Balanced)", "Comprehensive (Exhaustive)", "Concise (Quick Summary)"],
            index=0,
            label_visibility="collapsed"
        )
        depth_key = detail_level.split(" ")[0]

    st.markdown("</div>", unsafe_allow_html=True)

    if url_input:
        url = url_input.strip()
        is_playlist = is_playlist_url(url)

        if not BACKEND_API_KEY:
            st.error("⚠️ Gemini API key is missing. Please set GEMINI_API_KEY in your environment or Streamlit secrets.")
            st.stop()

        # ================== PLAYLIST MODE ==================
        if is_playlist:
            st.info("📂 **Playlist Detected**")
            with st.spinner("Fetching playlist structure..."):
                playlist_data = get_playlist_videos(url)

            st.write(f"**Playlist:** {playlist_data['title']} • **{playlist_data['total_videos']} videos** ({playlist_data['uploader']})")

            video_titles = [f"{v['index']}. {v['title']} ({v['duration_formatted']})" for v in playlist_data['videos']]
            scope = st.radio("Scope:", ["All videos in playlist", "Single video"], horizontal=True)

            selected_indices = list(range(len(playlist_data['videos']))) if scope == "All videos in playlist" else [video_titles.index(st.selectbox("Choose video:", video_titles))]

            if st.button("🚀 Generate Notes & PDF Booklet", type="primary", width="stretch"):
                p_bar = st.progress(0.0)
                status_box = st.empty()
                last_record_data = None

                for step_idx, v_idx in enumerate(selected_indices):
                    v_info = playlist_data['videos'][v_idx]
                    status_box.info(f"Processing ({step_idx + 1}/{len(selected_indices)}): **{v_info['title']}**...")

                    t_res = get_video_transcript(v_info['id'])
                    if not t_res['success']:
                        continue

                    n_res = generate_study_notes(
                        video_title=v_info['title'],
                        channel_name=playlist_data['uploader'],
                        transcript_text=t_res['timestamped_text'] or t_res['formatted_text'],
                        api_key=BACKEND_API_KEY,
                        detail_level=depth_key,
                        include_timestamps=True,
                        model_name="gemini-3.5-flash-lite"
                    )

                    if not n_res['success']:
                        continue

                    safe_name = sanitize_filename(v_info['title'])
                    pdf_path = OUTPUT_DIR / f"{v_idx + 1:02d}_{safe_name}.pdf"
                    create_study_pdf(
                        title=v_info['title'],
                        channel=playlist_data['uploader'],
                        markdown_content=n_res['notes_markdown'],
                        output_path=str(pdf_path),
                        playlist_title=playlist_data['title']
                    )

                    with open(str(pdf_path), "rb") as pf:
                        pdf_bytes = pf.read()

                    new_id = save_study_record(
                        user_id=USER_ID,
                        video_id=v_info['id'],
                        url=v_info['url'],
                        title=v_info['title'],
                        channel=playlist_data['uploader'],
                        duration=v_info['duration_formatted'],
                        thumbnail_url="",
                        playlist_title=playlist_data['title'],
                        notes_markdown=n_res['notes_markdown'],
                        transcript_text=t_res['timestamped_text'],
                        pdf_path=str(pdf_path),
                        pdf_bytes=pdf_bytes
                    )

                    last_record_data = {
                        'id': new_id,
                        'user_id': USER_ID,
                        'video_id': v_info['id'],
                        'url': v_info['url'],
                        'title': v_info['title'],
                        'channel': playlist_data['uploader'],
                        'duration': v_info['duration_formatted'],
                        'thumbnail_url': "",
                        'playlist_title': playlist_data['title'],
                        'notes_markdown': n_res['notes_markdown'],
                        'transcript_text': t_res['timestamped_text'],
                        'pdf_path': str(pdf_path),
                        'pdf_filename': pdf_path.name,
                        'pdf_blob': pdf_bytes,
                        'created_at': 'Just now'
                    }

                    p_bar.progress((step_idx + 1) / len(selected_indices))

                if last_record_data:
                    st.session_state.active_record = last_record_data
                    st.rerun()

        # ================== SINGLE VIDEO MODE ==================
        else:
            vid_id = extract_video_id(url)
            if not vid_id:
                st.error("Please enter a valid YouTube video link.")
            else:
                with st.spinner("Fetching lecture details..."):
                    try:
                        meta = get_video_metadata(url)
                    except Exception as e:
                        st.error(f"Failed to fetch video: {str(e)}")
                        meta = None

                if meta:
                    # Fully Responsive Mobile & Desktop Video Preview
                    st.markdown(f"""
                    <div class="dash-card">
                        <div style="font-size: 18px; font-weight: 700; color: #1E293B; margin-bottom: 8px;">{meta['title']}</div>
                        <div style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center;">
                            <span class="video-badge">👤 {meta['uploader']}</span>
                            <span class="duration-badge">⏱️ Duration: {meta['duration_formatted']}</span>
                            <span class="video-badge">📖 Ready to Study</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    if st.button("🚀 Generate Study Notes & PDF Guide", type="primary", width="stretch"):
                        with st.status("Synthesizing Lecture into Study Booklet...", expanded=True) as status:
                            st.write("📥 **Step 1:** Extracting transcript (bypassing cloud blocks)...")
                            t_res = get_video_transcript(vid_id)

                            if not t_res['success']:
                                status.update(label="Transcript extraction failed", state="error")
                                st.error(f"Extraction Error: {t_res.get('error')}")
                            else:
                                st.write(f"✅ Transcribed **{t_res['word_count']:,} words** ({t_res['language']}).")

                                st.write("🧠 **Step 2:** Gemini AI synthesizing lecture notes & quiz questions...")
                                payload = t_res['timestamped_text'] or t_res['formatted_text']
                                n_res = generate_study_notes(
                                    video_title=meta['title'],
                                    channel_name=meta['uploader'],
                                    transcript_text=payload,
                                    api_key=BACKEND_API_KEY,
                                    detail_level=depth_key,
                                    include_timestamps=True,
                                    model_name="gemini-3.5-flash-lite"
                                )

                                if not n_res['success']:
                                    status.update(label="AI Generation Failed", state="error")
                                    st.error(f"AI Error: {n_res.get('error')}")
                                else:
                                    st.write("📄 **Step 3:** Formatting publication-grade PDF booklet...")
                                    safe_name = sanitize_filename(meta['title'])
                                    pdf_path = OUTPUT_DIR / f"{safe_name}.pdf"

                                    create_study_pdf(
                                        title=meta['title'],
                                        channel=meta['uploader'],
                                        markdown_content=n_res['notes_markdown'],
                                        output_path=str(pdf_path)
                                    )

                                    with open(str(pdf_path), "rb") as pf:
                                        pdf_data = pf.read()

                                    # Save to SQLite Database
                                    new_id = save_study_record(
                                        user_id=USER_ID,
                                        video_id=vid_id,
                                        url=url,
                                        title=meta['title'],
                                        channel=meta['uploader'],
                                        duration=meta['duration_formatted'],
                                        thumbnail_url=meta.get('thumbnail', ''),
                                        playlist_title=None,
                                        notes_markdown=n_res['notes_markdown'],
                                        transcript_text=t_res['timestamped_text'],
                                        pdf_path=str(pdf_path),
                                        pdf_bytes=pdf_data
                                    )

                                    status.update(label="🎉 Study Notes & PDF Ready!", state="complete")

                                    # Directly load into memory (100% resilient across mobile browsers)
                                    record_data = {
                                        'id': new_id,
                                        'user_id': USER_ID,
                                        'video_id': vid_id,
                                        'url': url,
                                        'title': meta['title'],
                                        'channel': meta['uploader'],
                                        'duration': meta['duration_formatted'],
                                        'thumbnail_url': meta.get('thumbnail', ''),
                                        'playlist_title': None,
                                        'notes_markdown': n_res['notes_markdown'],
                                        'transcript_text': t_res['timestamped_text'],
                                        'pdf_path': str(pdf_path),
                                        'pdf_filename': pdf_path.name,
                                        'pdf_blob': pdf_data,
                                        'created_at': 'Just now'
                                    }
                                    st.session_state.active_record = record_data
                                    st.rerun()
    else:
        # Features Grid
        st.markdown("""
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; margin-top: 10px;">
            <div style="background: white; border: 1px solid #E2E8F0; border-radius: 12px; padding: 18px;">
                <div style="font-size: 24px; margin-bottom: 6px;">📑</div>
                <div style="font-weight: 700; color: #1E293B; margin-bottom: 4px;">Structured Notes</div>
                <div style="font-size: 13px; color: #64748B;">Executive summaries, exam cheat sheets, and concept breakdowns.</div>
            </div>
            <div style="background: white; border: 1px solid #E2E8F0; border-radius: 12px; padding: 18px;">
                <div style="font-size: 24px; margin-bottom: 6px;">💬</div>
                <div style="font-weight: 700; color: #1E293B; margin-bottom: 4px;">Interactive AI Tutor</div>
                <div style="font-size: 13px; color: #64748B;">Ask doubts and get answers based on the video in real time.</div>
            </div>
            <div style="background: white; border: 1px solid #E2E8F0; border-radius: 12px; padding: 18px;">
                <div style="font-size: 24px; margin-bottom: 6px;">🎯</div>
                <div style="font-weight: 700; color: #1E293B; margin-bottom: 4px;">Active Recall Quizzes</div>
                <div style="font-size: 13px; color: #64748B;">Self-test comprehension questions to prepare for tests.</div>
            </div>
            <div style="background: white; border: 1px solid #E2E8F0; border-radius: 12px; padding: 18px;">
                <div style="font-size: 24px; margin-bottom: 6px;">📄</div>
                <div style="font-weight: 700; color: #1E293B; margin-bottom: 4px;">Publication-Ready PDF</div>
                <div style="font-size: 13px; color: #64748B;">Download beautiful textbook-style PDF booklets.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
