import re
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from config import FFMPEG_PATH
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

def extract_video_id(url: str) -> Optional[str]:
    """Extract 11-character YouTube video ID from various URL formats."""
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",
        r"(?:shorts\/)([0-9A-Za-z_-]{11})"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_video_info(url: str) -> Dict[str, Any]:
    """Fetch video metadata using yt-dlp without downloading."""
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'js_runtimes': {'node': {}},
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'mweb', 'web']
            }
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            "id": info.get("id"),
            "title": info.get("title", "YouTube Video"),
            "duration": info.get("duration", 0),
            "uploader": info.get("uploader", "Unknown"),
            "thumbnail": info.get("thumbnail"),
            "view_count": info.get("view_count", 0)
        }

def get_transcript(video_id: str) -> List[Dict[str, Any]]:
    """
    Fetch transcript using youtube_transcript_api.
    Tries English, Hindi, and then any auto-generated language.
    Returns: list of dicts with 'text', 'start', 'duration'.
    """
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        # Try finding manual or generated transcripts (English or Hindi first)
        preferred_langs = ['en', 'hi', 'en-US', 'en-GB', 'en-IN']
        transcript = None
        
        try:
            transcript = transcript_list.find_transcript(preferred_langs)
        except Exception:
            # Fall back to first available transcript (and translate to English if needed)
            for t in transcript_list:
                transcript = t
                break
                
        if transcript:
            data = transcript.fetch()
            # Clean up text
            cleaned = []
            for item in data:
                text = item.get("text", "").replace("\n", " ").strip()
                if text and text != "[Music]" and text != "[Applause]":
                    cleaned.append({
                        "text": text,
                        "start": round(float(item.get("start", 0)), 2),
                        "duration": round(float(item.get("duration", 0)), 2)
                    })
            return cleaned
    except Exception as e:
        print(f"Transcript fetch error for {video_id}: {e}")
    
    return []

def download_video(url: str, output_path: Path) -> Path:
    """
    Download video in 720p or 1080p MP4 format suitable for fast processing.
    Bypasses 403 Forbidden using Android/iOS client spoofing, Node.js JS runtime,
    and automatic Chrome browser session fallback.
    """
    output_template = str(output_path.with_suffix('')) + ".%(ext)s"
    
    # Layer 1: Android/iOS client rotation with Node.js JS runtime
    base_opts = {
        'ffmpeg_location': str(FFMPEG_PATH),
        'js_runtimes': {'node': {}},
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'mweb', 'web']
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
        },
        'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/bestvideo+bestaudio/best',
        'outtmpl': output_template,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True
    }
    
    try:
        with yt_dlp.YoutubeDL(base_opts) as ydl:
            ydl.download([url])
    except Exception as e1:
        print(f"Layer 1 download error: {e1}. Retrying with Chrome cookies...")
        # Layer 2: Retry with Chrome browser cookies (resolves strict bot/403 IP challenges)
        try:
            cookie_opts = dict(base_opts)
            cookie_opts['cookiesfrombrowser'] = ('chrome', None, None, None)
            with yt_dlp.YoutubeDL(cookie_opts) as ydl:
                ydl.download([url])
        except Exception as e2:
            print(f"Layer 2 download error: {e2}. Retrying with direct single-stream format...")
            # Layer 3: Direct single mp4 stream fallback
            fallback_opts = {
                'ffmpeg_location': str(FFMPEG_PATH),
                'js_runtimes': {'node': {}},
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'ios']
                    }
                },
                'format': 'best[ext=mp4]/best',
                'outtmpl': output_template,
                'quiet': True,
                'no_warnings': True
            }
            with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                ydl.download([url])
        
    final_mp4 = output_path.with_suffix('.mp4')
    if final_mp4.exists():
        return final_mp4
    # Check if file with other extension was created and rename if needed
    for ext in ['.mkv', '.webm', '.mp4']:
        candidate = output_path.with_suffix(ext)
        if candidate.exists():
            return candidate
            
    return output_path

