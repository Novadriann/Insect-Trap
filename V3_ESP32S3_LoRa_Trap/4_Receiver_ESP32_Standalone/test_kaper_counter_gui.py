"""
====================================================================================
PROGRAM TESTING COUNTING KUPU KAPER - LAPTOP / PC (INTERACTIVE GUI & CALIBRATOR)
Fitur :
  1. GUI Interaktif untuk menguji deteksi dan perhitungan hama kupu kaper
  2. Slider parameter tuning real-time (Sensitivitas, Min/Max Area, Blur, Watershed)
  3. Tampilan komparasi Side-by-Side: Hasil Anotasi Bounding Box vs Mask Biner
  4. Algoritma pemisah kluster serangga menempel (Watershed Segmentation)
  5. Ekspor konfigurasi optimal ke 'kaper_config.json' (langsung pakai di RPi 5)
  6. Mendukung mode CLI untuk automated testing di terminal
Lab ELINS - Universitas Gadjah Mada
====================================================================================
"""

import sys
import os
import json
import time
import argparse
import cv2
import numpy as np

# Cek ketersediaan GUI Tkinter & PIL
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    from PIL import Image, ImageTk
    HAS_GUI = True
except ImportError:
    HAS_GUI = False

CONFIG_FILE = "kaper_config.json"

DEFAULT_CONFIG = {
    "blur_kernel": 5,
    "thresh_offset": 0,
    "min_area": 35,
    "max_area": 4500,
    "min_aspect_ratio": 0.25,
    "max_aspect_ratio": 4.0,
    "use_watershed": True,
    "clahe_clip": 2.5
}


class KaperDetector:
    """Engine pengolahan citra untuk segmentasi dan perhitungan kupu kaper."""
    
    def __init__(self, config=None):
        self.config = config if config else DEFAULT_CONFIG.copy()

    def process(self, img_bgr):
        if img_bgr is None:
            return None, None, 0, "Error"

        h, w = img_bgr.shape[:2]
        cfg = self.config

        # 1. Konversi Warna & Preprocessing
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # Blur untuk reduksi bintik noise
        ksize = int(cfg.get("blur_kernel", 5))
        if ksize % 2 == 0:
            ksize += 1
        ksize = max(1, ksize)
        blurred = cv2.GaussianBlur(gray, (ksize, ksize), 0)

        # 2. Peningkatan Kontras Adaptif (CLAHE)
        # Membantu mengangkat kontras sayap kaper abu/putih terhadap latar
        clip = float(cfg.get("clahe_clip", 2.5))
        clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8))
        enhanced = clahe.apply(blurred)

        # 3. Thresholding Adaptif / Otsu dengan Offset
        # Mengisolasi objek kaper dari latar lem perekat
        _, otsu_thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        offset = int(cfg.get("thresh_offset", 0))
        if offset != 0:
            # Sesuaikan nilai threshold dengan offset user
            thresh_val = np.mean(enhanced) + offset
            thresh_val = np.clip(thresh_val, 10, 245)
            _, bin_mask = cv2.threshold(enhanced, int(thresh_val), 255, cv2.THRESH_BINARY_INV)
        else:
            bin_mask = otsu_thresh

        # 4. Operasi Morfologi (Membersihkan debu halus & merapatkan badan kaper)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        bin_mask = cv2.morphologyEx(bin_mask, cv2.MORPH_OPEN, kernel, iterations=1)
        bin_mask = cv2.morphologyEx(bin_mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        # 5. Pemisahan Kluster Serangga (Watershed) jika diaktifkan
        detected_boxes = []
        use_watershed = cfg.get("use_watershed", True)

        if use_watershed:
            # Hitung distance transform
            dist_transform = cv2.distanceTransform(bin_mask, cv2.DIST_L2, 5)
            # Threshold untuk menemukan inti tubuh setiap serangga
            _, sure_fg = cv2.threshold(dist_transform, 0.35 * dist_transform.max() if dist_transform.max() > 0 else 0, 255, 0)
            sure_fg = np.uint8(sure_fg)

            # Area yang tidak diketahui
            sure_bg = cv2.dilate(bin_mask, kernel, iterations=2)
            unknown = cv2.subtract(sure_bg, sure_fg)

            # Marker labelling
            _, markers = cv2.connectedComponents(sure_fg)
            markers = markers + 1
            markers[unknown == 255] = 0

            # Jalankan Watershed
            img_ws = img_bgr.copy()
            markers = cv2.watershed(img_ws, markers)

            # Ekstrak kontur dari marker watershed
            unique_markers = np.unique(markers)
            for m in unique_markers:
                if m <= 1:  # 0 = boundary, 1 = background
                    continue
                mask_m = np.uint8(markers == m) * 255
                cnts, _ = cv2.findContours(mask_m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for cnt in cnts:
                    area = cv2.contourArea(cnt)
                    if cfg["min_area"] <= area <= cfg["max_area"]:
                        x, y, bw, bh = cv2.boundingRect(cnt)
                        aspect = float(bw) / bh if bh > 0 else 0
                        if cfg["min_aspect_ratio"] <= aspect <= cfg["max_aspect_ratio"]:
                            detected_boxes.append((x, y, bw, bh, area))
        else:
            # Kontur standar
            contours, _ = cv2.findContours(bin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if cfg["min_area"] <= area <= cfg["max_area"]:
                    x, y, bw, bh = cv2.boundingRect(cnt)
                    aspect = float(bw) / bh if bh > 0 else 0
                    if cfg["min_aspect_ratio"] <= aspect <= cfg["max_aspect_ratio"]:
                        detected_boxes.append((x, y, bw, bh, area))

        # 6. Gambar Anotasi
        annotated = img_bgr.copy()
        count = len(detected_boxes)

        # Urutkan dari atas ke bawah untuk penomoran teratur
        detected_boxes.sort(key=lambda b: (b[1], b[0]))

        for idx, (x, y, bw, bh, area) in enumerate(detected_boxes, 1):
            # Kotak pembatas serangga
            cv2.rectangle(annotated, (x, y), (x + bw, y + bh), (0, 255, 0), 2)
            # Titik pusat
            cx, cy = x + bw // 2, y + bh // 2
            cv2.circle(annotated, (cx, cy), 3, (0, 0, 255), -1)
            # Label nomor
            cv2.putText(annotated, f"#{idx}", (x, max(14, y - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)

        # Evaluasi Tingkat Ancaman Populasi Kaper
        if count < 5:
            threat = "Aman"
            color = (0, 200, 0)
        elif count <= 15:
            threat = "Waspada"
            color = (0, 165, 255)
        else:
            threat = "Bahaya"
            color = (0, 0, 255)

        # Banner Header Status
        overlay = annotated.copy()
        cv2.rectangle(overlay, (0, 0), (w, 38), (30, 30, 30), -1)
        cv2.addWeighted(overlay, 0.75, annotated, 0.25, 0, annotated)

        info_str = f"Kaper Terhitung: {count} Ekor | Status: {threat}"
        cv2.putText(annotated, info_str, (12, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.68, color, 2, cv2.LINE_AA)

        # Mask visual (3 channel untuk ditampilkan)
        mask_vis = cv2.cvtColor(bin_mask, cv2.COLOR_GRAY2BGR)

        return annotated, mask_vis, count, threat


# ====================================================================================
# APLIKASI GUI TKINTER
# ====================================================================================
class KaperTuningApp:
    def __init__(self, root, initial_image=None):
        self.root = root
        self.root.title("Testing & Calibrator Penghitung Kupu Kaper (Insect Trap) - Lab ELINS")
        self.root.geometry("1200x780")
        self.root.minsize(950, 650)

        self.config = self.load_config()
        self.detector = KaperDetector(self.config)

        self.current_image_path = initial_image
        self.img_bgr = None
        self.annotated_bgr = None
        self.mask_bgr = None

        self.create_widgets()

        if self.current_image_path and os.path.exists(self.current_image_path):
            self.load_image(self.current_image_path)
        else:
            # Coba cari sampel otomatis
            auto_samples = [
                "kaper_sample.png",
                "hasil_foto/hama_20260911_111854.jpg",
                "hasil_foto/NODE_01/hama_NODE_01_20260911_111854.jpg"
            ]
            for s in auto_samples:
                if os.path.exists(s):
                    self.load_image(s)
                    break

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    cfg = json.load(f)
                    print(f"[*] Berhasil memuat konfigurasi dari {CONFIG_FILE}")
                    return {**DEFAULT_CONFIG, **cfg}
            except Exception:
                pass
        return DEFAULT_CONFIG.copy()

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config, f, indent=4)
            messagebox.showinfo("Sukses", f"Konfigurasi berhasil disimpan ke '{CONFIG_FILE}'.\n\nFile ini siap disalin ke Raspberry Pi 5!")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal menyimpan konfigurasi: {e}")

    def create_widgets(self):
        # Frame Kontrol Atas (Tombol)
        top_frame = ttk.Frame(self.root, padding=8)
        top_frame.pack(fill=tk.X, side=tk.TOP)

        btn_open = ttk.Button(top_frame, text="📂 Buka File Gambar...", command=self.browse_image)
        btn_open.pack(side=tk.LEFT, padx=5)

        btn_save_cfg = ttk.Button(top_frame, text="💾 Simpan Konfigurasi (JSON)", command=self.save_config)
        btn_save_cfg.pack(side=tk.LEFT, padx=5)

        btn_save_img = ttk.Button(top_frame, text="🖼️ Simpan Hasil Deteksi...", command=self.save_annotated_image)
        btn_save_img.pack(side=tk.LEFT, padx=5)

        btn_reset = ttk.Button(top_frame, text="🔄 Reset Default", command=self.reset_default)
        btn_reset.pack(side=tk.LEFT, padx=5)

        self.lbl_path = ttk.Label(top_frame, text="Belum ada gambar yang dipilih", foreground="#555")
        self.lbl_path.pack(side=tk.LEFT, padx=15)

        # Paned Window Utama (Kiri: Slider Tuning, Kanan: Preview Gambar)
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=5)

        # --- PANEL KIRI: SLIDER TUNING PARAMETER ---
        control_frame = ttk.LabelFrame(main_paned, text=" Parameter Kalibrasi Deteksi ", padding=10)
        main_paned.add(control_frame, weight=1)

        # 1. Sensitivitas Threshold Offset
        ttk.Label(control_frame, text="Sensitivitas / Offset Ambang (-50 s/d +50):").pack(anchor=tk.W, pady=(5, 0))
        self.slider_offset = tk.Scale(control_frame, from_=-50, to=50, orient=tk.HORIZONTAL,
                                      command=self.on_param_change)
        self.slider_offset.set(self.config.get("thresh_offset", 0))
        self.slider_offset.pack(fill=tk.X, pady=(0, 8))

        # 2. Batas Minimum Ukuran Serangga (Min Area)
        ttk.Label(control_frame, text="Batas Min Luas Kaper (Piksel - Hilangkan debu):").pack(anchor=tk.W)
        self.slider_min_area = tk.Scale(control_frame, from_=5, to=300, orient=tk.HORIZONTAL,
                                        command=self.on_param_change)
        self.slider_min_area.set(self.config.get("min_area", 35))
        self.slider_min_area.pack(fill=tk.X, pady=(0, 8))

        # 3. Batas Maksimum Ukuran (Max Area)
        ttk.Label(control_frame, text="Batas Max Luas Kaper (Piksel - Abaikan noda besar):").pack(anchor=tk.W)
        self.slider_max_area = tk.Scale(control_frame, from_=500, to=10000, orient=tk.HORIZONTAL,
                                        command=self.on_param_change)
        self.slider_max_area.set(self.config.get("max_area", 4500))
        self.slider_max_area.pack(fill=tk.X, pady=(0, 8))

        # 4. Blur Gaussian
        ttk.Label(control_frame, text="Penghalus Derau (Blur Kernel Size):").pack(anchor=tk.W)
        self.slider_blur = tk.Scale(control_frame, from_=1, to=15, resolution=2, orient=tk.HORIZONTAL,
                                    command=self.on_param_change)
        self.slider_blur.set(self.config.get("blur_kernel", 5))
        self.slider_blur.pack(fill=tk.X, pady=(0, 8))

        # 5. Kontras CLAHE
        ttk.Label(control_frame, text="Penguat Kontras Sayap (CLAHE Clip):").pack(anchor=tk.W)
        self.slider_clahe = tk.Scale(control_frame, from_=1.0, to=5.0, resolution=0.5, orient=tk.HORIZONTAL,
                                     command=self.on_param_change)
        self.slider_clahe.set(self.config.get("clahe_clip", 2.5))
        self.slider_clahe.pack(fill=tk.X, pady=(0, 8))

        # 6. Checkbox Watershed (Pemisah Kluster Serangga)
        self.var_watershed = tk.BooleanVar(value=self.config.get("use_watershed", True))
        chk_ws = ttk.Checkbutton(control_frame, text="Pisahkan Kaper yang Menempel (Watershed)",
                                 variable=self.var_watershed, command=self.on_param_change)
        chk_ws.pack(anchor=tk.W, pady=(10, 15))

        # Info Ringkas
        desc_box = tk.Text(control_frame, height=9, wrap=tk.WORD, bg="#f9f9f9", fg="#333", relief=tk.SOLID, bd=1)
        desc_box.insert(tk.END, "💡 PETUNJUK TUNING KAPER:\n"
                               "1. Naikkan Min Area jika debu kecil atau noda lem ikut terhitung.\n"
                               "2. Geser Slider Offset jika sayap kaper belum terdeteksi penuh.\n"
                               "3. Aktifkan 'Watershed' agar 2 kupu kaper yang menempel dihitung sebagai 2 ekor terpisah.\n"
                               "4. Klik 'Simpan Konfigurasi' setelah menemukan hasil deteksi paling akurat.")
        desc_box.config(state=tk.DISABLED)
        desc_box.pack(fill=tk.X, pady=(5, 0))

        # --- PANEL KANAN: PREVIEW CITRA (NOTEBOOK TABS) ---
        preview_frame = ttk.Frame(main_paned)
        main_paned.add(preview_frame, weight=3)

        self.notebook = ttk.Notebook(preview_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Anotasi Hasil Deteksi
        self.tab_annotated = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_annotated, text=" 🎯 Hasil Deteksi & Anotasi ")
        self.lbl_img_annotated = ttk.Label(self.tab_annotated, anchor=tk.CENTER)
        self.lbl_img_annotated.pack(fill=tk.BOTH, expand=True)

        # Tab 2: Mask Biner (Proses Thresholding)
        self.tab_mask = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_mask, text=" ⬛ Mask Biner (Segmentasi) ")
        self.lbl_img_mask = ttk.Label(self.tab_mask, anchor=tk.CENTER)
        self.lbl_img_mask.pack(fill=tk.BOTH, expand=True)

        # Status Bar Bawah
        self.status_bar = ttk.Label(self.root, text="Siap. Silakan pilih foto perangkap hama.",
                                    relief=tk.SUNKEN, anchor=tk.W, padding=5)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def browse_image(self):
        filetypes = [
            ("File Gambar", "*.jpg;*.jpeg;*.png;*.bmp"),
            ("Semua File", "*.*")
        ]
        chosen = filedialog.askopenfilename(title="Pilih Gambar Perangkap Hama", filetypes=filetypes)
        if chosen:
            self.load_image(chosen)

    def load_image(self, path):
        if not os.path.exists(path):
            return
        img = cv2.imread(path)
        if img is None:
            messagebox.showerror("Error", f"Gagal membaca gambar dari: {path}")
            return

        self.current_image_path = path
        self.img_bgr = img
        filename = os.path.basename(path)
        self.lbl_path.config(text=f"File: {filename} ({img.shape[1]}x{img.shape[0]} px)")
        self.update_detection()

    def on_param_change(self, *args):
        self.config["thresh_offset"] = int(self.slider_offset.get())
        self.config["min_area"] = int(self.slider_min_area.get())
        self.config["max_area"] = int(self.slider_max_area.get())
        self.config["blur_kernel"] = int(self.slider_blur.get())
        self.config["clahe_clip"] = float(self.slider_clahe.get())
        self.config["use_watershed"] = bool(self.var_watershed.get())

        self.detector.config = self.config
        self.update_detection()

    def update_detection(self):
        if self.img_bgr is None:
            return

        t0 = time.time()
        annotated, mask, count, threat = self.detector.process(self.img_bgr)
        elapsed_ms = (time.time() - t0) * 1000.0

        self.annotated_bgr = annotated
        self.mask_bgr = mask

        self.status_bar.config(
            text=f"Total Hama Terhitung: {count} Ekor | Tingkat Ancaman: {threat} | Waktu Komputasi: {elapsed_ms:.1f} ms"
        )

        self.display_image(self.annotated_bgr, self.lbl_img_annotated)
        self.display_image(self.mask_bgr, self.lbl_img_mask)

    def display_image(self, cv_img, target_label):
        if cv_img is None:
            return

        # Dapatkan ukuran label
        lbl_w = target_label.winfo_width()
        lbl_h = target_label.winfo_height()

        if lbl_w < 50 or lbl_h < 50:
            lbl_w, lbl_h = 750, 520

        h, w = cv_img.shape[:2]
        scale = min(lbl_w / w, lbl_h / h)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))

        resized = cv2.resize(cv_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        rgb_img = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_img)
        img_tk = ImageTk.PhotoImage(pil_img)

        target_label.img_tk = img_tk  # Pertahankan referensi memori
        target_label.config(image=img_tk)

    def save_annotated_image(self):
        if self.annotated_bgr is None:
            messagebox.showwarning("Peringatan", "Belum ada hasil deteksi yang dapat disimpan.")
            return

        save_path = filedialog.asksaveasfilename(
            title="Simpan Gambar Hasil Deteksi",
            defaultextension=".jpg",
            filetypes=[("JPEG Image", "*.jpg"), ("PNG Image", "*.png")]
        )
        if save_path:
            cv2.imwrite(save_path, self.annotated_bgr)
            messagebox.showinfo("Sukses", f"Gambar hasil deteksi disimpan ke:\n{save_path}")

    def reset_default(self):
        self.config = DEFAULT_CONFIG.copy()
        self.slider_offset.set(self.config["thresh_offset"])
        self.slider_min_area.set(self.config["min_area"])
        self.slider_max_area.set(self.config["max_area"])
        self.slider_blur.set(self.config["blur_kernel"])
        self.slider_clahe.set(self.config["clahe_clip"])
        self.var_watershed.set(self.config["use_watershed"])
        self.on_param_change()


# ====================================================================================
# ENTRY POINT & MODE CLI TESTING
# ====================================================================================
def run_cli_test(image_path=None):
    """Menjalankan pengujian penghitung serangga via CLI tanpa tampilan GUI."""
    print("==================================================================")
    print("  CLI TEST: ENGINE PENGHITUNG KUPU KAPER (INSECT COUNTER)")
    print("==================================================================")

    # Cari gambar jika path tidak diberikan
    if not image_path:
        candidates = [
            "kaper_sample.png",
            "hasil_foto/hama_20260911_111854.jpg",
            "../hasil_foto/hama_20260911_111854.jpg"
        ]
        for c in candidates:
            if os.path.exists(c):
                image_path = c
                break

    if not image_path or not os.path.exists(image_path):
        print(f"[ERROR] Gambar tidak ditemukan: {image_path}")
        return False

    print(f"[*] Menguji file: {image_path}")
    img = cv2.imread(image_path)
    if img is None:
        print(f"[ERROR] Gagal memuat file gambar: {image_path}")
        return False

    detector = KaperDetector()
    t0 = time.time()
    annotated, mask, count, threat = detector.process(img)
    dt = (time.time() - t0) * 1000.0

    output_annotated = "test_result_kaper_annotated.jpg"
    cv2.imwrite(output_annotated, annotated)

    print(f"[HASIL] Jumlah Kaper Terdeteksi : {count} ekor")
    print(f"[HASIL] Status Tingkat Ancaman : {threat}")
    print(f"[HASIL] Waktu Pemrosesan Citra : {dt:.2f} ms")
    print(f"[HASIL] File Gambar Tersimpan  : {output_annotated}")

    # Simpan konfigurasi default jika belum ada
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        print(f"[OK] File konfigurasi '{CONFIG_FILE}' dibuat.")

    print("==================================================================\n")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kaper Insect Counter Tester & Calibrator")
    parser.add_argument("--image", type=str, help="Path ke file gambar yang ingin diuji")
    parser.add_argument("--cli", action="store_true", help="Jalankan di terminal mode CLI (tanpa GUI)")
    parser.add_argument("--test-cli", action="store_true", help="Uji otomatis CLI dengan gambar sampel")

    args = parser.parse_args()

    if args.cli or args.test_cli or not HAS_GUI:
        success = run_cli_test(args.image)
        sys.exit(0 if success else 1)
    else:
        root = tk.Tk()
        app = KaperTuningApp(root, args.image)
        root.mainloop()
