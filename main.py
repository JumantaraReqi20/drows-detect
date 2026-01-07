"""
Driver Drowsiness Detection (MediaPipe) - Modified with ESP32 Flash Control
"""

import cv2
import mediapipe as mp
import numpy as np
import time
import threading
import csv
import requests
from collections import deque
from smoothing import ExponentialMovingAverage

# ============================
# CONFIG (Scientific Basis)
# ============================

# --- TAMBAHAN: KONFIGURASI ESP32 ---
# Ganti IP ini sesuai dengan IP yang muncul di Serial Monitor Arduino
ESP_IP = "10.49.130.55" 
URL_FLASH_ON = f"http://{ESP_IP}/flash_on"
URL_FLASH_OFF = f"http://{ESP_IP}/flash_off"

# URL RTSP (Sesuai kode ESP32 sebelumnya)
RTSP_URL = f"rtsp://{ESP_IP}:8554/mjpeg/1"

CALIBRATION_SECONDS = 5.0

# [Ref: Caffier et al., 2003]
# Kedipan normal manusia ~0.1-0.4 detik. Microsleep dimulai > 0.5 detik.
# Kita set 1.0 detik sebagai batas toleransi maksimal sebelum alarm berbunyi.
EYE_CLOSED_SECONDS = 1.0

# [Ref: Safety Logic]
# Durasi waspada setelah menguap (Recovery time).
YAWN_RELIEF_SECONDS = 4.0

# [Ref: Caffier et al., 2003 - Microsleep Onset]
# Jika baru menguap, toleransi waktu dipotong menjadi 50%.
YAWN_FACTOR = 0.50

# [Ref: Signal Processing]
EMA_ALPHA_EAR = 0.30
EMA_ALPHA_MAR = 0.30

# [Ref: Soukupová & Čech, 2016]
EAR_MIN_CLAMP = 0.18
EAR_THRESHOLD_FACTOR = 0.75

# [Ref: Omidyeganeh et al., 2016]
MAR_THRESHOLD_STATIC = 0.50

PROGRESS_BAR_WIDTH = 220
LOG_CSV = "drowsiness_log.csv"

# ============================
# Landmarks (MediaPipe)
# ============================

LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [263, 387, 385, 362, 380, 373]

MOUTH_TOP = 13
MOUTH_BOTTOM = 14
MOUTH_LEFT = 78
MOUTH_RIGHT = 308

# ============================
# Helper Functions
# ============================

def euclid(a, b):
    return np.linalg.norm(np.array(a) - np.array(b))

def eye_aspect_ratio(landmarks, idx, w, h):
    # MediaPipe normalized coordinates -> pixel coordinates
    pts = [(int(landmarks[i][0] * w), int(landmarks[i][1] * h)) for i in idx]

    A = euclid(pts[1], pts[5])
    B = euclid(pts[2], pts[4])
    C = euclid(pts[0], pts[3])

    if C == 0:
        return 0.0
    return (A + B) / (2.0 * C)

def mouth_aspect_ratio(landmarks, w, h):
    t = (int(landmarks[MOUTH_TOP][0] * w),     int(landmarks[MOUTH_TOP][1] * h))
    b = (int(landmarks[MOUTH_BOTTOM][0] * w),  int(landmarks[MOUTH_BOTTOM][1] * h))
    l = (int(landmarks[MOUTH_LEFT][0] * w),   int(landmarks[MOUTH_LEFT][1] * h))
    r = (int(landmarks[MOUTH_RIGHT][0] * w),   int(landmarks[MOUTH_RIGHT][1] * h))

    vertical = euclid(t, b)
    horizontal = euclid(l, r)
    return vertical / horizontal if horizontal != 0 else 0

# def ema(prev, val, alpha):
#     return val if prev is None else alpha * val + (1 - alpha) * prev

# --- TAMBAHAN: FUNGSI FLASH ASYNC ---
def send_flash_request(url):
    try:
        # Timeout kecil (0.5s) agar tidak blocking jika ESP mati
        requests.get(url, timeout=0.5) 
    except Exception as e:
        print(f"ESP32 Connection Error: {e}")

def toggle_flash(turn_on):
    """Menjalankan request HTTP di thread terpisah agar video tidak patah-patah"""
    url = URL_FLASH_ON if turn_on else URL_FLASH_OFF
    threading.Thread(target=send_flash_request, args=(url,), daemon=True).start()

# ============================
# Alarm Thread (winsound)
# ============================

class AlarmThread(threading.Thread):
    """Alarm yang stabil menggunakan winsound.Beep()."""

    def __init__(self):
        super().__init__(daemon=True)
        self._on = False

    def start_alarm(self):
        self._on = True
        if not self.is_alive():
            self.start()

    def stop_alarm(self):
        self._on = False

    def run(self):
        while True:
            if self._on:
                try:
                    import winsound
                    winsound.Beep(1100, 500)
                except:
                    print("\a")  # fallback non-windows
                time.sleep(0.1)
            else:
                time.sleep(0.1)

# ============================
# Setup
# ============================

mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    static_image_mode=False,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# --- MODIFIKASI: Menggunakan RTSP ---
print(f"Connecting to RTSP Camera at: {RTSP_URL}...")
cap = cv2.VideoCapture(RTSP_URL)
# cap = cv2.VideoCapture(0) # Gunakan ini jika testing pakai Webcam Laptop

time.sleep(0.3)

clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))

alarm = AlarmThread()

csv_file = open(LOG_CSV, "w", newline="", encoding="utf-8")
writer = csv.DictWriter(csv_file, fieldnames=["timestamp","frame","EAR","MAR","state"])
writer.writeheader()

baseline_ear = None
ear_threshold = None

ear_smoother = ExponentialMovingAverage(alpha=EMA_ALPHA_EAR)
mar_smoother = ExponentialMovingAverage(alpha=EMA_ALPHA_MAR)
ema_ear = None
ema_mar = None

closed_start_time = None
last_yawn_time = None
flash_is_active = False # --- TAMBAHAN: Status Flash agar tidak spam request

start_time = time.time()
fps_deque = deque(maxlen=30)
frame_idx = 0

print("=== Drowsiness Detection Started ===")

# ============================
# Main Loop
# ============================

try:
    while True:
        start_f = time.time()

        ret, frame = cap.read()
        if not ret:
            print("Gagal membaca frame RTSP (Koneksi putus?)")
            break

        h, w = frame.shape[:2]

        # Low light enhancement
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = clahe.apply(gray)
        gray = cv2.GaussianBlur(gray, (3,3), 0)
        rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)

        results = face_mesh.process(rgb)

        ear_val, mar_val = None, None
        state = "normal"

        if results.multi_face_landmarks:
            mesh = results.multi_face_landmarks[0]
            landmarks = [(lm.x, lm.y) for lm in mesh.landmark]

            # Hitung EAR & MAR
            try:
                left = eye_aspect_ratio(landmarks, LEFT_EYE, w, h)
                right = eye_aspect_ratio(landmarks, RIGHT_EYE, w, h)
                ear_val = (left + right) / 2.0
                mar_val = mouth_aspect_ratio(landmarks, w, h)
            except:
                pass

            # ================================
            # Gambar titik hijau mata & mulut
            # ================================
            for idx in LEFT_EYE + RIGHT_EYE + [MOUTH_TOP, MOUTH_BOTTOM, MOUTH_LEFT, MOUTH_RIGHT]:
                cx = int(landmarks[idx][0] * w)
                cy = int(landmarks[idx][1] * h)
                cv2.circle(frame, (cx, cy), 1, (0,255,0), -1)

            # ============================
            # Auto-calibration EAR
            # ============================
            now = time.time()
            elapsed = now - start_time

            if elapsed <= CALIBRATION_SECONDS and ear_val:
                cv2.putText(frame, "Calibrating... keep eyes OPEN",
                            (40, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,255), 1)
                calib = ear_val
                if baseline_ear is None:
                    baseline_list = []
                baseline_list.append(calib)

            elif baseline_ear is None:
                baseline_ear = float(np.median(baseline_list))
                ear_threshold = max(EAR_MIN_CLAMP, baseline_ear * EAR_THRESHOLD_FACTOR)
                print(f"Calibration done. EAR baseline={baseline_ear:.3f}, thr={ear_threshold:.3f}")

            # ============================
            # EMA smoothing
            # ============================
            if ear_val is not None:
                # ema_ear = ema(ema_ear, ear_val, EMA_ALPHA_EAR)
                ema_ear = ear_smoother.update(ear_val)
            if mar_val is not None:
                # ema_mar = ema(ema_mar, mar_val, EMA_ALPHA_MAR)
                ema_mar = mar_smoother.update(mar_val)

            # ============================
            # Yawning detection
            # ============================
            yawn_active = False
            if ema_mar and ema_mar > MAR_THRESHOLD_STATIC:
                last_yawn_time = time.time()
                yawn_active = True
                state = "yawning"
                cv2.putText(frame, "YAWN", (10,150), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255,0,0), 2)

            # ============================
            # Eye closure timer (REAL seconds)
            # ============================
            if ema_ear is not None:
                current_thr = ear_threshold or 0.20

                # durasi default
                drowsiness_duration = EYE_CLOSED_SECONDS

                # jika baru menguap, buat lebih sensitif
                if last_yawn_time and (time.time() - last_yawn_time < YAWN_RELIEF_SECONDS):
                    drowsiness_duration = EYE_CLOSED_SECONDS * YAWN_FACTOR

                if ema_ear < current_thr:

                    if closed_start_time is None:
                        closed_start_time = time.time()

                    duration = time.time() - closed_start_time
                    frac = min(1.0, duration / drowsiness_duration)

                    bar_x, bar_y = 10, h - 30
                    cv2.rectangle(frame, (bar_x, bar_y),
                                  (bar_x + PROGRESS_BAR_WIDTH, bar_y+20), (60,60,60), -1)
                    cv2.rectangle(frame, (bar_x, bar_y),
                                  (bar_x + int(PROGRESS_BAR_WIDTH * frac), bar_y+20),
                                  (0,0,255), -1)

                    cv2.putText(frame, f"Eyes closed: {duration:.2f}s",
                                (bar_x, bar_y-8), cv2.FONT_HERSHEY_SIMPLEX,
                                0.5, (0,0,255), 1)

                    state = "eyes_closed"

                    # --- LOGIKA ALARM & FLASH ON ---
                    if duration >= drowsiness_duration:
                        alarm.start_alarm()
                        state = "ALARM"
                        
                        # TAMBAHAN: Nyalakan Flash jika belum nyala
                        if not flash_is_active:
                            toggle_flash(True)
                            flash_is_active = True

                else:
                    # Mata Terbuka (Normal)
                    closed_start_time = None
                    alarm.stop_alarm()
                    
                    # TAMBAHAN: Matikan Flash jika masih nyala
                    if flash_is_active:
                        toggle_flash(False)
                        flash_is_active = False

            # ============================
            # Display EAR & MAR
            # ============================
            if ema_ear:
                cv2.putText(frame, f"EAR: {ema_ear:.2f}", (10,20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,255), 1)
            if ema_mar:
                cv2.putText(frame, f"MAR: {ema_mar:.2f}", (10,40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,255), 1)
            if ear_threshold:
                cv2.putText(frame, f"Threshold: {ear_threshold:.2f}", (10,60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200,200,200), 1)

        else:
            state = "no_face"
            closed_start_time = None
            alarm.stop_alarm()

            # Reset agar bersih saat wajah terdeteksi lagi
            ear_smoother.reset()
            mar_smoother.reset()
            ema_ear = None
            ema_mar = None
            
            # TAMBAHAN: Matikan Flash jika wajah hilang
            if flash_is_active:
                toggle_flash(False)
                flash_is_active = False
                
            cv2.putText(frame, "No face detected", (40, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)

        # ============================
        # Logging
        # ============================
        writer.writerow({
            "timestamp": time.time(),
            "frame": frame_idx,
            "EAR": ema_ear if ema_ear else "",
            "MAR": ema_mar if ema_mar else "",
            "state": state
        })

        # ============================
        # FPS Display
        # ============================
        try:
            fps = 1.0 / (time.time() - start_f)
        except:
            fps =  1.0
        fps_deque.append(fps)
        cv2.putText(frame, f"FPS: {np.mean(fps_deque):.1f}",
                    (w - 75, 20), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (0,255,0), 1)

        cv2.imshow("Drowsiness Detection", frame)
        frame_idx += 1

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    # Matikan flash saat keluar program
    toggle_flash(False)
    
    csv_file.close()
    cap.release()
    face_mesh.close()
    cv2.destroyAllWindows()
    print("Saved log:", LOG_CSV)