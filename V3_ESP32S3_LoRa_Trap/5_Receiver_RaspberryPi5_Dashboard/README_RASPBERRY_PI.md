# 🍓 Panduan Lengkap Instalasi & Operasional Receiver Raspberry Pi 5
**Sistem Pemantauan Perangkap Hama Feromon (*Insect Trap Monitoring & AI Counting*)**  
*Lab ELINS - Departemen Ilmu Komputer dan Elektronika, Universitas Gadjah Mada*

Dokumen ini berisi panduan komprehensif penyiapan (*setup*), pengkabelan hardware, konfigurasi akses jarak jauh (*Tailscale*), penjelasan fungsi setiap file program, hingga otomatisasi sistem pada **Raspberry Pi 5 (RAM 2GB/4GB/8GB)**.

---

## 📑 Daftar Isi
1. [Arsitektur Sistem Receiver](#-1-arsitektur-sistem-receiver)
2. [Penjelasan & Fungsi Masing-Masing File Program](#-2-penjelasan--fungsi-masing-masing-file-program)
3. [Pengkabelan Hardware (ESP32 LoRa ke RPi 5)](#-3-pengkabelan-hardware-esp32-lora-ke-rpi-5)
4. [Alur Setup Raspberry Pi 5 dari Nol](#-4-alur-setup-raspberry-pi-5-dari-nol)
5. [Konfigurasi Akses Jarak Jauh via Tailscale](#-5-konfigurasi-akses-jarak-jauh-via-tailscale)
6. [Menjalankan Sistem & Web Dashboard](#-6-menjalankan-sistem--web-dashboard)
7. [Engine Deteksi AI (YOLOv8 ONNX & OpenCV Adaptif)](#-7-engine-deteksi-ai-yolov8-onnx--opencv-adaptif)
8. [Otomatisasi Booting (Systemd Service)](#-8-otomatisasi-booting-systemd-service)
9. [Panduan Troubleshooting & Solusi Error](#-9-panduan-troubleshooting--solusi-error)

---

## 🏗️ 1. Arsitektur Sistem Receiver

```text
[ESP32-S3 CAM Lapangan] (NODE_01 / NODE_02)
        │
        │ Gelombang Radio LoRa 915 MHz (Teks Sensor + Aliran Biner Foto JPEG)
        ▼
[Modul LoRa Ebyte E220-900T22D]
        │ UART (TXD/RXD)
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
║  │    - UI Responsif: Tampilan foto perbandingan, grafik tren, dll    │  ║
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
| **`app.py`** | Server Web Dashboard utama (Flask) | Mengaktifkan server web di port `5000`, menyediakan REST API (`/api/latest`, `/api/nodes`, `/export/csv`), dan **secara otomatis menyalakan thread `receiver_daemon` di latar belakang**. Cukup jalankan file ini untuk mengaktifkan seluruh sistem. |
| **`receiver_daemon.py`** | Service Daemon Penerima Serial LoRa | Menghubungkan Raspberry Pi ke ESP32 via `/dev/ttyUSB0` (115200 baud). Bertugas menangkap teks sensor DHT22 & RTC, merekonstruksi potongan biner JPEG menjadi file gambar utuh di folder `static/captures/`, lalu memanggil engine `kaper_counter_rpi5.py`. |
| **`kaper_counter_rpi5.py`** | Engine Deteksi & Penghitung Hama AI | Mengolah foto perangkap lem kuning untuk menghitung populasi kupu kaper (*Spodoptera exigua*). Memiliki **Dual Backend**: otomatis menggunakan model Deep Learning **YOLOv8 ONNX** jika file `kaper_yolo.onnx` tersedia; jika tidak, otomatis beralih ke **OpenCV Adaptif (CLAHE + LAB b-channel + Watershed)**. |
| **`kaper_config.json`** | Konfigurasi Parameter Deteksi OpenCV | Menyimpan ambang batas deteksi (*threshold offset*, ukuran area kontur minimal/maksimal, rasio aspek, clip limit CLAHE). Nilai ini dapat disesuaikan tanpa perlu mengubah kode Python. |
| **`simulate_feed.py`** | Skrip Pengujian / Injeksi Foto Instan | Digunakan untuk menguji Web Dashboard secara langsung di laboratorium tanpa perlu menyalakan pemancar LoRa di lapangan. Menjalankan deteksi pada foto sampel dan langsung memasukkan hasilnya ke database SQLite. |
| **`requirements.txt`** | Daftar Dependensi Python | Berisi pustaka minimal teroptimasi: `pyserial>=3.5`, `opencv-python-headless>=4.8.0`, `numpy>=1.24.0`, dan `flask>=3.0.0`. |
| **`setup_autostart.sh`** | Skrip Otomatisasi Booting Linux | Mendaftarkan `app.py` ke daemon `systemd` (`insect_trap.service`) agar server web dan penerima LoRa langsung otomatis menyala saat Raspberry Pi dinyalakan (*plug and play*). |
| **`templates/index.html`** | Tampilan Antarmuka Web Dashboard | Desain antarmuka modern gelap (*dark mode*) berbasis Tailwind CSS dan Chart.js. Mendukung seleksi multi-node (`NODE_01`, `NODE_02`), perbandingan foto asli vs anotasi, dan grafik tren waktu. |
| **`trap_monitoring.db`** | Database SQLite Utama | Menyimpan tabel `sensor_logs` (riwayat suhu, kelembaban, waktu) dan `image_logs` (nama file foto asli, foto anotasi, jumlah hama, tingkat bahaya). |
| **`sensor_history.csv`** | Cadangan Log Sensor Format Excel | File teks CSV berisi data log lingkungan yang dapat langsung diunduh dari dashboard untuk analisis data di Microsoft Excel / SPSS. |
| **`kaper_yolo.onnx`** | Model AI YOLOv8-Nano Terlatih | File bobot neural network hasil training di Google Colab dalam format Open Neural Network Exchange (ONNX), dirancang agar sangat ringan dan cepat di CPU ARM Raspberry Pi 5. |

---

## 🔌 3. Pengkabelan Hardware (ESP32 LoRa ke RPi 5)

Modul **ESP32 Dev Module (Receiver)** bertindak sebagai jembatan (*transparent bridge*) yang meneruskan paket radio dari modul LoRa Ebyte E220 ke port USB Raspberry Pi 5.

### Skema Pin LoRa Ebyte E220-900T22D ke ESP32:
| Pin LoRa E220 | Pin ESP32 Dev Module | Fungsi / Catatan |
| :--- | :--- | :--- |
| **VCC** | **Pin 5V (VIN)** | Suplai daya modul LoRa |
| **GND** | **Pin GND** | Ground bersama |
| **TXD** | **GPIO 16 (RX2)** | Jalur terima data serial LoRa ke ESP32 |
| **RXD** | **GPIO 17 (TX2)** | Jalur kirim data ESP32 ke LoRa |
| **M0** | **GND** | **Wajib ke GND** (Mode 0: Normal / Transceiver) |
| **M1** | **GND** | **Wajib ke GND** (Mode 0: Normal / Transceiver) |
| **AUX** | *Tidak perlu disambung (NC)* | Indikator buffer (opsional) |

### Koneksi ESP32 ke Raspberry Pi 5:
- Sambungkan port **USB ESP32** ke salah satu **port USB Raspberry Pi 5** menggunakan kabel data USB Micro / Type-C yang berkualitas baik.
- Kabel ini sekaligus memberi daya listrik ke ESP32 dan LoRa, serta membentuk port serial komunikasi `/dev/ttyUSB0`.

---

## 🛠️ 4. Alur Setup Raspberry Pi 5 dari Nol

### Langkah 4.1: Instalasi OS & Akses Awal
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

### Langkah 4.2: Konfigurasi Izin Serial Port
Agar Python dapat membaca port USB tanpa hambatan izin:
```bash
sudo usermod -a -G dialout $USER
```
Periksa apakah ESP32 terdeteksi:
```bash
ls /dev/ttyUSB*
```
*(Akan muncul `/dev/ttyUSB0`)*.

---

### Langkah 4.3: Transfer Program dari Laptop ke Pi 5
Buka **PowerShell di laptop Anda**, masuk ke folder proyek dan kirim folder `5_Receiver_RaspberryPi5_Dashboard`:
```powershell
scp -r "d:\KULIAH\4. Project Lab ELINS\Pemantauan Hama\Program Insect Trap\V3_ESP32S3_LoRa_Trap\5_Receiver_RaspberryPi5_Dashboard" insect-trap@srikayangan.local:~/
```

---

### Langkah 4.4: Instalasi Dependensi Python di Pi 5
Di terminal Raspberry Pi 5:
```bash
cd ~/5_Receiver_RaspberryPi5_Dashboard/pi_service
pip install -r requirements.txt --break-system-packages
```
> [!NOTE]
> Flag `--break-system-packages` digunakan pada Debian Bookworm/Trixie terbaru agar library OpenCV dan Flask terinstall langsung ke user environment tanpa konflik sistem.

---

## 🌐 5. Konfigurasi Akses Jarak Jauh via Tailscale

Tailscale digunakan agar Web Dashboard dapat diakses dari smartphone/laptop **dari mana saja di seluruh dunia** (bahkan saat RPi berada di kebun dengan modem 4G, dan Anda berada di kampus/rumah).

### Keunggulan Tailscale:
1. **Menembus CGNAT & Firewall:** Tidak memerlukan setting router atau IP publik statis.
2. **IP Statis Permanen:** Raspberry Pi akan memiliki IP tetap (misal: `100.90.201.108`) yang tidak akan berubah meski ganti Wi-Fi.
3. **Enkripsi WireGuard End-to-End:** Aman dari penyadapan di jaringan publik.

### Cara Instalasi di Raspberry Pi 5:
```bash
# 1. Unduh dan pasang Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# 2. Login ke jaringan Tailscale Anda
sudo tailscale up
```
Terminal akan memberikan tautan login browser, contoh:  
`To authenticate, visit: https://login.tailscale.com/a/xxxxxx`  
Buka link tersebut di browser laptop, lalu login dengan akun Google/Microsoft/Apple Anda.

Periksa IP Tailscale Raspberry Pi:
```bash
tailscale ip -4
```
*(Contoh output: `100.90.201.108`)*.

Pasang juga aplikasi **Tailscale** di Laptop dan Smartphone Anda, lalu login dengan akun yang sama. Sekarang seluruh perangkat Anda telah terhubung dalam satu jaringan pribadi virtual.

---

## 🚀 6. Menjalankan Sistem & Web Dashboard

### Cara Menjalankan (Cukup 1 Perintah):
Di terminal Raspberry Pi:
```bash
cd ~/5_Receiver_RaspberryPi5_Dashboard/pi_service
python3 app.py
```

> [!IMPORTANT]
> **Jangan menjalankan `app.py` dan `receiver_daemon.py` secara bersamaan di dua terminal berbeda**, karena `app.py` sudah otomatis menjalankan `receiver_daemon` di thread latar belakang. Jika dijalankan bersamaan, keduanya akan bertabrakan berebut port `/dev/ttyUSB0`.

### Mengakses Web Dashboard:
- Dari Laptop / HP via Tailscale:  
  👉 **`http://<IP_TAILSCALE_PI>:5000`** (misal: `http://100.90.201.108:5000`)
- Dari Laptop di jaringan Wi-Fi lokal yang sama:  
  👉 **`http://srikayangan.local:5000`**
- Dari layar Raspberry Pi sendiri:  
  👉 **`http://localhost:5000`**

---

## 🧠 7. Engine Deteksi AI (YOLOv8 ONNX & OpenCV Adaptif)

Program `kaper_counter_rpi5.py` dirancang sangat fleksibel dengan sistem **failover cerdas**:

1. **Mode YOLOv8 ONNX (Deep Learning):**
   - Jika file `kaper_yolo.onnx` diletakkan di folder `pi_service/`, sistem akan otomatis memuat model neural network menggunakan modul akselerasi bawaan **OpenCV DNN**.
   - Kecepatan inferensi: ~150–250 ms per foto di CPU quad-core Cortex-A76 Raspberry Pi 5 (sangat cepat, tanpa butuh GPU, dan hemat memori <100 MB).
2. **Mode OpenCV Adaptif (Computer Vision Klasik):**
   - Jika file ONNX tidak ada, sistem otomatis menggunakan fusi warna:
     - **Channel b* Ruang Warna LAB:** Membedakan sayap putih/transparan kaper dari lem kuning cerah.
     - **Grayscale CLAHE:** Menonjolkan kepala dan badan hitam kaper.
     - **Watershed Segmentation:** Memotong serangga yang menempel menjadi individu terpisah.

### Uji Coba Cepat Deteksi Mandiri:
```bash
# Uji deteksi langsung ke file gambar sampel:
python3 kaper_counter_rpi5.py --image test_lem_kuning.jpg

# Uji injeksi foto sampel ke Web Dashboard:
python3 simulate_feed.py test_lem_kuning.jpg
```

---

## ⚙️ 8. Otomatisasi Booting (Systemd Service)

Agar sistem penerima dan web dashboard **selalu menyala otomatis** setiap kali adaptor listrik Raspberry Pi 5 dicolokkan tanpa perlu membuka terminal atau laptop:

```bash
cd ~/5_Receiver_RaspberryPi5_Dashboard/pi_service
chmod +x setup_autostart.sh
./setup_autostart.sh
```

### Perintah Manajemen Service:
- Memeriksa status service:  
  `sudo systemctl status insect_trap.service`
- Menghentikan sistem:  
  `sudo systemctl stop insect_trap.service`
- Menjalankan kembali:  
  `sudo systemctl start insect_trap.service`
- Melihat log aktivitas real-time:  
  `sudo journalctl -u insect_trap.service -f`

---

## 🔍 9. Panduan Troubleshooting & Solusi Error

| Gejala / Error | Penyebab | Solusi |
| :--- | :--- | :--- |
| `Koneksi serial terputus: device reports readiness to read but returned no data (multiple access on port?)` | Ada 2 program yang membuka `/dev/ttyUSB0` secara bersamaan (misal `app.py` dan `receiver_daemon.py` berjalan berbarengan). | Jalankan `sudo killall python3`, lalu jalankan **hanya satu program saja**: `python3 app.py`. |
| Port `/dev/ttyUSB0` tidak ditemukan | Kabel USB ESP32 kendor atau belum tertancap rapat. | Cabut dan colokkan kembali kabel data USB ke port USB hitam RPi 5. Cek dengan perintah `ls /dev/ttyUSB*`. |
| Data radio LoRa tidak masuk sama sekali | 1. Pin M0 dan M1 LoRa belum ke GND.<br>2. Pin TXD/RXD terbalik.<br>3. Antena belum terpasang. | 1. Pastikan pin M0 dan M1 modul LoRa E220 dicolok ke **GND** ESP32.<br>2. LoRa TXD ke Pin 16, LoRa RXD ke Pin 17.<br>3. Pasang antena spiral/SMA pada modul LoRa. |
| YOLO mendeteksi `0 ekor` pada foto perangkap | Model ONNX diekspor sebelum proses training di Colab selesai (masih Epoch -1 / model kosong). | Rename model `mv kaper_yolo.onnx kaper_yolo.onnx.bak` agar sistem otomatis menggunakan engine OpenCV Adaptif yang sudah terbukti akurat, atau latih ulang YOLO di Colab hingga 80 epoch selesai. |
| SSH / Web Dashboard terputus saat logout Tailscale | Logout Tailscale mematikan IP `100.x.y.z`. | Selalu gunakan Wi-Fi lokal (`ssh insect-trap@srikayangan.local`) saat ingin mengubah konfigurasi akun Tailscale. |
