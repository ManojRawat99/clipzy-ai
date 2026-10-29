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

from config import OUTPUT_DIR, STATIC_DIR, SETTINGS_FILE, ASPECT_RATIOS
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

def load_settings() -> Dict[str, Any]:
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"gemini_api_key": os.environ.get("GEMINI_API_KEY", "")}

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
    return {
        "has_gemini_key": has_key,
        "masked_key": masked_key
    }

@app.post("/api/settings")
def update_settings(req: SettingsRequest):
    settings = load_settings()
    if req.gemini_api_key is not None:
        settings["gemini_api_key"] = req.gemini_api_key.strip()
    save_settings(settings)
    return {"message": "Settings saved successfully", "has_gemini_key": bool(settings.get("gemini_api_key"))}

# Mount static file endpoints
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting Clipzy AI Server on http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

