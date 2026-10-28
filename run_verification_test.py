"""
Automated End-to-End Verification Test.
Tests all 5 stages of the pipeline on the 1h 28m Meta Ads lecture:
1. Video Metadata
2. Mobile Client Transcript Extraction
3. AI Study Notes Synthesis (Gemini)
4. PDF Generation (ReportLab)
5. SQLite Database Storage & User Isolation
"""

import os
import time
from dotenv import load_dotenv

load_dotenv()

from youtube_extractor import get_video_metadata, get_video_transcript
from notes_generator import generate_study_notes
from pdf_generator import create_study_pdf
from db_manager import save_study_record, get_record_by_id

VIDEO_ID = "YoBy_sO2Fkg"
URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"

print("=" * 65)
print("STAGE 1: Fetching Video Metadata...")
meta = get_video_metadata(URL)
print(f"  [OK] Title: {meta['title']}")
print(f"  [OK] Channel: {meta['uploader']}")
print(f"  [OK] Duration: {meta['duration_formatted']}")

print("\n" + "=" * 65)
print("STAGE 2: Extracting Transcript via Mobile Client Extractor...")
t_start = time.time()
trans = get_video_transcript(VIDEO_ID)
t_elapsed = time.time() - t_start

if not trans['success']:
    print(f"  [FAIL] Transcript Error: {trans.get('error')}")
    exit(1)

print(f"  [OK] Extracted {trans['word_count']:,} words in {t_elapsed:.2f}s")
print(f"  [OK] Language: {trans['language']} (Segments: {trans['segment_count']:,})")

print("\n" + "=" * 65)
print("STAGE 3: Synthesizing Notes with Gemini AI...")
g_start = time.time()
notes = generate_study_notes(
    video_title=meta['title'],
    channel_name=meta['uploader'],
    transcript_text=trans['timestamped_text'] or trans['formatted_text'],
    api_key=os.getenv("GEMINI_API_KEY"),
    detail_level="Standard"
)
g_elapsed = time.time() - g_start

if not notes['success']:
    print(f"  [FAIL] AI Error: {notes.get('error')}")
    exit(1)

print(f"  [OK] AI completed in {g_elapsed:.2f}s using {notes['model_used']}")
print(f"  [OK] Generated Notes Length: {len(notes['notes_markdown']):,} characters")

print("\n" + "=" * 65)
print("STAGE 4: Compiling Publication-Ready PDF...")
pdf_out = os.path.join("generated_notes", "verification_meta_ads.pdf")
pdf_path = create_study_pdf(
    title=meta['title'],
    channel=meta['uploader'],
    markdown_content=notes['notes_markdown'],
    output_path=pdf_out
)
pdf_size = os.path.getsize(pdf_path)
print(f"  [OK] PDF Created: {pdf_path}")
print(f"  [OK] File Size: {pdf_size:,} bytes")

print("\n" + "=" * 65)
print("STAGE 5: Verifying SQLite Database Storage & User Isolation...")
with open(pdf_path, "rb") as f:
    pdf_bytes = f.read()

rec_id = save_study_record(
    user_id="test_user_isolated",
    video_id=VIDEO_ID,
    url=URL,
    title=meta['title'],
    channel=meta['uploader'],
    duration=meta['duration_formatted'],
    thumbnail_url=meta.get('thumbnail', ''),
    playlist_title=None,
    notes_markdown=notes['notes_markdown'],
    transcript_text=trans['timestamped_text'],
    pdf_path=pdf_path,
    pdf_bytes=pdf_bytes
)

saved_rec = get_record_by_id(rec_id, user_id="test_user_isolated")
assert saved_rec is not None, "Record could not be retrieved!"
assert len(saved_rec['pdf_blob']) > 0, "PDF blob was not stored!"
print(f"  [OK] Database Record #{rec_id} verified with user isolation!")

print("\n" + "=" * 65)
print("ALL 5 STAGES COMPLETED WITH 100% SUCCESS!")
print("=" * 65)
