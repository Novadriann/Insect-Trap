# Panduan Praktis: Koneksi SSH Raspberry Pi 5 & Pembuatan Model YOLO Kupu Kaper

Dokumen ini berisi panduan langkah-demi-langkah yang mudah dipahami untuk:
1. **Menghubungkan Laptop ke Raspberry Pi 5 via SSH** (Remote Terminal tanpa monitor/keyboard terpisah).
2. **Membuat dan Melatih Model AI YOLO Kupu Kaper** dari awal hingga siap dipasang di Raspberry Pi 5.

---

## BAGIAN 1: Cara SSH ke Raspberry Pi 5 dari Laptop (Windows)

SSH (*Secure Shell*) memungkinkan Anda membuka terminal Raspberry Pi 5 langsung dari PowerShell atau Command Prompt laptop melalui jaringan Wi-Fi/LAN.

### Langkah 1: Pastikan Raspberry Pi 5 & Laptop Terhubung ke Jaringan yang Sama
- Hubungkan Laptop dan Raspberry Pi 5 ke Wi-Fi yang sama (misal Wi-Fi rumah, kantor, atau Hotspot HP).
- *Tips Praktis*: Jika di lab/lapangan tanpa router, nyalakan **Personal Hotspot dari HP**, lalu sambungkan Laptop dan Raspberry Pi 5 ke hotspot HP tersebut.

---

### Langkah 2: Mengetahui IP Address atau Hostname Raspberry Pi 5
Di sistem operasi modern (Raspberry Pi OS 64-bit), nama bawaannya adalah `raspberrypi.local`.

Coba tes koneksi dari laptop Anda. Buka **PowerShell** di laptop dan ketik:
```powershell
ping raspberrypi.local
```
- Jika muncul balasan (*Reply from ...*), artinya laptop sudah bisa mengenali Raspberry Pi 5 secara langsung! Catat alamat IP yang muncul (misal `192.168.1.25`).
- Jika tidak merespons, Anda bisa melihat daftar perangkat yang terhubung melalui menu **Hotspot HP** atau aplikasi **Fing** di smartphone.

---

### Langkah 3: Melakukan SSH dari Windows PowerShell
Buka terminal **PowerShell** atau **Command Prompt**, lalu ketik perintah:

```powershell
ssh <username>@raspberrypi.local
```
*(Ganti `<username>` dengan nama user yang Anda buat saat flashing kartu SD, biasanya `pi` atau `admin`).*

Contoh:
```powershell
ssh pi@raspberrypi.local
```
Atau menggunakan alamat IP:
```powershell
ssh pi@192.168.1.25
```

1. Saat pertama kali konek, akan muncul pertanyaan:
   ```text
   Are you sure you want to continue connecting (yes/no/[fingerprint])?
   ```
   Ketik **`yes`** lalu tekan **Enter**.
2. Masukkan **Password** Raspberry Pi Anda (karakter password tidak akan tampil di layar saat diketik, ini fitur keamanan standar Linux). Tekan **Enter**.
3. **Selesai!** Tampilan prompt akan berubah menjadi terminal Raspberry Pi (contoh: `pi@raspberrypi:~ $`). Sekarang Anda sudah bisa mengontrol Raspberry Pi 5 secara penuh dari laptop!

---

### Langkah 4: Cara Menyalin File / Folder dari Laptop ke Raspberry Pi 5
Gunakan perintah `scp` dari PowerShell laptop (buka tab PowerShell baru):

```powershell
# Contoh menyalin folder dashboard pemantauan ke Raspberry Pi 5:
scp -r "d:\KULIAH\4. Project Lab ELINS\Pemantauan Hama\Program Insect Trap\V3_ESP32S3_LoRa_Trap\5_Receiver_RaspberryPi5_Dashboard" pi@raspberrypi.local:~/insect_trap/

# Contoh menyalin file konfigurasi kaper_config.json:
scp "d:\KULIAH\4. Project Lab ELINS\Pemantauan Hama\Program Insect Trap\V3_ESP32S3_LoRa_Trap\4_Receiver_ESP32_Standalone\kaper_config.json" pi@raspberrypi.local:~/insect_trap/pi_service/
```
*(Atau Anda bisa menggunakan software grafis gratis seperti **WinSCP** jika ingin drag-and-drop file seperti di Windows Explorer).*

---

## BAGIAN 2: Cara Bikin & Melatih Model YOLO Kupu Kaper

Untuk mendeteksi kupu kaper dengan Deep Learning, model yang paling direkomendasikan untuk Raspberry Pi 5 (2GB RAM) adalah **YOLOv8-Nano (`yolov8n`)**.
- Ukuran model sangat kecil (~6 MB).
- Waktu inferensi pada prosesor Cortex-A76 Pi 5 hanya **~40–70 milidetik** per foto.
- Konsumsi memori sangat hemat (tidak membuat Pi 5 kehabisan RAM).

> [!TIP]
> **Di mana sebaiknya melatih (training) model YOLO?**
> **Latihlah di Google Colab (Gratis GPU T4)** atau Laptop dengan VGA NVIDIA! Jangan melatih di Raspberry Pi karena proses training butuh jutaan kalkulasi matriks yang lambat jika di CPU. Raspberry Pi 5 digunakan khusus untuk **menjalankan model yang sudah jadi** (*inference*).

---

### Tahap 1: Kumpulkan Foto Kupu Kaper
1. Ambil foto-foto kaper dari perangkap hama Anda di folder `hasil_foto/`.
2. Kumpulkan sekitar **50 hingga 150 foto** yang memuat kupu kaper di lem perangkap dengan berbagai variasi sudut dan pencahayaan.

---

### Tahap 2: Labelling / Anotasi Gambar (Paling Mudah via Roboflow)
1. Buka browser dan buka situs gratis: [https://roboflow.com](https://roboflow.com).
2. Buat akun gratis -> Klik **Create New Project**.
3. Pilih Project Type: **Object Detection**, beri nama project misalnya: `kaper-detection`.
4. Unggah (Upload) 50–150 foto kaper yang sudah dikumpulkan.
5. Lakukan Anotasi: Buat kotak pembatas (*bounding box*) pada setiap kupu kaper yang tampak di foto, lalu beri label kelas: **`kaper`**.
6. Setelah selesai memberi label, klik **Generate Dataset**.
7. Pada menu Export, pilih format: **YOLOv8**.
8. Pilih opsi **download zip to computer** atau salin **Jupyter Notebook Download Code**. Anda akan mendapatkan file `data.yaml` dan folder gambar `train/`, `valid/`.

---

### Tahap 3: Melatih Model di Google Colab (Gratis GPU T4)
1. Buka [https://colab.research.google.com](https://colab.research.google.com) dan buat **New Notebook**.
2. Aktifkan GPU gratis: Menu **Runtime** -> **Change runtime type** -> Pilih **T4 GPU** -> Klik **Save**.
3. Masukkan kode berikut ke dalam cell Colab dan jalankan:

```python
# 1. Install library Ultralytics
!pip install ultralytics

# 2. Upload dataset Anda (atau gunakan kode download dari Roboflow)
# Contoh jika mengunggah file dataset.zip:
!unzip dataset.zip -d dataset/

# 3. Mulai Training dengan YOLOv8-Nano
from ultralytics import YOLO

# Muat arsitektur nano dengan transfer learning
model = YOLO('yolov8n.pt')

# Latih model selama 60 epoch
model.train(
    data='dataset/data.yaml',
    epochs=60,
    imgsz=640,
    batch=16,
    name='kaper_model'
)

# 4. Ekspor ke format ONNX (Format tercepat untuk Raspberry Pi 5)
model.export(format='onnx', optimize=True)
```

4. Proses training hanya memakan waktu sekitar **10–15 menit** di GPU Google Colab.
5. Setelah selesai, unduh file model hasil training:
   - File PyTorch: `runs/detect/kaper_model/weights/best.pt`
   - File ONNX: `runs/detect/kaper_model/weights/best.onnx`

---

### Tahap 4: Memasang Model ke Raspberry Pi 5

Program `kaper_counter_rpi5.py` yang sudah kita buat telah dilengkapi fitur **Auto-Detect Model YOLO**. Anda tidak perlu mengubah kode apapun!

1. Salin file `best.pt` atau `best.onnx` dari laptop ke folder Raspberry Pi:
   ```powershell
   scp best.onnx pi@raspberrypi.local:~/insect_trap/pi_service/kaper_yolo.onnx
   ```
2. Jalankan pengujian di Raspberry Pi via terminal SSH:
   ```bash
   cd ~/insect_trap/pi_service
   python3 kaper_counter_rpi5.py --image static/captures/NODE_01/foto_hama.jpg
   ```
3. Output terminal akan langsung menampilkan:
   ```text
   [RPi5 COUNTER] Model YOLO aktif: /home/pi/insect_trap/pi_service/kaper_yolo.onnx
   [HASIL] Node Pengirim : NODE_01
   [HASIL] Jumlah Kaper  : 5 ekor
   [HASIL] Status Hama   : Waspada
   [HASIL] Waktu Eksekusi: 48.2 ms
   [HASIL] Metode Deteksi: YOLO-DeepLearning
   ```

Selesai! Sistem perangkap hama Anda sekarang berjalan secara pintar menggunakan kecerdasan buatan (*AI Object Detection*) langsung di Raspberry Pi 5.
