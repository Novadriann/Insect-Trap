# Panduan Lengkap Konfigurasi LoRa Ebyte E220-900T22D

Panduan ini disusun berdasarkan tampilan aplikasi resmi **RF Setting E220_V1.1 (Chengdu Ebyte Electronic Technology Co.,Ltd)** sesuai dengan tangkapan layar yang Anda lampirkan.

---

## 🖥️ 1. Persiapan Perangkat Lunak & Keras

Untuk mengonfigurasi modul LoRa Ebyte E220 menggunakan software PC:
1. Hubungkan modul LoRa E220 ke PC melalui adapter **USB-to-TTL (CH340 / CP2102 / FTDI)**:
   - `VCC LoRa` -> `5V` (atau 3.3V)
   - `GND LoRa` -> `GND`
   - `TXD LoRa` -> `RXD USB-TTL`
   - `RXD LoRa` -> `TXD USB-TTL`
2. **PENTING - Masuk ke Mode Konfigurasi:**
   - Hubungkan pin **M0 ke 3.3V (HIGH)** dan **M1 ke 3.3V (HIGH)** (Mode 3: Sleep/Configuration Mode).
   - *Catatan:* Jika menggunakan fitur "software config" pada aplikasi, M0 & M1 tetap disarankan berada pada posisi konfigurasi (M0=1, M1=1) agar modul merespons perintah AT dengan stabil.
3. Buka aplikasi **E220_V1.1.exe**, pilih bahasa **English**, pilih COM Port adapter USB Anda, lalu klik tombol **Open**.
4. Klik tombol **Get** untuk membaca konfigurasi awal modul.

---

## ⚙️ 2. Nilai Konfigurasi yang Direkomendasikan (Tabel Parameter)

Isikan form pada software **E220_V1.1** persis sesuai tabel berikut:

| Parameter di GUI | Nilai yang Harus Diatur | Alasan Teknis & Penjelasan |
| :--- | :--- | :--- |
| **Baud Rate** | **115200** | Sangat penting! Mengirim gambar biner JPEG (~10-15 KB) membutuhkan kecepatan serial tinggi agar buffer mikrokontroler tidak menumpuk. |
| **Parity** | **8N1** | 8 Data bit, No Parity, 1 Stop bit (standar komunikasi UART). |
| **Air Rate** | **19.2 kbps** (atau 62.5 kbps) | **19.2 kbps** adalah kompromi emas: Jangkauan tembus kebun mencapai 1 – 2 km dengan waktu transmisi gambar hanya ~6 – 8 detik. Jika jarak <500m, pilih **62.5 kbps** (waktu kirim hanya ~2 detik). *Jangan gunakan 2.4 kbps karena mengirim foto akan memakan waktu >55 detik!* |
| **Packet Size** | **200 bytes** (atau 240 bytes) | Memungkinkan pemotongan *chunk* gambar yang lebih besar sehingga efisiensi transmisi meningkat dan *overhead* berkurang. |
| **Tran Mode** | **Transparent mode** | Mode transmisi transparan (apapun data biner yang masuk ke TXD langsung dipancarkan lewat gelombang radio ke RXD receiver). |
| **Wor Cycle** | **2000 ms** (Default) | Tidak berpengaruh dalam mode transparan kontinu, biarkan default. |
| **Power** | **22 dBm** (Maksimal / ~160mW) | Memberikan daya pancar maksimal agar sinyal mampu menembus rimbunnya dedaunan dan kanopi pohon di kebun. |
| **WorkMode** | **Normal** | Mode operasi normal. |
| **Channel RSSI** | **Enable** | Mengaktifkan pemantauan kekuatan sinyal lingkungan sekitar untuk mengecek interferensi frekuensi. |
| **LBT** | **Disable** | *Listen Before Talk* sebaiknya dimatikan agar transmisi potongan gambar tidak tertahan jika ada noise sesaat. |
| **Packet RSSI** | **Enable** | Memungkinkan receiver membaca kekuatan sinyal (*dBm*) pada setiap akhir paket. |
| **Address** | **00 00** (Hex) | Alamat broadcast/default yang sama untuk kedua modul. |
| **Channel** | **65** (atau 18) | **Channel 65** setara dengan frekuensi **915.125 MHz** (sesuai regulasi frekuensi ISM Indonesia 915-928 MHz). Pastikan kedua modul berada di channel yang sama! |
| **Key** | **00 00** (Hex / Kosong) | Tidak menggunakan enkripsi hardware agar transmisi data biner berkecepatan tinggi tidak mengalami latensi komputasi. |

---

## 💾 3. Langkah Menyimpan Parameter

1. Setelah semua kolom diatur sesuai tabel di atas, klik tombol **Set Param**.
2. Di kotak teks log software akan muncul pesan sukses: `Set parameters successfully!`.
3. Klik tombol **Get** sekali lagi untuk memverifikasi bahwa parameter telah tersimpan di memori EEPROM modul E220.
4. Ulangi proses yang sama persis untuk **Modul LoRa kedua (Receiver)**.
5. **Setelah selesai konfigurasi:**
   - Cabut kabel jumper M0 dan M1 dari 3.3V.
   - Sambungkan **M0 ke GND** dan **M1 ke GND** (Mode 0: Normal Operation) saat dipasang ke rangkaian ESP32-S3 maupun ESP32 Receiver.

---

## 📊 Perbandingan Kecepatan Pengiriman Gambar (Air Rate)

Estimasi waktu pengiriman 1 frame gambar JPEG ukuran **12 Kilobyte (12.288 Bytes)**:

| Air Rate | Perkiraan Jangkauan | Waktu Pengiriman Gambar | Rekomendasi Penggunaan |
| :---: | :---: | :---: | :--- |
| **2.4 kbps** | Sangat Jauh (> 3 km) | ± 52 Detik | Terlalu lambat untuk gambar, rentan putus di tengah jalan. |
| **9.6 kbps** | Jauh (2 – 3 km) | ± 13 Detik | Cukup baik untuk area perkebunan berbukit/terpencil. |
| **19.2 kbps** | **Sedang-Jauh (1 – 2 km)** | **± 6.5 Detik** | **Sangat Direkomendasikan (Paling Stabil)**. |
| **62.5 kbps** | Dekat-Sedang (< 1 km) | **± 2.1 Detik** | **Paling Cepat**, sangat bagus jika jarak stasiun < 1 km tanpa halangan tebal. |
