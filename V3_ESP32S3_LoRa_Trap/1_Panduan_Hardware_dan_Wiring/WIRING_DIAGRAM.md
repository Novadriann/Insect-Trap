# Diagram Wiring & Pengkabelan Sistem Pemantauan Hama (Revisi V3.1)

Dokumen ini berisi panduan pengkabelan (*wiring*) lengkap untuk **Node Transmitter (Kebun)** dan **Node Receiver (Stasiun / Raspberry Pi 5)** dengan fitur:
1. **Kipas DC 5V Berbasis Jadwal Waktu RTC:** Aktif otomatis dari **pukul 07:00 pagi hingga 17:00 sore**, dan mati di malam hari untuk efisiensi energi.
2. **Lampu Flash LED Pentol 5mm:** Menggunakan LED putih bulat kecil (DIP 5mm) + resistor 150Ω–220Ω langsung dari GPIO 47 tanpa perlu modul driver daya besar.

---

## 🌾 1. Node Transmitter (Node Perangkap / Kebun)

### Komponen yang Digunakan:
1. **ESP32-S3-CAM** (Modul kamera OV3660, Dual Type-C)
2. **LoRa Ebyte E220-900T22D** (Transceiver 900 MHz UART)
3. **Sensor DHT22 (AM2302)** (Suhu & Kelembaban)
4. **Modul RTC DS3231** (Real Time Clock I2C dengan baterai CR2032)
5. **Kipas Mini DC 5V** + **1 Transistor NPN (2N2222 / SS8050 / BD139)** sebagai sakelar elektronik
6. **Lampu Flash LED Pentol Putih 5mm** + **Resistor 150Ω – 220Ω**
7. **Power Supply HLK-PM01 / HLK 5V 2A** (Input 220V AC -> Output 5V DC 2A)

---

### A. Tabel Pengkabelan Node Transmitter

| Komponen | Pin Komponen | Pin ESP32-S3-CAM / Sumber Daya | Keterangan & Catatan |
| :--- | :--- | :--- | :--- |
| **HLK 5V 2A** | AC Line & Neutral | Jaringan Listrik 220V AC | Pasang sekring 1A untuk keamanan |
| **HLK 5V 2A** | Output +5V | **Pin 5V** ESP32-S3 | Suplai utama sistem |
| **HLK 5V 2A** | Output GND | **Pin GND** ESP32-S3 | Ground bersama (*Common Ground*) |
| **LoRa E220** | VCC | **+5V HLK** | Arus transmisi puncak ~120 mA |
| **LoRa E220** | GND | **GND** | Ground |
| **LoRa E220** | TXD | **GPIO 41** | LoRa TX -> ESP32-S3 RX (UART1) |
| **LoRa E220** | RXD | **GPIO 42** | LoRa RX -> ESP32-S3 TX (UART1) |
| **LoRa E220** | M0 | **GND** | Di-ground permanen (Mode 0: Transparan) |
| **LoRa E220** | M1 | **GND** | Di-ground permanen (Mode 0: Transparan) |
| **DHT22** | Pin 1 (VCC) | **3.3V** | Suplai daya sensor |
| **DHT22** | Pin 2 (DATA) | **GPIO 1** | Beri resistor pull-up 4.7kΩ–10kΩ ke 3.3V |
| **DHT22** | Pin 4 (GND) | **GND** | Ground |
| **RTC DS3231** | VCC | **3.3V** | Suplai daya RTC |
| **RTC DS3231** | GND | **GND** | Ground |
| **RTC DS3231** | SDA | **GPIO 2** | Jalur Data I2C Wire |
| **RTC DS3231** | SCL | **GPIO 3** | Jalur Clock I2C Wire |
| **LED Flash Pentol** | Anoda (+) Kaki Panjang | **GPIO 47 (via Resistor 150Ω–220Ω)** | Mengontrol lampu kilat foto |
| **LED Flash Pentol** | Katoda (-) Kaki Pendek | **GND** | Ground |
| **Sakelar Kipas** | Basis Transistor (B) | **GPIO 21 (via Resistor 1kΩ)** | Pemicu kipas (HIGH = 07:00 s/d 17:00) |
| **Sakelar Kipas** | Kolektor Transistor (C)| **Kabel Negatif (-) Kipas** | Sakelar jalur negatif kipas |
| **Sakelar Kipas** | Emitor Transistor (E) | **GND** | Ground |
| **Kipas DC 5V** | Kabel Positif (+) Merah| **+5V HLK** | Suplai daya 5V langsung |

---

### B. Diagram Blok Sirkuit Node Transmitter

```text
       [ PLN 220V AC ]
              │
              ▼
   ┌───────────────────────┐
   │  HLK 5V 2A (AC to DC) │
   └───┬───────────────┬───┘
      +5V             GND
       │               │
       ├───────────────┼───────────────► [ LoRa Ebyte E220 (VCC & GND) ]
       │               │                   ▲   ▲
       │               │                   │   │ TXD ──► GPIO 41 (RX)
       │               │                   │   └ RXD ◄── GPIO 42 (TX)
       │               │                   └──── M0 & M1 ke GND
       │               │
       ├───────────────┼───────────────► [ ESP32-S3-CAM (5V & GND) ]
       │               │                   │
       │               │                   ├─ 3.3V ──► DHT22 VCC & RTC VCC
       │               │                   ├─ GPIO 1 ◄── DHT22 DATA (Pull-up 10k)
       │               │                   ├─ GPIO 2 ◄─► RTC DS3231 SDA
       │               │                   ├─ GPIO 3 ──► RTC DS3231 SCL
       │               │                   │
       │               │                   ├─ GPIO 47 ──[ R 150Ω ]──(+) [ LED Pentol 5mm ] (─)──► GND
       │               │                   │
       │               │                   └─ GPIO 21 ──[ R 1kΩ ]──┐ (BASIS)
       │               │                                           │
       │               │                                     ┌─────┴─────┐
       │               │       (+)                 (─)       │Transistor │
       ├───────────────┴───[ Kipas DC 5V ]───────────────────┤  2N2222   │
       │                                                     │ (EMITOR)  │
       │                                                     └─────┬─────┘
       └───────────────────────────────────────────────────────────┴──► GND
```

---

## 📡 2. Node Receiver (Stasiun Penerima / Base Station)

### A. Mode Standalone (ESP32 Saja - Tanpa Raspberry Pi)
Digunakan saat pengujian lapangan dengan laptop / Serial Monitor:
- `LoRa VCC` -> `5V ESP32`
- `LoRa GND` -> `GND`
- `LoRa TXD` -> `GPIO 16 (RX2)`
- `LoRa RXD` -> `GPIO 17 (TX2)`
- `M0` & `M1` -> `GND`

### B. Mode Lengkap (ESP32 + Raspberry Pi 5)
- ESP32 Receiver menjalankan firmware `esp32_bridge.ino`.
- ESP32 dihubungkan ke port USB Raspberry Pi 5 (`/dev/ttyUSB0`) menggunakan kabel data USB.
- Raspberry Pi 5 menjalankan service `receiver_daemon.py`, `insect_counter.py`, dan Web Dashboard `app.py` pada port `5000`.
