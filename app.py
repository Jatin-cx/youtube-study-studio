"""
YouTube Study Studio AI - Full-Screen Interactive Study Workspace.
Features:
- Full-screen modern dashboard layout with responsive sidebar history.
- Multi-section study guide: Executive Summary, Cheat Sheet, Definitions, Formulas.
- Interactive AI Tutor Chat: Ask questions and clarify doubts directly about the lecture!
- Interactive Quiz & Flashcards: Click-to-reveal answers for active recall study.
- Complete PDF Export & SQLite Database Archive.
"""

import os
import re
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

# Page Configuration: Full-width modern dashboard
st.set_page_config(
    page_title="LectureScribe Studio AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Output directory for generated PDFs
OUTPUT_DIR = Path("generated_notes")
OUTPUT_DIR.mkdir(exist_ok=True)

# Initialize database
init_db()

# User Private Session Isolation (Each visitor gets their own private workspace)
import uuid

if "uid" in st.query_params:
    USER_ID = str(st.query_params["uid"])
else:
    USER_ID = st.session_state.get("user_id") or str(uuid.uuid4())[:12]
    st.query_params["uid"] = USER_ID

st.session_state["user_id"] = USER_ID


def sanitize_filename(name: str) -> str:
    """Sanitize strings for safe file paths."""
    sanitized = re.sub(r'[\\/*?:"<>|]', '', name)
    return sanitized.strip()[:60]


# ---------------- LUXURY MODERN FULL-SCREEN CSS ----------------
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', sans-serif;
}

/* App Background */
.stApp {
    background-color: #F8FAFC;
}

/* Adjust Main Container Padding */
.block-container {
    padding-top: 16px !important;
    padding-bottom: 32px !important;
    padding-left: 28px !important;
    padding-right: 28px !important;
    max-width: 100% !important;
}

/* Top Navigation Bar */
.top-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    padding: 12px 24px;
    margin-bottom: 20px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.03);
}

.brand-text {
    font-size: 20px;
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
    padding: 3px 8px;
    border-radius: 6px;
    letter-spacing: 0.5px;
}

/* Interactive Cards */
.interactive-card {
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    padding: 20px;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.02);
    margin-bottom: 16px;
}

/* Video Header Banner */
.video-banner {
    background: linear-gradient(135deg, #1E1B4B 0%, #312E81 50%, #4338CA 100%);
    border-radius: 16px;
    padding: 22px 26px;
    color: white;
    margin-bottom: 20px;
    box-shadow: 0 10px 20px -5px rgba(67, 56, 202, 0.25);
}

.video-banner-title {
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 6px;
}

.video-tag {
    background: rgba(255, 255, 255, 0.18);
    color: white;
    font-size: 12px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 20px;
    display: inline-block;
    margin-right: 8px;
}

/* Primary Action Buttons */
.stButton>button {
    background: linear-gradient(135deg, #4F46E5 0%, #6366F1 100%) !important;
    color: white !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: 9px 20px !important;
    border-radius: 10px !important;
    border: none !important;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25) !important;
    transition: all 0.2s ease !important;
}

.stButton>button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 16px rgba(99, 102, 241, 0.35) !important;
}

/* Download Button */
.stDownloadButton>button {
    background: linear-gradient(135deg, #059669 0%, #10B981 100%) !important;
    color: white !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: 9px 20px !important;
    border-radius: 10px !important;
    border: none !important;
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.25) !important;
}

/* Sidebar Styling */
[data-testid="stSidebar"] {
    background-color: #FFFFFF;
    border-right: 1px solid #E2E8F0;
    padding-top: 14px;
}

/* Quiz Box */
.quiz-card {
    background: #F8FAFC;
    border-left: 4px solid #6366F1;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 12px;
}

/* Streamlit Header removal */
header[data-testid="stHeader"] {
    background: transparent;
}
footer {
    visibility: hidden;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Session State Initialization for Interactive Workspace
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

    if st.button("➕ New Study Session", use_container_width=True):
        st.session_state.active_record = None
        st.session_state.chat_messages = []
        st.rerun()

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    # Search History in Sidebar
    hist_search = st.text_input("🔍 Search History", placeholder="Topic or channel...", label_visibility="collapsed")
    records = get_all_records(USER_ID, hist_search)

    if not records:
        st.caption("No past sessions yet. Generate your first lecture notes!")
    else:
        for r in records:
            col_h1, col_h2 = st.columns([4, 1])
            with col_h1:
                # Clickable session item
                is_current = st.session_state.active_record and st.session_state.active_record.get('id') == r['id']
                label = f"📖 {r['title'][:28]}..." if len(r['title']) > 28 else f"📖 {r['title']}"
                if st.button(label, key=f"rec_btn_{r['id']}", use_container_width=True):
                    full_r = get_record_by_id(r['id'], user_id=USER_ID)
                    st.session_state.active_record = full_r
                    st.session_state.chat_messages = []
                    st.rerun()
            with col_h2:
                if st.button("✕", key=f"rec_del_{r['id']}", help="Delete session"):
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
        Interactive Lecture Notes • AI Tutor Chat • Printable PDF
    </div>
</div>
""", unsafe_allow_html=True)


# =====================================================================
# MAIN STAGE: ACTIVE SESSION OR GENERATION INPUT
# =====================================================================

# CASE 1: Active Record Loaded (either just generated or selected from sidebar)
if st.session_state.active_record:
    rec = st.session_state.active_record

    # Header Banner of Active Lecture
    st.markdown(f"""
    <div class="video-banner">
        <div class="video-banner-title">{rec['title']}</div>
        <div style="margin-top: 8px;">
            <span class="video-tag">👤 {rec['channel']}</span>
            <span class="video-tag">⏱️ {rec['duration']}</span>
            <span class="video-tag">📅 {rec['created_at']}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Action Toolbar
    col_act1, col_act2, col_act3 = st.columns([1.2, 1.2, 3])
    with col_act1:
        if rec.get('pdf_blob'):
            st.download_button(
                label="⬇️ Download PDF Guide",
                data=rec['pdf_blob'],
                file_name=rec['pdf_filename'],
                mime="application/pdf",
                use_container_width=True
            )
        elif os.path.exists(rec.get('pdf_path', '')):
            with open(rec['pdf_path'], "rb") as pf:
                st.download_button(
                    label="⬇️ Download PDF Guide",
                    data=pf.read(),
                    file_name=rec['pdf_filename'],
                    mime="application/pdf",
                    use_container_width=True
                )
    with col_act2:
        if st.button("🔗 Open on YouTube", use_container_width=True):
            st.write(f"YouTube Link: {rec['url']}")
    with col_act3:
        st.write("")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # 4 INTERACTIVE WORKSPACE TABS
    tab_notes, tab_chat, tab_quiz, tab_transcript = st.tabs([
        "📖 Comprehensive Notes",
        "💬 Chat with AI Lecture Tutor",
        "🎯 Flashcards & Practice Quiz",
        "⏱️ Timestamped Transcript"
    ])

    # TAB 1: Comprehensive Notes
    with tab_notes:
        st.markdown(rec['notes_markdown'])

    # TAB 2: Interactive AI Tutor Chat (Ask doubts about this lecture!)
    with tab_chat:
        st.markdown("##### 💬 Ask Your AI Tutor About This Lecture")
        st.caption("Ask questions, request simpler explanations, formula derivations, or exam tips based on what was taught in this video.")

        # Display conversation history
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # Chat Input
        if user_prompt := st.chat_input("Ask a question about this lecture..."):
            st.session_state.chat_messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            # Generate response from Gemini with the lecture context
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

    # TAB 3: Flashcards & Practice Quiz
    with tab_quiz:
        st.markdown("##### 🎯 Self-Study & Active Recall Quiz")
        st.caption("Test your comprehension of the core concepts taught in this lecture.")

        # Extract comprehension section or display interactive flashcards
        notes_txt = rec['notes_markdown']
        if "Comprehension Check" in notes_txt or "Quiz" in notes_txt:
            st.markdown(notes_txt.split("Comprehension Check")[-1])
        else:
            st.info("Review the study notes to test your understanding!")

    # TAB 4: Timestamped Transcript
    with tab_transcript:
        st.markdown("##### ⏱️ Full Timestamped Transcript")
        st.text_area("Transcript with Timestamps", value=rec.get('transcript_text', 'No raw transcript stored.'), height=450)


# CASE 2: No active session - Display Interactive Generation Stage
else:
    st.markdown("""
    <div style="background: white; border: 1px solid #E2E8F0; border-radius: 16px; padding: 28px; box-shadow: 0 4px 12px rgba(0,0,0,0.03); margin-bottom: 24px;">
        <h3 style="margin-top: 0; color: #1E293B; font-weight: 800;">🚀 Create New Study Notes & PDF Guide</h3>
        <p style="color: #64748B; font-size: 14px; margin-bottom: 20px;">
            Paste any educational YouTube video or playlist link below. Our AI will transcribe, organize key concepts, extract formulas, and generate a printable PDF booklet.
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
            st.error("Gemini API key is missing from `.env` file.")
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

            if st.button("🚀 Generate Notes & PDF Booklet", type="primary"):
                p_bar = st.progress(0.0)
                status_box = st.empty()

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

                    p_bar.progress((step_idx + 1) / len(selected_indices))

                st.session_state.active_record = get_record_by_id(new_id, user_id=USER_ID)
                st.rerun()

        # ================== SINGLE VIDEO MODE ==================
        else:
            vid_id = extract_video_id(url)
            if not vid_id:
                st.error("Invalid YouTube URL. Please enter a valid YouTube link.")
            else:
                with st.spinner("Fetching lecture details..."):
                    try:
                        meta = get_video_metadata(url)
                    except Exception as e:
                        st.error(f"Failed to fetch video: {str(e)}")
                        meta = None

                if meta:
                    st.markdown("<div class='interactive-card'>", unsafe_allow_html=True)
                    c_th, c_info = st.columns([1, 4])
                    with c_th:
                        if meta.get('thumbnail'):
                            st.image(meta['thumbnail'], use_container_width=True)
                    with c_info:
                        st.markdown(f"#### {meta['title']}")
                        st.markdown(f"👤 **{meta['uploader']}** • ⏱️ {meta['duration_formatted']}")
                    st.markdown("</div>", unsafe_allow_html=True)

                    if st.button("🚀 Generate Study Notes & PDF Guide", type="primary"):
                        with st.status("Synthesizing Lecture into Study Booklet...", expanded=True) as status:
                            st.write("📥 1. Extracting lecture transcript...")
                            t_res = get_video_transcript(vid_id)

                            if not t_res['success']:
                                status.update(label="Transcript extraction failed", state="error")
                                st.error(f"Error: {t_res.get('error')}")
                            else:
                                st.write(f"✅ Extracted **{t_res['word_count']} words** from lecture audio.")

                                st.write("🧠 2. Synthesizing concepts, definitions, formulas & quiz...")
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
                                    st.error(f"Error: {n_res.get('error')}")
                                else:
                                    st.write("📄 3. Formatting and compiling publication PDF booklet...")
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

                                    # Load newly created record as active
                                    st.session_state.active_record = get_record_by_id(new_id, user_id=USER_ID)
                                    st.rerun()
    else:
        # Initial Welcome Features Grid
        st.markdown("""
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; margin-top: 10px;">
            <div style="background: white; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px;">
                <div style="font-size: 26px; margin-bottom: 8px;">📑</div>
                <div style="font-weight: 700; color: #1E293B; margin-bottom: 4px;">Structured Notes</div>
                <div style="font-size: 13px; color: #64748B;">Executive summaries, exam cheat sheets, and chronological concept breakdowns.</div>
            </div>
            <div style="background: white; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px;">
                <div style="font-size: 26px; margin-bottom: 8px;">💬</div>
                <div style="font-weight: 700; color: #1E293B; margin-bottom: 4px;">Interactive AI Tutor</div>
                <div style="font-size: 13px; color: #64748B;">Chat directly with the lecture! Ask clarifying questions and resolve doubts in real time.</div>
            </div>
            <div style="background: white; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px;">
                <div style="font-size: 26px; margin-bottom: 8px;">🎯</div>
                <div style="font-weight: 700; color: #1E293B; margin-bottom: 4px;">Active Recall Quizzes</div>
                <div style="font-size: 13px; color: #64748B;">Self-test comprehension questions and flashcard concepts to prepare for exams.</div>
            </div>
            <div style="background: white; border: 1px solid #E2E8F0; border-radius: 12px; padding: 20px;">
                <div style="font-size: 26px; margin-bottom: 8px;">📄</div>
                <div style="font-weight: 700; color: #1E293B; margin-bottom: 4px;">Publication-Ready PDF</div>
                <div style="font-size: 13px; color: #64748B;">Download beautiful, textbook-style PDF booklets with callout boxes and headers.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
