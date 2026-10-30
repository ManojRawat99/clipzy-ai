import os
import shutil
from pathlib import Path
import imageio_ffmpeg

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"
STATIC_DIR = BASE_DIR / "web"
SETTINGS_FILE = BASE_DIR / "settings.json"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Locate FFmpeg binary
def get_ffmpeg_binary() -> str:
    # 1. System PATH (Linux/Docker / System installed)
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    # 2. Local backend ffmpeg.exe (Windows local development)
    local_ffmpeg = BASE_DIR / "backend" / "ffmpeg.exe"
    if local_ffmpeg.exists():
        return str(local_ffmpeg)

    # 3. Bundled via imageio_ffmpeg
    try:
        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and os.path.exists(bundled):
            return bundled
    except Exception:
        pass
    return "ffmpeg"

FFMPEG_PATH = get_ffmpeg_binary()

# Add backend directory to PATH so yt-dlp and other tools find ffmpeg.exe automatically
backend_dir = str(BASE_DIR / "backend")
if backend_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = backend_dir + os.pathsep + os.environ.get("PATH", "")


# Default parameters
DEFAULT_NUM_CLIPS = 3
DEFAULT_MIN_DURATION = 25  # seconds
DEFAULT_MAX_DURATION = 60  # seconds

# Supported Aspect Ratios (Optimized 720p Mobile HD for blazing fast cloud rendering)
ASPECT_RATIOS = {
    "9:16": {"width": 720, "height": 1280, "ratio": 9.0 / 16.0, "name": "Shorts / Reels (9:16)"},
    "1:1": {"width": 720, "height": 720, "ratio": 1.0, "name": "Square (1:1)"},
    "4:5": {"width": 720, "height": 900, "ratio": 4.0 / 5.0, "name": "Portrait Feed (4:5)"},
    "16:9": {"width": 1280, "height": 720, "ratio": 16.0 / 9.0, "name": "Landscape (16:9)"}
}

DEFAULT_ASPECT_RATIO = "9:16"
TARGET_WIDTH = 720
TARGET_HEIGHT = 1280


