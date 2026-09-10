# Sistem Pemantauan Hama Perangkap Feromon (Insect Counting Trap) - Versi 3

Pengembangan sistem IoT pemantauan perangkap hama nirkabel berbasis **ESP32-S3-CAM**, **LoRa Ebyte E220-900T22D**, dan **Raspberry Pi 5 (2GB)** dengan kemampuan penghitungan serangga otomatis (*Automatic AI Insect Counting*) dan **Web Dashboard Interaktif**.

---

## 📁 Struktur Folder & Berkas Proyek

```text
V3_ESP32S3_LoRa_Trap/
├── 1_Panduan_Hardware_dan_Wiring/
│   ├── WIRING_DIAGRAM.md             # Diagram pengkabelan lengkap Transmitter & Receiver
│   └── SKEMA_FLASH_LED_DAN_POWER.md  # Skema rangkaian MOSFET Flash LED, Kipas, & HLK 5V 2A
├── 2_Konfigurasi_LoRa_E220/
│   ├── PANDUAN_KONFIGURASI_E220.md   # Panduan setting aplikasi GUI E220_V1.1 sesuai gambar
│   └── E220_Parameter_Summary.txt    # Ringkasan cepat nilai parameter LoRa E220
├── 3_Transmitter_ESP32S3/
│   └── Transmitter_ESP32S3.ino       # Program ESP32-S3 CAM (Kamera, DHT22, RTC, Flash, LoRa, Sleep)
├── 4_Receiver_ESP32_Standalone/
│   └── Receiver_ESP32_Standalone.ino # Program Receiver ESP32 tanpa Pi (Serial Monitor / OLED)
└── 5_Receiver_RaspberryPi5_Dashboard/
    ├── esp32_bridge/
    │   └── esp32_bridge.ino          # Firmware ESP32 Bridge LoRa ke USB Raspberry Pi 5
    ├── README_RASPBERRY_PI.md        # Panduan instalasi dan deployment di Raspberry Pi 5
    └── pi_service/
        ├── app.py                   # Server Flask Web Dashboard & REST API
        ├── receiver_daemon.py        # Background worker serial LoRa & image rebuilder
        ├── insect_counter.py         # Modul Computer Vision OpenCV penghitung hama (Bounding Box)
        ├── requirements.txt          # Dependensi library Python
        ├── setup_autostart.sh        # Script otomatisasi systemd service saat boot Pi 5
        └── templates/
            └── index.html            # UI Web Dashboard modern responsif (Tailwind & Chart.js)
```

---

## ⚡ 1. Ringkasan Alokasi Pin ESP32-S3 CAM (Transmitter)

Pinout telah dirancang khusus agar bebas dari konflik kamera OV3660 bawaan dan chip internal Octal PSRAM:
- **DHT22 Data**: `GPIO 1` (ADC1_CH0, diberi pull-up 4.7kΩ–10kΩ ke 3.3V)
- **RTC DS3231 I2C**: `GPIO 2 (SDA)` dan `GPIO 3 (SCL)`
- **LoRa Ebyte E220**:
  - `LoRa TXD` -> `GPIO 41 (ESP32-S3 RX)`
  - `LoRa RXD` -> `GPIO 42 (ESP32-S3 TX)`
  - `M0` & `M1` -> `GND` (Mode 0: Normal Transparent)
- **Flash LED (LED Pentol 5mm)**: `GPIO 47` (dihubungkan seri dengan resistor 150Ω–220Ω langsung ke LED pentol putih, tanpa perlu driver MOSFET besar)
- **Kendali Kipas DC 5V (Jadwal RTC 07:00 – 17:00)**: `GPIO 21` (mengendalikan Basis transistor NPN 2N2222 melalui resistor 1kΩ. Kipas menyala otomatis jam 7 pagi s/d 5 sore, dan status pin dipertahankan selama Deep Sleep via `gpio_hold_en`)
- **Catu Daya HLK 5V 2A**: Mengubah 220V AC menjadi 5V DC stabil untuk menyuplai ESP32-S3, LoRa E220, Kipas, dan LED Flash.

---

## 📡 2. Ringkasan Konfigurasi LoRa Ebyte E220-900T22D
Sesuai aplikasi resmi **E220_V1.1**:
- **Baud Rate**: `115200`
- **Air Rate**: `19.2 kbps` (Jangkauan optimal ~1-2 km, waktu kirim foto ~6-8 detik)
- **Packet Size**: `200 bytes` (atau 240 bytes)
- **Tran Mode**: `Transparent mode`
- **Transmit Power**: `22 dBm` (Maksimum 160 mW)
- **Channel**: `65` (Frekuensi 915.125 MHz ISM Indonesia)
- **Packet RSSI**: `Enable`
- **M0 & M1**: Keduanya dihubungkan ke `GND` setelah konfigurasi selesai.

---

## 💡 3. Saran & Evaluasi Teknis Sistem

1. **Lampu Flash LED Pentol Putih 5mm (Hemat & Ringkas):**
   - Menggunakan LED pentol putih bulat biasa (DIP 5mm) yang dipasang seri dengan resistor 150Ω – 220Ω (1/4W) langsung ke pin `GPIO 47` dan `GND`.
   - **Kelebihan:** Sangat praktis, tidak memerlukan modul driver MOSFET berdaya besar 1-3 Watt, dan aman bagi pin ESP32-S3 karena arus kerja hanya ~15 mA.
   - Cahaya putih dingin tetap memberikan kontras tajam pada permukaan lem perekat serangga.

2. **Kipas Pendingin DC 5V (Trigger Waktu RTC 07:00 – 17:00):**
   - Kipas dikontrol otomatis menyala pada siang hari (jam 7 pagi hingga 5 sore) saat suhu terik matahari tinggi, dan mati otomatis pada malam hari untuk memperpanjang usia motor dan efisiensi energi.
   - Dikendalikan oleh `GPIO 21` via transistor NPN kecil (2N2222 / SS8050) dengan resistor basis 1kΩ.
   - Status pin dipertahankan (*pin hold*) selama mikrokontroler berada dalam mode Deep Sleep menggunakan perintah `gpio_hold_en((gpio_num_t)FAN_PIN);` dan `gpio_deep_sleep_hold_en();`.

3. **Perlukah Dibuatkan Dashboard?**
   - **Sangat Perlu!** Karena sistem memotret 1x sehari untuk menghitung serangga (*image counting*), petani/peneliti membutuhkan antarmuka visual terpusat yang:
     - Menampilkan kondisi lingkungan (Suhu & Kelembaban) saat serangga hinggap.
     - Menampilkan foto asli perbandingan dengan foto hasil deteksi AI (*bounding box* serangga teridentifikasi).
     - Menampilkan tren populasi hama (apakah populasi meningkat tajam atau menurun setelah diberi perlakuan).
     - Memberikan indikator status bahaya (**Aman**, **Waspada**, atau **Bahaya**).
   - **Dashboard Web lengkap siap pakai** telah kami buat di folder `5_Receiver_RaspberryPi5_Dashboard/pi_service/` yang dapat dibuka langsung lewat browser laptop atau smartphone di jaringan Wi-Fi lokal.

4. **Fokus Lensa Kamera OV3660:**
   - Jarak kamera ke plat lem perekat feromon di dalam kotak umumnya berkisar antara **15 cm – 25 cm**.
   - Lensa bawaan OV3660 disetel untuk fokus jarak jauh (*infinity*). Putar ulir lensa OV3660 secara manual perlahan ke kiri/kanan sambil melihat hasil foto hingga bercak serangga di lem perekat terlihat tajam dan tidak buram.
