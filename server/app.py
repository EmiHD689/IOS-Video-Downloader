import json
import os
import re
import subprocess

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["https://emihd689.github.io"])


def safe_filename(title: str) -> str:
    name = re.sub(r"[^A-Za-z0-9 _-]", "", title or "video").strip()
    return (name or "video")[:80] + ".mp4"


@app.get("/")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/info")
def info():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "Kein Link angegeben"}), 400

    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-playlist", url],
            capture_output=True,
            text=True,
            timeout=45,
            check=True,
        )
        meta = json.loads(result.stdout.splitlines()[0])
        return jsonify({"title": meta.get("title", "video")})
    except subprocess.CalledProcessError:
        return jsonify({"error": "Link konnte nicht gelesen werden"}), 422
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Zeitüberschreitung beim Laden der Video-Infos"}), 504


@app.get("/api/download")
def download():
    url = (request.args.get("url") or "").strip()
    if not url:
        return jsonify({"error": "Kein Link angegeben"}), 400

    title_proc = subprocess.run(
        ["yt-dlp", "--get-title", "--no-playlist", url],
        capture_output=True,
        text=True,
        timeout=45,
    )
    filename = safe_filename(title_proc.stdout.strip())

    proc = subprocess.Popen(
        ["yt-dlp", "-f", "best", "--no-playlist", "-o", "-", url],
        stdout=subprocess.PIPE,
    )

    def generate():
        try:
            while True:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            proc.stdout.close()
            proc.wait()

    return Response(
        stream_with_context(generate()),
        mimetype="video/mp4",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
