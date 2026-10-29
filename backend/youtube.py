import re
import os
import json
import urllib.request
from pathlib import Path
from typing import List, Dict, Any, Optional
from config import FFMPEG_PATH, BASE_DIR
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

ANDROID_HEADERS = {
    'User-Agent': 'com.google.android.youtube/19.29.37 (Linux; U; Android 14; en_US; Pixel 8 Pro Build/UQ1A.240205.004) gzip',
    'Accept-Language': 'en-US,en;q=0.9',
}

def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11})(?:\?|&|\/|$)",
        r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})(?:\?|&|\/|$)",
        r"(?:shorts\/)([0-9A-Za-z_-]{11})(?:\?|&|\/|$)",
        r"(?:embed\/)([0-9A-Za-z_-]{11})(?:\?|&|\/|$)",
        r"^([0-9A-Za-z_-]{11})$"
    ]
    for pattern in patterns:
        match = re.search(pattern, url.strip())
        if match:
            return match.group(1)
    return None

def fetch_oembed_info(video_id: str) -> Dict[str, Any]:
    """
    Foolproof metadata fetch using Google's official public YouTube oEmbed API.
    Never blocked by datacenter IPs or bot-checks.
    """
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        req = urllib.request.Request(
            oembed_url, 
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            return {
                "id": video_id,
                "title": data.get("title", "YouTube Video"),
                "duration": 0,
                "uploader": data.get("author_name", "Creator"),
                "thumbnail": data.get("thumbnail_url") or f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                "view_count": 0
            }
    except Exception as e:
        print(f"oEmbed fetch note for {video_id}: {e}")
        
    return {
        "id": video_id,
        "title": "YouTube Video",
        "duration": 0,
        "uploader": "Creator",
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        "view_count": 0
    }

def get_cookie_file() -> Optional[Path]:
    """
    Check if cookies are provided via:
    1. Environment variable YOUTUBE_COOKIES or YOUTUBE_COOKIE_CONTENT
    2. Local cookies.txt file
    """
    cookie_env = os.environ.get("YOUTUBE_COOKIES") or os.environ.get("YOUTUBE_COOKIE_CONTENT")
    if cookie_env and len(cookie_env.strip()) > 20:
        env_cookie_path = BASE_DIR / "cookies.txt"
        try:
            with open(env_cookie_path, "w", encoding="utf-8") as f:
                f.write(cookie_env.strip())
            return env_cookie_path
        except Exception as e:
            print(f"Error writing cookie from env: {e}")

    candidates = [
        BASE_DIR / "cookies.txt",
        BASE_DIR / "backend" / "cookies.txt"
    ]
    for c in candidates:
        if c.exists() and c.stat().st_size > 10:
            return c
    return None

def get_video_info(url: str) -> Dict[str, Any]:
    """
    Fetch video metadata with multi-client rotation and instant oEmbed fallback.
    """
    video_id = extract_video_id(url)
    cookie_path = get_cookie_file()
    
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'geo_bypass': True,
        'geo_bypass_country': 'US',
        'http_headers': ANDROID_HEADERS
    }
    
    if cookie_path:
        ydl_opts['cookiefile'] = str(cookie_path)
    else:
        ydl_opts['extractor_args'] = {
            'youtube': {
                'player_client': ['android', 'ios']
            }
        }
        
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "id": info.get("id") or video_id,
                "title": info.get("title", "YouTube Video"),
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", "Unknown"),
                "thumbnail": info.get("thumbnail") or f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                "view_count": info.get("view_count", 0)
            }
    except Exception as e:
        print(f"yt-dlp info extraction notice: {e}. Falling back to Google oEmbed API...")
        if video_id:
            return fetch_oembed_info(video_id)
            
    return {
        "id": video_id or "video",
        "title": "YouTube Video",
        "duration": 0,
        "uploader": "Creator",
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg" if video_id else None,
        "view_count": 0
    }

def get_transcript(video_id: str) -> List[Dict[str, Any]]:
    """
    Fetch transcript using youtube_transcript_api.
    If unavailable or blocked, safely returns empty list without breaking the pipeline.
    """
    try:
        transcript_list = None
        if hasattr(YouTubeTranscriptApi, 'list_transcripts'):
            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            except Exception:
                pass
                
        if transcript_list is None:
            try:
                api_instance = YouTubeTranscriptApi()
                if hasattr(api_instance, 'list'):
                    transcript_list = api_instance.list(video_id)
            except Exception:
                pass

        if transcript_list:
            preferred_langs = ['en', 'hi', 'en-US', 'en-GB', 'en-IN', 'es', 'pt', 'id']
            transcript = None
            try:
                transcript = transcript_list.find_transcript(preferred_langs)
            except Exception:
                for t in transcript_list:
                    transcript = t
                    break

            if transcript:
                raw_items = transcript.fetch()
                cleaned = []
                for item in raw_items:
                    if isinstance(item, dict):
                        text = item.get("text", "")
                        start = item.get("start", 0)
                        dur = item.get("duration", 0)
                    else:
                        text = getattr(item, "text", "")
                        start = getattr(item, "start", 0)
                        dur = getattr(item, "duration", 0)

                    clean_text = text.replace("\n", " ").strip()
                    if clean_text and clean_text not in ("[Music]", "[Applause]", "[Sound]", "[Silence]"):
                        cleaned.append({
                            "text": clean_text,
                            "start": round(float(start), 2),
                            "duration": round(float(dur), 2)
                        })
                return cleaned
    except Exception as e:
        print(f"Transcript fetch note for {video_id}: {e}")
    
    return []

def download_video(url: str, output_path: Path) -> Path:
    """
    Download video in MP4 format.
    Multi-pass strategy with dynamic cookie and client handling guarantees format availability.
    """
    output_template = str(output_path.with_suffix('')) + ".%(ext)s"
    cookie_path = get_cookie_file()
    
    # Layer 1: Best quality MP4 download
    opts_layer1 = {
        'ffmpeg_location': str(FFMPEG_PATH),
        'geo_bypass': True,
        'geo_bypass_country': 'US',
        'http_headers': ANDROID_HEADERS,
        'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/bestvideo+bestaudio/best',
        'outtmpl': output_template,
        'merge_output_format': 'mp4',
        'quiet': False,
        'no_warnings': True
    }
    if cookie_path:
        opts_layer1['cookiefile'] = str(cookie_path)
    else:
        opts_layer1['extractor_args'] = {
            'youtube': {
                'player_client': ['android', 'ios']
            }
        }
        
    try:
        with yt_dlp.YoutubeDL(opts_layer1) as ydl:
            ydl.download([url])
    except Exception as e1:
        print(f"Layer 1 download note: {e1}. Retrying with Layer 2 (Single-stream / Format 18)...")
        # Layer 2: Android / iOS Format 18 or direct single-stream MP4
        opts_layer2 = {
            'ffmpeg_location': str(FFMPEG_PATH),
            'geo_bypass': True,
            'geo_bypass_country': 'IN',
            'http_headers': ANDROID_HEADERS,
            'format': '18/best[ext=mp4]/best',
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': True
        }
        if cookie_path:
            opts_layer2['cookiefile'] = str(cookie_path)
        else:
            opts_layer2['extractor_args'] = {
                'youtube': {
                    'player_client': ['android', 'ios']
                }
            }
            
        try:
            with yt_dlp.YoutubeDL(opts_layer2) as ydl:
                ydl.download([url])
        except Exception as e2:
            print(f"Layer 2 download note: {e2}. Retrying with Layer 3 (Universal fallback)...")
            # Layer 3: Universal fallback
            opts_layer3 = {
                'ffmpeg_location': str(FFMPEG_PATH),
                'geo_bypass': True,
                'format': 'best/worst',
                'outtmpl': output_template,
                'quiet': False,
                'no_warnings': True
            }
            if cookie_path:
                opts_layer3['cookiefile'] = str(cookie_path)
            else:
                opts_layer3['extractor_args'] = {
                    'youtube': {
                        'player_client': ['android']
                    }
                }
            with yt_dlp.YoutubeDL(opts_layer3) as ydl:
                ydl.download([url])
        
    final_mp4 = output_path.with_suffix('.mp4')
    if final_mp4.exists():
        return final_mp4
        
    for ext in ['.mkv', '.webm', '.mp4']:
        candidate = output_path.with_suffix(ext)
        if candidate.exists():
            return candidate
            
    return output_path
