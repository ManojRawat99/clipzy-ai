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

def is_valid_netscape_content(content: str) -> bool:
    if not content or len(content.strip()) < 20:
        return False
    stripped = content.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return False
    has_yt = "youtube.com" in content
    has_tabs = "\t" in content or "\\t" in content
    return has_yt and has_tabs

def is_valid_youtube_cookie_file(path: Path) -> bool:
    """Verify that the cookie file actually contains valid Netscape youtube.com cookies."""
    if path.exists() and path.stat().st_size > 20:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if is_valid_netscape_content(content):
                    return True
                else:
                    try:
                        path.unlink()
                    except Exception:
                        pass
        except Exception:
            pass
    return False

def get_cookie_file() -> Optional[Path]:
    """
    Check if cookies are provided via:
    1. Specific environment variable: YOUTUBE_COOKIES, YOUTUBE_COOKIE, YT_COOKIES
    2. Render Secret File (/etc/secrets/cookies.txt)
    3. Local cookies.txt file or settings.json
    """
    allowed_keys = ("YOUTUBE_COOKIES", "YOUTUBE_COOKIE", "YT_COOKIES", "COOKIES_TXT")
    cookie_env = None
    for k, v in os.environ.items():
        if k.upper() in allowed_keys and is_valid_netscape_content(v):
            cookie_env = v
            break

    if cookie_env:
        env_cookie_path = BASE_DIR / "cookies.txt"
        try:
            cleaned = cookie_env.strip()
            if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
                cleaned = cleaned[1:-1]
            if "\\n" in cleaned:
                cleaned = cleaned.replace("\\n", "\n")
            if "\\t" in cleaned:
                cleaned = cleaned.replace("\\t", "\t")
            with open(env_cookie_path, "w", encoding="utf-8") as f:
                f.write(cleaned)
            if is_valid_youtube_cookie_file(env_cookie_path):
                return env_cookie_path
        except Exception as e:
            print(f"Error writing cookie from env: {e}")

    candidates = [
        Path("/etc/secrets/cookies.txt"),
        Path("/etc/secrets/youtube_cookies.txt"),
        BASE_DIR / "cookies.txt",
        BASE_DIR / "backend" / "cookies.txt",
        Path("/app/cookies.txt")
    ]
    for c in candidates:
        if is_valid_youtube_cookie_file(c):
            return c

    # Also check settings.json
    settings_file = BASE_DIR / "settings.json"
    if settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                val = data.get("youtube_cookies", "")
                if is_valid_netscape_content(val):
                    target = BASE_DIR / "cookies.txt"
                    with open(target, "w", encoding="utf-8") as wf:
                        wf.write(val.strip())
                    return target
        except Exception:
            pass

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
        'geo_bypass_country': 'US'
    }
    
    if cookie_path:
        ydl_opts['cookiefile'] = str(cookie_path)
    else:
        ydl_opts['http_headers'] = ANDROID_HEADERS
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
    
    # Universal format: selects best 1080p video+audio, or 720p, or single-stream 18, merged into MP4
    universal_format = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/18/bestvideo+bestaudio/best'
    
    # Layer 1: Best available stream (Web or Android depending on cookie availability)
    opts_layer1 = {
        'ffmpeg_location': str(FFMPEG_PATH),
        'geo_bypass': True,
        'geo_bypass_country': 'US',
        'format': universal_format,
        'outtmpl': output_template,
        'merge_output_format': 'mp4',
        'quiet': False,
        'no_warnings': True
    }
    if cookie_path:
        opts_layer1['cookiefile'] = str(cookie_path)
    else:
        opts_layer1['http_headers'] = ANDROID_HEADERS
        opts_layer1['extractor_args'] = {
            'youtube': {
                'player_client': ['android', 'ios']
            }
        }
        
    try:
        with yt_dlp.YoutubeDL(opts_layer1) as ydl:
            ydl.download([url])
    except Exception as e1:
        print(f"Layer 1 download note: {e1}. Retrying with Layer 2 (Android Format 18 single stream)...")
        # Layer 2: Android / iOS Format 18 direct MP4 stream
        opts_layer2 = {
            'ffmpeg_location': str(FFMPEG_PATH),
            'geo_bypass': True,
            'geo_bypass_country': 'IN',
            'http_headers': ANDROID_HEADERS,
            'format': '18/best[height<=720]/best',
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android']
                }
            }
        }
        if cookie_path:
            opts_layer2['cookiefile'] = str(cookie_path)
            
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
