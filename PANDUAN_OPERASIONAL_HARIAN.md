# 📋 STANDAR OPERASIONAL PROSEDUR (SOP) HARIAN
## Sistem Pemantauan Perangkap Hama Feromon (Insect Trap Monitoring)
*Lab ELINS - Departemen Ilmu Komputer dan Elektronika, Universitas Gadjah Mada*

Dokumen ini berisi panduan praktis langkah demi langkah untuk menyalakan, menghubungkan, menjalankan, dan mematikan sistem stasiun penerima Raspberry Pi 5 dan Web Dashboard.

---

## 🎒 1. Checklist Peralatan
Pastikan peralatan berikut sudah siap sebelum memulai:
* [ ] **Raspberry Pi 5** (dilengkapi kartu MicroSD OS)
* [ ] **Adaptor Daya Type-C** (Charger HP Fast Charging / SuperVOOC 45W)
* [ ] **Modul ESP32 LoRa Receiver** + Kabel Data USB
* [ ] **Smartphone** (untuk Hotspot Internet)
* [ ] **Laptop** (dengan aplikasi Tailscale terpasang)

---

## ⚡ 2. Tahap Penyalaan Hardware di Lokasi

1. **Aktifkan Hotspot HP:**
   * Nyalakan Personal Hotspot di HP Anda.
   * *Catatan:* Pastikan nama WiFi (SSID) dan password-nya sama dengan yang sudah pernah dihubungkan ke Raspberry Pi agar Raspi otomatis tersambung tanpa perlu monitor.
2. **Hubungkan Modul LoRa ke Raspberry Pi:**
   * Tancapkan kabel USB dari modul ESP32 LoRa Receiver ke salah satu **port USB Raspberry Pi 5**.
3. **Nyalakan Daya Raspberry Pi:**
   * Colokkan charger ke stopkontak listrik PLN.
   * Tancapkan kabel USB Type-C ke port daya Raspberry Pi.
   * Lampu LED Merah akan menyala konstan, dan LED Hijau akan berkedip-kedip membaca data MicroSD.
   * **Tunggu 45 – 60 detik** hingga sistem selesai booting dan terhubung ke Hotspot HP Anda.

---

## 💻 3. Tahap Menghubungkan Laptop ke Raspberry Pi

1. **Koneksi Jaringan Laptop:**
   * Sambungkan laptop Anda ke Hotspot HP yang sama (atau WiFi yang memiliki akses internet).
   * Pastikan aplikasi **Tailscale** di laptop aktif (ikon titik di pojok kanan bawah taskbar Windows).
2. **Buka Terminal Laptop:**
   * Tekan tombol `Windows + R`, ketik `cmd`, lalu tekan `Enter` (atau buka PowerShell).
3. **Login Jarak Jauh (SSH):**
   * Ketik perintah berikut lalu tekan `Enter`:
     ```cmd
     ssh insect-trap@100.64.81.29
     ```
   * Jika muncul konfirmasi keamanan: ketik `yes` lalu `Enter`.
   * Saat diminta password, masukkan:
     ```text
     ;.
     ```
     *(Karakter memang tidak muncul di layar, langsung ketik titik koma dan titik lalu tekan `Enter`)*.
4. **Tanda Berhasil:**
   * Baris perintah terminal akan berubah menjadi:
     ```text
     insect-trap@srikayangan:~ $
     ```

---

## 🚀 4. Tahap Menjalankan Program Monitoring & Web Dashboard

Di dalam jendela terminal SSH Raspberry Pi tersebut, jalankan perintah berikut:

```bash
cd ~/5_Receiver_RaspberryPi5_Dashboard/pi_service
python3 app.py
```

* Sistem akan menginisialisasi modul LoRa di `/dev/ttyUSB0` dan menyalakan Web Server di port `5000`.
* ⚠️ **PENTING:** Biarkan jendela terminal ini **tetap terbuka** selama sistem beroperasi (jangan ditutup dan jangan tekan `CTRL + C`).

---

## 🌐 5. Tahap Membuka Tampilan Dashboard di Laptop

1. Buka browser **Google Chrome** atau **Microsoft Edge** di laptop Anda.
2. Buka alamat berikut:
   ```text
   http://100.64.81.29:5000
   ```
3. **Tampilan Web Monitoring:**
   * Foto perangkap serangga terbaru otomatis diperbarui.
   * Kotak hijau (*bounding box*) hasil deteksi kecerdasan buatan (AI) menandai serangga hama yang tertangkap.
   * Grafik tren populasi hama dan kondisi lingkungan (suhu & kelembaban) tersaji secara real-time.
   * Klik tombol hijau **`Unduh CSV`** jika ingin mengekspor data ke format Excel.

---

## 🛑 6. Tahap Mematikan Sistem Secara Aman (SOP Shutdown)

*PENTING: Jangan mencabut langsung kabel charger saat Raspberry Pi menyala agar kartu memori MicroSD tidak korup.*

1. Pada terminal yang sedang menjalankan `app.py`, tekan tombol kombinasi:
   ```text
   CTRL + C
   ```
   *(Server web akan berhenti dengan aman)*.
2. Ketik perintah shutdown:
   ```bash
   sudo poweroff
   ```
   *(Masukkan password `;.` jika diminta)*.
3. Tunggu sekitar **10 detik** sampai lampu aktivitas hijau di Raspberry Pi mati total dan hanya tersisa lampu merah.
4. **Cabut adaptor daya charger dari stopkontak listrik.** Sistem sudah mati dengan aman.

---
*Dokumentasi ini dibuat otomatis untuk proyek Insect Trap Monitoring IoT & AI - ELINS UGM.*
