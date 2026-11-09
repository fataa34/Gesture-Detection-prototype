import base64
import math
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = Path(os.environ.get("MODEL_PATH", BASE_DIR / "gesture_recognizer.task"))
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", BASE_DIR / "hasil_capture"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_IMAGE_BYTES + 1024 * 1024

NAMA_MODEL_INDONESIA = {
    "Thumb_Up": "Jempol ke atas",
    "Thumb_Down": "Jempol ke bawah",
    "Victory": "Peace",
    "Open_Palm": "Telapak terbuka",
    "Closed_Fist": "Kepalan tangan",
    "Pointing_Up": "Telunjuk ke atas",
    "ILoveYou": "I love you",
}

POLA_CUSTOM = {
    (1, 0, 0, 0, 1): "Telepon",
    (0, 1, 0, 0, 1): "Rock",
    (0, 1, 1, 1, 0): "Tiga",
    (0, 1, 1, 1, 1): "Empat",
    # Tambahkan pola custom di sini.
    # (0, 0, 0, 0, 1): "Kelingking",
}

recognizer = None
recognizer_lock = threading.Lock()


def create_recognizer():
    global recognizer
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"Model tidak ditemukan: {MODEL_PATH}. "
            "Letakkan gesture_recognizer.task di folder proyek."
        )

    BaseOptions = mp.tasks.BaseOptions
    GestureRecognizer = mp.tasks.vision.GestureRecognizer
    GestureRecognizerOptions = mp.tasks.vision.GestureRecognizerOptions
    RunningMode = mp.tasks.vision.RunningMode

    options = GestureRecognizerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=RunningMode.IMAGE,
    )
    recognizer = GestureRecognizer.create_from_options(options)


def jari_terbuka(titik):
    hasil_jari = []

    # Perkiraan sederhana posisi jempol berdasarkan jarak landmark.
    jarak_ujung = math.dist(
        (titik[4].x, titik[4].y), (titik[17].x, titik[17].y)
    )
    jarak_sendi = math.dist(
        (titik[3].x, titik[3].y), (titik[17].x, titik[17].y)
    )
    hasil_jari.append(1 if jarak_ujung > jarak_sendi else 0)

    ujung_jari = [8, 12, 16, 20]
    sendi_jari = [6, 10, 14, 18]
    for ujung, sendi in zip(ujung_jari, sendi_jari):
        hasil_jari.append(1 if titik[ujung].y < titik[sendi].y else 0)

    return hasil_jari


def decode_image(data_url):
    if not isinstance(data_url, str) or "," not in data_url:
        raise ValueError("Data gambar tidak valid.")
    header, encoded = data_url.split(",", 1)
    if not header.startswith("data:image/"):
        raise ValueError("Format harus berupa gambar.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("Data gambar tidak dapat dibaca.") from exc
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("Ukuran gambar kosong atau melebihi 5 MB.")
    array = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Gambar tidak dapat diproses.")
    return frame


def recognize_frame(frame):
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    with recognizer_lock:
        result = recognizer.recognize(image)

    response = {
        "name": "Tidak dikenali",
        "recognized": False,
        "source": None,
        "pattern": None,
        "color": "#dc3545",
        "score": None,
    }

    if not result.hand_landmarks:
        return response

    # Prioritaskan isyarat bawaan model.
    model_name = "None"
    score = None
    if result.gestures and result.gestures[0]:
        category = result.gestures[0][0]
        model_name = category.category_name
        score = float(category.score)

    if model_name in NAMA_MODEL_INDONESIA:
        response.update({
            "name": NAMA_MODEL_INDONESIA[model_name],
            "recognized": True,
            "source": "model",
            "color": "#198754",
            "score": score,
        })
        return response

    # Jika model tidak menghasilkan label yang didukung, cek pola custom.
    fingers = jari_terbuka(result.hand_landmarks[0])
    pattern = tuple(fingers)
    if pattern in POLA_CUSTOM:
        response.update({
            "name": POLA_CUSTOM[pattern],
            "recognized": True,
            "source": "custom",
            "pattern": list(pattern),
            "color": "#fd7e14",
        })
    return response


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "model_ready": recognizer is not None,
    })


@app.post("/api/detect")
def detect():
    if recognizer is None:
        return jsonify({"error": "Model belum siap. Periksa file model."}), 503
    payload = request.get_json(silent=True) or {}
    try:
        frame = decode_image(payload.get("image", ""))
        result = recognize_frame(frame)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        app.logger.exception("Kesalahan saat mendeteksi gambar")
        return jsonify({"error": "Terjadi kesalahan saat proses deteksi."}), 500


@app.post("/api/save")
def save_photo():
    payload = request.get_json(silent=True) or {}
    label = str(payload.get("label", "")).strip()
    source = str(payload.get("source", "")).strip()

    if payload.get("recognized") is not True or not label:
        return jsonify({"error": "Foto hanya dapat disimpan jika isyarat dikenali."}), 400
    if source not in {"model", "custom"}:
        return jsonify({"error": "Sumber isyarat tidak valid."}), 400

    try:
        frame = decode_image(payload.get("image", ""))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    safe_label = secure_filename(label.replace(" ", "_")) or "isyarat"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{safe_label}_{timestamp}.jpg"
    destination = UPLOAD_DIR / filename

    if not cv2.imwrite(str(destination), frame, [cv2.IMWRITE_JPEG_QUALITY, 92]):
        return jsonify({"error": "Gagal menyimpan foto."}), 500

    return jsonify({
        "ok": True,
        "filename": filename,
        "url": f"/photos/{filename}",
        "message": f"Foto {label} berhasil disimpan.",
    })


@app.get("/api/gallery")
def gallery():
    photos = []
    for path in sorted(UPLOAD_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS:
            photos.append({
                "filename": path.name,
                "url": f"/photos/{path.name}",
                "created": datetime.fromtimestamp(path.stat().st_mtime).strftime("%d-%m-%Y %H:%M:%S"),
            })
    return jsonify(photos[:100])


@app.get("/photos/<path:filename>")
def photo(filename):
    # Hanya melayani file gambar dari folder hasil_capture.
    return send_from_directory(UPLOAD_DIR, filename)


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "Ukuran permintaan terlalu besar."}), 413


if __name__ == "__main__":
    try:
        create_recognizer()
    except Exception as exc:
        raise SystemExit(f"Gagal menyiapkan model: {exc}")

    # Untuk pengembangan lokal saja. Produksi memakai Gunicorn (Procfile).
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False)
