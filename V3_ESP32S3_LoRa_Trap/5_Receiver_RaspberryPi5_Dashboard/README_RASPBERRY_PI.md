# Panduan Instalasi & Pengoperasian Receiver di Raspberry Pi 5

Panduan ini memandu Anda menghubungkan ESP32 Bridge LoRa ke Raspberry Pi 5 (2GB), menjalankan algoritma penghitung serangga (*Insect Counting*), dan mengaktifkan Web Dashboard interaktif.

---

## 🔌 1. Langkah Koneksi Fisik (Hardware)

1. Pastikan program `esp32_bridge.ino` sudah di-upload ke modul **ESP32 Dev Module (Receiver)** menggunakan Arduino IDE.
2. Pasang modul LoRa Ebyte E220 ke ESP32:
   - `LoRa TXD` -> `GPIO 16 (RX2)`
   - `LoRa RXD` -> `GPIO 17 (TX2)`
   - `M0` & `M1` -> `GND`
   - `VCC` -> `5V` (atau 3.3V)
   - `GND` -> `GND`
3. Hubungkan ESP32 ke salah satu port **USB Raspberry Pi 5** menggunakan kabel data USB.
4. Nyalakan Raspberry Pi 5 menggunakan adaptor resmi Type-C 5V 5A (atau 5V 3A).

---

## 💻 2. Pengujian Port Serial di Raspberry Pi 5

Buka Terminal di Raspberry Pi 5 (atau via SSH), lalu ketikkan perintah berikut untuk melihat nama port ESP32:
```bash
ls /dev/ttyUSB* /dev/ttyACM*
```
Biasanya port akan terdeteksi sebagai `/dev/ttyUSB0` atau `/dev/ttyACM0`.

Pastikan user memiliki izin membaca port serial:
```bash
sudo usermod -a -G dialout $USER
```
*(Jika baru pertama kali menambahkan grup dialout, lakukan `sudo reboot` atau logout-login kembali).*

---

## 🚀 3. Instalasi Dependensi Python

Masuk ke folder proyek service di Raspberry Pi 5:
```bash
cd "/home/pi/Program Insect Trap/V3_ESP32S3_LoRa_Trap/5_Receiver_RaspberryPi5_Dashboard/pi_service"
```
*(Sesuaikan path folder dengan lokasi Anda di Raspberry Pi).*

Buat Virtual Environment dan install dependensi:
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 🌐 4. Menjalankan Dashboard & Receiver

Cukup jalankan satu perintah:
```bash
python3 app.py
```
Program akan otomatis:
1. Membuka koneksi serial ke ESP32 LoRa Bridge di background thread.
2. Membaca data suhu, kelembaban, dan waktu RTC yang masuk.
3. Menyimpan data ke database SQLite `trap_monitoring.db` dan `sensor_history.csv`.
4. Menerima gambar transmisi LoRa, menyusun potongan data biner JPEG, dan memverifikasi integritas file.
5. Menjalankan modul `insect_counter.py` untuk mendeteksi dan menghitung serangga di lem feromon secara instan.
6. Menyajikan **Web Dashboard** di port 5000.

### Cara Mengakses Dashboard:
- Dari Raspberry Pi 5 sendiri: Buka browser Chromium, lalu kunjungi: `http://localhost:5000`
- Dari Laptop / Smartphone dalam jaringan Wi-Fi yang sama: Kunjungi: `http://<IP_RASPBERRY_PI>:5000` (contoh: `http://192.168.1.15:5000`).

---

## ⚙️ 5. Menjadikan Layanan Berjalan Otomatis Saat Boot (Autostart)

Agar sistem selalu otomatis berjalan tanpa perlu membuka terminal setiap kali Raspberry Pi 5 dinyalakan, gunakan script autostart yang telah kami sediakan:
```bash
chmod +x setup_autostart.sh
./setup_autostart.sh
```

### Perintah Berguna Terkait Service:
- Memeriksa status: `sudo systemctl status insect_trap.service`
- Menghentikan sementara: `sudo systemctl stop insect_trap.service`
- Memulai kembali: `sudo systemctl restart insect_trap.service`
- Melihat log real-time: `sudo journalctl -u insect_trap.service -f`
