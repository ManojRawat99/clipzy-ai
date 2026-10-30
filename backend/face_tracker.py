import cv2
import mediapipe as mp
import numpy as np
from pathlib import Path
from typing import Tuple
from config import ASPECT_RATIOS

def compute_crop_coordinates(
    video_path: Path, 
    start_time: float, 
    duration: float, 
    aspect_ratio: str = "9:16"
) -> Tuple[int, int, int, int, int, int]:
    """
    Analyzes video segment using MediaPipe Face Detection to determine
    the best crop box that keeps the speaker centered for the chosen aspect ratio.
    Returns: (x, y, crop_w, crop_h, target_w, target_h)
    """
    ar_info = ASPECT_RATIOS.get(aspect_ratio, ASPECT_RATIOS["9:16"])
    target_w = ar_info["width"]
    target_h = ar_info["height"]
    target_ratio = ar_info["ratio"]
    
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return (0, 0, 1920, 1080, target_w, target_h)
        
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    
    if width <= 0 or height <= 0:
        cap.release()
        return (0, 0, 1920, 1080, target_w, target_h)
        
    orig_ratio = width / float(height)
    
    # 1. Calculate Crop Dimensions
    if aspect_ratio == "16:9" or abs(orig_ratio - target_ratio) < 0.05:
        # No horizontal cropping needed
        cap.release()
        return (0, 0, width, height, target_w, target_h)
        
    if target_ratio < orig_ratio:
        # Target is narrower (e.g., 9:16, 1:1, or 4:5 from 16:9)
        crop_h = height
        crop_w = int(height * target_ratio)
        if crop_w % 2 != 0:
            crop_w -= 1
        crop_y = 0
        needs_horizontal_tracking = True
    else:
        # Target is wider
        crop_w = width
        crop_h = int(width / target_ratio)
        if crop_h % 2 != 0:
            crop_h -= 1
        crop_y = max(0, (height - crop_h) // 2)
        crop_x = 0
        needs_horizontal_tracking = False

    default_x = max(0, (width - crop_w) // 2)
    
    if not needs_horizontal_tracking:
        cap.release()
        return (crop_x, crop_y, crop_w, crop_h, target_w, target_h)
        
    # 2. Fast face tracking with 5 downscaled sample frames
    detected_centers = []
    
    try:
        mp_face_detection = mp.solutions.face_detection
        # model_selection=0 is fast, light short-range model (perfect for selfies/talking heads)
        with mp_face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.5) as face_detector:
            sample_timestamps = [start_time + (i * max(1.0, duration / 6.0)) for i in range(1, 6)]
            for ts in sample_timestamps:
                cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000.0)
                ret, frame = cap.read()
                if not ret or frame is None:
                    continue
                    
                # Downscale to 320px width for blazing fast 15ms detection
                h_f, w_f = frame.shape[:2]
                scale = 320.0 / w_f
                small = cv2.resize(frame, (320, max(1, int(h_f * scale))), interpolation=cv2.INTER_NEAREST)
                rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                
                results = face_detector.process(rgb_small)
                if results and results.detections:
                    best_face = None
                    max_area = 0
                    for detection in results.detections:
                        bbox = detection.location_data.relative_bounding_box
                        area = bbox.width * bbox.height
                        if area > max_area:
                            max_area = area
                            best_face = bbox
                    if best_face:
                        face_cx = int((best_face.xmin + best_face.width / 2.0) * width)
                        detected_centers.append(face_cx)
    except Exception as e:
        print(f"Face tracking error: {e}")
    finally:
        cap.release()
        
    if detected_centers:
        median_cx = int(np.median(detected_centers))
        x = median_cx - (crop_w // 2)
        x = max(0, min(x, width - crop_w))
    else:
        x = default_x
        
    if x % 2 != 0:
        x = max(0, x - 1)
        
    return (int(x), int(crop_y), int(crop_w), int(crop_h), int(target_w), int(target_h))

def compute_916_crop_coordinates(video_path: Path, start_time: float, duration: float) -> Tuple[int, int, int, int]:
    """Backward compatibility wrapper for 9:16."""
    x, y, w, h, _, _ = compute_crop_coordinates(video_path, start_time, duration, "9:16")
    return (x, y, w, h)
