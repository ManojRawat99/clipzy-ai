import re
import os
import json
import shutil
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

def normalize_cookie_text(content: str) -> tuple[str, int]:
    """
    Normalizes cookies text into strict, valid Netscape format for yt-dlp.
    Handles:
    - Base64 encoding
    - Escaped newlines and tabs (\\n, \\t)
    - Space-separated lines (e.g. from Render dashboard input or copy-paste)
    - Tab-separated lines
    Returns (normalized_netscape_content, cookie_count)
    """
    if not content:
        return "", 0
        
    raw = content.strip()
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        raw = raw[1:-1].strip()
        
    # Check if raw is base64 encoded
    if ' ' not in raw and '\t' not in raw and '\n' not in raw and len(raw) > 30:
        try:
            import base64
            decoded = base64.b64decode(raw).decode('utf-8', errors='ignore')
            if 'youtube.com' in decoded:
                raw = decoded
        except Exception:
            pass
            
    # Unescape literal string representations from cloud environment inputs
    if "\\r\\n" in raw:
        raw = raw.replace("\\r\\n", "\n")
    if "\\n" in raw:
        raw = raw.replace("\\n", "\n")
    if "\\t" in raw:
        raw = raw.replace("\\t", "\t")
        
    # 1. Clean flattened comments: Remove any # comment before the first domain if flattened
    raw = re.sub(r'#.*?(?=(?:\.youtube\.com|\.google\.com|youtube\.com|google\.com)\s)', '', raw, flags=re.DOTALL)

    # 2. Check if text is flattened into 1 or 2 lines
    lines = raw.splitlines()
    if len(lines) <= 2 and ("youtube.com" in raw or "google.com" in raw):
        chunks = re.split(r'\s+(?=(?:\.youtube\.com|\.google\.com|youtube\.com|google\.com)\s)', raw.strip())
    else:
        chunks = lines

    out = [
        "# Netscape HTTP Cookie File",
        "# https://curl.se/rfc/cookie_spec.html",
        "# This is a generated file! Do not edit."
    ]
    valid_count = 0
    
    for chunk in chunks:
        line = chunk.strip()
        if not line or line.startswith("#"):
            continue
            
        # Parse fields
        if "\t" in line:
            parts = line.split("\t")
        else:
            # Handle multiple spaces from copy-paste or Render dashboard
            parts = line.split()
            
        if len(parts) >= 7:
            domain = parts[0].strip()
            subdomains = parts[1].strip().upper()
            flag = "TRUE" if subdomains in ("TRUE", "1", "YES") else ("FALSE" if subdomains in ("FALSE", "0", "NO") else "TRUE")
            path = parts[2].strip() or "/"
            secure_val = parts[3].strip().upper()
            secure = "TRUE" if secure_val in ("TRUE", "1", "YES") else ("FALSE" if secure_val in ("FALSE", "0", "NO") else "TRUE")
            expiry = parts[4].strip()
            if not expiry.isdigit():
                expiry = "0"
            name = parts[5].strip()
            value = " ".join(parts[6:]).strip()
            
            # Filter for YouTube / Google domain cookies
            if "youtube.com" in domain or "google.com" in domain:
                out.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}")
                valid_count += 1
        elif len(parts) >= 5 and ("youtube.com" in parts[0] or "google.com" in parts[0]):
            domain = parts[0].strip()
            name = parts[-2].strip()
            value = parts[-1].strip()
            out.append(f"{domain}\tTRUE\t/\tTRUE\t0\t{name}\t{value}")
            valid_count += 1

    if valid_count > 0:
        return "\n".join(out) + "\n", valid_count
    return "", 0

def is_valid_netscape_content(content: str) -> bool:
    if not content or len(content.strip()) < 20:
        return False
    _, count = normalize_cookie_text(content)
    return count > 0

def is_valid_youtube_cookie_file(path: Path) -> bool:
    """Verify that the cookie file actually contains valid Netscape youtube.com cookies."""
    if path.exists() and path.stat().st_size > 20:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            _, count = normalize_cookie_text(content)
            return count > 0
        except Exception:
            pass
    return False

def get_cookie_file() -> Optional[Path]:
    """
    Locates YouTube cookies from:
    1. ANY environment variable (YOUTUBE_COOKIES, YT_COOKIES, COOKIES, or any env containing youtube.com)
    2. Render Secret Files (/etc/secrets/cookies.txt, /etc/secrets/*)
    3. settings.json or local cookies.txt
    Normalizes them automatically into strict Netscape format and saves to BASE_DIR / 'cookies.txt'.
    """
    target = BASE_DIR / "cookies.txt"

    # 1. First, check environment variables
    priority_keys = [
        "YOUTUBE_COOKIES", "YOUTUBE_COOKIE", "YT_COOKIES", "YT_COOKIE",
        "COOKIES_TXT", "COOKIE_FILE", "COOKIES", "COOKIE", "YOUTUBE_COOKIES_TXT"
    ]
    env_content = None
    matched_key = None
    for k, v in os.environ.items():
        if not v or len(v.strip()) < 15:
            continue
        clean_k = k.strip().upper()
        if clean_k in priority_keys or any(clean_k == p for p in priority_keys):
            env_content = v
            matched_key = k
            break
            
    if not env_content:
        # Search all env vars for any variable with youtube cookies (ignore json objects)
        for k, v in os.environ.items():
            if not v or len(v.strip()) < 20:
                continue
            stripped = v.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                continue
            if "youtube.com" in v or "LOGIN_INFO" in v or "VISITOR_INFO" in v:
                env_content = v
                matched_key = k
                break
                
    if env_content:
        print(f"[Clipzy AI] [COOKIES] Found candidate environment variable '{matched_key}' (length {len(env_content)} chars)")
        normalized, count = normalize_cookie_text(env_content)
        if count > 0:
            try:
                with open(target, "w", encoding="utf-8") as f:
                    f.write(normalized)
                print(f"[Clipzy AI] [COOKIES] Successfully normalized & loaded {count} YouTube cookies from env '{matched_key}'")
                return target
            except Exception as e:
                print(f"Error writing normalized cookie from env '{matched_key}': {e}")
        else:
            print(f"[Clipzy AI] [COOKIES] Warning: Env var '{matched_key}' could not be normalized into Netscape format")

    # 2. Check Render Secret Files and known file paths
    candidate_paths = [
        Path("/etc/secrets/cookies.txt"),
        Path("/etc/secrets/youtube_cookies.txt"),
        Path("/etc/secrets/cookies"),
        BASE_DIR / "cookies.txt",
        BASE_DIR / "backend" / "cookies.txt",
        Path("/app/cookies.txt")
    ]
    
    # Also scan /etc/secrets/ directory if present
    secrets_dir = Path("/etc/secrets")
    if secrets_dir.is_dir():
        try:
            for f in secrets_dir.glob("*"):
                if f.is_file() and f not in candidate_paths:
                    candidate_paths.append(f)
        except Exception:
            pass
                
    for path in candidate_paths:
        if path.exists() and path.stat().st_size > 20:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                normalized, count = normalize_cookie_text(content)
                if count > 0:
                    if path != target:
                        with open(target, "w", encoding="utf-8") as f:
                            f.write(normalized)
                        try:
                            print(f"[Clipzy AI] [COOKIES] Loaded {count} YouTube cookies from secret file: {path}")
                        except Exception:
                            pass
                        return target
                    return path
            except Exception:
                pass

    # 3. Check settings.json
    settings_file = BASE_DIR / "settings.json"
    if settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                val = data.get("youtube_cookies", "")
                if val:
                    normalized, count = normalize_cookie_text(val)
                    if count > 0:
                        with open(target, "w", encoding="utf-8") as f:
                            f.write(normalized)
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
    node_bin = shutil.which("node") or shutil.which("nodejs")
    
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'geo_bypass': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android_vr', 'android']
            }
        }
    }
    
    if node_bin:
        ydl_opts['js_runtimes'] = {'node': {}}
        
    if cookie_path:
        ydl_opts['cookiefile'] = str(cookie_path)
    else:
        ydl_opts['http_headers'] = ANDROID_HEADERS
        
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
    Multi-pass strategy with dynamic client and format fallback guarantees availability.
    """
    output_template = str(output_path.with_suffix('')) + ".%(ext)s"
    cookie_path = get_cookie_file()
    node_bin = shutil.which("node") or shutil.which("nodejs")
    
    # Pure mobile & VR player clients (immune to datacenter web bot-checks)
    client_list = ['android_vr', 'android']
    
    # Universal format: best video (up to 1080p) + best audio, or best 720p, or single stream 18, or best
    universal_format = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/bestvideo+bestaudio/18/best'
    
    # Layer 1: Best available stream with cookies (if available)
    opts_layer1 = {
        'ffmpeg_location': str(FFMPEG_PATH),
        'geo_bypass': True,
        'format': universal_format,
        'outtmpl': output_template,
        'merge_output_format': 'mp4',
        'quiet': False,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': client_list
            }
        }
    }
    if node_bin:
        opts_layer1['js_runtimes'] = {'node': {}}
        
    if cookie_path:
        opts_layer1['cookiefile'] = str(cookie_path)
    else:
        opts_layer1['http_headers'] = ANDROID_HEADERS
        
    try:
        with yt_dlp.YoutubeDL(opts_layer1) as ydl:
            ydl.download([url])
    except Exception as e1:
        print(f"Layer 1 download note: {e1}. Retrying with Layer 2 (Pure Android VR/Android WITHOUT cookies)...")
        # Clean any partial/broken downloads
        for p in output_path.parent.glob(f"{output_path.stem}*"):
            if p.name.endswith(".part") or p.name.endswith(".ytdl"):
                try: p.unlink()
                except Exception: pass
        # Layer 2: Bypass cookies completely using Android VR / Android client (never blocked by bot-checks)
        opts_layer2 = {
            'ffmpeg_location': str(FFMPEG_PATH),
            'geo_bypass': True,
            'format': universal_format,
            'outtmpl': output_template,
            'merge_output_format': 'mp4',
            'quiet': False,
            'no_warnings': True,
            'http_headers': ANDROID_HEADERS,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android_vr', 'android']
                }
            }
        }
        if node_bin:
            opts_layer2['js_runtimes'] = {'node': {}}
            
        try:
            with yt_dlp.YoutubeDL(opts_layer2) as ydl:
                ydl.download([url])
        except Exception as e2:
            print(f"Layer 2 download note: {e2}. Retrying with Layer 3 (Format 18 single-stream MP4)...")
            # Clean any partial/broken downloads
            for p in output_path.parent.glob(f"{output_path.stem}*"):
                if p.name.endswith(".part") or p.name.endswith(".ytdl"):
                    try: p.unlink()
                    except Exception: pass
            # Layer 3: Direct single-stream Format 18
            opts_layer3 = {
                'ffmpeg_location': str(FFMPEG_PATH),
                'geo_bypass': True,
                'format': '18/best[height<=720]/best',
                'outtmpl': output_template,
                'quiet': False,
                'no_warnings': True,
                'http_headers': ANDROID_HEADERS,
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'android_vr']
                    }
                }
            }
            if node_bin:
                opts_layer3['js_runtimes'] = {'node': {}}
            try:
                with yt_dlp.YoutubeDL(opts_layer3) as ydl:
                    ydl.download([url])
            except Exception as e3:
                print(f"Layer 3 download note: {e3}. Retrying with Layer 4 (Universal fallback)...")
                # Layer 4: Universal fallback
                opts_layer4 = {
                    'ffmpeg_location': str(FFMPEG_PATH),
                    'geo_bypass': True,
                    'format': 'best/worst',
                    'outtmpl': output_template,
                    'quiet': False,
                    'no_warnings': True
                }
                if node_bin:
                    opts_layer4['js_runtimes'] = {'node': {}}
                with yt_dlp.YoutubeDL(opts_layer4) as ydl:
                    ydl.download([url])
        
    final_mp4 = output_path.with_suffix('.mp4')
    if final_mp4.exists():
        return final_mp4
        
    for ext in ['.mkv', '.webm', '.mp4']:
        candidate = output_path.with_suffix(ext)
        if candidate.exists():
            return candidate
            
    return output_path
