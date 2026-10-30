import os
import uuid
import subprocess
import threading
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional
import time

from config import (
    FFMPEG_PATH, 
    OUTPUT_DIR, 
    TEMP_DIR, 
    DEFAULT_NUM_CLIPS,
    DEFAULT_MIN_DURATION,
    DEFAULT_MAX_DURATION,
    TARGET_WIDTH,
    TARGET_HEIGHT
)
from youtube import extract_video_id, get_video_info, get_transcript, download_video
from ai_analyzer import find_viral_clips
from face_tracker import compute_crop_coordinates, compute_916_crop_coordinates
from subtitle_generator import generate_ass_subtitles

# Global jobs registry
JOBS: Dict[str, Dict[str, Any]] = {}

def update_job(job_id: str, status: str, progress: int, message: str, clips: Optional[List[Dict[str, Any]]] = None, error: Optional[str] = None):
    if job_id in JOBS:
        JOBS[job_id]["status"] = status
        JOBS[job_id]["progress"] = progress
        JOBS[job_id]["message"] = message
        if clips is not None:
            JOBS[job_id]["clips"] = clips
        if error:
            JOBS[job_id]["error"] = error
            JOBS[job_id]["status"] = "failed"

def sanitize_filename(text: str) -> str:
    return "".join(c for c in text if c.isalnum() or c in (" ", "-", "_")).rstrip()[:40].strip().replace(" ", "_")

def run_ffmpeg_render(
    input_video: Path,
    start_time: float,
    duration: float,
    crop_x: int,
    crop_y: int,
    crop_w: int,
    crop_h: int,
    target_w: int,
    target_h: int,
    ass_path: Optional[Path],
    output_path: Path
):
    """
    Renders the clip using FFmpeg with smart crop and scale to target dimensions.
    Burns animated .ass subtitles if provided.
    """
    vf_filters = [
        f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y}",
        f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease",
        f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black"
    ]
    
    if ass_path and ass_path.exists():
        # Clean path for ffmpeg: forward slashes and escaped colons
        clean_ass = str(ass_path).replace("\\", "/").replace(":", "\\:")
        vf_filters.append(f"subtitles='{clean_ass}'")
        
    filter_chain = ",".join(vf_filters)
    
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-ss", str(start_time),
        "-t", str(duration),
        "-i", str(input_video),
        "-vf", filter_chain,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path)
    ]
    
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        print(f"FFmpeg error: {proc.stderr[:400]}")
        # Retry without subtitles if subtitles filter had syntax issues
        if ass_path:
            simple_chain = ",".join(vf_filters[:-1])
            retry_cmd = [
                FFMPEG_PATH, "-y",
                "-ss", str(start_time),
                "-t", str(duration),
                "-i", str(input_video),
                "-vf", simple_chain,
                "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                str(output_path)
            ]
            subprocess.run(retry_cmd, check=True)
        else:
            raise RuntimeError(f"FFmpeg render failed: {proc.stderr[:300]}")

def process_video_job(
    job_id: str,
    url: str,
    num_clips: int,
    min_duration: int,
    max_duration: int,
    gemini_key: Optional[str],
    aspect_ratio: str = "9:16"
):
    try:
        update_job(job_id, "processing", 10, "Fetching video details...")
        video_id = extract_video_id(url)
        if not video_id:
            raise ValueError("Invalid YouTube URL. Please provide a valid YouTube link.")
            
        info = get_video_info(url)
        video_title = info.get("title", "Video")
        total_duration = float(info.get("duration", 0) or 0)
        
        update_job(job_id, "processing", 20, "Extracting video transcript...")
        transcript = get_transcript(video_id)
        
        # If duration was not found in metadata, calculate from transcript
        if total_duration <= 5.0 and transcript:
            last_item = transcript[-1]
            total_duration = float(last_item.get("start", 0)) + float(last_item.get("duration", 0))
        if total_duration <= 5.0:
            total_duration = 240.0 # Safe 4-minute estimate fallback
        
        update_job(job_id, "processing", 35, "AI is analyzing viral hooks & highlights...")
        clip_candidates = find_viral_clips(
            transcript=transcript,
            total_duration=total_duration,
            api_key=gemini_key,
            num_clips=num_clips,
            min_duration=float(min_duration),
            max_duration=float(max_duration)
        )
        
        if not clip_candidates:
            raise ValueError("Could not find suitable clips in this video.")
            
        update_job(job_id, "processing", 50, "Downloading source video...")
        source_video_path = TEMP_DIR / f"source_{job_id}.mp4"
        downloaded_path = download_video(url, source_video_path)
        
        # Verify video duration from actual downloaded media
        try:
            import cv2
            cap = cv2.VideoCapture(str(downloaded_path))
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
                if frame_count > 0 and fps > 0:
                    real_dur = frame_count / fps
                    if real_dur > 5.0:
                        total_duration = real_dur
                cap.release()
        except Exception as e_probe:
            print(f"Video duration probe note: {e_probe}")
        
        generated_clips = []
        total_candidates = len(clip_candidates)
        
        for idx, cand in enumerate(clip_candidates):
            c_start = cand["start"]
            c_end = cand["end"]
            c_dur = c_end - c_start
            
            step_progress = int(50 + ((idx + 1) / total_candidates) * 45)
            update_job(
                job_id, 
                "processing", 
                step_progress, 
                f"Generating clip #{idx+1} of {total_candidates}: '{cand['title']}'..."
            )
            
            # Step A: Smart face tracking for selected aspect ratio
            crop_x, crop_y, crop_w, crop_h, target_w, target_h = compute_crop_coordinates(
                downloaded_path, c_start, min(10.0, c_dur), aspect_ratio=aspect_ratio
            )
            
            # Step B: Generate viral subtitles
            ass_path = None
            if transcript:
                ass_path = TEMP_DIR / f"sub_{job_id}_{idx}.ass"
                generate_ass_subtitles(transcript, c_start, c_end, ass_path, aspect_ratio=aspect_ratio)
                
            # Step C: Render final vertical MP4
            title_slug = sanitize_filename(cand["title"])
            output_filename = f"clip_{idx+1}_{job_id[:6]}_{title_slug}.mp4"
            output_file = OUTPUT_DIR / output_filename
            
            run_ffmpeg_render(
                input_video=downloaded_path,
                start_time=c_start,
                duration=c_dur,
                crop_x=crop_x,
                crop_y=crop_y,
                crop_w=crop_w,
                crop_h=crop_h,
                target_w=target_w,
                target_h=target_h,
                ass_path=ass_path,
                output_path=output_file
            )
            
            generated_clips.append({
                "id": f"{job_id}_{idx}",
                "title": cand["title"],
                "hook": cand.get("hook", ""),
                "viral_score": cand.get("viral_score", 90),
                "reason": cand.get("reason", ""),
                "start": c_start,
                "end": c_end,
                "duration": round(c_dur, 1),
                "aspect_ratio": aspect_ratio,
                "filename": output_filename,
                "download_url": f"/output/{output_filename}"
            })
            
        # Clean up temporary source video to save disk space
        try:
            if downloaded_path.exists():
                downloaded_path.unlink()
        except Exception:
            pass
            
        update_job(
            job_id, 
            "completed", 
            100, 
            f"Successfully generated {len(generated_clips)} viral 9:16 clips!", 
            clips=generated_clips
        )
        
    except Exception as e:
        raw_err = str(e)
        print(f"Job {job_id} error: {traceback.format_exc()}")
        
        # Humanize and clean error message for mobile display
        if "confirm you're not a bot" in raw_err.lower():
            friendly_err = "YouTube bot check triggered for this video on cloud IP. Trying another link or adding YouTube cookies in Render resolves this."
        elif "private video" in raw_err.lower():
            friendly_err = "This YouTube video is set to private and cannot be clipped."
        elif "members-only" in raw_err.lower():
            friendly_err = "This YouTube video is members-only content."
        elif "could not find suitable clips" in raw_err.lower():
            friendly_err = "Could not find enough speech or highlights in this short video."
        elif "invalid youtube url" in raw_err.lower():
            friendly_err = "Please enter a valid YouTube video or Shorts link."
        elif "http error 403" in raw_err.lower():
            friendly_err = "YouTube stream access temporary 403. Please retry with another video link."
        else:
            friendly_err = raw_err[:160]
            
        update_job(job_id, "failed", 0, "Processing failed", error=friendly_err)

def start_clipping_job(
    url: str,
    num_clips: int = DEFAULT_NUM_CLIPS,
    min_duration: int = DEFAULT_MIN_DURATION,
    max_duration: int = DEFAULT_MAX_DURATION,
    gemini_key: Optional[str] = None,
    aspect_ratio: str = "9:16"
) -> str:
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "job_id": job_id,
        "url": url,
        "aspect_ratio": aspect_ratio,
        "status": "queued",
        "progress": 0,
        "message": "Job queued...",
        "clips": [],
        "created_at": time.time(),
        "error": None
    }
    
    thread = threading.Thread(
        target=process_video_job,
        args=(job_id, url, num_clips, min_duration, max_duration, gemini_key, aspect_ratio),
        daemon=True
    )
    thread.start()
    return job_id

