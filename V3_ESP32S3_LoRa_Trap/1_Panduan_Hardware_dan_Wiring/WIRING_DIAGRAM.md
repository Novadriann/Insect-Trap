# Diagram Wiring & Pengkabelan Sistem Pemantauan Hama

Dokumen ini berisi panduan pengkabelan (*wiring*) lengkap untuk **Node Transmitter (Kebun)** dan **Node Receiver (Stasiun / Raspberry Pi 5)**.

---

## 🌾 1. Node Transmitter (Node Perangkap / Kebun)

Node Transmitter bertugas mengukur suhu, kelembaban, waktu aktual, menyalakan flash, mengambil foto plate perekat feromon serangga, dan mengirimkannya via LoRa Ebyte E220 ke stasiun penerima.

### Komponen yang Digunakan:
1. **ESP32-S3-CAM** (Modul kamera OV3660, Dual Type-C)
2. **LoRa Ebyte E220-900T22D** (Transceiver 900 MHz UART)
3. **Sensor DHT22 (AM2302)** (Suhu & Kelembaban presisi tinggi)
4. **Modul RTC DS3231** (Real Time Clock I2C dengan baterai koin CR2032)
5. **Kipas Mini DC 5V** (Pendingin sirkulasi box)
6. **Lampu Flash LED Putih High-Power (1W-3W)** + **Driver MOSFET (AOD4184 / IRLZ44N)**
7. **Power Supply HLK-PM01 / HLK 5V 2A** (Input 220V AC -> Output 5V DC 2A)

---

### A. Tabel Pengkabelan Node Transmitter

| Komponen | Pin Komponen | Pin ESP32-S3-CAM | Keterangan / Sumber Daya |
| :--- | :--- | :--- | :--- |
| **Power Input** | AC Live & Neutral | - | Masuk ke pin AC L & N modul HLK 5V 2A |
| **HLK 5V 2A** | Output +5V | **5V Pin** | Menyuplai daya ke ESP32-S3 |
| **HLK 5V 2A** | Output GND | **GND Pin** | Ground bersama (*Common GND*) |
| **Kipas DC 5V** | Positif (+) Merah | - | **Langsung ke +5V HLK** (Nyala terus 24/7) |
| **Kipas DC 5V** | Negatif (-) Hitam | - | **Langsung ke GND HLK** |
| **LoRa E220** | VCC | - | **Langsung ke +5V HLK** (Arus TX puncak ~120mA) |
| **LoRa E220** | GND | **GND** | Ke Ground bersama |
| **LoRa E220** | TXD | **GPIO 41** | LoRa TX -> ESP32-S3 RX (UART1) |
| **LoRa E220** | RXD | **GPIO 42** | LoRa RX -> ESP32-S3 TX (UART1) |
| **LoRa E220** | M0 | **GND** | Di-ground-kan permanen (Mode 0: Normal Transparent) |
| **LoRa E220** | M1 | **GND** | Di-ground-kan permanen (Mode 0: Normal Transparent) |
| **LoRa E220** | AUX | - | Dibiarkan terbuka (*Floating*) atau ke GPIO 21 (opsional) |
| **DHT22** | Pin 1 (VCC) | **3.3V** (atau 5V) | Suplai tegangan sensor |
| **DHT22** | Pin 2 (DATA) | **GPIO 1** | Diberi resistor pull-up 4.7kΩ – 10kΩ ke 3.3V |
| **DHT22** | Pin 3 (NC) | - | Tidak terhubung (*Not Connected*) |
| **DHT22** | Pin 4 (GND) | **GND** | Ground |
| **RTC DS3231** | VCC | **3.3V** (atau 5V) | Suplai tegangan RTC |
| **RTC DS3231** | GND | **GND** | Ground |
| **RTC DS3231** | SDA | **GPIO 2** | Jalur Data I2C Wire |
| **RTC DS3231** | SCL | **GPIO 3** | Jalur Clock I2C Wire |
| **Flash Driver**| Signal / Gate | **GPIO 47** | Pemicu lampu kilat (via resistor 220Ω) |
| **Flash Driver**| VCC LED (+) | - | Hubungkan ke +5V HLK |
| **Flash Driver**| GND Source | **GND** | Ground bersama |

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
       ├───────────────┼───────────────► [ KIPAS DC 5V (Always ON) ]
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
       │               │                   ├─ GPIO 1 ◄── DHT22 DATA (Pull-up 10k ke 3.3V)
       │               │                   ├─ GPIO 2 ◄─► RTC DS3231 SDA
       │               │                   ├─ GPIO 3 ──► RTC DS3231 SCL
       │               │                   │
       │               │                   └─ GPIO 47 ──[ 220Ω ]──┐
       │               │                                          │
       │               │                                      (GATE)
       │               │                                   ┌─────────┐
       ├───────────────┼──[ Resistor 2.2Ω 2W ]──(+) [LED] (─)│ MOSFET  │
       │               │                                   │ AOD4184 │
       │               └───────────────────────────────────│ (SOURCE)│
       │                                                   └─────────┘
```

> ⚠️ **Catatan Penting Pin ESP32-S3:**
> - Pin **GPIO 35, 36, 37** TIDAK BOLEH DIGUNAKAN karena terhubung langsung ke chip internal Octal PSRAM.
> - Pin **GPIO 43 & 44** adalah port USB UART bawaan (TTL) yang digunakan untuk Serial Monitor & Debugging.
> - Pin **GPIO 47, 41, 42, 1, 2, 3** yang dipilih di atas 100% aman dan bebas dari konflik kamera OV3660.

---

## 📡 2. Node Receiver (Stasiun Penerima / Base Station)

Node Receiver menangkap transmisi LoRa dari kebun, mengekstrak data sensor, merekonstruksi file JPEG, dan meneruskannya ke Raspberry Pi 5 untuk image counting serta Web Dashboard.

### Pilihan A: Mode Standalone (ESP32 Saja - Tanpa Raspberry Pi)
Digunakan jika ingin membawa receiver portabel ke kebun dengan laptop atau layar OLED:

| ESP32 Dev Module | LoRa Ebyte E220 900T22D | Keterangan |
| :--- | :--- | :--- |
| **5V (atau VIN)** | VCC | Suplai tegangan LoRa |
| **GND** | GND | Ground |
| **GPIO 16 (RX2)** | TXD | LoRa TX -> ESP32 RX2 |
| **GPIO 17 (TX2)** | RXD | LoRa RX -> ESP32 TX2 |
| **GND** | M0 | Mode Transparan (Mode 0) |
| **GND** | M1 | Mode Transparan (Mode 0) |
| *Kabel USB* | Ke Laptop / PC | Membuka Serial Monitor 115200 baud |

---

### Pilihan B: Mode Lengkap (ESP32 + Raspberry Pi 5)

Pada mode ini, ESP32 Dev Module berfungsi sebagai **LoRa-to-USB Bridge** berkecepatan tinggi yang ditancapkan langsung ke port USB Raspberry Pi 5.

```text
  [ Antena LoRa ]
         │
         ▼
┌──────────────────┐
│ LoRa Ebyte E220  │
└────────┬─────────┘
         │ UART (GPIO 16 & 17)
         ▼
┌──────────────────┐
│ ESP32 Dev Module │
└────────┬─────────┘
         │
    Kabel USB (Data & Power 5V)
         │
         ▼
┌────────────────────────────────────────────────────────┐
│                   RASPBERRY PI 5                       │
│                                                        │
│  Port USB: /dev/ttyUSB0 (Menerima Stream Data)         │
│  Service 1: receiver_daemon.py (Simpan CSV & Gambar)   │
│  Service 2: insect_counter.py (OpenCV Image Counting) │
│  Service 3: app.py (Web Dashboard Port 5000)          │
└────────────────────────────────────────────────────────┘
```

#### Keuntungan Menghubungkan ESP32 ke Raspberry Pi 5 via USB:
1. **Plug & Play dan Aman:** Tidak perlu membagi tegangan 3.3V/5V atau membebani pin GPIO header Raspberry Pi 5.
2. **Isolasi Gangguan:** Raspberry Pi 5 memiliki port USB 3.0/2.0 yang terlindung dari arus balik atau lonjakan tegangan LoRa.
3. **Daya Terjamin:** Port USB Raspberry Pi 5 mampu menyuplai arus hingga 1.5A untuk periferal USB.
