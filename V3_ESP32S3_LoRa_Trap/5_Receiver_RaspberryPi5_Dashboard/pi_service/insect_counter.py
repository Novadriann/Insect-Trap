"""
====================================================================================
MODUL PENGHITUNG SERANGGA OTOMATIS (INSECT COUNTER ENGINE)
Fitur    : - Deteksi bercak serangga pada lem perekat feromon menggunakan OpenCV
           - Segmentasi adaptif dengan filter kontur (luas area & sirkularitas)
           - Anotasi otomatis: Kotak pembatas (Bounding Box) & penomoran serangga
           - Evaluasi tingkat ancaman hama (Aman, Waspada, Bahaya)
           - Dukungan modular model Deep Learning YOLOv8 (jika model .pt tersedia)
Lab ELINS - Universitas Gadjah Mada
====================================================================================
"""

import cv2
import numpy as np
import os
import time

class InsectCounter:
    def __init__(self, min_area=20, max_area=2500, yolo_model_path=None):
        """
        Inisialisasi engine penghitung serangga.
        :param min_area: Batas minimum luas kontur piksel (menghilangkan debu kecil)
        :param max_area: Batas maksimum luas kontur piksel (menghilangkan bayangan/tepi kotak)
        :param yolo_model_path: Path opsional ke model YOLO (.pt) jika tersedia
        """
        self.min_area = min_area
        self.max_area = max_area
        self.yolo_model = None

        if yolo_model_path and os.path.exists(yolo_model_path):
            try:
                from ultralytics import YOLO
                self.yolo_model = YOLO(yolo_model_path)
                print(f"[INSECT COUNTER] Berhasil memuat model YOLO: {yolo_model_path}")
            except Exception as e:
                print(f"[INSECT COUNTER] Gagal memuat model YOLO ({e}), menggunakan engine OpenCV.")

    def count_insects_opencv(self, image_path, output_annotated_path=None):
        """
        Menghitung serangga menggunakan computer vision klasik (OpenCV Contours).
        Sangat cepat dan efisien untuk Raspberry Pi 5.
        """
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"Gagal membuka file gambar: {image_path}")

        h_orig, w_orig = img.shape[:2]

        # 1. Konversi ke Grayscale & HSV
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # 2. Reduksi noise dengan Gaussian Blur
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # 3. Segmentasi Threshold Adaptif (Mendeteksi objek serangga gelap di latar perangkap terang)
        # Menggunakan kombinasi Otsu Thresholding dan CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast_enhanced = clahe.apply(blurred)

        # Thresholding inversi (serangga gelap menjadi putih di mask biner)
        _, thresh = cv2.threshold(contrast_enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # 4. Operasi Morfologi (Membersihkan titik debu kecil & menyatukan bagian tubuh serangga)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=1)

        # 5. Deteksi Kontur
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detected_insects = []
        annotated_img = img.copy()

        index = 1
        for cnt in contours:
            area = cv2.contourArea(cnt)

            # Filter kontur berdasarkan batas luas area piksel
            if self.min_area <= area <= self.max_area:
                # Dapatkan koordinat bounding box
                x, y, w, h = cv2.boundingRect(cnt)

                # Filter aspek rasio (mencegah garis memanjang lem atau goresan terhitung)
                aspect_ratio = float(w) / h if h > 0 else 0
                if 0.2 < aspect_ratio < 5.0:
                    detected_insects.append({
                        "id": index,
                        "x": int(x),
                        "y": int(y),
                        "width": int(w),
                        "height": int(h),
                        "area": float(area)
                    })

                    # Gambar kotak pembatas warna hijau terang
                    cv2.rectangle(annotated_img, (x, y), (x + w, y + h), (0, 255, 0), 2)

                    # Beri label nomor serangga
                    label = f"#{index}"
                    cv2.putText(annotated_img, label, (x, max(15, y - 4)), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
                    index += 1

        total_count = len(detected_insects)

        # Tentukan Status Bahaya Populasi Hama
        if total_count < 10:
            threat_level = "Aman"
            status_color = (0, 200, 0) # Hijau
        elif total_count <= 25:
            threat_level = "Waspada"
            status_color = (0, 165, 255) # Oranye
        else:
            threat_level = "Bahaya"
            status_color = (0, 0, 255) # Merah

        # Tambahkan Banner Informasi di Atas Gambar
        overlay = annotated_img.copy()
        cv2.rectangle(overlay, (0, 0), (w_orig, 42), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.75, annotated_img, 0.25, 0, annotated_img)

        info_text = f"Total Hama: {total_count} | Status: {threat_level}"
        cv2.putText(annotated_img, info_text, (10, 28), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2, cv2.LINE_AA)

        # Simpan gambar teranotasi jika path diberikan
        if output_annotated_path:
            out_dir = os.path.dirname(output_annotated_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            cv2.imwrite(output_annotated_path, annotated_img)

        return {
            "total_count": total_count,
            "threat_level": threat_level,
            "insects": detected_insects,
            "annotated_image_path": output_annotated_path,
            "method": "OpenCV-Contour"
        }

    def count_insects_yolo(self, image_path, output_annotated_path=None):
        """
        Deteksi menggunakan model YOLO jika pengguna memiliki model custom terlatih.
        """
        if self.yolo_model is None:
            return self.count_insects_opencv(image_path, output_annotated_path)

        results = self.yolo_model.predict(source=image_path, save=False, conf=0.35)
        res = results[0]

        annotated_img = res.plot()
        total_count = len(res.boxes)

        if total_count < 10:
            threat_level = "Aman"
        elif total_count <= 25:
            threat_level = "Waspada"
        else:
            threat_level = "Bahaya"

        if output_annotated_path:
            out_dir = os.path.dirname(output_annotated_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            cv2.imwrite(output_annotated_path, annotated_img)

        return {
            "total_count": total_count,
            "threat_level": threat_level,
            "insects": [{"x": float(b.xywh[0][0]), "y": float(b.xywh[0][1])} for b in res.boxes],
            "annotated_image_path": output_annotated_path,
            "method": "YOLOv8"
        }

    def process_image(self, image_path, output_annotated_path=None):
        """
        Fungsi utama pemrosesan: Otomatis memilih YOLO jika ada model, atau fallback ke OpenCV.
        """
        if self.yolo_model is not None:
            return self.count_insects_yolo(image_path, output_annotated_path)
        return self.count_insects_opencv(image_path, output_annotated_path)


# ====================================================================================
# PENGUJIAN MANDIRI (STANDALONE TEST)
# ====================================================================================
if __name__ == "__main__":
    import sys
    print("[*] Testing Insect Counter Engine...")
    counter = InsectCounter(min_area=15, max_area=2500)
    
    # Gunakan sampel gambar yang ada jika tersedia
    sample_img = "sample.jpg"
    if len(sys.argv) > 1:
        sample_img = sys.argv[1]
    
    if os.path.exists(sample_img):
        res = counter.process_image(sample_img, "annotated_sample.jpg")
        print(f"[RESULT] Deteksi Selesai: {res['total_count']} serangga terhitung.")
        print(f"[RESULT] Tingkat Ancaman : {res['threat_level']}")
        print(f"[RESULT] File Hasil       : {res['annotated_image_path']}")
    else:
        print(f"[INFO] File {sample_img} tidak ditemukan untuk tes mandiri.")
