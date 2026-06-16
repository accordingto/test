import os
import uuid
import threading
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import yt_dlp
import demucs.separate

app = Flask(__name__, static_folder=".")
CORS(app)

DOWNLOAD_DIR = "/tmp/yt_vocal_remover"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

jobs = {}


def process_job(job_id, youtube_url):
    job_dir = os.path.join(DOWNLOAD_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    audio_path = os.path.join(job_dir, "audio.mp3")

    try:
        jobs[job_id]["status"] = "downloading"
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(job_dir, "audio.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "quiet": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            jobs[job_id]["title"] = info.get("title", "Unknown")

        jobs[job_id]["status"] = "separating"
        demucs.separate.main([
            "--mp3",
            "--two-stems", "vocals",
            "-o", job_dir,
            audio_path,
        ])

        # demucs outputs to job_dir/htdemucs/audio/no_vocals.mp3
        no_vocals = os.path.join(job_dir, "htdemucs", "audio", "no_vocals.mp3")
        if not os.path.exists(no_vocals):
            raise FileNotFoundError("Separation output not found")

        jobs[job_id]["status"] = "done"
        jobs[job_id]["result"] = no_vocals

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/submit", methods=["POST"])
def submit():
    data = request.get_json()
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "Missing URL"}), 400

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued", "title": None, "result": None, "error": None}
    t = threading.Thread(target=process_job, args=(job_id, url), daemon=True)
    t.start()
    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "status": job["status"],
        "title": job["title"],
        "error": job["error"],
    })


@app.route("/api/download/<job_id>")
def download(job_id):
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        return jsonify({"error": "Not ready"}), 404
    title = (job.get("title") or "music").replace("/", "_")
    return send_file(
        job["result"],
        as_attachment=True,
        download_name=f"{title}_no_vocals.mp3",
        mimetype="audio/mpeg",
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
