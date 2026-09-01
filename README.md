# Sistem Pemantauan Hama Jarak Jauh (Insect Counting Trap)
Proyek ini adalah sistem IoT untuk memantau jumlah hama serangga di dalam perangkap lem ber-feromon. Sistem akan mengambil gambar dari dalam perangkap satu kali sehari dan mengirimkannya secara nirkabel sejauh beberapa kilometer menggunakan gelombang radio LoRa ke stasiun penerima (Komputer/Laptop) untuk disimpan sebagai file `.jpg`.

## 🛠️ 1. Spesifikasi Hardware
Komponen utama yang digunakan dalam sistem ini:
1. **Transmitter (Node Kebun):**
   * Mikrokontroler: ESP32-CAM (AI Thinker Board)
   * Modul Kamera: OV3660 (3 Megapixel)
   * Modul Komunikasi: LoRa Ebyte E220-900T22D
   * Power Supply: Adaptor AC to DC 5V (Minimal 2 Ampere sangat diwajibkan)
2. **Receiver (Node Stasiun / Laptop):**
   * Mikrokontroler: ESP32 Dev Module V1
   * Modul Komunikasi: LoRa Ebyte E220-900T22D
   * Power Supply: Kabel USB langsung ke Laptop/PC
3. **Lain-lain:** 
   * USB-TTL (FTDI/CH340) untuk meng-upload program ke ESP32-CAM.
   * Kabel Jumper secukupnya.

---

## 🔌 2. Diagram Wiring (Pengkabelan)

### A. Transmitter (ESP32-CAM + LoRa)
> **PENTING:** Gunakan pin 13 dan 14 (fitur GPIO Matrix) untuk LoRa agar tidak berbenturan dengan pin U0R/U0T yang dipakai untuk upload program.

| ESP32-CAM (Transmitter) | Modul LoRa Ebyte E220 | Adaptor AC to DC (5V 2A) |
| :--- | :--- | :--- |
| **5V** | VCC | VCC / Positif (+) |
| **GND** | GND | GND / Negatif (-) |
| **GPIO 13** | **TXD** | - |
| **GPIO 14** | **RXD** | - |
| **GND** | M0 | - |
| **GND** | M1 | - |

### B. Receiver (ESP32 Dev Module V1 + LoRa)
| ESP32 Dev Module (Receiver) | Modul LoRa Ebyte E220 | 
| :--- | :--- | 
| **5V** (atau 3.3V) | VCC | 
| **GND** | GND | 
| **GPIO 16 (RX2)** | **TXD** | 
| **GPIO 17 (TX2)** | **RXD** | 
| **GND** | M0 | 
| **GND** | M1 | 

---

## 💻 3. Cara Mengupload Program

### A. Upload ke ESP32-CAM (Transmitter)
ESP32-CAM tidak memiliki port USB sendiri, sehingga membutuhkan alat USB-TTL.
1. Hubungkan USB-TTL ke ESP32-CAM: `5V ke 5V`, `GND ke GND`, `TX ke U0R`, dan `RX ke U0T`.
2. **Hubungkan pin `GPIO 0` ke `GND`** pada ESP32-CAM untuk masuk ke *Flash Mode*.
3. Colokkan USB-TTL ke komputer. Buka Arduino IDE.
4. Pergi ke **Tools > Board**, pilih **"AI Thinker ESP32-CAM"**.
5. Pergi ke **Tools > PSRAM**, pastikan terpilih **"Enabled"**.
6. Buka file `Transmitter_ESP32CAM.ino`, klik tombol **Upload**.
7. Jika di layar Arduino IDE muncul tulisan *Connecting...*, tekan tombol kecil **RST (Reset)** di bagian bawah ESP32-CAM satu kali.
8. Setelah *Done Uploading*, **cabut kabel `GPIO 0` dari `GND`**, lalu tekan tombol **RST** sekali lagi untuk menjalankan program.

### B. Upload ke ESP32 Dev Module (Receiver)
1. Colokkan ESP32 langsung ke komputer dengan kabel USB Micro/Type-C.
2. Buka Arduino IDE, **Tools > Board**, pilih **"ESP32 Dev Module"**.
3. Buka file `Receiver_ESP32.ino`, lalu klik **Upload**.

---

## ⚙️ 4. Cara Menjalankan Sistem & Python
1. **Penerima (Receiver):** Colokkan ESP32 Receiver ke port USB Laptop.
2. Cek di *Device Manager* port berapa yang digunakan (misal: `COM5`).
3. Buka file `Python_Image_Builder/receiver.py` dengan Notepad, edit baris `SERIAL_PORT = 'COM5'` sesuai dengan port komputermu, lalu Save.
4. Buka *Command Prompt (CMD)*, ketikkan:
   ```cmd
   cd "d:\KULIAH\4. Project Lab ELINS\Pemantauan Hama\All Program\Python_Image_Builder"
   pip install pyserial
   python receiver.py
   ```
5. **Pengirim (Transmitter):** Nyalakan Adaptor listrik di kebun untuk ESP32-CAM.
6. Gambar akan dikirim, disatukan oleh Python, dan muncul sebagai file berekstensi `.jpg` di dalam folder `Python_Image_Builder`.

---

## 🔄 5. Alur Program (Sistem Kerja)

1. **Wake Up (Bangun Tidur):** Timer internal ESP32-CAM akan membangunkan alat setiap 24 jam sekali dari mode *Deep Sleep*.
2. **Kamera Inisialisasi:** Sensor OV3660 diaktifkan. Program otomatis membalik gambar (*vflip*) dan mengatur warna/kecerahan karena karakteristik khusus dari OV3660.
3. **Capture (Jepret):** Kamera mengambil 1 buah foto dengan resolusi VGA (640x480) dalam format JPEG.
4. **Chunking (Pemotongan Data):** Karena batas maksimal buffer memori LoRa di udara sangat kecil, gambar JPEG (sebesar ~10-15 KB) akan dicacah oleh ESP32-CAM menjadi potongan kecil sebesar 150 byte.
5. **Transmisi LoRa:** 
   * Pertama, dikirim string penanda `---START---` dan ukuran byte gambar.
   * Lalu potongan-potongan gambar dikirim secara bertahap via pin UART 13 & 14 (jeda 50ms per potongan agar tidak *overflow* di udara).
   * Ditutup dengan penanda `---END---`.
6. **Deep Sleep (Mati Suri):** Selesai mengirim, ESP32-CAM langsung masuk ke mode hemat energi ekstrem (Deep Sleep) selama 24 jam berikutnya.
7. **Penerimaan & Rekonstruksi:** ESP32 Receiver menangkap sinyal di udara dan langsung membuangnya (*passthrough*) ke port USB Laptop. Script Python di laptop menangkap pecahan data tersebut, menyusunnya kembali (*rebuild*) sesuai ukuran awal, dan menyimpannya menjadi file `.jpg`.

---
> 📝 **Catatan Sebelum Deploy ke Lapangan:** 
> Pastikan kamu sudah mengubah baris `uint64_t TIME_TO_SLEEP = 30;` kembali menjadi `24 * 60 * 60;` di dalam `Transmitter_ESP32CAM.ino` agar alat benar-benar tidur selama 1 hari penuh! Serta hapus tanda `//` pada `digitalWrite(FLASH_PIN, HIGH);` jika perangkapmu gelap dan butuh lampu kilat.
