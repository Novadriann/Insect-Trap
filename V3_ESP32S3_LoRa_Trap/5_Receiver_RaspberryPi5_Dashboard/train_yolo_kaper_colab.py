"""
====================================================================================
SKRIP TRAINING MODEL YOLOv8-NANO UNTUK KUPU KAPER (GOOGLE COLAB / LAPTOP GPU)
Tujuan   : Menghasilkan model deteksi 'best.pt' dan 'best.onnx' untuk Raspberry Pi 5
Model    : YOLOv8 Nano (yolov8n) - Sangat cepat & efisien di CPU ARM Cortex-A76 Pi 5
Lab ELINS - Universitas Gadjah Mada
====================================================================================

PETUNJUK CEPAT DI GOOGLE COLAB (GRATIS GPU T4):
1. Buka https://colab.research.google.com
2. Ubah runtime ke GPU: Runtime -> Change runtime type -> T4 GPU
3. Salin dan jalankan seluruh kode di bawah ini per blok cell.
"""

# LANGKAH 1: Instalasi Library Ultralytics (YOLOv8)
# Di Colab jalankan: !pip install ultralytics
import os
from ultralytics import YOLO

def main():
    print("==================================================================")
    print("  MEMULAI PROSES TRAINING YOLOv8-NANO DETEKSI KUPU KAPER")
    print("==================================================================")

    # ------------------------------------------------------------------
    # LANGKAH 2: SIAPKAN DATASET
    # ------------------------------------------------------------------
    # Disarankan membuat anotasi dataset kaper di https://roboflow.com (Gratis)
    # Format Ekspor Roboflow: YOLOv8
    # Hasil download berupa folder berisi file 'data.yaml', folder 'train/', 'valid/'
    
    DATA_YAML = "data.yaml"  # Ganti sesuai path data.yaml dari dataset Anda

    # Cek ketersediaan file dataset
    if not os.path.exists(DATA_YAML):
        print(f"[WARNING] File '{DATA_YAML}' tidak ditemukan!")
        print("Pastikan Anda sudah mengunggah dataset berformat YOLOv8 yang berisi 'data.yaml'.")
        print("\nContoh struktur dataset:")
        print("dataset/")
        print("  ├── data.yaml")
        print("  ├── train/images/ & train/labels/")
        print("  └── valid/images/ & valid/labels/")
        return

    # ------------------------------------------------------------------
    # LANGKAH 3: MEMUAT PRETRAINED MODEL YOLOV8 NANO
    # ------------------------------------------------------------------
    # Menggunakan yolov8n.pt (pretrained weights COCO) untuk transfer learning
    print("[*] Memuat base weights yolov8n.pt...")
    model = YOLO("yolov8n.pt")

    # ------------------------------------------------------------------
    # LANGKAH 4: PROSES TRAINING
    # ------------------------------------------------------------------
    # Parameter optimal untuk dataset kaper (50 - 200 gambar):
    # - epochs : 50 s/d 100 epoch (cukup untuk mencapai mAP > 0.85)
    # - imgsz  : 640 (sesuai resolusi kamera ESP32-S3)
    # - batch  : 16
    print("[*] Memulai fine-tuning training model...")
    model.train(
        data=DATA_YAML,
        epochs=60,
        imgsz=640,
        batch=16,
        device=0,          # Gunakan 0 untuk GPU, atau 'cpu' jika di laptop tanpa GPU
        workers=2,
        name="kaper_detector_v1"
    )

    # ------------------------------------------------------------------
    # LANGKAH 5: VALIDASI & EVALUASI HASIL
    # ------------------------------------------------------------------
    print("\n[*] Menjalankan evaluasi akurasi model...")
    metrics = model.val()
    print(f"[HASIL EVALUASI] mAP 50-95: {metrics.box.map:.4f}")
    print(f"[HASIL EVALUASI] mAP 50   : {metrics.box.map50:.4f}")

    # ------------------------------------------------------------------
    # LANGKAH 6: EKSPOR KE FORMAT ONNX UNTUK RASPBERRY PI 5
    # ------------------------------------------------------------------
    # Format ONNX berjalan hingga 2x lebih kencang di CPU Raspberry Pi 5 dibanding PyTorch
    print("\n[*] Mengekspor model ke format ONNX (Sangat optimal untuk CPU ARM Pi 5)...")
    onnx_file = model.export(format="onnx", imgsz=640, optimize=True)
    print(f"[SUKSES] File ONNX berhasil dibuat: {onnx_file}")

    print("\n==================================================================")
    print("  CARA MEMASANG KE RASPBERRY PI 5:")
    print("  1. Unduh file 'best.pt' atau 'best.onnx' hasil training di atas")
    print("  2. Salin file tersebut ke folder Raspberry Pi 5:")
    print("     pi_service/kaper_yolo.onnx  (atau pi_service/best.pt)")
    print("  3. Selesai! Program 'kaper_counter_rpi5.py' akan OTOMATIS mendeteksi")
    print("     dan beralih menggunakan model YOLO ini.")
    print("==================================================================\n")


if __name__ == "__main__":
    main()
