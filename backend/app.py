import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

# Ensure local backend imports work in all execution modes
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

from config import BASE_DIR, OUTPUT_DIR, STATIC_DIR, SETTINGS_FILE, ASPECT_RATIOS
from pipeline import start_clipping_job, JOBS

app = FastAPI(
    title="Clipzy AI - Viral Shorts & Reels Clipper",
    version="1.0.0"
)

# Enable CORS for Chrome Extension and Web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    try:
        from youtube import get_cookie_file
        matching_keys = [k for k in os.environ if any(x in k.upper() for x in ("COOKIE", "YT", "YOUTUBE"))]
        if matching_keys:
            print(f"[Clipzy AI] [ENV DISCOVERY] Detected environment variables: {matching_keys}")
        cookie_path = get_cookie_file()
        if cookie_path and cookie_path.exists():
            try:
                with open(cookie_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = [l for l in f.read().splitlines() if l.strip() and not l.startswith("#")]
                print("=" * 60)
                print(f"[Clipzy AI] [COOKIES ACTIVE] {len(lines)} YouTube cookies successfully loaded!")
                print(f"[Clipzy AI] Cookie Path: {cookie_path}")
                print(f"[Clipzy AI] Permanent server-wide authentication active for ALL users!")
                print("=" * 60)
            except Exception as e:
                print(f"[Clipzy AI] Startup cookie reading error: {e}")
        else:
            print("[Clipzy AI] [COOKIES] No YouTube cookies found in ENV or Secret Files.")
            print("[Clipzy AI] Note: Set YOUTUBE_COOKIES in Render Environment for server-wide bypass.")
    except Exception as e:
        print(f"[Clipzy AI] Startup error: {e}")

@app.get("/favicon.ico", include_in_schema=False)
def get_favicon():
    fav_file = STATIC_DIR / "favicon.ico"
    if fav_file.exists():
        return FileResponse(fav_file)
    return {"status": "ok"}

class ClipRequest(BaseModel):
    url: str
    num_clips: Optional[int] = 3
    min_duration: Optional[int] = 25
    max_duration: Optional[int] = 55
    aspect_ratio: Optional[str] = "9:16"
    gemini_key: Optional[str] = None

class SettingsRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    youtube_cookies: Optional[str] = None

def load_settings() -> Dict[str, Any]:
    settings = {"gemini_api_key": os.environ.get("GEMINI_API_KEY", "")}
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings.update(json.load(f))
        except Exception:
            pass
            
    # Auto-restore cookies from environment or disk if missing
    cookie_path = BASE_DIR / "cookies.txt"
    if not cookie_path.exists() or cookie_path.stat().st_size < 10:
        try:
            from youtube import get_cookie_file
            get_cookie_file()
        except Exception:
            pass
                
    return settings

def save_settings(data: Dict[str, Any]):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

@app.post("/api/clip")
def create_clip_job(req: ClipRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="YouTube URL is required")
        
    settings = load_settings()
    active_gemini_key = req.gemini_key or settings.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")
    
    job_id = start_clipping_job(
        url=url,
        num_clips=req.num_clips or 3,
        min_duration=req.min_duration or 25,
        max_duration=req.max_duration or 55,
        gemini_key=active_gemini_key,
        aspect_ratio=req.aspect_ratio or "9:16"
    )
    
    return {
        "job_id": job_id,
        "status": "queued",
        "aspect_ratio": req.aspect_ratio or "9:16",
        "message": "Viral clipping job started!"
    }

@app.get("/api/status/{job_id}")
def get_job_status(job_id: str):
    if job_id not in JOBS:
        return {
            "job_id": job_id,
            "status": "not_found",
            "progress": 0,
            "message": "Job not found or server restarted.",
            "clips": [],
            "error": None
        }
    return JOBS[job_id]

@app.get("/api/clips")
def list_clips():
    """List all generated clips stored in output/"""
    clips = []
    if OUTPUT_DIR.exists():
        for file in sorted(OUTPUT_DIR.glob("*.mp4"), key=os.path.getmtime, reverse=True):
            stat = file.stat()
            clips.append({
                "filename": file.name,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "download_url": f"/output/{file.name}",
                "created_at": stat.st_mtime
            })
    return clips

@app.get("/api/settings")
def get_settings_status():
    settings = load_settings()
    key = settings.get("gemini_api_key", "")
    has_key = bool(key and len(key) > 5)
    masked_key = f"{key[:4]}...{key[-4:]}" if has_key else ""
    
    # Auto-detect cookie from env vars, secret files, or disk
    from youtube import get_cookie_file
    cookie_path = get_cookie_file()
    
    cookie_lines = 0
    saved_cookies_text = ""
    is_yt = False
    source = "None"
    
    if cookie_path and cookie_path.exists() and cookie_path.stat().st_size > 20:
        try:
            with open(cookie_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                cookie_lines = len([l for l in content.splitlines() if l.strip() and not l.startswith("#")])
                saved_cookies_text = content
                is_yt = "youtube.com" in content
                source = "Server Environment"
        except Exception:
            pass
            
    return {
        "has_gemini_key": has_key,
        "masked_key": masked_key,
        "has_cookies": bool(cookie_lines > 0),
        "is_youtube_cookie": is_yt,
        "cookie_count": cookie_lines,
        "source": source,
        "youtube_cookies": saved_cookies_text
    }

@app.post("/api/settings")
def update_settings(req: SettingsRequest):
    settings = load_settings()
    cookie_path = BASE_DIR / "cookies.txt"
    
    if req.gemini_api_key is not None:
        settings["gemini_api_key"] = req.gemini_api_key.strip()
        
    if req.youtube_cookies is not None:
        cookie_val = req.youtube_cookies.strip()
        if len(cookie_val) > 20:
            from youtube import normalize_cookie_text
            normalized, count = normalize_cookie_text(cookie_val)
            if count > 0:
                settings["youtube_cookies"] = normalized
                with open(cookie_path, "w", encoding="utf-8") as f:
                    f.write(normalized)
            else:
                settings["youtube_cookies"] = cookie_val
                with open(cookie_path, "w", encoding="utf-8") as f:
                    f.write(cookie_val)
        elif len(cookie_val) == 0:
            settings.pop("youtube_cookies", None)
            if cookie_path.exists():
                try:
                    cookie_path.unlink()
                except Exception:
                    pass
                    
    save_settings(settings)
    
    cookie_lines = 0
    if cookie_path.exists() and cookie_path.stat().st_size > 20:
        try:
            with open(cookie_path, "r", encoding="utf-8", errors="ignore") as f:
                cookie_lines = len([l for l in f.read().splitlines() if l.strip() and not l.startswith("#")])
        except Exception:
            pass
            
    return {
        "message": "Settings saved successfully",
        "has_gemini_key": bool(settings.get("gemini_api_key")),
        "has_cookies": bool(cookie_lines > 0),
        "cookie_count": cookie_lines
    }

# Mount static file endpoints
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting Clipzy AI Server on http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

