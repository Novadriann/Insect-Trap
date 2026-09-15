import json
import os

notebook = {
    "nbformat": 4,
    "nbformat_minor": 0,
    "metadata": {
        "accelerator": "GPU",
        "colab": {"provenance": []},
        "kernelspec": {"display_name": "Python 3", "name": "python3"},
        "language_info": {"name": "python"}
    },
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# 🦋 Training Model YOLOv8-Nano Deteksi Kupu Kaper\n",
                "**Sistem Pemantauan Perangkap Hama (Insect Trap) - Lab ELINS UGM**\n",
                "\n",
                "Notebook ini melatih model Deep Learning **YOLOv8-Nano** untuk mendeteksi hama kupu kaper (*Spodoptera exigua*) dan mengekspornya ke format **ONNX** yang siap dipasang langsung di **Raspberry Pi 5**.\n",
                "\n",
                "---\n",
                "### ⚠️ PENTING: Aktifkan Akselerasi GPU Gratis\n",
                "Pastikan runtime Colab Anda menggunakan **GPU T4**:\n",
                "1. Klik menu **Runtime** di atas -> **Change runtime type**.\n",
                "2. Pilih **T4 GPU** -> Klik **Save**."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# ==============================================================================\n",
                "# 1. CEK GPU & INSTALL ULTRALYTICS (YOLOv8)\n",
                "# ==============================================================================\n",
                "!nvidia-smi\n",
                "\n",
                "!pip install ultralytics"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "---\n",
                "### 📦 Upload Dataset\n",
                "1. Klik ikon **Folder** (Files) di panel sebelah kiri Google Colab.\n",
                "2. Upload file **`dataset_kaper_yolo.zip`** yang sudah disiapkan.\n",
                "3. Jalankan cell di bawah ini untuk mengekstrak dataset."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# ==============================================================================\n",
                "# 2. EKSTRAK DATASET KAPER\n",
                "# ==============================================================================\n",
                "import os, glob, shutil, random\n",
                "\n",
                "# Cek apakah dataset sudah diekstrak sebelumnya\n",
                "if not os.path.exists('dataset/data.yaml'):\n",
                "    # Cari file zip yang relevan\n",
                "    zip_candidates = glob.glob('*kaper*.zip') + glob.glob('*dataset*.zip') + glob.glob('*.zip')\n",
                "    \n",
                "    if not zip_candidates:\n",
                "        print('[!] File dataset zip belum ditemukan di Colab.')\n",
                "        print('>>> Silakan klik tombol \"Choose Files\" di bawah ini untuk memilih file dataset_kaper_yolo.zip dari laptop Anda:')\n",
                "        from google.colab import files\n",
                "        uploaded = files.upload()\n",
                "        zip_candidates = glob.glob('*.zip')\n",
                "\n",
                "    kaper_zips = [f for f in zip_candidates if 'dataset_kaper_yolo' in f.lower()]\n",
                "    if kaper_zips:\n",
                "        target = kaper_zips[0]\n",
                "        print(f'[*] Mengekstrak {target}...')\n",
                "        !unzip -q -o \"$target\"\n",
                "        print('[OK] Ekstraksi dataset selesai!')\n",
                "    elif os.path.exists('kaper-dataset1.zip') and os.path.exists('Training Dataset.zip'):\n",
                "        print('[*] Menggabungkan file gambar dan anotasi dari CVAT...')\n",
                "        !unzip -q -o 'Training Dataset.zip' -d temp_img/\n",
                "        !unzip -q -o 'kaper-dataset1.zip' -d temp_ann/\n",
                "        for split in ['train', 'val']:\n",
                "            os.makedirs(f'dataset/{split}/images', exist_ok=True)\n",
                "            os.makedirs(f'dataset/{split}/labels', exist_ok=True)\n",
                "        raw_imgs = glob.glob('temp_img/**/*.jpg', recursive=True) + glob.glob('temp_img/**/*.png', recursive=True)\n",
                "        random.seed(42)\n",
                "        random.shuffle(raw_imgs)\n",
                "        split_idx = int(len(raw_imgs) * 0.8)\n",
                "        for i, img_path in enumerate(raw_imgs):\n",
                "            sp = 'train' if i < split_idx else 'val'\n",
                "            base = os.path.splitext(os.path.basename(img_path))[0]\n",
                "            shutil.copy(img_path, f'dataset/{sp}/images/')\n",
                "            lbl = glob.glob(f'temp_ann/**/{base}.txt', recursive=True)\n",
                "            if lbl:\n",
                "                shutil.copy(lbl[0], f'dataset/{sp}/labels/{base}.txt')\n",
                "        with open('dataset/data.yaml', 'w') as f:\n",
                "            f.write('path: /content/dataset\\ntrain: train/images\\nval: val/images\\n\\nnames:\\n  0: Kaper\\n')\n",
                "        print('[OK] Penggabungan dataset CVAT berhasil!')\n",
                "    else:\n",
                "        print('[!] File dataset_kaper_yolo.zip tidak ditemukan. Silakan upload file tersebut ke panel kiri Colab!')\n",
                "\n",
                "# Pastikan konfigurasi path absolut untuk Ultralytics\n",
                "if os.path.exists('dataset/data.yaml'):\n",
                "    with open('dataset/data.yaml', 'r') as f:\n",
                "        cfg = f.read()\n",
                "    if 'path: dataset' in cfg:\n",
                "        cfg = cfg.replace('path: dataset', 'path: /content/dataset')\n",
                "        with open('dataset/data.yaml', 'w') as f:\n",
                "            f.write(cfg)\n",
                "    train_count = len(glob.glob('dataset/train/images/*'))\n",
                "    val_count = len(glob.glob('dataset/val/images/*'))\n",
                "    print(f'\\n📊 Dataset Siap: Training = {train_count} gambar, Validasi = {val_count} gambar')\n",
                "    !cat dataset/data.yaml\n",
                "else:\n",
                "    print('\\n❌ Error: Folder dataset/ belum berhasil terbentuk!')"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "---\n",
                "### 🚀 Mulai Training Model YOLOv8-Nano\n",
                "Proses fine-tuning transfer learning akan berlangsung sekitar 5–10 menit di GPU T4."
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# ==============================================================================\n",
                "# 3. TRAINING YOLOV8-NANO\n",
                "# ==============================================================================\n",
                "from ultralytics import YOLO\n",
                "\n",
                "# Muat model dasar nano pretrained COCO\n",
                "model = YOLO('yolov8n.pt')\n",
                "\n",
                "# Jalankan training\n",
                "results = model.train(\n",
                "    data='dataset/data.yaml',\n",
                "    epochs=80,\n",
                "    imgsz=640,\n",
                "    batch=8,\n",
                "    device=0,\n",
                "    workers=2,\n",
                "    name='kaper_detector'\n",
                ")\n",
                "\n",
                "print('\\n[SELESAI!] Training berhasil diselesaikan!')"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "---\n",
                "### 📈 Evaluasi Akurasi & Grafik Hasil Training"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# ==============================================================================\n",
                "# 4. VISUALISASI METRIK AKURASI & HASIL PREDIKSI\n",
                "# ==============================================================================\n",
                "from IPython.display import Image, display\n",
                "import glob\n",
                "\n",
                "print('Grafik Metrik Training (Loss, Precision, Recall, mAP):')\n",
                "if os.path.exists('runs/detect/kaper_detector/results.png'):\n",
                "    display(Image('runs/detect/kaper_detector/results.png', width=800))\n",
                "\n",
                "print('\\nContoh Hasil Deteksi Bounding Box pada Gambar Validasi:')\n",
                "val_preds = glob.glob('runs/detect/kaper_detector/val_batch*_pred.jpg')\n",
                "for vp in val_preds[:2]:\n",
                "    display(Image(vp, width=800))"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "---\n",
                "### ⚙️ Ekspor Model ke Format ONNX (Untuk Raspberry Pi 5) & Download Otomatis"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "# ==============================================================================\n",
                "# 5. EKSPOR KE ONNX & DOWNLOAD MODEL\n",
                "# ==============================================================================\n",
                "from google.colab import files\n",
                "import glob, os\n",
                "\n",
                "print('[*] Mengekspor model ke format ONNX (Sangat optimal untuk ARM CPU Pi 5)...')\n",
                "onnx_file = model.export(format='onnx', imgsz=640)\n",
                "print(f'[SUKSES] File ONNX dibuat: {onnx_file}')\n",
                "\n",
                "# Cari path bobot best.onnx dan best.pt terbaru\n",
                "best_onnx = onnx_file if os.path.exists(onnx_file) else glob.glob('runs/detect/**/weights/best.onnx', recursive=True)[-1]\n",
                "best_pt = best_onnx.replace('.onnx', '.pt')\n",
                "\n",
                "print('\\n[*] Mengunduh file model ke laptop Anda...')\n",
                "files.download(best_onnx)\n",
                "if os.path.exists(best_pt):\n",
                "    files.download(best_pt)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "---\n",
                "### 🎯 Cara Memasang Model ke Raspberry Pi 5:\n",
                "Setelah file **`best.onnx`** terunduh di laptop Anda:\n",
                "1. Buka PowerShell di laptop Anda, lalu jalankan perintah `scp` ini:\n",
                "   ```powershell\n",
                "   scp best.onnx insect-trap@100.90.201.108:~/5_Receiver_RaspberryPi5_Dashboard/pi_service/kaper_yolo.onnx\n",
                "   ```\n",
                "2. Program `kaper_counter_rpi5.py` di Raspberry Pi 5 akan **otomatis mengenali file `kaper_yolo.onnx`** dan langsung menggunakan AI Deep Learning!"
            ]
        }
    ]
}

paths = [
    r'd:\KULIAH\4. Project Lab ELINS\Pemantauan Hama\Training_YOLO_Kaper_Colab.ipynb',
    r'd:\KULIAH\4. Project Lab ELINS\Pemantauan Hama\Program Insect Trap\V3_ESP32S3_LoRa_Trap\5_Receiver_RaspberryPi5_Dashboard\Training_YOLO_Kaper_Colab.ipynb'
]

for p in paths:
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=2, ensure_ascii=False)
    print('Notebook saved to:', p)
