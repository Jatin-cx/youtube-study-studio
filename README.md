# 🎓 YouTube Study Notes & PDF Generator

Turn any educational YouTube video or playlist into comprehensive, textbook-grade study notes and downloadable PDFs.

---

## 🌟 Key Features
- **Single Video & Full Playlist Support**: Simply paste any YouTube video or playlist link.
- **Accurate Transcript Extraction**: Pulls human captions and auto-transcripts with timestamps using `youtube-transcript-api` & `yt-dlp`.
- **Textbook Study Note Synthesis**:
  - Executive summary and core lecture objectives.
  - Exam revision cheat sheet & key takeaways.
  - Detailed chronological topic breakdown with timestamps.
  - Key definitions, acronyms, and technical vocabulary.
  - Mathematical formulas, scientific laws, and code blocks.
  - Common exam pitfalls and misunderstandings.
  - Self-quiz review questions.
- **Publication-Grade PDF Generation**: Clean typography, margins, headers, callouts, and dynamic page numbering ("Page X of Y").
- **Interactive Web UI**: Fast local web application built with Streamlit.

---

## 🚀 Quick Start

### 1. Launch the App
Double-click `run_app.bat` or run the following in terminal:
```bash
cd C:\Users\Dell\.gemini\antigravity\scratch\youtube_study_tool
.venv\Scripts\activate
streamlit run app.py
```

### 2. Enter Gemini API Key
- Enter your free Gemini API key in the sidebar (get one from [Google AI Studio](https://aistudio.google.com)).
- Alternatively, copy `.env.example` to `.env` and paste your key:
  ```env
  GEMINI_API_KEY=your_key_here
  ```

### 3. Generate Notes
1. Paste a video or playlist URL.
2. Choose your preferred depth (*Standard*, *Comprehensive*, or *Concise*).
3. Click **"🚀 Generate Study Notes & PDF"**.
4. Preview the study notes directly on the screen or click **"⬇️ Download Study Guide PDF"**.
