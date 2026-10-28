"""
CLI Test and Utility for YouTube Study Notes & PDF Generator.
Usage:
    python cli_test.py <YOUTUBE_URL> [--api_key YOUR_KEY]
"""

import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

from youtube_extractor import get_video_metadata, get_video_transcript, extract_video_id
from notes_generator import generate_study_notes
from pdf_generator import create_study_pdf

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Generate Study PDF from YouTube URL")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--api-key", default=None, help="Gemini API Key")
    parser.add_argument("--output", default="output_study_guide.pdf", help="Output PDF path")
    args = parser.parse_args()

    vid_id = extract_video_id(args.url)
    if not vid_id:
        print("❌ Error: Invalid YouTube URL.")
        sys.exit(1)

    print(f"📥 Fetching video metadata for {args.url}...")
    meta = get_video_metadata(args.url)
    print(f"🎬 Title: {meta['title']}")
    print(f"👤 Channel: {meta['uploader']}")

    print("📝 Extracting transcript...")
    transcript = get_video_transcript(vid_id)
    if not transcript['success']:
        print(f"❌ Failed to extract transcript: {transcript.get('error')}")
        sys.exit(1)

    print(f"✅ Extracted {transcript['word_count']} words.")

    print("🧠 Generating structured study notes with Gemini...")
    notes_res = generate_study_notes(
        video_title=meta['title'],
        channel_name=meta['uploader'],
        transcript_text=transcript['timestamped_text'] or transcript['formatted_text'],
        api_key=args.api_key
    )

    if not notes_res['success']:
        print(f"❌ Error generating notes: {notes_res.get('error')}")
        sys.exit(1)

    print("📄 Compiling PDF...")
    create_study_pdf(
        title=meta['title'],
        channel=meta['uploader'],
        markdown_content=notes_res['notes_markdown'],
        output_path=args.output
    )

    print(f"🎉 Success! Generated study guide PDF at: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
