FROM python:3.11-slim

# Install ffmpeg (required by yt-dlp) and git (required by demucs)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the demucs htdemucs model (~300MB) into the image
# so the first request doesn't need to wait for download
RUN python -c "from demucs.pretrained import get_model; get_model('htdemucs')"

COPY . .

EXPOSE 8000

CMD gunicorn app:app \
    --bind 0.0.0.0:${PORT:-8000} \
    --timeout 300 \
    --workers 1 \
    --threads 4
