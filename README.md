# Sistem Pemantauan Hama Jarak Jauh (Insect Trap Monitoring IoT)
**Berbasis ESP32-S3 CAM, LoRa Ebyte E220-900T22D, DHT22, RTC DS3231, & Image Builder**

Proyek ini adalah sistem IoT nirkabel untuk memantau populasi serangga hama di dalam perangkap lem perekat ber-feromon di lahan perkebunan. Sistem mengambil gambar kondisi perangkap secara berkala/harian serta membaca suhu dan kelembaban lingkungan, lalu mentransmisikannya secara nirkabel sejauh beberapa kilometer menggunakan gelombang radio LoRa 915 MHz ke stasiun penerima (Laptop/PC) untuk disimpan ke file log Excel (`.csv`) dan file gambar foto asli (`.jpg`).

---

## 🛠️ 1. Spesifikasi Hardware

### A. Transmitter Node (Perangkat Lapangan / Kebun):
1. **Mikrokontroler:** **ESP32-S3-CAM** (Kamera OV3660, Dual Type-C, Octal PSRAM)
2. **Modul Komunikasi:** **LoRa Ebyte E220-900T22D** (Transceiver 900 MHz UART 22 dBm)
3. **Sensor Lingkungan:** **DHT22 (AM2302)** (Suhu & Kelembaban Presisi)
4. **Real Time Clock:** **RTC DS3231** (Waktu nyata presisi tinggi I2C dengan baterai CR2032)
5. **Pendingin:** **Kipas Mini DC 5V** + **Transistor NPN (2N2222 / SS8050)** (Aktif otomatis pukul 07:00 – 17:00)
6. **Pencahayaan Flash:** **Lampu LED Pentol Putih 5mm (DIP)** + **Resistor 150Ω – 220Ω**
7. **Catu Daya:** **Modul AC-to-DC Hi-Link HLK 5V 2A** (Input PLN 220V AC -> Output 5V DC 2A)

### B. Receiver Node (Stasiun Penerima / Laptop):
1. **Mikrokontroler:** **ESP32 Dev Module V1** (30 Pin / 38 Pin)
2. **Modul Komunikasi:** **LoRa Ebyte E220-900T22D**
3. **Catu Daya & Komunikasi:** Kabel Data USB langsung ke Port Laptop/PC

---

## 🔌 2. Diagram Wiring (Pengkabelan Lengkap)

### A. Transmitter (ESP32-S3-CAM Node Kebun)

| Komponen | Pin Komponen | Terhubung ke Pin ESP32-S3 / Daya | Keterangan & Catatan |
| :--- | :--- | :--- | :--- |
| **Sumber Listrik**| AC Live (L) & Neutral (N)| **Pin AC L & N Modul HLK 5V 2A** | Disarankan pasang sekring 1A pada kabel L |
| **HLK 5V 2A** | Output +5V | **Pin 5V** ESP32-S3-CAM | Jalur daya utama 5V sistem |
| **HLK 5V 2A** | Output GND | **Pin GND** ESP32-S3-CAM | Ground bersama (*Common GND*) |
| **LoRa Ebyte E220**| VCC | **+5V HLK** (atau 5V ESP32) | Arus transmisi puncak ~120 mA |
| | GND | **GND** | Ground |
| | **TXD** | **GPIO 41** | LoRa TXD -> ESP32-S3 RX (UART1) |
| | **RXD** | **GPIO 42** | LoRa RXD -> ESP32-S3 TX (UART1) |
| | **M0** | **GND** | **Wajib ke GND** (Mode 0: Transceiver Normal) |
| | **M1** | **GND** | **Wajib ke GND** (Mode 0: Transceiver Normal) |
| **Sensor DHT22** | Pin 1 (VCC) | **Pin 3.3V** ESP32-S3 | Daya sensor |
| | Pin 2 (DATA) | **GPIO 1** | Beri resistor pull-up 4.7kΩ – 10kΩ ke 3.3V |
| | Pin 4 (GND) | **GND** | Ground |
| **RTC DS3231** | VCC | **Pin 3.3V** ESP32-S3 | Daya RTC |
| | GND | **GND** | Ground |
| | **SDA** | **GPIO 2** | Jalur Komunikasi I2C SDA |
| | **SCL** | **GPIO 3** | Jalur Komunikasi I2C SCL |
| **LED Flash Pentol**| Anoda (+) *Kaki Panjang* | **GPIO 47** | **Wajib pasang seri Resistor 150Ω – 220Ω** |
| *(Putih 5mm)* | Katoda (-) *Kaki Pendek*| **GND** | Ground |
| **Kipas Mini DC 5V**| Kabel Merah Positif (+) | **+5V HLK** | Sumber tegangan kipas langsung dari 5V |
| | Kabel Hitam Negatif (-)| **Kolektor (C)** Transistor 2N2222 | Sakelar pemutus/penghubung GND |
| **Transistor Kipas**| Basis (B) | **GPIO 21** | **Wajib pasang seri Resistor 1kΩ** |
| *(NPN 2N2222)* | Kolektor (C) | **Kabel Negatif (-) Kipas** | Jalur sakelar kipas |
| | Emitor (E) | **GND** | Ground |

> 💡 **Proteksi Kipas:** Pasang 1 buah dioda 1N4007 / 1N4148 secara paralel terbalik pada kabel daya kipas (garis/katoda dioda ke Kabel Merah +5V, anoda ke Kabel Hitam -) untuk meredam tegangan induksi saat kipas dimatikan.

---

### B. Receiver (ESP32 Dev Module + LoRa E220)

| Modul LoRa Ebyte E220 | ESP32 Dev Module (Receiver) | Keterangan |
| :--- | :--- | :--- |
| **VCC** | **Pin 5V** (atau VIN) | Suplai tegangan modul LoRa |
| **GND** | **Pin GND** | Ground |
| **TXD** | **GPIO 16 (RX2)** | LoRa TX -> ESP32 RX |
| **RXD** | **GPIO 17 (TX2)** | LoRa RX -> ESP32 TX |
| **M0** | **GND** | **Wajib ke GND** (Mode 0: Normal) |
| **M1** | **GND** | **Wajib ke GND** (Mode 0: Normal) |
| **Port USB ESP32** | **Port USB Laptop / PC** | Mengalirkan data via serial COM (115200 baud) |

---

## 📡 3. Konfigurasi LoRa Ebyte E220 (Software E220_V1.1)

Pastikan **KEDUA MODUL LoRa (Transmitter & Receiver)** disetel dengan parameter yang **IDENTIK**:

| Parameter | Nilai Pengaturan | Alasan Teknis |
| :--- | :--- | :--- |
| **Baud Rate** | **115200 bps** | Kecepatan tinggi agar aliran biner foto tidak tertahan |
| **Parity** | **8N1** | 8 Bit Data, No Parity, 1 Stop Bit |
| **Air Rate** | **62.5 Kbps** (atau 19.2 Kbps) | Pengiriman foto cepat (~2 detik pada 62.5K) |
| **Packet Size** | **200 Bytes** | Ukuran chunk paket optimal |
| **Tran Mode** | **Normal** (Transparent) | Mode transmisi data transparan langsung |
| **Power** | **22 dBm** | Daya pancar maksimal (~160 mW) |
| **Channel** | **65** (Frekuensi 915.125 MHz) | Frekuensi LoRa ISM Indonesia (Keduanya harus sama!) |
| **Address** | **0** | Alamat broadcast/default |
| **Channel RSSI** | **Disable** | Dimatikan agar tidak ada overhead |
| **Packet RSSI** | **Disable** | **Wajib Disable** agar tidak menyisipkan byte ekstra di file gambar |

---

## 📂 4. Struktur Program & Berkas Proyek

Folder kerja terbaru sistem berada di dalam:
```text
V3_ESP32S3_LoRa_Trap/
├── 1_Panduan_Hardware_dan_Wiring/
│   ├── WIRING_DIAGRAM.md             # Tabel wiring dan diagram blok rangkaian
│   └── SKEMA_FLASH_LED_DAN_POWER.md  # Skema transistor kipas & LED pentol 5mm
├── 2_Konfigurasi_LoRa_E220/
│   ├── PANDUAN_KONFIGURASI_E220.md   # Panduan konfigurasi GUI E220_V1.1
│   └── E220_Parameter_Summary.txt    # Ringkasan cepat parameter radio
├── 3_Transmitter_ESP32S3/
│   └── Transmitter_ESP32S3/
│       └── Transmitter_ESP32S3.ino   # Program ESP32-S3 CAM Transmitter
└── 4_Receiver_ESP32_Standalone/
    ├── Receiver_ESP32_Standalone/
    │   └── Receiver_ESP32_Standalone.ino # Program Receiver Bridge ESP32
    └── receiver_pc.py                # Script Image Builder & Sensor Logger di Laptop
```

---

## 💻 5. Cara Mengupload Program

### A. Upload ke ESP32-S3-CAM (Transmitter)
ESP32-S3-CAM sudah dilengkapi port USB Type-C internal (tidak memerlukan modul USB-TTL eksternal).
1. Hubungkan kabel data USB Type-C ke **Port TTL / UART** pada ESP32-S3-CAM.
2. Buka **Arduino IDE**.
3. Buka file sketch:
   `V3_ESP32S3_LoRa_Trap/3_Transmitter_ESP32S3/Transmitter_ESP32S3/Transmitter_ESP32S3.ino`
4. Masuk ke menu **Tools** di Arduino IDE dan pastikan pengaturan berikut:
   * **Board:** `"ESP32S3 Dev Module"`
   * **Port:** Pilih COM ESP32-S3 Anda (misal `COM11` atau `COM34`)
   * **PSRAM:** **`"OPI PSRAM"`** *(Wajib diaktifkan agar memori kamera bekerja)*
   * **Flash Size:** `"8MB (64Mb)"` atau `"16MB"`
   * **Partition Scheme:** `"Huge APP (3MB No OTA/1MB SPIFFS)"`
   * **Upload Speed:** `921600`
5. Klik tombol **Upload** (tanda panah ke kanan).
6. Tunggu hingga proses upload selesai (*Done Uploading*).

### B. Upload ke ESP32 Dev Module (Receiver)
1. Colokkan ESP32 Receiver ke laptop via kabel USB Micro/Type-C.
2. Buka **Arduino IDE**.
3. Buka file sketch:
   `V3_ESP32S3_LoRa_Trap/4_Receiver_ESP32_Standalone/Receiver_ESP32_Standalone/Receiver_ESP32_Standalone.ino`
4. Di menu **Tools**, atur:
   * **Board:** `"ESP32 Dev Module"`
   * **Port:** Pilih COM ESP32 Receiver Anda (misal `COM5`)
5. Klik tombol **Upload**.
6. **PENTING:** Setelah selesai upload, **TUTUP Serial Monitor di Arduino IDE** agar port COM tidak terkunci saat dijalankan oleh script Python.

---

## 🚀 6. Cara Menjalankan Sistem di Laptop (Image Builder)

1. Pastikan modul ESP32 Receiver tetap tercolok ke port USB laptop.
2. Buka **Command Prompt (CMD)** atau **PowerShell**, lalu masuk ke folder receiver:
   ```cmd
   cd "d:\KULIAH\4. Project Lab ELINS\Pemantauan Hama\Program Insect Trap\V3_ESP32S3_LoRa_Trap\4_Receiver_ESP32_Standalone"
   ```
3. Install pustaka pendukung (jika belum pernah):
   ```cmd
   pip install pyserial
   ```
4. Jalankan script penerima:
   ```cmd
   python receiver_pc.py
   ```
5. **Nyalakan Node Transmitter di kebun:**
   - Script akan otomatis mendeteksi port COM ESP32 Anda.
   - Setiap kali transmisi masuk, data suhu (°C), kelembaban (%), dan jam RTC langsung tercatat rapi ke file **`log_sensor.csv`**.
   - Aliran biner foto JPEG akan diunduh dengan progress bar (`100%`) dan otomatis disimpan menjadi file foto **`.jpg`** di dalam folder **`hasil_foto/`**.

---

## 🔄 7. Alur Logika Sistem (Sistem Kerja Otomatis)

1. **Wake Up (Bangun Tidur):** Timer ESP32-S3 membangunkan mikrokontroler dari mode *Deep Sleep*.
2. **Evaluasi Jadwal Kipas via RTC DS3231:**
   - Program membaca waktu aktual dari RTC DS3231.
   - **Pukul 07:00 – 17:00 (Siang Hari):** Pin `GPIO 21` disetel `HIGH`, transistor aktif, dan kipas menyala mendinginkan box dari panas matahari.
   - **Pukul 17:01 – 06:59 (Malam Hari):** Pin `GPIO 21` disetel `LOW`, kipas mati otomatis untuk efisiensi energi.
   - Status pin dikunci (*pin hold*) selama tidur menggunakan perintah `gpio_hold_en((gpio_num_t)FAN_PIN);` dan `gpio_deep_sleep_hold_en();`.
3. **Membaca & Mengirim Data Sensor:**
   - Sensor DHT22 membaca suhu dan kelembaban udara.
   - Dikirim ke LoRa dengan format: `[DATA] Waktu: YYYY-MM-DD HH:MM:SS, Suhu: XX.X C, Kelembaban: YY.Y %, Kipas: ON/OFF`.
4. **Jepret Foto Perangkap Hama:**
   - Lampu Flash LED Pentol 5mm dinyalakan via `GPIO 47`.
   - Sensor kamera OV3660 mengambil 1 frame gambar JPEG (resolusi VGA/QVGA).
   - Lampu Flash langsung dimatikan setelah pengambilan foto selesai.
5. **Transmisi LoRa:**
   - Dikirim header: `---START---` lalu baris berikutnya ukuran total byte file foto.
   - Potongan biner gambar dikirim per-chunk sebesar 150 byte dengan jeda 40–50 ms.
   - Ditutup dengan penanda `---END---`.
6. **Penerimaan di Laptop:**
   - ESP32 Receiver meneruskan aliran data secara transparan (*bypass*).
   - Script `receiver_pc.py` menangkap paket, mencatat sensor ke CSV, dan menyatukan kembali file biner menjadi gambar `.jpg` utuh.
7. **Deep Sleep:** Selesai transmisi, ESP32-S3 masuk ke mode *Deep Sleep* untuk menghemat daya hingga jadwal siklus berikutnya.

---

> 📝 **Catatan Pengujian vs Lapangan:**
> - Di dalam file `Transmitter_ESP32S3.ino`:
>   - Untuk **Uji Coba di Lab:** Baris `const uint64_t WAKEUP_INTERVAL_SECONDS = 30;` dan `SEND_PHOTO_ONCE_DAILY = false` agar foto dikirim setiap 30 detik.
>   - Untuk **Pemasangan di Kebun:** Ubah `WAKEUP_INTERVAL_SECONDS` menjadi `1800` (30 menit) dan set `SEND_PHOTO_ONCE_DAILY = true` agar foto hanya dikirim 1 kali sehari pada jam target (misal jam 8 pagi)!
