import cv2
import mediapipe as mp
import numpy as np
import time
import threading
import requests  # Untuk komunikasi ke ESP32
import winsound  # Untuk bunyi beep di Windows

# ==========================================
# 1. KONFIGURASI SISTEM (Setting di sini)
# ==========================================

# --- Konfigurasi Jaringan ESP32 ---
ESP_IP = "10.49.130.55"  # <--- GANTI dengan IP ESP32 Anda
RTSP_URL = f"rtsp://{ESP_IP}:8554/mjpeg/1"
URL_FLASH_ON = f"http://{ESP_IP}/flash_on"
URL_FLASH_OFF = f"http://{ESP_IP}/flash_off"

# --- Konfigurasi Deteksi Kantuk ---
EAR_THRESHOLD = 0.2       # Batas mata dianggap tertutup (Rata-rata 0.2 - 0.25)
MAR_THRESHOLD = 0.50        # Batas mulut dianggap menguap
TIME_THRESHOLD = 1       # Detik. Jika mata tutup > 1.5 detik -> ALARM
EMA_ALPHA = 0.3             # Smoothing factor (biar angka tidak loncat-loncat)

# ==========================================
# 2. DEFINISI LANDMARK MEDIAPIPE
# ==========================================
# Index titik koordinat untuk Mata Kiri, Kanan, dan Mulut
LEFT_EYE_IDX = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [362, 385, 387, 263, 380, 373]
MOUTH_IDX = [13, 14, 78, 308] # Atas, Bawah, Kiri, Kanan

# ==========================================
# 3. FUNGSI-FUNGSI BANTUAN (HELPER)
# ==========================================

def calculate_ear(landmarks, indices, w, h):
    """Menghitung Eye Aspect Ratio (EAR)"""
    # Ambil koordinat pixel dari landmark
    coords = []
    for i in indices:
        lm = landmarks[i]
        coords.append((int(lm.x * w), int(lm.y * h)))

    # Hitung jarak vertikal dan horizontal
    # Vertical 1: titik ke-1 vs ke-5
    v1 = np.linalg.norm(np.array(coords[1]) - np.array(coords[5]))
    # Vertical 2: titik ke-2 vs ke-4
    v2 = np.linalg.norm(np.array(coords[2]) - np.array(coords[4]))
    # Horizontal: titik ke-0 vs ke-3
    h_dist = np.linalg.norm(np.array(coords[0]) - np.array(coords[3]))

    if h_dist == 0: return 0.0
    ear = (v1 + v2) / (2.0 * h_dist)
    return ear

def calculate_mar(landmarks, indices, w, h):
    """Menghitung Mouth Aspect Ratio (MAR)"""
    coords = []
    for i in indices:
        lm = landmarks[i]
        coords.append((int(lm.x * w), int(lm.y * h)))

    # Vertical: Atas (0) vs Bawah (1)
    v_dist = np.linalg.norm(np.array(coords[0]) - np.array(coords[1]))
    # Horizontal: Kiri (2) vs Kanan (3)
    h_dist = np.linalg.norm(np.array(coords[2]) - np.array(coords[3]))

    if h_dist == 0: return 0.0
    return v_dist / h_dist

def send_flash_command(is_on):
    """
    Mengirim perintah HTTP ke ESP32.
    Dijalankan di Thread terpisah agar video tidak lag.
    """
    url = URL_FLASH_ON if is_on else URL_FLASH_OFF
    try:
        # Timeout kecil agar program tidak hang jika ESP mati
        requests.get(url, timeout=0.5)
        # print(f"Sent to ESP32: {'ON' if is_on else 'OFF'}")
    except Exception as e:
        print(f"Gagal koneksi ke ESP32: {e}")

def play_alarm():
    """Membunyikan beep standar Windows"""
    try:
        winsound.Beep(2000, 500) # Frekuensi 2000Hz, Durasi 500ms
    except:
        pass

# ==========================================
# 4. PROGRAM UTAMA (MAIN LOOP)
# ==========================================

def main():
    # Setup MediaPipe
    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )

    # Setup Kamera (Gunakan RTSP_URL jika siap, atau 0 untuk webcam laptop)
    print(f"Mencoba menghubungkan ke: {RTSP_URL}")
    cap = cv2.VideoCapture(RTSP_URL) 
    # cap = cv2.VideoCapture(0) # <-- Uncomment ini untuk test pake webcam laptop

    # Variabel Status
    start_close_time = None  # Waktu mulai mata tertutup
    flash_state = False      # Status flash saat ini (biar gak kirim request terus2an)
    ema_ear = 0.3            # Nilai awal smoothing
    
    print("Sistem Deteksi Kantuk Berjalan... Tekan 'Q' untuk keluar.")

    while True:
        # 1. Baca Frame
        ret, frame = cap.read()
        if not ret:
            print("Gagal mengambil frame (Koneksi RTSP putus/Selesai).")
            break

        h, w = frame.shape[:2]
        
        # 2. Preprocessing (Opsional: Perbaiki kontras)
        # Convert BGR (OpenCV) ke RGB (MediaPipe)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 3. Deteksi Wajah
        results = face_mesh.process(rgb_frame)
        
        current_status = "AMAN"
        color_status = (0, 255, 0) # Hijau

        if results.multi_face_landmarks:
            mesh = results.multi_face_landmarks[0].landmark
            
            # 4. Hitung EAR & MAR
            left_ear = calculate_ear(mesh, LEFT_EYE_IDX, w, h)
            right_ear = calculate_ear(mesh, RIGHT_EYE_IDX, w, h)
            avg_ear = (left_ear + right_ear) / 2.0
            
            mar = calculate_mar(mesh, MOUTH_IDX, w, h)

            # Smoothing nilai EAR (Exponential Moving Average)
            ema_ear = (EMA_ALPHA * avg_ear) + ((1 - EMA_ALPHA) * ema_ear)

            # Tampilkan Nilai di Layar
            cv2.putText(frame, f"EAR: {ema_ear:.2f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            cv2.putText(frame, f"MAR: {mar:.2f}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

            # ========================================
            # 5. LOGIKA DETEKSI (Time Based)
            # ========================================
            
            is_drowsy = False

            # Cek Mata Tertutup
            if ema_ear < EAR_THRESHOLD:
                # Jika baru pertama kali terdeteksi tutup, catat waktunya
                if start_close_time is None:
                    start_close_time = time.time()
                
                # Hitung durasi tertutup
                duration = time.time() - start_close_time
                
                # Visualisasi Bar Durasi
                bar_width = int(min(duration / TIME_THRESHOLD, 1.0) * 200)
                cv2.rectangle(frame, (10, 70), (10 + bar_width, 90), (0, 0, 255), -1)
                cv2.putText(frame, f"{duration:.1f}s", (220, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                # Jika Durasi melebihi batas -> BAHAYA
                if duration > TIME_THRESHOLD:
                    is_drowsy = True
                    current_status = "MENGANTUK!"
                    color_status = (0, 0, 255) # Merah

            else:
                # Mata terbuka, reset waktu
                start_close_time = None

            # Cek Menguap (Tambahan sederhana)
            if mar > MAR_THRESHOLD:
                cv2.putText(frame, "MENGUAP", (w-150, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)

            # ========================================
            # 6. AKSI (ALARM & FLASH)
            # ========================================

            if is_drowsy:
                # A. Bunyikan Alarm (Async sederana)
                #    Kita pakai winsound langsung di sini (blocking sebentar gpp, 
                #    atau pakai thread kalau mau sangat mulus)
                threading.Thread(target=play_alarm, daemon=True).start()

                # B. Nyalakan Flash (Hanya kirim jika status sebelumnya Mati)
                if not flash_state:
                    threading.Thread(target=send_flash_command, args=(True,), daemon=True).start()
                    flash_state = True
            else:
                # Matikan Flash (Hanya kirim jika status sebelumnya Nyala)
                if flash_state:
                    threading.Thread(target=send_flash_command, args=(False,), daemon=True).start()
                    flash_state = False

        else:
            cv2.putText(frame, "WAJAH TIDAK TERDETEKSI", (10, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            # Reset timer jika wajah hilang
            start_close_time = None
            if flash_state:
                threading.Thread(target=send_flash_command, args=(False,), daemon=True).start()
                flash_state = False

        # Tampilkan Status Utama
        cv2.putText(frame, current_status, (w//2 - 50, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color_status, 3)

        # 7. Tampilkan Window
        cv2.imshow("Sistem Deteksi Kantuk - IoT", frame)

        # Tombol Keluar (ESC atau Q)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break

    # Cleanup
    # Pastikan flash mati saat keluar program
    send_flash_command(False)
    cap.release()
    cv2.destroyAllWindows()
    print("Program Selesai.")

if __name__ == "__main__":
    main()