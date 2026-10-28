"""
YouTube Video and Playlist Metadata & Transcript Extractor.
Supports single video URLs and full playlist URLs.
"""

import re
from typing import Dict, List, Optional, Any
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import yt_dlp


def clean_youtube_url(url: str) -> str:
    """Strip extraneous tracking parameters from YouTube URLs."""
    return url.strip()


def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:shorts\/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_playlist_id(url: str) -> Optional[str]:
    """Extract YouTube playlist ID from URL."""
    match = re.search(r'[?&]list=([0-9A-Za-z_-]+)', url)
    if match:
        return match.group(1)
    return None


def is_playlist_url(url: str) -> bool:
    """Check if the URL points to a playlist."""
    return "list=" in url and not url.startswith("https://www.youtube.com/watch?v=") or ("playlist?list=" in url)


def get_video_metadata(url_or_id: str) -> Dict[str, Any]:
    """Fetch video metadata (title, channel, duration, etc.) using yt-dlp."""
    ydl_opts = {
        'skip_download': True,
        'extract_flat': True,
        'quiet': True,
        'no_warnings': True,
    }
    
    video_url = url_or_id if url_or_id.startswith("http") else f"https://www.youtube.com/watch?v={url_or_id}"
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        return {
            'id': info.get('id'),
            'title': info.get('title', 'Unknown Title'),
            'uploader': info.get('uploader', 'Unknown Channel'),
            'duration': info.get('duration', 0),
            'duration_formatted': format_duration(info.get('duration', 0)),
            'thumbnail': info.get('thumbnail', ''),
            'description': info.get('description', '')
        }


def get_playlist_videos(playlist_url: str) -> Dict[str, Any]:
    """Extract all video entries from a playlist."""
    ydl_opts = {
        'skip_download': True,
        'extract_flat': 'in_playlist',
        'quiet': True,
        'no_warnings': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
        entries = info.get('entries', [])
        
        videos = []
        for idx, entry in enumerate(entries, start=1):
            if entry and entry.get('id'):
                videos.append({
                    'index': idx,
                    'id': entry.get('id'),
                    'title': entry.get('title', f"Video {idx}"),
                    'duration': entry.get('duration', 0),
                    'duration_formatted': format_duration(entry.get('duration', 0)),
                    'url': f"https://www.youtube.com/watch?v={entry.get('id')}"
                })
                
        return {
            'title': info.get('title', 'YouTube Playlist'),
            'uploader': info.get('uploader', 'Unknown Creator'),
            'total_videos': len(videos),
            'videos': videos
        }


def format_duration(seconds: int) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    if not seconds:
        return "00:00"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def format_timestamp(seconds: float) -> str:
    """Format a float timestamp in seconds to MM:SS or HH:MM:SS."""
    total_seconds = int(seconds)
    m, s = divmod(total_seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def get_video_transcript(video_id: str, preferred_languages: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Fetch transcripts for a YouTube video.
    Returns structured transcript with timestamps and clean text.
    """
    if preferred_languages is None:
        preferred_languages = ['en', 'en-US', 'hi', 'es', 'fr', 'de']
        
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id)
        
        # Try to find transcript in preferred languages
        transcript = None
        selected_lang = None
        is_generated = False
        
        # 1. Try manual transcript in preferred languages
        for lang in preferred_languages:
            try:
                transcript = transcript_list.find_manually_created_transcript([lang])
                selected_lang = transcript.language_code
                is_generated = False
                break
            except Exception:
                continue
                
        # 2. Try generated transcript if no manual one found
        if not transcript:
            for lang in preferred_languages:
                try:
                    transcript = transcript_list.find_generated_transcript([lang])
                    selected_lang = transcript.language_code
                    is_generated = True
                    break
                except Exception:
                    continue
                    
        # 3. Fallback: Take the first available transcript
        if not transcript:
            for t in transcript_list:
                transcript = t
                selected_lang = t.language_code
                is_generated = t.is_generated
                break

        if not transcript:
            return {
                'success': False,
                'error': 'No transcript could be retrieved for this video.',
                'raw_segments': [],
                'formatted_text': '',
                'timestamped_text': ''
            }
            
        fetched = transcript.fetch()
        
        # Build clean formatted text and timestamped text
        raw_text_pieces = []
        current_block_start = 0.0
        current_block_text = []
        grouped_timestamped = []
        raw_segments = []
        
        for item in fetched:
            text = getattr(item, 'text', str(item)).strip()
            start = getattr(item, 'start', 0.0)
            duration = getattr(item, 'duration', 0.0)
            
            if not text:
                continue
                
            raw_segments.append({'text': text, 'start': start, 'duration': duration})
            raw_text_pieces.append(text)
            
            if not current_block_text:
                current_block_start = start
                current_block_text.append(text)
            elif start - current_block_start >= 45.0:
                block_str = f"[{format_timestamp(current_block_start)}] " + " ".join(current_block_text)
                grouped_timestamped.append(block_str)
                current_block_start = start
                current_block_text = [text]
            else:
                current_block_text.append(text)
                
        if current_block_text:
            block_str = f"[{format_timestamp(current_block_start)}] " + " ".join(current_block_text)
            grouped_timestamped.append(block_str)
            
        full_text = " ".join(raw_text_pieces)
        timestamped_full = "\n\n".join(grouped_timestamped)
        
        return {
            'success': True,
            'language': selected_lang,
            'is_generated': is_generated,
            'raw_segments': raw_segments,
            'formatted_text': full_text,
            'timestamped_text': timestamped_full,
            'segment_count': len(raw_segments),
            'word_count': len(full_text.split())
        }
        
    except TranscriptsDisabled:
        return {
            'success': False,
            'error': 'Transcripts are disabled for this video by the creator.',
            'raw_segments': [],
            'formatted_text': '',
            'timestamped_text': ''
        }
    except NoTranscriptFound:
        return {
            'success': False,
            'error': 'No transcript was found for this video.',
            'raw_segments': [],
            'formatted_text': '',
            'timestamped_text': ''
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to retrieve transcript: {str(e)}',
            'raw_segments': [],
            'formatted_text': '',
            'timestamped_text': ''
        }
