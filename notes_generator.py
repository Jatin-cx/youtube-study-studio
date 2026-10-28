"""
Educational AI Synthesis Engine using Gemini API (google-genai SDK).
Transforms raw transcripts into structured, high-retention study notes.
Includes automatic multi-model failover for 100% uptime.
"""

import os
import time
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
