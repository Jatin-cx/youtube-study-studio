"""
YouTube Study Studio AI - High-Visibility, Tactile & Interactive UI.
Optimized for high-contrast visibility in Light/Dark/System modes.
Features:
- Prominent 3-dots / settings popover menu with reading modes (Default, Sepia, High Contrast, Dark).
- Big, tactile, unmissable tap buttons with high contrast borders and shadows.
- One-tap quick sample chips for instant testing.
- Crisp mobile-first layout with high-visibility duration and status badges.
- 100% backend & API key integrity preserved.
"""

import os
import re
import json
import uuid
import random
from datetime import datetime
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
from notes_generator import (
    generate_study_notes,
    generate_flashcards,
    generate_mindmap,
    generate_cram_sheet,
    extract_video_chapters,
    translate_study_notes
)
from pdf_generator import create_study_pdf
from db_manager import (
    init_db,
    save_study_record,
    get_all_records,
    get_record_by_id,
    delete_record,
    get_db_stats,
    update_study_artifacts
)
from google import genai

# Load backend environment variables (strictly preserving backend keys)
load_dotenv()
BACKEND_API_KEY = os.getenv("GEMINI_API_KEY", "")
if not BACKEND_API_KEY:
    try:
        BACKEND_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        pass

# Page Configuration
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

# User Private Session Isolation
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:12]

USER_ID = st.session_state.user_id

# Interactive Display Modes state
if "reading_mode" not in st.session_state:
    st.session_state.reading_mode = "Bright Clean (Default)"

if "font_size" not in st.session_state:
    st.session_state.font_size = "Normal (15px)"

# Active Recall Flashcards & Translation State
if "fc_idx" not in st.session_state:
    st.session_state.fc_idx = 0

if "fc_flipped" not in st.session_state:
    st.session_state.fc_flipped = False

if "fc_mastered" not in st.session_state:
    st.session_state.fc_mastered = set()

if "translated_cache" not in st.session_state:
    st.session_state.translated_cache = {}


def sanitize_filename(name: str) -> str:
    """Sanitize strings for safe file paths."""
    sanitized = re.sub(r'[\\/*?:"<>|]', '', name)
    return sanitized.strip()[:60]


# ---------------- THEME & HIGH-VISIBILITY COLOR PALETTES ----------------
# Determine colors based on reading mode
if st.session_state.reading_mode == "Sepia Book Mode 📜":
    BG_COLOR = "#FAF5EB"
    CARD_BG = "#FFFDF9"
    TEXT_COLOR = "#2D241E"
    BORDER_COLOR = "#E7DBC5"
    ACCENT_COLOR = "#8B5CF6"
elif st.session_state.reading_mode == "High-Contrast Light ☀️":
    BG_COLOR = "#FFFFFF"
    CARD_BG = "#F8FAFC"
    TEXT_COLOR = "#000000"
    BORDER_COLOR = "#94A3B8"
    ACCENT_COLOR = "#2563EB"
elif st.session_state.reading_mode == "Midnight Dark 🌙":
    BG_COLOR = "#0F172A"
    CARD_BG = "#1E293B"
    TEXT_COLOR = "#F8FAFC"
    BORDER_COLOR = "#334155"
    ACCENT_COLOR = "#6366F1"
else:
    # Bright Clean Default
    BG_COLOR = "#F1F5F9"
    CARD_BG = "#FFFFFF"
    TEXT_COLOR = "#0F172A"
    BORDER_COLOR = "#CBD5E1"
    ACCENT_COLOR = "#4F46E5"

FONT_PX = "18px" if "Large" in st.session_state.font_size else "15px"

CUSTOM_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {{
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}}

.stApp {{
    background-color: {BG_COLOR} !important;
    color: {TEXT_COLOR} !important;
}}

/* Responsive padding */
.block-container {{
    padding-top: 12px !important;
    padding-bottom: 36px !important;
    padding-left: 18px !important;
    padding-right: 18px !important;
    max-width: 100% !important;
}}

/* Top Navigation Bar with High Visibility */
.top-nav {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: {CARD_BG};
    border: 1.5px solid {BORDER_COLOR};
    border-radius: 14px;
    padding: 12px 18px;
    margin-bottom: 16px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}}

.brand-text {{
    font-size: 19px;
    font-weight: 800;
    color: {TEXT_COLOR};
    display: flex;
    align-items: center;
    gap: 8px;
}}

.brand-badge {{
    background: #EEF2FF;
    color: #4F46E5;
    font-size: 11px;
    font-weight: 800;
    padding: 3px 8px;
    border-radius: 6px;
    border: 1px solid #C7D2FE;
}}

/* High Visibility Cards */
.dash-card {{
    background: {CARD_BG};
    border-radius: 14px;
    border: 1.5px solid {BORDER_COLOR};
    box-shadow: 0 4px 8px -2px rgba(0, 0, 0, 0.06);
    padding: 20px;
    margin-bottom: 16px;
    color: {TEXT_COLOR};
}}

/* Badges with High Contrast */
.video-badge {{
    background: #EEF2FF;
    color: #3730A3;
    font-weight: 700;
    font-size: 13px;
    padding: 5px 12px;
    border-radius: 6px;
    border: 1px solid #C7D2FE;
    display: inline-block;
    margin-right: 6px;
    margin-bottom: 6px;
}}

.duration-badge {{
    background: #FEF3C7;
    color: #92400E;
    font-weight: 800;
    font-size: 13px;
    padding: 5px 12px;
    border-radius: 6px;
    border: 1px solid #FDE68A;
    display: inline-block;
    margin-right: 6px;
    margin-bottom: 6px;
}}

/* BIG, HIGH-CONTRAST UNMISSABLE BUTTONS */
.stButton>button {{
    width: 100% !important;
    background: linear-gradient(135deg, #4338CA 0%, #6366F1 100%) !important;
    color: #FFFFFF !important;
    font-weight: 800 !important;
    font-size: 16px !important;
    padding: 14px 24px !important;
    border-radius: 12px !important;
    border: 2px solid #3730A3 !important;
    box-shadow: 0 6px 14px rgba(79, 70, 229, 0.35) !important;
    cursor: pointer !important;
    letter-spacing: 0.3px !important;
    transition: transform 0.1s ease, box-shadow 0.1s ease !important;
}}

.stButton>button:hover {{
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 18px rgba(79, 70, 229, 0.45) !important;
    background: linear-gradient(135deg, #3730A3 0%, #4F46E5 100%) !important;
}}

.stButton>button:active {{
    transform: translateY(1px) !important;
}}

/* Download Button (Vibrant Emerald) */
.stDownloadButton>button {{
    background: linear-gradient(135deg, #047857 0%, #10B981 100%) !important;
    color: #FFFFFF !important;
    font-weight: 800 !important;
    font-size: 15px !important;
    padding: 11px 22px !important;
    border-radius: 10px !important;
    border: 1.5px solid #065F46 !important;
    box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3) !important;
}}

/* Input Box with High-Contrast Border */
.stTextInput>div>div>input {{
    border-radius: 10px !important;
    font-size: 15px !important;
    padding: 12px 14px !important;
    border: 2px solid {BORDER_COLOR} !important;
    background: {CARD_BG} !important;
    color: {TEXT_COLOR} !important;
}}

.stTextInput>div>div>input:focus {{
    border-color: #6366F1 !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25) !important;
}}

/* Clean typography */
.study-text {{
    font-size: {FONT_PX} !important;
    line-height: 1.65 !important;
    color: {TEXT_COLOR} !important;
}}

/* Sleek Modern Tabs */
.stTabs [data-baseweb="tab-list"] {{
    gap: 6px !important;
    background-color: rgba(0, 0, 0, 0.04) !important;
    padding: 6px !important;
    border-radius: 12px !important;
    border: 1px solid {BORDER_COLOR} !important;
}}

.stTabs [data-baseweb="tab"] {{
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 13.5px !important;
    padding: 8px 14px !important;
    color: {TEXT_COLOR} !important;
    transition: all 0.15s ease !important;
}}

.stTabs [aria-selected="true"] {{
    background: {CARD_BG} !important;
    color: {ACCENT_COLOR} !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
    border: 1px solid {BORDER_COLOR} !important;
}}

/* Interactive Pill Badges */
.badge-pill {{
    background: #EEF2FF;
    color: #4338CA;
    font-size: 12px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 9999px;
    border: 1px solid #C7D2FE;
    display: inline-block;
}}

/* 1-Page Cram Sheet Styling */
.cram-card {{
    background: {CARD_BG};
    border-radius: 14px;
    border: 2px solid {ACCENT_COLOR};
    box-shadow: 0 8px 24px -4px rgba(99, 102, 241, 0.15);
    padding: 24px;
    margin-bottom: 20px;
    color: {TEXT_COLOR};
    line-height: 1.6;
}}

/* 3D Tactile Flashcard Box */
.flashcard-box {{
    min-height: 220px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    border-radius: 16px;
    padding: 28px 20px;
    margin: 16px 0;
    box-shadow: 0 10px 25px -4px rgba(79, 70, 229, 0.15);
    transition: all 0.25s ease-in-out;
}}

.flashcard-front {{
    background: {CARD_BG};
    border: 2px solid #C7D2FE;
    border-left: 6px solid #4F46E5;
}}

.flashcard-back {{
    background: #F0FDF4;
    border: 2px solid #A7F3D0;
    border-left: 6px solid #10B981;
}}

/* Chapter Timeline Item */
.chapter-item {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-radius: 12px;
    border: 1.5px solid {BORDER_COLOR};
    margin-bottom: 10px;
    background: {CARD_BG};
    transition: all 0.15s ease;
}}

.chapter-item:hover {{
    border-color: #6366F1;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.12);
}}

/* Make Streamlit top header three-dots menu prominently visible */
header[data-testid="stHeader"] {{
    background: transparent !important;
}}

button[data-testid="baseButton-headerNoPadding"] {{
    background: rgba(99, 102, 241, 0.1) !important;
    border-radius: 8px !important;
    border: 1px solid rgba(99, 102, 241, 0.2) !important;
    padding: 4px 8px !important;
}}

/* Completely remove Streamlit Community Cloud "Manage app" button and badges */
#manage-app-button,
[data-testid="manage-app-button"],
div[class*="viewerBadge"],
.viewerBadge_container__1QSob,
.viewerBadge_link__1S137,
a[class*="viewerBadge"],
button[kind="manageApp"],
[class*="ManageApp"],
[data-testid="stStatusWidget"],
iframe[title="streamlit_app_share"] {{
    display: none !important;
    visibility: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
    height: 0 !important;
    width: 0 !important;
    position: absolute !important;
    z-index: -9999 !important;
}}

footer {{
    display: none !important;
    visibility: hidden !important;
}}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Session State Initialization
if "active_record" not in st.session_state:
    st.session_state.active_record = None

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

if "quick_url" not in st.session_state:
    st.session_state.quick_url = ""


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
# TOP APP BAR WITH HIGH-VISIBILITY 3-DOTS / SETTINGS POPOVER
# =====================================================================
top_c1, top_c2 = st.columns([4, 1])

with top_c1:
    st.markdown("""
    <div class="top-nav">
        <div class="brand-text">
            <span>🎓</span>
            <span>LectureScribe AI</span>
            <span class="brand-badge">STUDIO</span>
        </div>
        <div style="font-size: 13px; opacity: 0.8; font-weight: 500;">
            Study Notes • AI Tutor Chat • Printable PDF
        </div>
    </div>
    """, unsafe_allow_html=True)

with top_c2:
    # High-visibility 3-dots / Options Menu with Reading Modes
    with st.popover("⋮ More Options & Modes", use_container_width=True):
        st.markdown("#### 🎨 Display & Reading Mode")
        chosen_mode = st.radio(
            "Select Appearance Mode:",
            options=["Bright Clean (Default)", "High-Contrast Light ☀️", "Sepia Book Mode 📜", "Midnight Dark 🌙"],
            index=["Bright Clean (Default)", "High-Contrast Light ☀️", "Sepia Book Mode 📜", "Midnight Dark 🌙"].index(st.session_state.reading_mode)
        )
        if chosen_mode != st.session_state.reading_mode:
            st.session_state.reading_mode = chosen_mode
            st.rerun()

        st.divider()
        st.markdown("#### 🔤 Text Reading Size")
        chosen_font = st.radio(
            "Font Size:",
            options=["Normal (15px)", "Large (Comfortable reading - 18px)"],
            index=0 if "Normal" in st.session_state.font_size else 1
        )
        if chosen_font != st.session_state.font_size:
            st.session_state.font_size = chosen_font
            st.rerun()

        st.divider()
        st.caption("🔒 All sessions are privately isolated to your current device.")


# =====================================================================
# MAIN STAGE: ACTIVE SESSION OR GENERATION INPUT
# =====================================================================

# CASE 1: Active Record Loaded
if st.session_state.active_record:
    rec = st.session_state.active_record

    # Header Card of Active Lecture
    st.markdown(f"""
    <div class="dash-card" style="background: linear-gradient(135deg, #1E1B4B 0%, #312E81 50%, #4338CA 100%); color: white; border: none;">
        <h3 style="margin: 0 0 10px 0; color: white; font-size: 20px;">{rec['title']}</h3>
        <div style="display: flex; flex-wrap: wrap; gap: 8px;">
            <span class="video-badge" style="background: rgba(255,255,255,0.2); color: white; border: 1px solid rgba(255,255,255,0.3);">👤 {rec['channel']}</span>
            <span class="duration-badge">⏱️ {rec['duration']}</span>
            <span class="video-badge" style="background: rgba(255,255,255,0.2); color: white; border: 1px solid rgba(255,255,255,0.3);">📅 {rec['created_at']}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Action Toolbar
    col_act1, col_act2 = st.columns([1.5, 1])
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

    # Modern Interactive Workspace Tabs
    tab_notes, tab_cram, tab_flashcards, tab_mindmap, tab_chapters, tab_chat, tab_translate, tab_export = st.tabs([
        "📖 Notes",
        "⚡ 1-Page Cram",
        "🎴 Flashcards & Anki",
        "🗺️ Mind Map",
        "⏱️ Chapters",
        "💬 AI Tutor",
        "🌐 Translate",
        "📥 Export Hub"
    ])

    # 1. COMPREHENSIVE STUDY NOTES TAB
    with tab_notes:
        st.markdown(f"<div class='study-text'>{rec['notes_markdown']}</div>", unsafe_allow_html=True)

    # 2. 1-PAGE EXAM CRAM SHEET TAB
    with tab_cram:
        st.markdown("##### ⚡ 1-Page Exam Morning Cram Sheet")
        st.caption("High-density revision sheet with must-memorize formulas, core definitions, and exam trap alerts.")

        cram_content = rec.get('cram_sheet_markdown')
        if not cram_content:
            st.info("💡 Generate an ultra-condensed 1-page cram sheet for 10-minute exam review.")
            if st.button("⚡ Generate 1-Page Exam Cram Sheet", type="primary", key="btn_gen_cram"):
                with st.spinner("Synthesizing high-yield cram sheet..."):
                    cram_res = generate_cram_sheet(rec['notes_markdown'], rec['title'], BACKEND_API_KEY)
                    update_study_artifacts(rec['id'], cram_sheet_markdown=cram_res)
                    rec['cram_sheet_markdown'] = cram_res
                    st.session_state.active_record = rec
                    st.rerun()
        else:
            st.markdown(f"<div class='cram-card'>{cram_content}</div>", unsafe_allow_html=True)
            st.download_button(
                label="⬇️ Download 1-Page Cram Sheet (.md)",
                data=cram_content,
                file_name=f"cram_sheet_{sanitize_filename(rec['title'])}.md",
                mime="text/markdown",
                key="dl_cram_btn"
            )

    # 3. INTERACTIVE ACTIVE-RECALL FLASHCARDS & ANKI TAB
    with tab_flashcards:
        st.markdown("##### 🎴 Active-Recall Study Flashcards")
        st.caption("Test your recall with 3D flashcards or export directly to Anki / Quizlet.")

        fc_raw = rec.get('flashcards_json')
        if not fc_raw:
            st.info("💡 Active-recall flashcards help test definitions, equations, and edge cases before exams.")
            if st.button("🎴 Generate Interactive Flashcard Deck", type="primary", key="btn_gen_fc"):
                with st.spinner("Crafting high-yield study flashcards..."):
                    cards = generate_flashcards(rec['notes_markdown'], rec['title'], BACKEND_API_KEY)
                    fc_str = json.dumps(cards)
                    update_study_artifacts(rec['id'], flashcards_json=fc_str)
                    rec['flashcards_json'] = fc_str
                    st.session_state.active_record = rec
                    st.session_state.fc_idx = 0
                    st.session_state.fc_flipped = False
                    st.rerun()
        else:
            try:
                flashcards = json.loads(fc_raw)
            except Exception:
                flashcards = []

            if flashcards:
                total_cards = len(flashcards)
                curr_idx = st.session_state.fc_idx % total_cards
                curr_card = flashcards[curr_idx]
                card_id = curr_card.get('id', curr_idx + 1)
                is_mastered = card_id in st.session_state.fc_mastered

                col_c1, col_c2, col_c3 = st.columns([2, 1, 1])
                with col_c1:
                    st.markdown(f"<span class='badge-pill'>🏷️ {curr_card.get('category', 'Core Concept')}</span>", unsafe_allow_html=True)
                with col_c2:
                    st.markdown(f"<div style='font-weight: 700; text-align: center; color: {TEXT_COLOR};'>Card {curr_idx + 1} of {total_cards}</div>", unsafe_allow_html=True)
                with col_c3:
                    st.markdown(f"<div style='font-size: 13px; text-align: right; font-weight: 700; color: #10B981;'>{'✅ Mastered' if is_mastered else '⏳ In Progress'}</div>", unsafe_allow_html=True)

                st.progress((curr_idx + 1) / total_cards)

                if not st.session_state.fc_flipped:
                    st.markdown(f"""
                    <div class="flashcard-box flashcard-front">
                        <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 1.2px; color: #4F46E5; font-weight: 800; margin-bottom: 12px;">QUESTION / CONCEPT</div>
                        <div style="font-size: 20px; font-weight: 700; line-height: 1.4; color: {TEXT_COLOR}; margin-bottom: 16px;">
                            {curr_card.get('front', '')}
                        </div>
                        <div style="font-size: 13px; color: #94A3B8; font-style: italic;">
                            Click "Flip Card" below to reveal answer ⬇️
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="flashcard-box flashcard-back">
                        <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 1.2px; color: #059669; font-weight: 800; margin-bottom: 12px;">EXPLANATION & ANSWER</div>
                        <div style="font-size: 18px; font-weight: 600; line-height: 1.5; color: {TEXT_COLOR}; margin-bottom: 14px;">
                            {curr_card.get('back', '')}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                btn_prev, btn_flip, btn_next, btn_master = st.columns([1, 1.4, 1, 1.2])
                with btn_prev:
                    if st.button("⬅️ Previous", key="fc_btn_prev", width="stretch"):
                        st.session_state.fc_idx = (curr_idx - 1) % total_cards
                        st.session_state.fc_flipped = False
                        st.rerun()
                with btn_flip:
                    flip_label = "🔄 Flip to Question" if st.session_state.fc_flipped else "🔄 Flip to Answer"
                    if st.button(flip_label, type="primary", key="fc_btn_flip", width="stretch"):
                        st.session_state.fc_flipped = not st.session_state.fc_flipped
                        st.rerun()
                with btn_next:
                    if st.button("➡️ Next", key="fc_btn_next", width="stretch"):
                        st.session_state.fc_idx = (curr_idx + 1) % total_cards
                        st.session_state.fc_flipped = False
                        st.rerun()
                with btn_master:
                    if is_mastered:
                        if st.button("↩️ Need Review", key="fc_btn_unmaster", width="stretch"):
                            st.session_state.fc_mastered.remove(card_id)
                            st.rerun()
                    else:
                        if st.button("✅ Mark Mastered", key="fc_btn_master", width="stretch"):
                            st.session_state.fc_mastered.add(card_id)
                            st.rerun()

                st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

                anki_csv_data = "#separator:tab\n#html:true\n#tags column:3\n"
                for c in flashcards:
                    f = c.get('front', '').replace('\t', ' ').replace('\n', '<br>')
                    b = c.get('back', '').replace('\t', ' ').replace('\n', '<br>')
                    cat = c.get('category', 'LectureScribe').replace(' ', '_')
                    anki_csv_data += f"{f}\t{b}\t{cat}\n"

                st.download_button(
                    label="⬇️ Export Flashcard Deck for Anki & Quizlet (.csv)",
                    data=anki_csv_data,
                    file_name=f"anki_deck_{sanitize_filename(rec['title'])}.csv",
                    mime="text/tab-separated-values",
                    key="dl_anki_csv",
                    width="stretch"
                )

    # 4. VISUAL CONCEPT MIND MAP TAB
    with tab_mindmap:
        st.markdown("##### 🗺️ Visual Concept Architecture & Logic Flow")
        st.caption("Interactive diagram showing how key concepts branch and interconnect.")

        mm_raw = rec.get('mindmap_code')
        if not mm_raw:
            st.info("💡 Map out the logical flow and hierarchy of this lecture as a visual flowchart.")
            if st.button("🗺️ Generate Visual Concept Map", type="primary", key="btn_gen_mm"):
                with st.spinner("Generating lecture concept graph..."):
                    mm_code = generate_mindmap(rec['notes_markdown'], rec['title'], BACKEND_API_KEY)
                    update_study_artifacts(rec['id'], mindmap_code=mm_code)
                    rec['mindmap_code'] = mm_code
                    st.session_state.active_record = rec
                    st.rerun()
        else:
            st.markdown(f"""```mermaid
{mm_raw}
```""")
            with st.expander("📋 View & Copy Mermaid Diagram Code (for Notion & Obsidian)"):
                st.code(mm_raw, language="mermaid")

    # 5. CLICKABLE VIDEO CHAPTERS & TIMELINE TAB
    with tab_chapters:
        st.markdown("##### ⏱️ Timestamped Chapters & Topic Navigation")
        st.caption("Click any chapter button to jump directly to that exact moment on YouTube in a new tab.")

        ch_raw = rec.get('chapters_json')
        if not ch_raw:
            chapters = extract_video_chapters(rec.get('transcript_text', ''), rec['title'], BACKEND_API_KEY)
            ch_str = json.dumps(chapters)
            update_study_artifacts(rec['id'], chapters_json=ch_str)
            rec['chapters_json'] = ch_str
        else:
            try:
                chapters = json.loads(ch_raw)
            except Exception:
                chapters = []

        if not chapters:
            st.info("No timestamp markers found in this video's subtitles.")
        else:
            for ch in chapters:
                ts = ch.get('timestamp', '00:00')
                sec = ch.get('seconds', 0)
                title = ch.get('title', 'Lecture Topic')
                summary = ch.get('summary', '')
                yt_jump_url = f"https://www.youtube.com/watch?v={rec['video_id']}&t={sec}s"

                st.markdown(f"""
                <div class="chapter-item">
                    <div style="flex: 1; padding-right: 12px;">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                            <span class="duration-badge">⏱️ {ts}</span>
                            <span style="font-weight: 700; font-size: 15px; color: {TEXT_COLOR};">{title}</span>
                        </div>
                        <div style="font-size: 13px; color: #64748B;">{summary}</div>
                    </div>
                    <div>
                        <a href="{yt_jump_url}" target="_blank" style="text-decoration: none;">
                            <button style="background: #EEF2FF; color: #4338CA; border: 1.5px solid #C7D2FE; font-weight: 700; font-size: 13px; padding: 7px 14px; border-radius: 8px; cursor: pointer;">
                                ▶️ Play {ts}
                            </button>
                        </a>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # 6. AI LECTURE TUTOR CHAT TAB
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

    # 7. MULTI-LANGUAGE TRANSLATION TAB
    with tab_translate:
        st.markdown("##### 🌐 Multi-Language Study Guide Translation")
        st.caption("Translate your comprehensive study notes into your preferred language while keeping mathematical formulas intact.")

        lang_col1, lang_col2 = st.columns([3, 1.5])
        with lang_col1:
            target_lang = st.selectbox(
                "Choose Translation Language:",
                ["Spanish (Español)", "Hindi (हिन्दी)", "French (Français)", "German (Deutsch)", "Japanese (日本語)", "Mandarin (中文)", "Portuguese (Português)", "Arabic (العربية)", "Russian (Русский)"],
                key="sel_target_lang"
            )
        with lang_col2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            btn_translate = st.button("🌐 Translate Notes", type="primary", key="btn_do_translate", width="stretch")

        cache_key = f"{rec['id']}_{target_lang}"
        if btn_translate:
            with st.spinner(f"Translating notes into {target_lang}..."):
                translated_text = translate_study_notes(rec['notes_markdown'], target_lang, BACKEND_API_KEY)
                st.session_state.translated_cache[cache_key] = translated_text

        if cache_key in st.session_state.translated_cache:
            st.markdown(f"#### 📖 Translated Notes ({target_lang})")
            st.markdown(f"<div class='study-text'>{st.session_state.translated_cache[cache_key]}</div>", unsafe_allow_html=True)
        else:
            st.caption("Select your target language and tap 'Translate Notes' to view.")

    # 8. MULTI-PLATFORM EXPORT HUB TAB
    with tab_export:
        st.markdown("##### 📥 Multi-Platform Export Center")
        st.caption("Export your synthesized study materials to your favorite knowledge and flashcard apps.")

        exp_c1, exp_c2 = st.columns(2)

        with exp_c1:
            st.markdown(f"""
            <div class="dash-card">
                <div style="font-size: 24px; margin-bottom: 6px;">📄</div>
                <div style="font-weight: 800; font-size: 16px; margin-bottom: 4px; color: {TEXT_COLOR};">Printable PDF Guide</div>
                <div style="font-size: 13px; color: #64748B; margin-bottom: 14px;">Publication-grade textbook booklet with running headers, callouts, and page numbers.</div>
            </div>
            """, unsafe_allow_html=True)
            if rec.get('pdf_blob'):
                st.download_button("⬇️ Download PDF Booklet", data=rec['pdf_blob'], file_name=rec['pdf_filename'], mime="application/pdf", key="dl_pdf_exp", width="stretch")
            elif os.path.exists(rec.get('pdf_path', '')):
                with open(rec['pdf_path'], "rb") as pf:
                    st.download_button("⬇️ Download PDF Booklet", data=pf.read(), file_name=rec['pdf_filename'], mime="application/pdf", key="dl_pdf_exp", width="stretch")

            st.markdown(f"""
            <div class="dash-card" style="margin-top: 14px;">
                <div style="font-size: 24px; margin-bottom: 6px;">🎴</div>
                <div style="font-weight: 800; font-size: 16px; margin-bottom: 4px; color: {TEXT_COLOR};">Anki & Quizlet Deck (.csv)</div>
                <div style="font-size: 13px; color: #64748B; margin-bottom: 14px;">Tab-separated active-recall flashcard deck ready for 1-click import into Anki.</div>
            </div>
            """, unsafe_allow_html=True)
            anki_exp_data = "#separator:tab\n#html:true\n#tags column:3\n"
            if rec.get('flashcards_json'):
                try:
                    c_list = json.loads(rec['flashcards_json'])
                    for c in c_list:
                        anki_exp_data += f"{c.get('front', '')}\t{c.get('back', '')}\tLectureScribe\n"
                except Exception:
                    pass
            st.download_button("⬇️ Download Anki Deck (.csv)", data=anki_exp_data, file_name=f"anki_{sanitize_filename(rec['title'])}.csv", mime="text/tab-separated-values", key="dl_anki_exp", width="stretch")

        with exp_c2:
            st.markdown(f"""
            <div class="dash-card">
                <div style="font-size: 24px; margin-bottom: 6px;">📝</div>
                <div style="font-weight: 800; font-size: 16px; margin-bottom: 4px; color: {TEXT_COLOR};">Notion Markdown (.md)</div>
                <div style="font-size: 13px; color: #64748B; margin-bottom: 14px;">Formatted with Notion callout blocks, toggle headers, and clean lists.</div>
            </div>
            """, unsafe_allow_html=True)
            notion_md = f"# 🎓 {rec['title']}\n\n**Instructor:** {rec['channel']} • **Duration:** {rec['duration']}\n\n---\n\n{rec['notes_markdown']}"
            st.download_button("⬇️ Download Notion Markdown (.md)", data=notion_md, file_name=f"notion_{sanitize_filename(rec['title'])}.md", mime="text/markdown", key="dl_notion_exp", width="stretch")

            st.markdown(f"""
            <div class="dash-card" style="margin-top: 14px;">
                <div style="font-size: 24px; margin-bottom: 6px;">📓</div>
                <div style="font-weight: 800; font-size: 16px; margin-bottom: 4px; color: {TEXT_COLOR};">Obsidian Vault Markdown (.md)</div>
                <div style="font-size: 13px; color: #64748B; margin-bottom: 14px;">Includes YAML frontmatter, backlinks, and tags for your Obsidian knowledge vault.</div>
            </div>
            """, unsafe_allow_html=True)
            obsidian_md = f"""---
title: "{rec['title']}"
channel: "{rec['channel']}"
url: "{rec.get('url', '')}"
date: "{datetime.now().strftime('%Y-%m-%d')}"
tags:
  - university/lecture
  - study-notes
  - lecturescribe
---

# [[{rec['title']}]]
**Source:** [{rec['channel']}]({rec.get('url', '')})

{rec['notes_markdown']}
"""
            st.download_button("⬇️ Download Obsidian Markdown (.md)", data=obsidian_md, file_name=f"obsidian_{sanitize_filename(rec['title'])}.md", mime="text/markdown", key="dl_obsidian_exp", width="stretch")


# CASE 2: No active session - Generation Screen
else:
    st.markdown("""
    <div class="dash-card">
        <h3 style="margin-top: 0; font-weight: 800; font-size: 21px;">🚀 Create Study Notes & PDF Guide</h3>
        <p style="opacity: 0.85; font-size: 14px; margin-bottom: 14px;">
            Paste any educational YouTube video or playlist link below. The AI will extract concepts, formulas, definitions, and format a publication-ready PDF.
        </p>
    """, unsafe_allow_html=True)

    url_col, opt_col = st.columns([3, 1.2])
    with url_col:
        url_input = st.text_input(
            "YouTube Video or Playlist URL:",
            value=st.session_state.quick_url,
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

    # Quick Sample Action Chips
    st.markdown("<div style='font-size: 12px; font-weight: 600; opacity: 0.7; margin-top: 8px;'>💡 Quick Samples (Tap to try):</div>", unsafe_allow_html=True)
    chip_c1, chip_c2, chip_c3 = st.columns(3)
    with chip_c1:
        if st.button("⚡ Meta Ads Lecture", use_container_width=True):
            st.session_state.quick_url = "https://www.youtube.com/watch?v=YoBy_sO2Fkg"
            st.rerun()
    with chip_c2:
        if st.button("🧠 3Blue1Brown AI", use_container_width=True):
            st.session_state.quick_url = "https://www.youtube.com/watch?v=aircAruvnKk"
            st.rerun()
    with chip_c3:
        if st.button("📐 Khan Academy Math", use_container_width=True):
            st.session_state.quick_url = "https://www.youtube.com/watch?v=WUvTyaaNkzM"
            st.rerun()

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

            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

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
                        'flashcards_json': None,
                        'mindmap_code': None,
                        'cram_sheet_markdown': None,
                        'chapters_json': None,
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
                    # Clean High-Contrast Mobile & Desktop Video Preview
                    st.markdown(f"""
                    <div class="dash-card">
                        <div style="font-size: 19px; font-weight: 800; margin-bottom: 8px;">{meta['title']}</div>
                        <div style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 14px;">
                            <span class="video-badge">👤 {meta['uploader']}</span>
                            <span class="duration-badge">⏱️ Duration: {meta['duration_formatted']}</span>
                            <span class="video-badge" style="background: #ECFDF5; color: #065F46; border: 1px solid #A7F3D0;">📖 Ready to Generate</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # PROMINENT HIGH-CONTRAST GENERATE BUTTON
                    st.markdown("<div style='margin-top: 4px; margin-bottom: 8px;'>", unsafe_allow_html=True)
                    generate_button = st.button("🚀 Generate Study Notes & PDF Guide", type="primary", width="stretch")
                    st.markdown("</div>", unsafe_allow_html=True)

                    if generate_button:
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

                                    # Directly load into memory for instant mobile display
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
                                        'flashcards_json': None,
                                        'mindmap_code': None,
                                        'cram_sheet_markdown': None,
                                        'chapters_json': None,
                                        'created_at': 'Just now'
                                    }
                                    st.session_state.active_record = record_data
                                    st.rerun()
    else:
        # Modern Features Grid
        st.markdown(f"""
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; margin-top: 10px;">
            <div style="background: {CARD_BG}; border: 1.5px solid {BORDER_COLOR}; border-radius: 12px; padding: 18px; color: {TEXT_COLOR};">
                <div style="font-size: 26px; margin-bottom: 6px;">📑</div>
                <div style="font-weight: 800; margin-bottom: 4px;">Structured Notes & PDF</div>
                <div style="font-size: 13px; color: #64748B;">Executive summaries, formulas, and textbook-style PDF booklets.</div>
            </div>
            <div style="background: {CARD_BG}; border: 1.5px solid {BORDER_COLOR}; border-radius: 12px; padding: 18px; color: {TEXT_COLOR};">
                <div style="font-size: 26px; margin-bottom: 6px;">⚡</div>
                <div style="font-weight: 800; margin-bottom: 4px;">1-Page Exam Cram Sheet</div>
                <div style="font-size: 13px; color: #64748B;">High-density revision summary for 10-minute exam morning review.</div>
            </div>
            <div style="background: {CARD_BG}; border: 1.5px solid {BORDER_COLOR}; border-radius: 12px; padding: 18px; color: {TEXT_COLOR};">
                <div style="font-size: 26px; margin-bottom: 6px;">🎴</div>
                <div style="font-weight: 800; margin-bottom: 4px;">3D Flashcards & Anki</div>
                <div style="font-size: 13px; color: #64748B;">Interactive active-recall cards with 1-click Anki CSV export.</div>
            </div>
            <div style="background: {CARD_BG}; border: 1.5px solid {BORDER_COLOR}; border-radius: 12px; padding: 18px; color: {TEXT_COLOR};">
                <div style="font-size: 26px; margin-bottom: 6px;">🗺️</div>
                <div style="font-weight: 800; margin-bottom: 4px;">Concept Mind Maps</div>
                <div style="font-size: 13px; color: #64748B;">Visual flowcharts mapping out concept dependencies and logic flow.</div>
            </div>
            <div style="background: {CARD_BG}; border: 1.5px solid {BORDER_COLOR}; border-radius: 12px; padding: 18px; color: {TEXT_COLOR};">
                <div style="font-size: 26px; margin-bottom: 6px;">⏱️</div>
                <div style="font-weight: 800; margin-bottom: 4px;">Clickable Video Chapters</div>
                <div style="font-size: 13px; color: #64748B;">Direct deep links to jump straight into specific video moments.</div>
            </div>
            <div style="background: {CARD_BG}; border: 1.5px solid {BORDER_COLOR}; border-radius: 12px; padding: 18px; color: {TEXT_COLOR};">
                <div style="font-size: 26px; margin-bottom: 6px;">💬</div>
                <div style="font-weight: 800; margin-bottom: 4px;">AI Lecture Tutor</div>
                <div style="font-size: 13px; color: #64748B;">Chat in real-time to solve doubts and explore derivations.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
