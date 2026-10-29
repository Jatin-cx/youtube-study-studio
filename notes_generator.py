"""
Educational AI Synthesis Engine using Gemini API (google-genai SDK).
Transforms raw transcripts into structured, high-retention study notes.
Includes automatic multi-model failover for 100% uptime.
"""

import os
import time
import json
import re
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# Prioritized stable models with automatic fallback
STABLE_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite"
]

SYSTEM_STUDY_PROMPT = """You are an expert academic tutor and university professor creating comprehensive, publication-grade study notes from a lecture transcript.

Your goal is to convert the spoken lecture into clear, highly readable, structured written notes that a student can study from and prepare for exams.

Structure your output in clean Markdown using exactly the following sections:

# [Lecture Title]

## 1. Executive Summary & Core Objective
- A concise summary (3-5 sentences) capturing the core focus, thesis, and goal of this lecture.

## 2. Key Takeaways (Exam Revision Cheat Sheet)
- 5-8 bullet points summarizing the most critical concepts to remember.

## 3. In-Depth Lecture Breakdown
- Break down the lecture chronologically and conceptually into major topics.
- For each concept:
  - Explain the theoretical concept clearly and simply.
  - Detail step-by-step mechanisms, proofs, or practical examples given by the instructor.
  - Include relevant timestamp references (e.g., `[04:20]`) where appropriate.

## 4. Key Terminology & Definitions
- Create a clear glossary table or list of all technical terms, definitions, and acronyms introduced.

## 5. Formulas, Theorems & Core Rules (if applicable)
- Highlight all mathematical formulas, scientific laws, code snippets, or operational rules.

## 6. Common Pitfalls & Exam Warnings
- Note common misconceptions, confusing points, or high-probability exam questions mentioned or implied.

## 7. Comprehension Check (Self-Test Quiz)
- 5 thoughtful review questions (with expandable/hidden or clearly marked answers) to test understanding.

Guidelines:
- Maintain an encouraging, clear, and academic tone.
- Do NOT use filler conversational text (e.g., "The speaker says..."). Present it as direct, authoritative subject matter.
- Format neatly with bold text, bullet points, numbered lists, and callout blocks where suitable.
"""


def get_genai_client(api_key: Optional[str] = None) -> genai.Client:
    """Initialize the Google GenAI client."""
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("GEMINI_API_KEY")
        except Exception:
            pass

    if not key:
        raise ValueError(
            "Gemini API Key not found. Please provide an API key in the UI or set GEMINI_API_KEY in your .env file."
        )
    return genai.Client(api_key=key)


def generate_study_notes(
    video_title: str,
    channel_name: str,
    transcript_text: str,
    api_key: Optional[str] = None,
    detail_level: str = "Standard",
    include_timestamps: bool = True,
    model_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate structured study notes from a video transcript using Gemini.
    Features automatic fallback to alternative models if temporary high-traffic occurs.
    """
    client = get_genai_client(api_key)

    detail_instruction = ""
    if detail_level == "Concise":
        detail_instruction = "Provide a concise, high-yield summary focusing primarily on core points and exam review."
    elif detail_level == "Comprehensive":
        detail_instruction = "Provide extremely detailed, exhaustive study notes explaining every single concept, example, and detail taught in the lecture without skipping anything."

    timestamp_instruction = "Include timestamp markers where helpful." if include_timestamps else "Do not include timestamp tags in the notes."

    # If transcript is very large (> 120,000 characters), truncate gently to fit comfortably
    clean_transcript = transcript_text[:120000] if len(transcript_text) > 120000 else transcript_text

    prompt = f"""Lecture Metadata:
- Title: {video_title}
- Instructor / Channel: {channel_name}
- Note Depth Preference: {detail_level} ({detail_instruction})
- Timestamp Preference: {timestamp_instruction}

Transcript of the lecture:
\"\"\"
{clean_transcript}
\"\"\"

Please generate the comprehensive study notes now following the specified structure.
"""

    # Build model trial list with fallback
    models_to_try = [model_name] if model_name else []
    for m in STABLE_MODELS:
        if m not in models_to_try:
            models_to_try.append(m)

    last_error = ""
    for current_model in models_to_try:
        try:
            response = client.models.generate_content(
                model=current_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_STUDY_PROMPT,
                    temperature=0.3,
                )
            )

            if response and response.text:
                return {
                    'success': True,
                    'notes_markdown': response.text,
                    'model_used': current_model
                }
        except Exception as e:
            last_error = str(e)
            # Brief pause before trying fallback model
            time.sleep(1)
            continue

    return {
        'success': False,
        'error': f"Generation failed across models: {last_error}",
        'notes_markdown': ''
    }


def generate_flashcards(
    notes_markdown: str,
    video_title: str = "Lecture",
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Generate interactive active-recall flashcards from lecture notes.
    Returns a list of dicts: [{'id': 1, 'category': '...', 'front': '...', 'back': '...'}]
    """
    client = get_genai_client(api_key)
    prompt = f"""Based on the following lecture notes for '{video_title}', generate 10 to 14 high-yield study flashcards for active-recall exam revision.
Rules:
1. Each card should have:
   - "id": integer starting at 1
   - "category": a short category string (e.g. "Core Concept", "Formula", "Definition", "Exam Trap", "Algorithm")
   - "front": clear, concise question, prompt, or term
   - "back": complete, accurate answer, key formula, or explanation (2-4 sentences max)
2. Return ONLY a valid JSON array of objects. Do not wrap in markdown or backticks.

Lecture Notes:
{notes_markdown[:14000]}
"""
    for model_name in STABLE_MODELS:
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json"
                )
            )
            if resp and resp.text:
                clean_text = resp.text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text[7:]
                elif clean_text.startswith("```"):
                    clean_text = clean_text[3:]
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3]
                data = json.loads(clean_text.strip())
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception:
            continue

    # Resilient fallback parser: generate flashcards directly from notes
    fallback_cards = []
    card_id = 1
    for line in notes_markdown.splitlines():
        line = line.strip()
        if (line.startswith("- **") or line.startswith("* **")) and ":" in line:
            parts = line.lstrip("-* ").split(":", 1)
            term = parts[0].replace("**", "").strip()
            desc = parts[1].strip()
            if len(term) > 2 and len(desc) > 8:
                fallback_cards.append({
                    "id": card_id,
                    "category": "Core Term",
                    "front": f"What is {term}?",
                    "back": desc
                })
                card_id += 1
                if card_id > 10:
                    break

    if not fallback_cards:
        fallback_cards = [
            {"id": 1, "category": "Executive Summary", "front": f"What is the central topic of {video_title}?", "back": "Review Section 1 of the comprehensive notes for the complete thesis and core findings."},
            {"id": 2, "category": "Key Formula", "front": "What are the primary formulas or theorems in this lecture?", "back": "Refer to Section 5 in your study booklet for all detailed derivations and rules."},
            {"id": 3, "category": "Exam Trap", "front": "What common pitfalls or misconceptions should you avoid?", "back": "Check Section 6 of your study guide for high-probability exam warnings."}
        ]
    return fallback_cards


def generate_mindmap(
    notes_markdown: str,
    video_title: str = "Lecture",
    api_key: Optional[str] = None
) -> str:
    """
    Generate a clean Mermaid.js flowchart (graph TD) mapping out the concept architecture.
    """
    client = get_genai_client(api_key)
    prompt = f"""Generate a valid Mermaid.js flowchart (graph TD) that visually outlines the core concept hierarchy and logic flow for the lecture: '{video_title}'.
Rules:
1. Start strictly with 'graph TD'.
2. Use alphanumeric node IDs with NO special characters or brackets inside IDs (e.g., A, B1, B2, C1, C2).
3. Put ALL label text in double quotes inside square brackets: A["Lecture: Core Topic"] --> B["Module 1"].
4. Structure:
   - Root Node: The Lecture Title.
   - 3 to 5 Primary Concept Branches.
   - Each Branch connecting to 2-3 key sub-topics or rules.
   - A concluding synthesis node (e.g. Mastered Concepts).
5. Output ONLY the raw Mermaid diagram code. Do not include markdown code fences or explanation.

Lecture Notes:
{notes_markdown[:14000]}
"""
    for model_name in STABLE_MODELS:
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2
                )
            )
            if resp and resp.text:
                raw = resp.text.strip()
                if raw.startswith("```mermaid"):
                    raw = raw[10:]
                elif raw.startswith("```"):
                    raw = raw[3:]
                if raw.endswith("```"):
                    raw = raw[:-3]
                raw = raw.strip()
                if "graph TD" in raw or "flowchart TD" in raw or "mindmap" in raw:
                    return raw
        except Exception:
            continue

    # Deterministic fallback mindmap
    safe_title = video_title.replace('"', '').replace("'", "")[:40]
    return f"""graph TD
    Root["🎓 {safe_title}"] --> Mod1["1. Executive Foundations"]
    Root --> Mod2["2. Core Mechanisms & Principles"]
    Root --> Mod3["3. Practical Applications & Formulas"]
    Root --> Mod4["4. Exam Warnings & Mastery"]
    Mod1 --> Sub1["Core Thesis & Scope"]
    Mod2 --> Sub2["Key Concepts & Terminology"]
    Mod3 --> Sub3["Equations & Implementations"]
    Mod4 --> Sub4["Common Misconceptions"]
"""


def generate_cram_sheet(
    notes_markdown: str,
    video_title: str = "Lecture",
    api_key: Optional[str] = None
) -> str:
    """
    Generate an ultra-condensed 1-page exam cram sheet.
    """
    client = get_genai_client(api_key)
    prompt = f"""You are creating an ultra-condensed, high-density 1-Page "Exam Morning Cram Sheet" for '{video_title}'.
A student is 15 minutes away from an exam and needs to quickly review the absolute most critical facts, equations, and traps.

Structure in Markdown:
# ⚡ 1-Page Exam Cram Sheet: {video_title}

### 🎯 Core Thesis (In 2 Sentences)
- [Punchy 2-sentence summary of the core theoretical takeaway]

### 🔑 High-Frequency Formulas & Axioms
- [Bullet list of 4-6 most important formulas, mathematical rules, or algorithms]

### 📌 Must-Know Definitions (One-Liners)
- **Term 1**: [One-liner definition]
- **Term 2**: [One-liner definition]
- **Term 3**: [One-liner definition]
- **Term 4**: [One-liner definition]

### ⚠️ Exam Traps: "Do NOT Confuse..."
- [3 common misconceptions that professors frequently test on]

### 💡 Quick Recall Mnemonics
- [2-3 memory hooks or mental shortcuts]

Keep it concise, dense, and formatted cleanly.
Lecture Notes:
{notes_markdown[:15000]}
"""
    for model_name in STABLE_MODELS:
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2
                )
            )
            if resp and resp.text:
                return resp.text.strip()
        except Exception:
            continue

    return f"""# ⚡ 1-Page Exam Cram Sheet: {video_title}

### 🎯 Core Thesis
- This lecture synthesizes the core fundamental principles of {video_title}. Focus on theoretical foundations and their concrete applications.

### 🔑 High-Frequency Takeaways
- Review all primary formulas and rules highlighted in your study booklet.
- Pay special attention to boundary conditions and exceptions.

### ⚠️ Exam Traps
- Watch out for edge cases and confusing similar definitions.
- Double-check units and assumptions during derivations.
"""


def extract_video_chapters(
    transcript_text: str,
    video_title: str = "Lecture",
    api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Extract or generate timestamped chapter bookmarks with direct YouTube jump links.
    Returns: [{'timestamp': '04:15', 'seconds': 255, 'title': '...', 'summary': '...'}]
    """
    chapters = []
    pattern = re.compile(r'\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*([^\[\n]+)')
    matches = pattern.findall(transcript_text[:30000]) if transcript_text else []
    
    seen_seconds = set()
    step_jump = max(1, len(matches) // 8) if len(matches) > 8 else 1
    for idx in range(0, len(matches), step_jump):
        ts_str, text_snippet = matches[idx]
        parts = list(map(int, ts_str.split(':')))
        if len(parts) == 3:
            total_sec = parts[0] * 3600 + parts[1] * 60 + parts[2]
        else:
            total_sec = parts[0] * 60 + parts[1]
            
        if total_sec not in seen_seconds:
            seen_seconds.add(total_sec)
            title = text_snippet.strip()
            if len(title) > 60:
                title = title[:57] + "..."
            chapters.append({
                "timestamp": ts_str,
                "seconds": total_sec,
                "title": title or f"Chapter at {ts_str}",
                "summary": "Key discussion topic in this section."
            })
            if len(chapters) >= 10:
                break

    if not chapters:
        chapters = [
            {"timestamp": "00:00", "seconds": 0, "title": "Introduction & Objectives", "summary": "Opening remarks and lecture scope."},
            {"timestamp": "05:00", "seconds": 300, "title": "Core Foundations & Theory", "summary": "Primary conceptual breakdown."},
            {"timestamp": "15:00", "seconds": 900, "title": "Deep Dive & Examples", "summary": "Detailed demonstrations and analysis."},
            {"timestamp": "30:00", "seconds": 1800, "title": "Advanced Applications & Q&A", "summary": "Edge cases, revision, and wrap-up."}
        ]
    return chapters


def translate_study_notes(
    notes_markdown: str,
    target_language: str,
    api_key: Optional[str] = None
) -> str:
    """
    Translate study notes into another language while preserving Markdown and formulas.
    """
    client = get_genai_client(api_key)
    prompt = f"""You are an expert bilingual academic translator.
Translate the following study notes accurately into {target_language}.
Rules:
1. Preserve all Markdown structure, headings, bold tags, bullet points, and code fences.
2. Keep all mathematical formulas ($...$ or $$...$$) and code symbols exactly as written.
3. Keep technical English terms in parentheses next to the translation where helpful.

Notes to translate:
{notes_markdown[:25000]}
"""
    for model_name in STABLE_MODELS:
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2
                )
            )
            if resp and resp.text:
                return resp.text.strip()
        except Exception:
            continue
    return f"Translation to {target_language} could not be completed at this moment."
