# 🍓 Panduan Lengkap Instalasi & Operasional Receiver Raspberry Pi 5
**Sistem Pemantauan Perangkap Hama Feromon (*Insect Trap Monitoring & AI Counting*)**  
*Lab ELINS - Departemen Ilmu Komputer dan Elektronika, Universitas Gadjah Mada*

Dokumen ini berisi panduan komprehensif penyiapan (*setup*), pengkabelan hardware, konfigurasi akses jarak jauh (*Tailscale*), penjelasan fungsi setiap file program, fitur komunikasi 2 arah (*bidirectional LoRa control*), hingga otomatisasi sistem pada **Raspberry Pi 5 (RAM 2GB/4GB/8GB)**.

---

## 📑 Daftar Isi
1. [Arsitektur Sistem Receiver](#-1-arsitektur-sistem-receiver)
2. [Penjelasan & Fungsi Masing-Masing File Program](#-2-penjelasan--fungsi-masing-masing-file-program)
3. [Pengkabelan Hardware (ESP32 LoRa ke RPi 5)](#-3-pengkabelan-hardware-esp32-lora-ke-rpi-5)
4. [Fitur Kontrol Dua Arah (Bidirectional LoRa Control & REST API)](#-4-fitur-kontrol-dua-arah-bidirectional-lora-control--rest-api)
5. [Alur Setup Raspberry Pi 5 dari Nol](#-5-alur-setup-raspberry-pi-5-dari-nol)
6. [Konfigurasi Akses Jarak Jauh via Tailscale](#-6-konfigurasi-akses-jarak-jauh-via-tailscale)
7. [Engine Deteksi AI (YOLOv8 ONNX & OpenCV Adaptif)](#-7-engine-deteksi-ai-yolov8-onnx--opencv-adaptif)
8. [Menjalankan Sistem & Web Dashboard](#-8-menjalankan-sistem--web-dashboard)
9. [Otomatisasi Booting (Systemd Service)](#-9-otomatisasi-booting-systemd-service)
10. [Panduan Troubleshooting & Solusi Error](#-10-panduan-troubleshooting--solusi-error)

---

## 🏗️ 1. Arsitektur Sistem Receiver

```text
[ESP32-S3 CAM Lapangan] (NODE_01 / NODE_02)
        ▲
        │ Uplink: Teks Sensor + Aliran Biner Foto JPEG
        │ Downlink: Perintah Kontrol (SNAP / Set Jadwal) via Receive Window 2 Detik
        ▼
[Modul LoRa Ebyte E220-900T22D Receiver]
        │ UART (TXD/RXD) Dua Arah
        ▼
[ESP32 Dev Module (Receiver Bridge)]
        │ Kabel USB (/dev/ttyUSB0 pada 115200 bps)
        ▼
╔══════════════════════════════════════════════════════════════════════════╗
║                       RASPBERRY PI 5 (2GB RAM)                           ║
║                                                                          ║
║  ┌────────────────────────────────────────────────────────────────────┐  ║
║  │ 1. receiver_daemon.py (Background Serial Worker)                   │  ║
║  │    - Membaca data serial /dev/ttyUSB0                              │  ║
║  │    - Parsing suhu, kelembaban, waktu RTC, status kipas             │  ║
║  │    - Injeksi Downlink Perintah Tertunda (Pending Commands)         │  ║
║  │    - Rekonstruksi biner paket gambar JPEG utuh                     │  ║
║  │    - Menyimpan log ke SQLite (trap_monitoring.db) & CSV            │  ║
║  └─────────────────┬──────────────────────────────────────────────────┘  ║
║                    │ Memicu pemrosesan gambar                            ║
║                    ▼                                                     ║
║  ┌────────────────────────────────────────────────────────────────────┐  ║
║  │ 2. kaper_counter_rpi5.py (AI & Computer Vision Engine)             │  ║
║  │    - Backend 1: YOLOv8 ONNX (Akselerasi CPU OpenCV DNN)            │  ║
║  │    - Backend 2: OpenCV Adaptif (CLAHE + LAB b* + Watershed)        │  ║
║  │    - Klasifikasi Ancaman: Aman (<5) / Waspada (5-15) / Bahaya (>15)│  ║
║  │    - Menggambar Bounding Box hijau & simpan foto beranotasi        │  ║
║  └─────────────────┬──────────────────────────────────────────────────┘  ║
║                    │ Menyimpan hasil kalkulasi                           ║
║                    ▼                                                     ║
║  ┌────────────────────────────────────────────────────────────────────┐  ║
║  │ 3. app.py (Flask Web Dashboard Server - Port 5000)                 │  ║
║  │    - REST API: /api/latest, /api/nodes, /api/history, /export/csv  │  ║
║  │    - REST API Kontrol: /api/command/trigger, /schedule, /status    │  ║
║  │    - UI Responsif: Kontrol 2 Arah, Komparator Foto, Grafik Tren    │  ║
║  └─────────────────┬──────────────────────────────────────────────────┘  ║
╚════════════════════╪══════════════════════════════════════════════════════╝
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
   [Jaringan Lokal Wi-Fi]   [Tailscale Mesh VPN]
   http://192.168.x.x:5000  http://100.x.y.z:5000
         │                       │
         └───────────┬───────────┘
                     ▼
       [Smartphone / Tablet / Laptop Petani]
```

---

## 📂 2. Penjelasan & Fungsi Masing-Masing File Program

Seluruh kode program stasiun penerima berada di dalam folder:  
`V3_ESP32S3_LoRa_Trap/5_Receiver_RaspberryPi5_Dashboard/pi_service/`

| Nama File | Fungsi Utama | Keterangan Teknis |
| :--- | :--- | :--- |
| **`app.py`** | Server Web Dashboard utama (Flask) | Mengaktifkan server web di port `5000`, menyediakan REST API pemantauan & **REST API Kontrol Dua Arah** (`/api/command/trigger`, `/api/command/schedule`, `/api/command/status`), dan **secara otomatis menyalakan thread `receiver_daemon` di latar belakang**. Cukup jalankan file ini untuk mengaktifkan seluruh sistem. |
| **`receiver_daemon.py`** | Service Daemon Penerima Serial & Injektor Downlink | Menghubungkan Raspberry Pi ke ESP32 via `/dev/ttyUSB0` (115200 baud). Bertugas menangkap teks sensor DHT22 & RTC, **menginjeksikan perintah tertunda ke LoRa saat jendela dengar node**, merekonstruksi potongan biner JPEG menjadi file gambar utuh di folder `static/captures/`, lalu memanggil engine `kaper_counter_rpi5.py`. |
| **`kaper_counter_rpi5.py`** | Engine Deteksi & Penghitung Hama AI | Mengolah foto perangkap lem kuning untuk menghitung populasi kupu kaper (*Spodoptera exigua*). Memiliki **Dual Backend**: otomatis menggunakan model Deep Learning **YOLOv8 ONNX** jika file `kaper_yolo.onnx` tersedia; jika tidak, otomatis beralih ke **OpenCV Adaptif (CLAHE + LAB b-channel + Watershed)**. |
| **`kaper_config.json`** | Konfigurasi Parameter Deteksi OpenCV | Menyimpan ambang batas deteksi (*threshold offset*, ukuran area kontur minimal/maksimal, rasio aspek, clip limit CLAHE). Nilai ini dapat disesuaikan tanpa perlu mengubah kode Python. |
| **`simulate_feed.py`** | Skrip Pengujian / Injeksi Foto Instan | Digunakan untuk menguji Web Dashboard secara langsung di laboratorium tanpa perlu menyalakan pemancar LoRa di lapangan. Menjalankan deteksi pada foto sampel dan langsung memasukkan hasilnya ke database SQLite. |
| **`requirements.txt`** | Daftar Dependensi Python | Berisi pustaka minimal teroptimasi: `pyserial>=3.5`, `opencv-python-headless>=4.8.0`, `numpy>=1.24.0`, dan `flask>=3.0.0`. |
| **`setup_autostart.sh`** | Skrip Otomatisasi Booting Linux | Mendaftarkan `app.py` ke daemon `systemd` (`insect_trap.service`) agar server web dan penerima LoRa langsung otomatis menyala saat Raspberry Pi dinyalakan (*plug and play*). |
| **`templates/index.html`** | Tampilan Antarmuka Web Dashboard | Desain antarmuka modern gelap (*dark mode*) berbasis Tailwind CSS dan Chart.js. Dilengkapi kartu **Kontrol Dua Arah & Penjadwalan Jarak Jauh** (tombol jepret manual, form ubah jam jadwal, riwayat perintah, notifikasi toast). |
| **`trap_monitoring.db`** | Database SQLite Utama | Menyimpan 3 tabel utama: `sensor_logs` (riwayat suhu & RH), `image_logs` (nama file foto, jumlah serangga, ancaman), dan **`pending_commands`** (antrean perintah kontrol downlink). |
| **`sensor_history.csv`** | Cadangan Log Sensor Format Excel | File teks CSV berisi data log lingkungan yang dapat langsung diunduh dari dashboard untuk analisis data di Microsoft Excel / SPSS. |
| **`kaper_yolo.onnx`** | Model AI YOLOv8-Nano Terlatih | File bobot neural network hasil training di Google Colab dalam format Open Neural Network Exchange (ONNX), dirancang agar sangat ringan dan cepat di CPU ARM Raspberry Pi 5. |

---

## 🔌 3. Pengkabelan Hardware (ESP32 LoRa ke RPi 5)

Modul **ESP32 Dev Module (Receiver)** bertindak sebagai jembatan (*transparent bridge*) dua arah yang meneruskan paket data dari modul LoRa Ebyte E220 ke port USB Raspberry Pi 5 dan sebaliknya.

### Skema Pin LoRa Ebyte E220-900T22D ke ESP32:
| Pin LoRa E220 | Pin ESP32 Dev Module | Fungsi / Catatan |
| :--- | :--- | :--- |
| **VCC** | **Pin 5V (VIN)** | Suplai daya modul LoRa |
| **GND** | **Pin GND** | Ground bersama |
| **TXD** | **GPIO 16 (RX2)** | Jalur terima data serial LoRa ke ESP32 |
| **RXD** | **GPIO 17 (TX2)** | Jalur kirim data ESP32 ke LoRa (Downlink) |
| **M0** | **GND** | **Wajib ke GND** (Mode 0: Transceiver Transparan) |
| **M1** | **GND** | **Wajib ke GND** (Mode 0: Transceiver Transparan) |
| **AUX** | *Tidak perlu disambung (NC)* | Indikator buffer (opsional) |

### Koneksi ESP32 ke Raspberry Pi 5:
- Sambungkan port **USB ESP32** ke salah satu **port USB Raspberry Pi 5** menggunakan kabel data USB yang berkualitas baik.
- Kabel ini sekaligus memberi daya listrik ke ESP32 dan LoRa, serta membentuk port serial komunikasi `/dev/ttyUSB0`.

---

## 🎮 4. Fitur Kontrol Dua Arah (Bidirectional LoRa Control & REST API)

Fitur ini memungkinkan pengguna / dosen untuk:
1. **Trigger Jepret Manual (*On-Demand Snapshot*)**: Menginstruksikan node kamera lapangan untuk memotret saat itu juga dari dashboard.
2. **Pengubahan Jadwal Foto Dinamis**: Mengubah jam dan menit pengambilan foto harian (misal disetel jam 18:00) yang disimpan secara permanen di NVS ESP32-S3.

### Alur Protokol "Receive Window"
1. Node lapangan bangun dari *Deep Sleep* -> mengirim data sensor `[DATA]`.
2. Node membuka **Receive Window selama 2 detik**.
3. Raspberry Pi (`receiver_daemon.py`) menerima data sensor -> memeriksa tabel antrean `pending_commands`.
4. Jika ada perintah tertunda, `receiver_daemon` menulis string perintah ke serial `/dev/ttyUSB0` -> modul LoRa memancarkan perintah ke node.
5. Node mengeksekusi perintah (memotret atau menyimpan jadwal ke NVS) -> mengirim balasan `ACK`.

### Sintaks Perintah Downlink
- **Jepret Manual**: `CMD,NODE_01,SNAP\n`
- **Ubah Jadwal**: `CMD,NODE_01,SCHEDULE,18,00\n`

### REST API Kontrol di `app.py`:
- `POST /api/command/trigger` (JSON: `{"node_id": "NODE_01"}`)
- `POST /api/command/schedule` (JSON: `{"node_id": "NODE_01", "hour": 18, "minute": 0}`)
- `GET /api/command/status?node=NODE_01`

---

## 🛠️ 5. Alur Setup Raspberry Pi 5 dari Nol

### Langkah 5.1: Instalasi OS & Akses Awal
1. Gunakan aplikasi **Raspberry Pi Imager** di laptop untuk menulis OS ke MicroSD.
2. Pilih OS: **Raspberry Pi OS (64-bit)** (Debian Bookworm atau versi terbaru).
3. Klik tombol pengaturan (*gear*) di Imager untuk mengisi:
   - Hostname: `srikayangan`
   - Username: `insect-trap`
   - Password: `[password-anda]`
   - Konfigurasi Wi-Fi / Hotspot lokal.
4. Masukkan MicroSD ke Raspberry Pi 5, hubungkan adaptor daya Type-C (5V 3A atau 5V 5A).
5. Dari laptop di Wi-Fi yang sama, login SSH:
   ```powershell
   ssh insect-trap@srikayangan.local
   ```

---

### Langkah 5.2: Konfigurasi Izin Serial Port
Agar Python dapat membaca dan menulis ke port USB tanpa hambatan izin:
```bash
sudo usermod -a -G dialout $USER
```
Periksa apakah ESP32 terdeteksi:
```bash
ls /dev/ttyUSB*
```
*(Akan muncul `/dev/ttyUSB0`)*.

---

### Langkah 5.3: Transfer Program dari Laptop ke Pi 5
Buka **PowerShell di laptop Anda**, masuk ke folder proyek dan kirim folder `5_Receiver_RaspberryPi5_Dashboard`:
```powershell
scp -r "d:\KULIAH\4. Project Lab ELINS\Pemantauan Hama\Program Insect Trap\V3_ESP32S3_LoRa_Trap\5_Receiver_RaspberryPi5_Dashboard" insect-trap@srikayangan.local:~/
```

---

### Langkah 5.4: Instalasi Dependensi Python di Pi 5
Di terminal Raspberry Pi 5:
```bash
cd ~/5_Receiver_RaspberryPi5_Dashboard/pi_service
pip install -r requirements.txt --break-system-packages
```

---

## 🌐 6. Konfigurasi Akses Jarak Jauh via Tailscale

Tailscale digunakan agar Web Dashboard dapat diakses dari smartphone/laptop **dari mana saja di seluruh dunia**:

```bash
# 1. Unduh dan pasang Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# 2. Login dan aktifkan
sudo tailscale up

# 3. Catat IP Tailscale
tailscale ip -4
```
Akses dashboard dari browser smartphone/laptop di mana saja:  
👉 **`http://<IP_TAILSCALE>:5000`** *(misal: `http://100.90.201.108:5000`)*

---

## 🧠 7. Engine Deteksi AI (YOLOv8 ONNX & OpenCV Adaptif)

Engine `kaper_counter_rpi5.py` secara otomatis menggunakan arsitektur terbaik:
- **Prioritas 1 (Deep Learning)**: Memuat `kaper_yolo.onnx` via OpenCV DNN CPU Accelerator.
- **Prioritas 2 (Computer Vision Adaptif)**: LAB b* channel + CLAHE + Watershed jika file ONNX tidak tersedia.

---

## 🚀 8. Menjalankan Sistem & Web Dashboard

Cukup jalankan satu perintah:
```bash
cd ~/5_Receiver_RaspberryPi5_Dashboard/pi_service
python3 app.py
```

> [!CAUTION]
> Jangan menjalankan `receiver_daemon.py` dan `app.py` secara bersamaan di terminal berbeda karena akan menyebabkan konflik port USB `/dev/ttyUSB0`. Cukup jalankan `app.py`.

---

## ⚙️ 9. Otomatisasi Booting (Systemd Service)

Agar sistem menyala otomatis saat Raspberry Pi dihidupkan:
```bash
cd ~/5_Receiver_RaspberryPi5_Dashboard/pi_service
chmod +x setup_autostart.sh
./setup_autostart.sh
```

---

## 🔍 10. Panduan Troubleshooting & Solusi Error

1. **`device reports readiness to read but returned no data`**:
   - Terjadi karena ada 2 proses Python yang membuka port serial bersamaan.
   - Solusi: `sudo killall python3`, lalu jalankan `python3 app.py`.
2. **Data LoRa tidak masuk**:
   - Pastikan pin M0 dan M1 modul LoRa terhubung kuat ke GND.
   - Tekan tombol reset (EN) di ESP32-S3 Transmitter lapangan.
3. **Perintah manual belum dieksekusi**:
   - Node di kebun sedang berada di mode *Deep Sleep*. Perintah akan otomatis terkirim segera saat node bangun dan membuka Receive Window 2 detiknya.
