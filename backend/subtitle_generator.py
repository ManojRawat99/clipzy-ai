import os
from pathlib import Path
from typing import List, Dict, Any
from config import ASPECT_RATIOS

def format_ass_time(seconds: float) -> str:
    """Format seconds into ASS time format: H:MM:SS.cs"""
    seconds = max(0.0, seconds)
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    return f"{hrs}:{mins:02d}:{secs:02d}.{centis:02d}"

def generate_ass_subtitles(
    transcript: List[Dict[str, Any]], 
    clip_start: float, 
    clip_end: float, 
    output_ass_path: Path,
    aspect_ratio: str = "9:16"
) -> Path:
    """
    Generates high-retention viral style animated .ass subtitles
    scaled dynamically for any aspect ratio (9:16, 1:1, 4:5, 16:9).
    """
    ar_info = ASPECT_RATIOS.get(aspect_ratio, ASPECT_RATIOS["9:16"])
    play_res_x = ar_info["width"]
    play_res_y = ar_info["height"]
    
    # Calculate margin and font size dynamically for target resolution
    if aspect_ratio == "9:16":
        font_size = 38
        margin_v = 240  # Keeps captions in TikTok/Reels safe center
    elif aspect_ratio == "1:1":
        font_size = 32
        margin_v = 80
    elif aspect_ratio == "4:5":
        font_size = 34
        margin_v = 120
    else:  # 16:9
        font_size = 32
        margin_v = 60
        
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res_x}
PlayResY: {play_res_y}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ViralDefault,DejaVu Sans,Arial,sans-serif,{font_size},&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,0,2,40,40,{margin_v},1
Style: ViralHighlight,DejaVu Sans,Arial,sans-serif,{font_size+2},&H0000FFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,105,105,0,0,1,4,0,2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    
    # Filter items that fall within [clip_start, clip_end]
    relevant = []
    for item in transcript:
        item_start = item["start"]
        item_end = item_start + item["duration"]
        if item_end > clip_start and item_start < clip_end:
            rel_start = max(0.0, item_start - clip_start)
            rel_end = min(clip_end - clip_start, item_end - clip_start)
            relevant.append({
                "text": item["text"].strip(),
                "start": rel_start,
                "end": rel_end
            })

    # Chunk into fast, punchy 3-5 word groups
    for item in relevant:
        words = item["text"].split()
        if not words:
            continue
            
        duration = max(0.4, item["end"] - item["start"])
        word_duration = duration / len(words)
        
        chunk_size = 4
        for i in range(0, len(words), chunk_size):
            chunk_words = words[i:i + chunk_size]
            c_start = item["start"] + (i * word_duration)
            c_end = min(item["end"], c_start + (len(chunk_words) * word_duration))
            
            upper_words = [w.upper() for w in chunk_words]
            if len(upper_words) > 1:
                # First word highlighted in yellow, remaining in white
                formatted_text = f"{{\\c&H0000FFFF&}}{upper_words[0]}{{\\c&H00FFFFFF&}} " + " ".join(upper_words[1:])
            else:
                formatted_text = f"{{\\c&H0000FFFF&}}{upper_words[0]}"
                
            start_str = format_ass_time(c_start)
            end_str = format_ass_time(c_end)
            events.append(f"Dialogue: 0,{start_str},{end_str},ViralDefault,,0,0,0,,{formatted_text}")

    content = header + "\n".join(events) + "\n"
    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    return output_ass_path
