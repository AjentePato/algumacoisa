"""
Music Downloader - Backend Flask + yt-dlp
Requisitos:
    pip install flask yt-dlp
Uso:
    python app.py
Depois acesse: http://localhost:5000
"""

import os
import re
import json
import uuid
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
import yt_dlp

# ==================== CONFIGURAÇÕES ====================
app = Flask(__name__, template_folder=".", static_folder=".")
DOWNLOAD_DIR = Path("downloads").absolute()
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Armazena progresso em memória: {task_id: {...}}
TASKS = {}


# ==================== FUNÇÕES AUXILIARES ====================
def sanitize_filename(name: str) -> str:
    """Remove caracteres inválidos do nome do arquivo."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


def human_size(num_bytes):
    """Converte bytes para formato legível."""
    if not num_bytes:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.2f} TB"


def human_time(seconds):
    """Converte segundos para HH:MM:SS."""
    if not seconds:
        return "00:00"
    seconds = int(seconds)
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


# ==================== HOOKS DE PROGRESSO ====================
def make_progress_hook(task_id):
    """Cria um hook que atualiza o progresso da task."""
    def hook(d):
        task = TASKS.get(task_id)
        if not task:
            return
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            percent = (downloaded / total * 100) if total else 0
            task.update({
                "status": "downloading",
                "percent": round(percent, 2),
                "speed": human_size(d.get("speed")) + "/s" if d.get("speed") else "—",
                "eta": human_time(d.get("eta")),
                "downloaded": human_size(downloaded),
                "total": human_size(total),
                "filename": d.get("filename", "")
            })
        elif d["status"] == "finished":
            task.update({
                "status": "processing",
                "percent": 100,
                "message": "Convertendo / finalizando..."
            })
    return hook


def make_postprocessor_hook(task_id):
    def hook(d):
        task = TASKS.get(task_id)
        if task:
            task["message"] = f"Pós-processando: {d.get('postprocessor', '')}"
    return hook


# ==================== FUNÇÕES DE DOWNLOAD ====================
def extract_info(url: str, download=False):
    """Extrai informações de uma URL sem baixar."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": not download,
        "extract_flat": False,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=download)


def get_playlist_info(url: str):
    """Retorna lista de faixas de uma playlist."""
    opts = {"quiet": True, "extract_flat": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if "entries" in info:
        return [{
            "id": e.get("id"),
            "title": e.get("title"),
            "duration": e.get("duration"),
            "url": e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}",
            "uploader": e.get("uploader") or e.get("channel")
        } for e in info["entries"] if e]
    return [info]


def download_audio(url: str, task_id: str, quality: str = "192"):
    """Baixa áudio e converte para MP3."""
    outtmpl = str(DOWNLOAD_DIR / "%(title)s.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "progress_hooks": [make_progress_hook(task_id)],
        "postprocessor_hooks": [make_postprocessor_hook(task_id)],
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": quality,
        }],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "ignoreerrors": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def download_video(url: str, task_id: str, quality: str = "best"):
    """Baixa vídeo em MP4."""
    format_map = {
        "best": "bestvideo+bestaudio/best",
        "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "720": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480": "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "360": "bestvideo[height<=360]+bestaudio/best[height<=360]",
    }
    outtmpl = str(DOWNLOAD_DIR / "%(title)s.%(ext)s")
    ydl_opts = {
        "format": format_map.get(quality, format_map["best"]),
        "outtmpl": outtmpl,
        "progress_hooks": [make_progress_hook(task_id)],
        "postprocessor_hooks": [make_postprocessor_hook(task_id)],
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def run_download(task_id: str, url: str, mode: str, quality: str):
    """Executa download em thread separada."""
    try:
        TASKS[task_id]["status"] = "starting"
        TASKS[task_id]["message"] = "Iniciando..."
        if mode == "audio":
            download_audio(url, task_id, quality)
        else:
            download_video(url, task_id, quality)
        TASKS[task_id].update({
            "status": "done",
            "percent": 100,
            "message": "Download concluído com sucesso! ✅"
        })
    except Exception as e:
        TASKS[task_id].update({
            "status": "error",
            "message": f"Erro: {str(e)}"
        })


# ==================== ROTAS FLASK ====================
@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/info", methods=["POST"])
def api_info():
    """Retorna metadados de uma URL (vídeo ou playlist)."""
    data = request.get_json()
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL vazia"}), 400
    try:
        info = extract_info(url)
        if "entries" in info:
            tracks = get_playlist_info(url)
            return jsonify({
                "type": "playlist",
                "title": info.get("title", "Playlist"),
                "count": len(tracks),
                "tracks": tracks[:100]  # limita preview
            })
        return jsonify({
            "type": "video",
            "title": info.get("title"),
            "duration": human_time(info.get("duration")),
            "uploader": info.get("uploader"),
            "thumbnail": info.get("thumbnail"),
            "view_count": info.get("view_count"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/download", methods=["POST"])
def api_download():
    """Inicia download em background."""
    data = request.get_json()
    url = data.get("url", "").strip()
    mode = data.get("mode", "audio")      # 'audio' ou 'video'
    quality = data.get("quality", "192")  # ex: '192', '320', '720', 'best'
    if not url:
        return jsonify({"error": "URL vazia"}), 400

    task_id = uuid.uuid4().hex
    TASKS[task_id] = {
        "id": task_id,
        "url": url,
        "mode": mode,
        "quality": quality,
        "status": "queued",
        "percent": 0,
        "message": "Na fila...",
    }
    thread = threading.Thread(
        target=run_download,
        args=(task_id, url, mode, quality),
        daemon=True
    )
    thread.start()
    return jsonify({"task_id": task_id})


@app.route("/api/progress/<task_id>")
def api_progress(task_id):
    """Retorna progresso de uma task."""
    task = TASKS.get(task_id)
    if not task:
        return jsonify({"error": "Task não encontrada"}), 404
    return jsonify(task)


@app.route("/api/files")
def api_files():
    """Lista arquivos baixados."""
    files = []
    for f in sorted(DOWNLOAD_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file():
            files.append({
                "name": f.name,
                "size": human_size(f.stat().st_size),
                "mtime": f.stat().st_mtime,
            })
    return jsonify(files)


@app.route("/api/file/<path:filename>")
def api_file(filename):
    """Baixa arquivo baixado."""
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)


# ==================== MAIN ====================
if __name__ == "__main__":
    print("🎵 Music Downloader rodando em http://localhost:5000")
    print(f"📁 Pasta de downloads: {DOWNLOAD_DIR}")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
