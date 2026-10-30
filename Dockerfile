FROM python:3.11-slim

# Install system dependencies: FFmpeg, Node.js, and MediaPipe/OpenCV libraries + Fonts for subtitles
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    ca-certificates \
    curl \
    libgl1 \
    libglib2.0-0 \
    fonts-dejavu-core \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir -U "yt-dlp[default]" "yt-dlp-ejs"

# Copy application files (excluding local temp/output if any)
COPY backend/ ./backend/
COPY web/ ./web/

# Create output and temp directories
RUN mkdir -p /app/output /app/temp

ENV PYTHONUNBUFFERED=1
ENV PORT=7860

# Expose port (7860 is default for Hugging Face Spaces, 8000 for standard)
EXPOSE 7860

CMD ["python", "backend/app.py"]

