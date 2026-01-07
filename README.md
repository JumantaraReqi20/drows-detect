# Drowsiness Detection System with ESP32-CAM Integration

![Language](https://img.shields.io/badge/language-Python%20%7C%20C%2B%2B-blue)
![Platform](https://img.shields.io/badge/platform-ESP32%20%7C%20Windows%2FLinux-green)
![Library](https://img.shields.io/badge/library-MediaPipe%20%7C%20OpenCV-orange)

Sistem deteksi kantuk pengemudi *real-time* berbasis Computer Vision yang terintegrasi dengan perangkat keras ESP32-CAM. Sistem ini menggunakan analisis wajah (Facial Landmarks) untuk mendeteksi tanda-tanda kelelahan seperti mata tertutup (*Microsleep*) dan menguap, kemudian mengirimkan sinyal peringatan nirkabel untuk menyalakan Flash LED pada unit kamera.

## 🌟 Fitur Utama

* **Real-time Detection:** Menggunakan **MediaPipe Face Mesh** untuk pelacakan landmark wajah presisi tinggi.
* **Scientific Metrics:**
    * **EAR (Eye Aspect Ratio):** Mendeteksi kedipan dan mata tertutup berdasarkan *Soukupová & Čech (2016)*.
    * **MAR (Mouth Aspect Ratio):** Mendeteksi aktivitas menguap (*Yawning*).
* **Wireless Integration:** Terhubung ke ESP32-CAM melalui protokol **RTSP** untuk video stream latensi rendah.
* **Active Feedback:** Mengirim request HTTP asinkron ke ESP32 untuk menyalakan **Flash LED** (Strobe Light) saat bahaya terdeteksi.
* **Smart Alarm:** Logika alarm cerdas yang memperhitungkan "Recovery Time" setelah menguap (berdasarkan *Caffier et al., 2003*).
* **Data Logging:** Menyimpan riwayat deteksi ke file CSV (`drowsiness_log.csv`) untuk analisis lebih lanjut.

## 📂 Struktur Proyek

```text
├── main.py               # Program utama (Python) berjalan di Host PC/Laptop
├── requirements.txt      # Daftar library Python yang dibutuhkan
├── drowsiness_log.csv    # Output log data
└── src/                  # Firmware untuk ESP32-CAM
    ├── main.cpp          # Kode utama ESP32 (RTSP & Web Server)
    ├── main.h            # Header file
    └── ...

```

## 🛠️ Prasyarat Hardware & Software

### Hardware

1. **ESP32-CAM Module** (AI-Thinker Model recommended).
2. **FTDI Programmer** (untuk upload kode ke ESP32).
3. **PC/Laptop** dengan Webcam (opsional) atau koneksi WiFi untuk RTSP.

### Software

* Python 3.8+
* PlatformIO atau Arduino IDE (untuk upload firmware ESP32).

## 🚀 Instalasi & Penggunaan

### 1. Persiapan ESP32-CAM (Firmware)

Firmware ini bertugas sebagai IP Camera (RTSP Server) dan Web Server untuk kontrol LED.

1. Buka folder proyek di **PlatformIO** atau copy isi `src/` ke Arduino IDE.
2. Edit file kredensial WiFi (atau `wifikeys.h` jika ada) untuk memasukkan SSID dan Password.
3. Upload kode ke ESP32-CAM.
4. Buka **Serial Monitor** (Baudrate 115200) dan catat **IP Address** yang muncul (Contoh: `192.168.1.15`).

### 2. Persiapan Python Environment

Jalankan perintah berikut di terminal:

```bash
# Install dependencies
pip install -r requirements.txt

```

### 3. Konfigurasi `main.py`

Buka file `main.py` dan sesuaikan variabel konfigurasi dengan IP Address ESP32 Anda:

```python
# --- KONFIGURASI ESP32 ---
ESP_IP = "192.168.1.15"  # <--- Ganti dengan IP ESP32 Anda

```

### 4. Menjalankan Program

```bash
python main.py

```

Sistem akan melakukan koneksi RTSP ke kamera. Saat pertama kali berjalan, akan ada proses **Kalibrasi Otomatis** selama 5 detik. **Pastikan mata Anda terbuka dan menatap kamera selama proses ini.**

## 📊 Dasar Ilmiah & Parameter

Sistem ini dibangun berdasarkan referensi jurnal ilmiah untuk akurasi deteksi:

* **Eye Aspect Ratio (EAR):** Mengukur rasio jarak vertikal dan horizontal mata. Ambang batas dihitung secara dinamis saat kalibrasi.
* **Microsleep Detection:** Alarm berbunyi jika mata tertutup > **1.0 detik** (toleransi menurun menjadi 50% jika baru saja menguap).
* **Yawning Factor:** Menguap dideteksi jika MAR > **0.50**.

## 🤝 Kontribusi

Pull Request dipersilakan. Untuk perubahan besar, mohon buka issue terlebih dahulu untuk mendiskusikan apa yang ingin Anda ubah.

## 📝 Lisensi

[MIT License](https://www.google.com/search?q=LICENSE)