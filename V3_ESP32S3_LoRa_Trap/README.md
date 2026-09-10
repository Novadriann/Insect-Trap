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
- **DHT22 Data**: `GPIO 1` (ADC1_CH0)
- **RTC DS3231 I2C**: `GPIO 2 (SDA)` dan `GPIO 3 (SCL)`
- **LoRa Ebyte E220**:
  - `LoRa TXD` -> `GPIO 41 (ESP32-S3 RX)`
  - `LoRa RXD` -> `GPIO 42 (ESP32-S3 TX)`
  - `M0` & `M1` -> `GND` (Mode 0: Normal Transparent)
- **Flash LED Trigger**: `GPIO 47` (ke Gate Driver MOSFET)
- **Kipas Mini DC 5V**: Terhubung langsung ke output `+5V & GND HLK` (Menyala terus-menerus 24/7 untuk sirkulasi suhu)
- **Catu Daya HLK 5V 2A**: Mengubah 220V AC menjadi 5V DC stabil untuk menyuplai ESP32-S3, LoRa E220, Kipas, dan Flash LED.

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

1. **Rekomendasi Lampu Flash LED Putih:**
   - **Jenis yang Disarankan:** **1W atau 3W High-Power LED Bead Cool White (6000K–6500K)** beralas *Star PCB Aluminium*, atau **Modul COB LED 5V Sudut Lebar (120°)**.
   - **Alasan Teknis:** Suhu warna 6000K–6500K menghasilkan kontras warna paling tinggi antara papan perangkap feromon (kuning/putih) dan serangga hama.
   - **Rangkaian Driver:** Jangan sambungkan LED langsung ke pin ESP32-S3! Gunakan **N-Channel MOSFET (AOD4184 / IRLZ44N)** yang dikontrol via GPIO 47. Rangkaian lengkap tersedia di [SKEMA_FLASH_LED_DAN_POWER.md](file:///d:/KULIAH/4.%20Project%20Lab%20ELINS/Pemantauan%20Hama/Program%20Insect%20Trap/V3_ESP32S3_LoRa_Trap/1_Panduan_Hardware_dan_Wiring/SKEMA_FLASH_LED_DAN_POWER.md).

2. **Kipas Pendingin DC 5V (Continuous Cooling):**
   - Sangat tepat dinyalakan terus-menerus karena kotak perangkap di kebun terkena radiasi panas matahari yang dapat menaikkan suhu internal kotak hingga >50°C.
   - Pasang kipas pada posisi **Exhaust (menyedot udara panas ke luar)** di bagian atas kotak, dan buat lubang ventilasi masuk ber-kisi (*louvers*) miring ke bawah di bagian bawah kotak agar air hujan tidak tampias masuk.
   - Berikan kapasitor elektrolit **100µF/16V** di pin daya kipas untuk meredam kebisingan induktif motor.

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
