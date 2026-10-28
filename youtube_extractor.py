"""
YouTube Video and Playlist Metadata & Transcript Extractor.
Supports single video URLs and full playlist URLs.
Includes Android/iOS mobile client fallback to bypass cloud IP blocks.
"""

import re
import requests
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
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 8,
        'retries': 2,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web']
            }
        }
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
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web']
            }
        }
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


def get_transcript_via_ytdlp(video_id: str, preferred_languages: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Fallback transcript extractor using yt-dlp with YouTube Android/iOS mobile client emulation.
    Bypasses datacenter and cloud IP blocks on Streamlit Cloud, AWS, and GCP.
    """
    if preferred_languages is None:
        preferred_languages = ['en', 'en-US', 'hi', 'es', 'fr', 'de']
        
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': 10,
        'retries': 2,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web']
            }
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            subs = info.get('subtitles') or {}
            auto_subs = info.get('automatic_captions') or {}
            
            all_captions = {}
            for lang, tracks in auto_subs.items():
                all_captions[lang] = tracks
            for lang, tracks in subs.items():
                all_captions[lang] = tracks
                
            selected_lang = None
            for plang in preferred_languages:
                if plang in all_captions:
                    selected_lang = plang
                    break
                    
            if not selected_lang and all_captions:
                selected_lang = next(iter(all_captions.keys()))
                
            if not selected_lang:
                return {
                    'success': False,
                    'error': 'No subtitles or transcripts found for this video.',
                    'raw_segments': [],
                    'formatted_text': '',
                    'timestamped_text': ''
                }
                
            formats = all_captions[selected_lang]
            json3_track = next((f['url'] for f in formats if f.get('ext') == 'json3'), None)
            
            raw_segments = []
            raw_text_pieces = []
            grouped_timestamped = []
            current_block_start = 0.0
            current_block_text = []

            if json3_track:
                resp = requests.get(json3_track, timeout=15).json()
                events = resp.get('events', [])
                for ev in events:
                    t_start = ev.get('tStartMs', 0) / 1000.0
                    d_ms = ev.get('dDurationMs', 0) / 1000.0
                    seg_text = "".join(seg.get('utf8', '') for seg in ev.get('segs', []) if seg.get('utf8'))
                    seg_text = seg_text.strip()
                    if not seg_text or seg_text == '\n':
                        continue
                        
                    raw_segments.append({'text': seg_text, 'start': t_start, 'duration': d_ms})
                    raw_text_pieces.append(seg_text)
                    
                    if not current_block_text:
                        current_block_start = t_start
                        current_block_text.append(seg_text)
                    elif t_start - current_block_start >= 45.0:
                        block_str = f"[{format_timestamp(current_block_start)}] " + " ".join(current_block_text)
                        grouped_timestamped.append(block_str)
                        current_block_start = t_start
                        current_block_text = [seg_text]
                    else:
                        current_block_text.append(seg_text)
            else:
                track_url = formats[0]['url']
                vtt_text = requests.get(track_url, timeout=15).text
                clean_lines = [l.strip() for l in vtt_text.splitlines() if l.strip() and not l.startswith('WEBVTT') and '-->' not in l]
                full_raw = " ".join(clean_lines)
                raw_text_pieces.append(full_raw)
                grouped_timestamped.append(full_raw)
                
            if current_block_text:
                block_str = f"[{format_timestamp(current_block_start)}] " + " ".join(current_block_text)
                grouped_timestamped.append(block_str)
                
            full_text = " ".join(raw_text_pieces)
            timestamped_full = "\n\n".join(grouped_timestamped)
            
            return {
                'success': True,
                'language': selected_lang,
                'is_generated': True,
                'raw_segments': raw_segments,
                'formatted_text': full_text,
                'timestamped_text': timestamped_full,
                'segment_count': len(raw_segments),
                'word_count': len(full_text.split())
            }
    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to retrieve transcript: {str(e)}',
            'raw_segments': [],
            'formatted_text': '',
            'timestamped_text': ''
        }


def get_video_transcript(video_id: str, preferred_languages: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Fetch transcripts for a YouTube video.
    Uses yt-dlp mobile client (Android/iOS) as PRIMARY to bypass cloud datacenter IP blocks.
    Falls back to YouTubeTranscriptApi.
    """
    if preferred_languages is None:
        preferred_languages = ['en', 'en-US', 'hi', 'es', 'fr', 'de']
        
    # 1. Try mobile client emulation FIRST (bypasses cloud IP bans on Streamlit Cloud/AWS/GCP)
    ytdlp_res = get_transcript_via_ytdlp(video_id, preferred_languages)
    if ytdlp_res.get('success'):
        return ytdlp_res

    # 2. Fallback to YouTubeTranscriptApi if mobile client didn't find tracks
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id)
        
        transcript = None
        selected_lang = None
        is_generated = False
        
        # Try manual transcript
        for lang in preferred_languages:
            try:
                transcript = transcript_list.find_manually_created_transcript([lang])
                selected_lang = transcript.language_code
                is_generated = False
                break
            except Exception:
                continue
                
        # Try generated transcript
        if not transcript:
            for lang in preferred_languages:
                try:
                    transcript = transcript_list.find_generated_transcript([lang])
                    selected_lang = transcript.language_code
                    is_generated = True
                    break
                except Exception:
                    continue
                    
        # Take first available
        if not transcript:
            for t in transcript_list:
                transcript = t
                selected_lang = t.language_code
                is_generated = t.is_generated
                break

        if not transcript:
            return ytdlp_res  # return original error
            
        fetched = transcript.fetch()
        
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
        
    except Exception:
        return ytdlp_res
