# Buka absensi/face_recognition_utils.py

import cv2
import os
import numpy as np
from PIL import Image
from django.conf import settings
from .models import DataWajah

TRAINER_DIR = os.path.join(settings.MEDIA_ROOT, "trainer")
TRAINER_PATH = os.path.join(TRAINER_DIR, "trainer.yml")
FACE_CASCADE_PATH = os.path.join(
    settings.BASE_DIR, "absensi", "cascades", "haarcascade_frontalface_default.xml"
)

def train_model():
    print("[INFO] Memeriksa kebutuhan training...")
    if not os.path.exists(FACE_CASCADE_PATH):
        print(f"[ERROR] File cascade tidak ditemukan di: {FACE_CASCADE_PATH}")
        return False

    os.makedirs(TRAINER_DIR, exist_ok=True)
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    detector = cv2.CascadeClassifier(FACE_CASCADE_PATH)

    face_samples, ids = [], []
    semua_data_wajah = DataWajah.objects.all()

    if not semua_data_wajah.exists():
        print("[WARNING] Tidak ada data wajah di database untuk di-train.")
        return False

    for data_wajah in semua_data_wajah:
        image_path = data_wajah.data_embedding.path
        if not os.path.exists(image_path):
            print(f"[WARNING] Dilewati: File gambar tidak ada di path {image_path}")
            continue
        try:
            PIL_img = Image.open(image_path).convert("L")
            img_numpy = np.array(PIL_img, "uint8")
            user_id = data_wajah.id_user.id_user
            faces = detector.detectMultiScale(img_numpy)
            for x, y, w, h in faces:
                face_samples.append(img_numpy[y : y + h, x : x + w])
                ids.append(user_id)
        except Exception as e:
            print(f"[ERROR] Gagal memproses {image_path}: {e}")

    if not ids:
        print(
            "[ERROR] Training gagal: Tidak ada wajah yang bisa dideteksi dari gambar dataset."
        )
        return False

    print(f"[INFO] Memulai training dengan {len(face_samples)} sampel wajah...")
    recognizer.train(face_samples, np.array(ids))
    recognizer.write(TRAINER_PATH)
    print(f"[INFO] Training selesai. Model disimpan di {TRAINER_PATH}")
    return True


def recognize_face(image_array):
    if not os.path.exists(TRAINER_PATH):
        print("[ERROR] File trainer.yml tidak ditemukan. Sistem belum siap.")
        return None, None, "Sistem belum siap. Silakan hubungi admin."

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(TRAINER_PATH)
    face_cascade = cv2.CascadeClassifier(FACE_CASCADE_PATH)
    gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)

    faces = face_cascade.detectMultiScale(
        gray, scaleFactor=1.2, minNeighbors=5, minSize=(100, 100)
    )

    if len(faces) == 0:
        return None, None, "Tidak ada wajah terdeteksi di kamera."

    (x, y, w, h) = faces[0]
    id_user, confidence = recognizer.predict(gray[y : y + h, x : x + w])
    return id_user, confidence, None


def is_model_trained():
    """
    Fungsi sederhana untuk memeriksa apakah file model trainer sudah ada.
    """
    return os.path.exists(TRAINER_PATH)