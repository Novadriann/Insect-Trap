"""
====================================================================================
ENGINE PENGHITUNG KUPU KAPER - RASPBERRY PI 5 (2GB RAM OPTIMIZED)
Hardware : Raspberry Pi 5 (Cortex-A76 Quad Core @ 2.4 GHz, RAM 2GB)
Fitur    : - Sangat ringan (alokasi RAM < 80 MB, aman untuk varian 2GB)
           - Kecepatan pemrosesan tinggi (inferensi ~30-60 ms per foto 640x480)
           - Membaca kalibrasi otomatis dari 'kaper_config.json' (hasil tuning laptop)
           - Segmentasi adaptif kaper (CLAHE + Adaptive Otsu + Watershed Cluster Split)
           - Filter kontur untuk mengeliminasi debu, serat daun, atau lem perekat
           - Anotasi otomatis Bounding Box, ID serangga (#1, #2), & Evaluasi Ancaman
           - Dukungan modular model Deep Learning YOLO (.onnx / .pt) jika tersedia
Lab ELINS - Universitas Gadjah Mada
====================================================================================
"""

import os
import sys
import json
import time
import argparse
import cv2
import numpy as np

# Lokasi file konfigurasi kalibrasi
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "kaper_config.json")

DEFAULT_CONFIG = {
    "blur_kernel": 5,
    "thresh_offset": 0,
    "min_area": 20,
    "max_area": 30000,
    "min_aspect_ratio": 0.2,
    "max_aspect_ratio": 5.0,
    "use_watershed": True,
    "clahe_clip": 2.5
}


class RaspberryPiKaperCounter:
    """
    Engine penghitung serangga kaper teroptimasi untuk Raspberry Pi 5.
    Mendukung input multi-node (NODE_01, NODE_02).
    """
    def __init__(self, config_path=CONFIG_PATH, yolo_model_path=None):
        self.config_path = config_path
        self.config = self.load_config()
        self.yolo_model = None
        self.yolo_dnn = None
        self.yolo_backend = None
        self.yolo_model_path = yolo_model_path

        # Cari model otomatis jika path tidak ditentukan
        if self.yolo_model_path is None:
            candidates = [
                os.path.join(BASE_DIR, "kaper_yolo.onnx"),
                os.path.join(BASE_DIR, "best.onnx"),
                os.path.join(BASE_DIR, "kaper_yolo.pt"),
                os.path.join(BASE_DIR, "best.pt")
            ]
            for c in candidates:
                if os.path.exists(c):
                    self.yolo_model_path = c
                    break

        if self.yolo_model_path and os.path.exists(self.yolo_model_path):
            # Coba 1: Ultralytics jika library terinstall
            try:
                from ultralytics import YOLO
                self.yolo_model = YOLO(self.yolo_model_path)
                self.yolo_backend = "ultralytics"
                print(f"[RPi5 COUNTER] Model YOLO aktif via Ultralytics: {self.yolo_model_path}")
            except Exception:
                # Coba 2: OpenCV DNN (Native, sangat cepat & ringan untuk RPi5 CPU, tanpa butuh PyTorch)
                if self.yolo_model_path.endswith(".onnx"):
                    try:
                        self.yolo_dnn = cv2.dnn.readNetFromONNX(self.yolo_model_path)
                        self.yolo_backend = "opencv_dnn"
                        print(f"[RPi5 COUNTER] Model YOLO ONNX aktif via OpenCV DNN (Ringan & Cepat): {self.yolo_model_path}")
                    except Exception as e_dnn:
                        print(f"[RPi5 COUNTER] Gagal memuat ONNX via OpenCV DNN ({e_dnn}), fallback ke OpenCV klasik.")

    def load_config(self):
        """Memuat parameter kalibrasi dari kaper_config.json."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    cfg = json.load(f)
                    print(f"[RPi5 COUNTER] Konfigurasi dimuat dari: {self.config_path}")
                    return {**DEFAULT_CONFIG, **cfg}
            except Exception as e:
                print(f"[RPi5 COUNTER] Gagal membaca konfigurasi ({e}), menggunakan default.")
        return DEFAULT_CONFIG.copy()

    def process_image(self, image_path, output_annotated_path=None, node_id="NODE_01"):
        """
        Memproses foto perangkap hama dan menghitung populasi kupu kaper.
        :param image_path: Path gambar asli (JPEG/PNG)
        :param output_annotated_path: Path tujuan penyimpanan foto beranotasi
        :param node_id: ID node pengirim ('NODE_01', 'NODE_02')
        :return: dict hasil perhitungan
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"File gambar tidak ditemukan: {image_path}")

        t_start = time.time()
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Gagal membaca format gambar: {image_path}")

        h_orig, w_orig = img.shape[:2]
        cfg = self.config

        # Jika model YOLO aktif, gunakan model deep learning
        if self.yolo_backend == "ultralytics":
            return self.process_image_yolo(img, image_path, output_annotated_path, node_id, t_start)
        elif self.yolo_backend == "opencv_dnn":
            return self.process_image_yolo_dnn(img, image_path, output_annotated_path, node_id, t_start)

        # 1. Konversi ke Grayscale & Ruang Warna LAB
        # Pada lem kuning, channel b* (Blue-Yellow) membedakan sayap putih/transparan dari latar kuning dengan tajam!
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        _, _, b_channel = cv2.split(lab)

        # a. Deteksi Sayap Putih & Objek Non-Kuning via Channel b*
        b_mean = np.mean(b_channel)
        b_thresh_val = max(130, int(b_mean - 25))
        _, mask_lab = cv2.threshold(b_channel, b_thresh_val, 255, cv2.THRESH_BINARY_INV)

        # b. Deteksi Badan Hitam & Objek Gelap via Grayscale CLAHE
        ksize = int(cfg.get("blur_kernel", 5))
        if ksize % 2 == 0:
            ksize += 1
        ksize = max(1, ksize)
        blurred = cv2.GaussianBlur(gray, (ksize, ksize), 0)

        clip = float(cfg.get("clahe_clip", 2.5))
        clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8))
        enhanced = clahe.apply(blurred)

        offset = int(cfg.get("thresh_offset", 0))
        if offset != 0:
            thresh_val = np.mean(enhanced) + offset
            thresh_val = np.clip(thresh_val, 10, 245)
            _, mask_dark = cv2.threshold(enhanced, int(thresh_val), 255, cv2.THRESH_BINARY_INV)
        else:
            _, mask_dark = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # c. Fusi Masker (Menggabungkan sayap putih + badan hitam)
        combined_mask = cv2.bitwise_or(mask_lab, mask_dark)

        # 4. Operasi Morfologi (Closing 5x5 menyatukan sayap putih dan badan hitam menjadi 1 tubuh utuh)
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        bin_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel_close, iterations=2)
        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        bin_mask = cv2.morphologyEx(bin_mask, cv2.MORPH_OPEN, kernel_open, iterations=1)

        # 5. Pemisahan Serangga Berdekatan (Watershed Segmentation)
        detected_insects = []
        use_watershed = cfg.get("use_watershed", True)

        if use_watershed:
            dist_transform = cv2.distanceTransform(bin_mask, cv2.DIST_L2, 5)
            max_val = dist_transform.max()
            sure_fg_thresh = 0.35 * max_val if max_val > 0 else 0
            _, sure_fg = cv2.threshold(dist_transform, sure_fg_thresh, 255, 0)
            sure_fg = np.uint8(sure_fg)

            sure_bg = cv2.dilate(bin_mask, kernel_open, iterations=2)
            unknown = cv2.subtract(sure_bg, sure_fg)

            _, markers = cv2.connectedComponents(sure_fg)
            markers = markers + 1
            markers[unknown == 255] = 0

            img_ws = img.copy()
            markers = cv2.watershed(img_ws, markers)

            unique_markers = np.unique(markers)
            for m in unique_markers:
                if m <= 1:
                    continue
                mask_m = np.uint8(markers == m) * 255
                cnts, _ = cv2.findContours(mask_m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for cnt in cnts:
                    area = cv2.contourArea(cnt)
                    if cfg["min_area"] <= area <= cfg["max_area"]:
                        x, y, bw, bh = cv2.boundingRect(cnt)
                        aspect = float(bw) / bh if bh > 0 else 0
                        if cfg["min_aspect_ratio"] <= aspect <= cfg["max_aspect_ratio"]:
                            detected_insects.append({
                                "x": int(x), "y": int(y),
                                "width": int(bw), "height": int(bh),
                                "area": float(area)
                            })
        else:
            contours, _ = cv2.findContours(bin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if cfg["min_area"] <= area <= cfg["max_area"]:
                    x, y, bw, bh = cv2.boundingRect(cnt)
                    aspect = float(bw) / bh if bh > 0 else 0
                    if cfg["min_aspect_ratio"] <= aspect <= cfg["max_aspect_ratio"]:
                        detected_insects.append({
                            "x": int(x), "y": int(y),
                            "width": int(bw), "height": int(bh),
                            "area": float(area)
                        })

        # Urutkan koordinat agar penomoran rapi
        detected_insects.sort(key=lambda item: (item["y"], item["x"]))

        # 6. Gambar Anotasi (Bounding Box Hijau & Penomoran)
        annotated_img = img.copy()
        for idx, ins in enumerate(detected_insects, 1):
            ins["id"] = idx
            x, y, bw, bh = ins["x"], ins["y"], ins["width"], ins["height"]
            cv2.rectangle(annotated_img, (x, y), (x + bw, y + bh), (0, 255, 0), 2)
            cv2.circle(annotated_img, (x + bw // 2, y + bh // 2), 3, (0, 0, 255), -1)
            cv2.putText(annotated_img, f"#{idx}", (x, max(14, y - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)

        total_count = len(detected_insects)

        # 7. Evaluasi Status Ambang Batas Populasi Kaper
        if total_count < 5:
            threat_level = "Aman"
            status_color = (0, 200, 0) # Hijau
        elif total_count <= 15:
            threat_level = "Waspada"
            status_color = (0, 165, 255) # Oranye
        else:
            threat_level = "Bahaya"
            status_color = (0, 0, 255) # Merah

        # 8. Banner Informasi di Atas Gambar
        overlay = annotated_img.copy()
        cv2.rectangle(overlay, (0, 0), (w_orig, 40), (25, 25, 25), -1)
        cv2.addWeighted(overlay, 0.75, annotated_img, 0.25, 0, annotated_img)

        banner_text = f"[{node_id}] Kaper: {total_count} Ekor | Status: {threat_level}"
        cv2.putText(annotated_img, banner_text, (10, 27),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2, cv2.LINE_AA)

        # 9. Simpan Hasil Gambar Beranotasi
        if output_annotated_path:
            out_dir = os.path.dirname(output_annotated_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            cv2.imwrite(output_annotated_path, annotated_img)

        proc_time_ms = (time.time() - t_start) * 1000.0

        return {
            "node_id": node_id,
            "total_count": total_count,
            "threat_level": threat_level,
            "process_time_ms": round(proc_time_ms, 1),
            "insects": detected_insects,
            "annotated_image_path": output_annotated_path,
            "method": "RPi5-OpenCV-Watershed"
        }

    def process_image_yolo(self, img, image_path, output_annotated_path, node_id, t_start):
        """Inferensi menggunakan model Deep Learning YOLO (PyTorch/ONNX)."""
        results = self.yolo_model.predict(source=img, conf=0.35, verbose=False)
        res = results[0]

        annotated_img = res.plot()
        h_orig, w_orig = img.shape[:2]
        total_count = len(res.boxes)

        detected_insects = []
        for idx, box in enumerate(res.boxes, 1):
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            detected_insects.append({
                "id": idx,
                "x": int(x1), "y": int(y1),
                "width": int(x2 - x1), "height": int(y2 - y1),
                "confidence": round(conf, 2)
            })

        if total_count < 5:
            threat_level = "Aman"
            status_color = (0, 200, 0)
        elif total_count <= 15:
            threat_level = "Waspada"
            status_color = (0, 165, 255)
        else:
            threat_level = "Bahaya"
            status_color = (0, 0, 255)

        overlay = annotated_img.copy()
        cv2.rectangle(overlay, (0, 0), (w_orig, 40), (25, 25, 25), -1)
        cv2.addWeighted(overlay, 0.75, annotated_img, 0.25, 0, annotated_img)

        banner_text = f"[{node_id}] YOLO Kaper: {total_count} Ekor | Status: {threat_level}"
        cv2.putText(annotated_img, banner_text, (10, 27),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2, cv2.LINE_AA)

        if output_annotated_path:
            out_dir = os.path.dirname(output_annotated_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            cv2.imwrite(output_annotated_path, annotated_img)

        proc_time_ms = (time.time() - t_start) * 1000.0

        return {
            "node_id": node_id,
            "total_count": total_count,
            "threat_level": threat_level,
            "process_time_ms": round(proc_time_ms, 1),
            "insects": detected_insects,
            "annotated_image_path": output_annotated_path,
            "method": "YOLO-Ultralytics"
        }

    def process_image_yolo_dnn(self, img, image_path, output_annotated_path, node_id, t_start):
        """Inferensi ONNX menggunakan OpenCV DNN (Sangat cepat, efisien, tanpa butuh PyTorch/Ultralytics)."""
        h_orig, w_orig = img.shape[:2]

        # 1. Preprocessing input YOLOv8 (640x640, float32 [0, 1], swap RB)
        blob = cv2.dnn.blobFromImage(img, 1.0 / 255.0, (640, 640), swapRB=True, crop=False)
        self.yolo_dnn.setInput(blob)
        preds = self.yolo_dnn.forward()  # Shape: (1, 5, 8400) untuk 1 kelas

        # 2. Reshape: squeeze batch -> transpose jadi (8400, 5)
        preds = np.squeeze(preds, axis=0).T

        x_factor = w_orig / 640.0
        y_factor = h_orig / 640.0

        boxes = []
        confidences = []

        # 3. Filter kandidat box dengan confidence threshold
        conf_thresh = 0.35
        for row in preds:
            conf = float(row[4])
            if conf >= conf_thresh:
                cx, cy, w, h = float(row[0]), float(row[1]), float(row[2]), float(row[3])
                x1 = int((cx - 0.5 * w) * x_factor)
                y1 = int((cy - 0.5 * h) * y_factor)
                bw = int(w * x_factor)
                bh = int(h * y_factor)
                boxes.append([x1, y1, bw, bh])
                confidences.append(conf)

        # 4. Non-Maximum Suppression (NMS) untuk membuang kotak ganda
        indices = cv2.dnn.NMSBoxes(boxes, confidences, score_threshold=conf_thresh, nms_threshold=0.45)

        annotated_img = img.copy()
        detected_insects = []

        if len(indices) > 0:
            # Flatten jika array 2D
            flat_indices = indices.flatten() if hasattr(indices, 'flatten') else [i[0] for i in indices]
            for idx, i in enumerate(flat_indices, 1):
                x, y, bw, bh = boxes[i]
                conf = confidences[i]
                x1, y1 = max(0, x), max(0, y)
                x2, y2 = min(w_orig, x + bw), min(h_orig, y + bh)

                detected_insects.append({
                    "id": idx,
                    "x": int(x1), "y": int(y1),
                    "width": int(x2 - x1), "height": int(y2 - y1),
                    "confidence": round(conf, 2)
                })

                # Gambar kotak pembatas Bounding Box & Label
                box_color = (0, 255, 0)
                cv2.rectangle(annotated_img, (x1, y1), (x2, y2), box_color, 2)
                lbl_text = f"#{idx} Kaper {int(conf * 100)}%"
                (tw, th), _ = cv2.getTextSize(lbl_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                cv2.rectangle(annotated_img, (x1, max(0, y1 - th - 6)), (x1 + tw + 4, y1), box_color, -1)
                cv2.putText(annotated_img, lbl_text, (x1 + 2, max(th + 2, y1 - 3)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)

        total_count = len(detected_insects)

        # Evaluasi Ambang Batas Ancaman Hama
        if total_count < 5:
            threat_level = "Aman"
            status_color = (0, 200, 0)
        elif total_count <= 15:
            threat_level = "Waspada"
            status_color = (0, 165, 255)
        else:
            threat_level = "Bahaya"
            status_color = (0, 0, 255)

        # Banner status di bagian atas gambar
        overlay = annotated_img.copy()
        cv2.rectangle(overlay, (0, 0), (w_orig, 40), (25, 25, 25), -1)
        cv2.addWeighted(overlay, 0.75, annotated_img, 0.25, 0, annotated_img)

        banner_text = f"[{node_id}] YOLO ONNX Kaper: {total_count} Ekor | Status: {threat_level}"
        cv2.putText(annotated_img, banner_text, (10, 27),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2, cv2.LINE_AA)

        if output_annotated_path:
            out_dir = os.path.dirname(output_annotated_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            cv2.imwrite(output_annotated_path, annotated_img)

        proc_time_ms = (time.time() - t_start) * 1000.0

        return {
            "node_id": node_id,
            "total_count": total_count,
            "threat_level": threat_level,
            "process_time_ms": round(proc_time_ms, 1),
            "insects": detected_insects,
            "annotated_image_path": output_annotated_path,
            "method": "YOLOv8-OpenCV-DNN"
        }


# ====================================================================================
# MODE PENGUJIAN MANDIRI DI TERMINAL RASPBERRY PI 5 (SSH CLI)
# ====================================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Raspberry Pi 5 Kaper Counter")
    parser.add_argument("--image", type=str, help="Path gambar foto perangkap hama")
    parser.add_argument("--node", type=str, default="NODE_01", help="ID Node (NODE_01 atau NODE_02)")
    parser.add_argument("--out", type=str, default=None, help="Path output foto teranotasi")

    args = parser.parse_args()
    counter = RaspberryPiKaperCounter()

    test_img = args.image
    if not test_img:
        # Coba gunakan sampel yang tersedia
        sample_candidates = [
            os.path.join(BASE_DIR, "static", "captures", "sample.jpg"),
            os.path.join(BASE_DIR, "..", "..", "4_Receiver_ESP32_Standalone", "hasil_foto", "hama_20260910_121458.jpg")
        ]
        for s in sample_candidates:
            if os.path.exists(s):
                test_img = s
                break

    if test_img and os.path.exists(test_img):
        out_path = args.out or os.path.join(BASE_DIR, "test_rpi5_annotated.jpg")
        print("==================================================================")
        print(f"  RASPBERRY PI 5: PENGUJIAN PENGHITUNG KUPU KAPER [{args.node}]")
        print(f"  File Masukan : {test_img}")
        print("==================================================================")

        res = counter.process_image(test_img, out_path, node_id=args.node)
        print(f"[HASIL] Node Pengirim : {res['node_id']}")
        print(f"[HASIL] Jumlah Kaper  : {res['total_count']} ekor")
        print(f"[HASIL] Status Hama   : {res['threat_level']}")
        print(f"[HASIL] Waktu Eksekusi: {res['process_time_ms']} ms")
        print(f"[HASIL] Foto Tersimpan: {res['annotated_image_path']}")
        print("==================================================================\n")
    else:
        print("[!] Tentukan path gambar dengan: python kaper_counter_rpi5.py --image <path_foto.jpg>")
