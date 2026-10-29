import json
import re
import os
from typing import List, Dict, Any, Optional
from pathlib import Path

# Try importing google.genai
try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

VIRAL_HOOK_KEYWORDS = [
    "why", "how to", "secret", "never", "always", "mistake", "truth",
    "stop doing", "rule", "money", "don't", "the biggest", "shocking",
    "the reason", "listen", "watch this", "what if", "remember", "hack",
    "strategy", "crazy", "warning", "lesson", "real reason"
]

def analyze_transcript_heuristic(
    transcript: List[Dict[str, Any]], 
    total_duration: float, 
    num_clips: int = 3,
    min_duration: float = 25.0,
    max_duration: float = 55.0
) -> List[Dict[str, Any]]:
    """
    100% Free heuristic analyzer: Detects high-engagement 30-55s clips
    based on hook words, sentence density, and emotional markers.
    """
    if not transcript or total_duration < min_duration:
        # Fallback if no transcript is available: Generate evenly spaced highlight segments
        clips = []
        if total_duration < min_duration:
            clips.append({
                "start": 0.0,
                "end": round(total_duration, 1),
                "title": "Highlight Moment",
                "hook": "Key takeaway",
                "viral_score": 85,
                "reason": "Complete video highlight"
            })
            return clips
            
        step = max(total_duration / (num_clips + 1), min_duration)
        for i in range(num_clips):
            start = round(step * (i + 0.5), 1)
            end = round(min(start + 45.0, total_duration - 1.0), 1)
            if end - start >= 20.0:
                clips.append({
                    "start": start,
                    "end": end,
                    "title": f"Key Highlight #{i+1}",
                    "hook": "High-interest segment",
                    "viral_score": 80 + (i * 4),
                    "reason": "Balanced peak engagement moment"
                })
        return clips

    # Merge transcript into 35-50 second candidate segments
    candidates = []
    t_len = len(transcript)
    
    for i in range(t_len):
        start_time = transcript[i]["start"]
        current_text = []
        end_time = start_time
        
        for j in range(i, t_len):
            item = transcript[j]
            current_text.append(item["text"])
            end_time = item["start"] + item["duration"]
            duration = end_time - start_time
            
            if duration >= min_duration:
                if duration <= max_duration:
                    full_text = " ".join(current_text)
                    first_sentence = current_text[0].lower()
                    
                    # Calculate viral score
                    score = 65
                    
                    # Hook keyword bonus
                    for kw in VIRAL_HOOK_KEYWORDS:
                        if kw in first_sentence:
                            score += 15
                            break
                            
                    # Question bonus
                    if "?" in full_text:
                        score += 8
                        
                    # Exclamation / energy bonus
                    if "!" in full_text:
                        score += 5
                        
                    # Word pace density bonus (words per second)
                    word_count = len(full_text.split())
                    wps = word_count / max(duration, 1)
                    if 2.2 <= wps <= 3.8:  # Good, energetic talking speed
                        score += 10
                        
                    score = min(score, 98)
                    
                    # Generate title from first 6-8 words
                    words = full_text.split()
                    title = " ".join(words[:7]).title()
                    if not title.endswith("..."):
                        title += "..."
                        
                    candidates.append({
                        "start": round(start_time, 1),
                        "end": round(end_time, 1),
                        "text": full_text,
                        "title": title,
                        "hook": current_text[0][:60],
                        "viral_score": score,
                        "reason": f"Strong hook with {score}% engagement rating"
                    })
                break

    # Sort by viral score descending
    candidates.sort(key=lambda x: x["viral_score"], reverse=True)
    
    # Pick top non-overlapping clips
    selected: List[Dict[str, Any]] = []
    for cand in candidates:
        if len(selected) >= num_clips:
            break
        # Check overlap
        overlaps = False
        for s in selected:
            if not (cand["end"] < s["start"] or cand["start"] > s["end"]):
                overlaps = True
                break
        if not overlaps:
            selected.append(cand)
            
    # Fallback if non-overlapping list is too small
    if not selected and candidates:
        selected = candidates[:num_clips]
        
    return selected

def analyze_transcript_gemini(
    transcript: List[Dict[str, Any]], 
    total_duration: float, 
    api_key: str,
    num_clips: int = 3,
    min_duration: float = 25.0,
    max_duration: float = 55.0
) -> List[Dict[str, Any]]:
    """
    AI-powered viral moment extraction using Google Gemini Flash API.
    """
    if not HAS_GENAI or not api_key:
        return analyze_transcript_heuristic(transcript, total_duration, num_clips, min_duration, max_duration)
        
    try:
        client = genai.Client(api_key=api_key)
        
        # Build compact transcript string with timestamps
        transcript_lines = []
        for item in transcript:
            transcript_lines.append(f"[{item['start']:.1f}s - {item['start']+item['duration']:.1f}s]: {item['text']}")
        transcript_str = "\n".join(transcript_lines)
        
        # Truncate if extremely long
        if len(transcript_str) > 60000:
            transcript_str = transcript_str[:60000] + "\n...(truncated)"
            
        prompt = f"""
You are an expert social media viral clip editor (MrBeast, Alex Hormozi, OpusClip).
Analyze this timestamped video transcript and find the top {num_clips} MOST VIRAL, high-retention segments suitable for YouTube Shorts, TikTok, and Instagram Reels.

Criteria for each clip:
1. Duration MUST be between {min_duration} and {max_duration} seconds.
2. Must begin with a strong psychological hook (question, shocking statement, secret, conflict, or high-value insight).
3. Must complete a full thought or punchline (no awkward mid-sentence cuts).
4. Assign a viral score between 75 and 99.

Transcript:
{transcript_str}

Respond ONLY with valid JSON in this exact structure:
[
  {{
    "start": float_start_seconds,
    "end": float_end_seconds,
    "title": "Punchy Catchy Title",
    "hook": "Opening hook sentence",
    "viral_score": 95,
    "reason": "Why this will hook the viewer in the first 3 seconds"
  }}
]
"""
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.4,
                response_mime_type="application/json"
            )
        )
        
        raw_json = response.text.strip()
        # Clean markdown wrappers if present
        if raw_json.startswith("```json"):
            raw_json = raw_json[7:]
        if raw_json.endswith("```"):
            raw_json = raw_json[:-3]
        
        data = json.loads(raw_json)
        if isinstance(data, list) and len(data) > 0:
            # Validate boundaries
            cleaned = []
            for item in data[:num_clips]:
                start = max(0.0, float(item.get("start", 0)))
                end = min(total_duration, float(item.get("end", start + 35.0)))
                if end - start < 15.0:
                    end = min(total_duration, start + 35.0)
                cleaned.append({
                    "start": round(start, 1),
                    "end": round(end, 1),
                    "title": str(item.get("title", "Viral Clip")),
                    "hook": str(item.get("hook", "")),
                    "viral_score": int(item.get("viral_score", 88)),
                    "reason": str(item.get("reason", "High engagement viral moment"))
                })
            return cleaned
    except Exception as e:
        print(f"Gemini API analysis error: {e}, falling back to heuristic")
        
    return analyze_transcript_heuristic(transcript, total_duration, num_clips, min_duration, max_duration)

def find_viral_clips(
    transcript: List[Dict[str, Any]], 
    total_duration: float, 
    api_key: Optional[str] = None,
    num_clips: int = 3,
    min_duration: float = 25.0,
    max_duration: float = 55.0
) -> List[Dict[str, Any]]:
    """Main entry point: uses Gemini if key exists, otherwise heuristic."""
    if api_key and api_key.strip():
        return analyze_transcript_gemini(transcript, total_duration, api_key.strip(), num_clips, min_duration, max_duration)
    return analyze_transcript_heuristic(transcript, total_duration, num_clips, min_duration, max_duration)

