# PANDUAN OPERASIONAL & DEPLOYMENT SISTEM SMART INSECT TRAP (V4.0)

Dokumen ini berisi panduan lengkap pengoperasian, arsitektur sistem terbaru (V4.0 Always ON), konfigurasi *auto-start on boot*, dan akses jarak jauh permanen untuk sistem pemantauan perangkap hama kaper berbasis IoT LoRa dan Edge AI Raspberry Pi 5.

---

## 1. Arsitektur & Spesifikasi Sistem (V4.0)

```
[ESP32-S3-CAM Transmitter (Kebun / Lapangan)]
  ├─ Sumber Daya: Adaptor PLN (HLK 5V) -> Always ON (Tanpa Deep Sleep)
  ├─ LoRa Ebyte E220-900T22D (915 MHz, GPIO 41 RX, GPIO 42 TX)
  ├─ Sensor DHT22 (GPIO 1) -> Kirim data setiap 60 detik
  ├─ RTC DS3231 (I2C: GPIO 2 SDA, GPIO 3 SCL) -> Jam tersinkronisasi otomatis
  ├─ Flash LED (GPIO 47) -> Nyala saat jepret
  └─ Kipas DC 5V (GPIO 21) -> ON pukul 07:00 - 17:00 WIB
       │
       │ (Gelombang Radio LoRa 915 MHz, jarak jangkauan 200-300 meter)
       ▼
[ESP32 Dev Module Receiver Bridge]
  ├─ LoRa Ebyte E220 (GPIO 16 RX2, GPIO 17 TX2, M0 & M1 terhubung ke GND)
  └─ Kabel Micro-USB -> Port USB Raspberry Pi 5 (/dev/ttyUSB0)
       │
       ▼
[Raspberry Pi 5 Server (Ruangan / Pos)]
  ├─ receiver_daemon.py: Background serial listener & image reconstructor
  ├─ kaper_counter_rpi5.py: Model AI YOLO ONNX (Image Counting & Bounding Box)
  ├─ app.py: Flask Web Server (Port 5000)
  ├─ systemd: Auto-start on boot (insect-trap.service & ngrok-tunnel.service)
  └─ Ngrok Static Tunnel: Akses publik permanen seumur hidup
```

---

## 2. Fitur Baru pada Firmware V4.0
1. **Always ON Mode:** ESP32-S3 tidak masuk ke *Deep Sleep* karena ditenagai listrik PLN (HLK 5V).
2. **Instant SNAP (< 3 Detik):** Perintah dari web dashboard dikirim seketika via USB Serial -> LoRa -> ESP32-S3 langsung menyalakan flash dan memotret tanpa menunggu siklus bangun tidur.
3. **Pengiriman Sensor 60 Detik:** Suhu, kelembaban, dan status kipas dikirim setiap 60 detik secara konsisten.
4. **Jadwal Foto Harian Dinamis:** Jam foto harian (default 08:00 WIB) dapat diubah langsung dari web dashboard. Begitu diubah, `lastPhotoDay` langsung di-reset sehingga jadwal baru dapat langsung diuji di hari yang sama.
5. **Sinkronisasi RTC Otomatis:** Raspberry Pi secara berkala mengirimkan downlink `SETTIME` ke RTC DS3231 transmitter agar jam alat selalu akurat 100%.

---

## 3. SOP Pengoperasian Harian

### A. Menyalakan Sistem (Power-On)
1. **Transmitter (Kebun):** Tancapkan colokan adaptor PLN (HLK 5V) ke stopkontak. Lampu indikator akan menyala dan transmitter langsung aktif.
2. **Receiver & Raspberry Pi 5:**
   * Pastikan kabel Micro-USB ESP32 Receiver tertancap ke port USB Raspberry Pi 5.
   * Tancapkan adaptor daya resmi Raspberry Pi 5 ke stopkontak.
   * Tunggu sekitar 30–45 detik agar Raspberry Pi selesai booting.
   * **Selesai!** Dashboard web dan tunnel internet otomatis aktif sendiri tanpa perlu membuka terminal.

### B. Membuka Dashboard Web
Buka browser (Google Chrome / Safari) di HP atau laptop:
* **Link Publik Permanen (Dari Luar / Internet):**
  `https://panning-overtake-sputter.ngrok-free.dev`
* **Link Lokal / Tailscale:**
  `http://100.64.81.29:5000` atau `http://localhost:5000`

### C. Mematikan Sistem Secara Aman (Power-Off)
1. Masuk via SSH ke Raspberry Pi: `ssh insect-trap@100.64.81.29`
2. Jalankan perintah shutdown: `sudo poweroff`
3. Tunggu hingga lampu hijau Raspberry Pi mati total (~10 detik), lalu cabut adaptor daya.

---

## 4. Konfigurasi Auto-Start Service (systemd)

Jika memasang ulang di Raspberry Pi baru, file service berada di folder `pi_service/systemd/`:

1. **Pasang Service Dashboard & LoRa:**
   ```bash
   sudo cp pi_service/systemd/insect-trap.service /etc/systemd/system/
   ```

2. **Pasang Service Ngrok Permanent Tunnel:**
   ```bash
   sudo cp pi_service/systemd/ngrok-tunnel.service /etc/systemd/system/
   ```

3. **Aktifkan Service:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now insect-trap.service
   sudo systemctl enable --now ngrok-tunnel.service
   ```

4. **Perintah Cek Status:**
   ```bash
   sudo systemctl status insect-trap.service
   sudo systemctl status ngrok-tunnel.service
   ```

---

## 5. Kontak & Pengembang
* **Pengembang:** Nova Adrian (Lab ELINS, Universitas Gadjah Mada)
* **Repositori GitHub:** https://github.com/Novadriann/Insect-Trap
