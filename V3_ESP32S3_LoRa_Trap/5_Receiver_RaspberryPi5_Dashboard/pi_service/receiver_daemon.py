"""
====================================================================================
SERVICE RECEIVER DAEMON - RASPBERRY PI 5
Fungsi   : - Membaca aliran data serial dari ESP32 LoRa Bridge secara background
           - Menyimpan data suhu, kelembaban, dan waktu ke SQLite & CSV
           - Menangkap dan merekonstruksi aliran biner gambar JPEG
           - Memicu eksekusi otomatis deteksi serangga (insect_counter.py)
           - Memperbarui database pemantauan secara real-time
Lab ELINS - Universitas Gadjah Mada
====================================================================================
"""

import serial
import serial.tools.list_ports
import time
import os
import sqlite3
import csv
import threading
from insect_counter import InsectCounter

# --- PENGATURAN DIREKTORI & DATABASE ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "trap_monitoring.db")
CSV_PATH = os.path.join(BASE_DIR, "sensor_history.csv")
CAPTURES_DIR = os.path.join(BASE_DIR, "static", "captures")
ANNOTATED_DIR = os.path.join(BASE_DIR, "static", "annotated")

os.makedirs(CAPTURES_DIR, exist_ok=True)
os.makedirs(ANNOTATED_DIR, exist_ok=True)

# Inisialisasi Detektor Serangga
counter_engine = InsectCounter(min_area=15, max_area=2500)


def init_database():
    """Membuat tabel database SQLite jika belum ada."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Tabel pembacaan sensor DHT22 & RTC
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp_pc TEXT,
        waktu_rtc TEXT,
        suhu REAL,
        kelembaban REAL
    )
    """)

    # Tabel hasil tangkapan gambar & perhitungan hama
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS image_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp_pc TEXT,
        waktu_rtc TEXT,
        filename_raw TEXT,
        filename_annotated TEXT,
        insect_count INTEGER,
        threat_level TEXT,
        file_size_bytes INTEGER
    )
    """)

    conn.commit()
    conn.close()

    # Inisialisasi file CSV
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp_PC", "Waktu_RTC", "Suhu_C", "Kelembaban_RH"])


def find_serial_port(preferred_port=None):
    """Mencari port serial ESP32 secara otomatis di Linux / Raspberry Pi / Windows."""
    if preferred_port:
        return preferred_port

    ports = serial.tools.list_ports.comports()
    for p in ports:
        # Deteksi port serial ESP32 / CH340 / CP2102 / ACM
        p_name = p.device
        desc = p.description.lower()
        if "usb" in p_name.lower() or "acm" in p_name.lower() or "cp210" in desc or "ch340" in desc or "uart" in desc:
            return p_name

    # Default port Raspberry Pi jika ada
    if os.path.exists("/dev/ttyUSB0"):
        return "/dev/ttyUSB0"
    if os.path.exists("/dev/ttyACM0"):
        return "/dev/ttyACM0"

    # Jika di Windows dan ada COM yang aktif
    if ports:
        return ports[0].device

    return None


def run_receiver(port=None, baudrate=115200):
    """Loop utama penerimaan serial LoRa di Raspberry Pi 5."""
    init_database()
    print("[RECEIVER DAEMON] Memulai receiver LoRa...")

    while True:
        target_port = find_serial_port(port)
        if not target_port:
            print("[RECEIVER DAEMON] Menunggu perangkat ESP32 Bridge terhubung ke port USB...")
            time.sleep(3)
            continue

        try:
            ser = serial.Serial(target_port, baudrate, timeout=2)
            print(f"[RECEIVER DAEMON] Terhubung ke {target_port} pada {baudrate} baud.")
        except Exception as e:
            print(f"[RECEIVER DAEMON] Gagal membuka port {target_port}: {e}. Mencoba lagi dalam 3 detik...")
            time.sleep(3)
            continue

        latest_rtc_time = time.strftime("%Y-%m-%d %H:%M:%S")

        while True:
            try:
                line = ser.readline()
                if not line:
                    continue

                text = line.decode('utf-8', errors='ignore').strip()

                # ------------------------------------------------------------------
                # 1. PARSING DATA SENSOR
                # ------------------------------------------------------------------
                if text.startswith("[DATA]") or text.startswith("SENSOR,"):
                    print(f"\n[+] SENSOR DATA DITERIMA: {text}")
                    suhu = 0.0
                    kelembaban = 0.0
                    waktu_rtc = latest_rtc_time

                    try:
                        if text.startswith("[DATA]"):
                            # Format: [DATA] Waktu: 2026-09-10 10:30:00, Suhu: 28.5 C, Kelembaban: 75.0 %
                            parts = text.split(",")
                            for p in parts:
                                p = p.strip()
                                if "Waktu:" in p:
                                    waktu_rtc = p.replace("[DATA] Waktu:", "").strip()
                                elif "Suhu:" in p:
                                    suhu = float(p.replace("Suhu:", "").replace("C", "").strip())
                                elif "Kelembaban:" in p:
                                    kelembaban = float(p.replace("Kelembaban:", "").replace("%", "").strip())
                        else:
                            # Format: SENSOR,NODE01,28.5,75.0,10-09-2026,10:30:00
                            parts = text.split(",")
                            suhu = float(parts[2].strip())
                            kelembaban = float(parts[3].strip())
                            waktu_rtc = f"{parts[4].strip()} {parts[5].strip()}"

                        latest_rtc_time = waktu_rtc
                        now_pc = time.strftime("%Y-%m-%d %H:%M:%S")

                        # Simpan ke SQLite
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("INSERT INTO sensor_logs (timestamp_pc, waktu_rtc, suhu, kelembaban) VALUES (?, ?, ?, ?)",
                                  (now_pc, waktu_rtc, suhu, kelembaban))
                        conn.commit()
                        conn.close()

                        # Simpan ke CSV
                        with open(CSV_PATH, mode='a', newline='') as f:
                            writer = csv.writer(f)
                            writer.writerow([now_pc, waktu_rtc, suhu, kelembaban])

                        print(f"[OK] Sensor tersimpan: Suhu={suhu}°C, RH={kelembaban}%, Waktu={waktu_rtc}")

                    except Exception as err:
                        print(f"[ERROR] Gagal parsing sensor: {err}")

                # ------------------------------------------------------------------
                # 2. PENERIMAAN ALIRAN GAMBAR BINER
                # ------------------------------------------------------------------
                elif "---START---" in text:
                    print("\n[*] MEMULAI PENERIMAAN GAMBAR DARI LORA...")
                    expected_length = 0

                    # Format bisa ---START---<length> atau baris berikutnya adalah length
                    if len(text.split("---START---")) > 1 and text.split("---START---")[1].strip().isdigit():
                        expected_length = int(text.split("---START---")[1].strip())
                    else:
                        next_line = ser.readline().decode('utf-8', errors='ignore').strip()
                        if next_line.isdigit():
                            expected_length = int(next_line)

                    if expected_length <= 0:
                        print("[ERROR] Ukuran gambar tidak valid. Pembatalan.")
                        continue

                    print(f"[*] Ukuran data yang diharapkan: {expected_length} bytes.")
                    image_buffer = bytearray()
                    start_time = time.time()

                    # Baca aliran byte biner hingga ukuran terpenuhi
                    while len(image_buffer) < expected_length:
                        sisa = expected_length - len(image_buffer)
                        chunk = ser.read(min(180, sisa))
                        if chunk:
                            image_buffer.extend(chunk)
                            pct = (len(image_buffer) / expected_length) * 100.0
                            print(f"\rProgress Download: {len(image_buffer)} / {expected_length} B ({pct:.1f}%)", end="")
                        else:
                            # Cek timeout jika tidak ada byte masuk selama 15 detik
                            if time.time() - start_time > 60:
                                print("\n[WARNING] Timeout pengunduhan gambar.")
                                break

                    print() # Baris baru

                    # Baca marker END jika ada di serial buffer
                    time.sleep(0.1)
                    if ser.in_waiting:
                        tail = ser.read(ser.in_waiting)
                        # Bersihkan tail

                    # Simpan file gambar mentah
                    timestamp_str = time.strftime("%Y%m%d_%H%M%S")
                    raw_filename = f"trap_{timestamp_str}.jpg"
                    raw_filepath = os.path.join(CAPTURES_DIR, raw_filename)

                    with open(raw_filepath, "wb") as img_file:
                        img_file.write(image_buffer)

                    print(f"[OK] Gambar mentah berhasil disimpan: {raw_filepath}")

                    # ------------------------------------------------------------------
                    # 3. PROSES IMAGE COUNTING OTOMATIS
                    # ------------------------------------------------------------------
                    annotated_filename = f"trap_{timestamp_str}_annotated.jpg"
                    annotated_filepath = os.path.join(ANNOTATED_DIR, annotated_filename)

                    try:
                        print("[*] Menjalankan algoritma penghitung serangga otomatis...")
                        count_result = counter_engine.process_image(raw_filepath, annotated_filepath)
                        total_insects = count_result["total_count"]
                        threat_level = count_result["threat_level"]

                        print(f"[SUKSES DETEKSI] Jumlah Hama: {total_insects} | Status: {threat_level}")

                        # Simpan hasil deteksi ke SQLite database
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        now_pc = time.strftime("%Y-%m-%d %H:%M:%S")
                        c.execute("""
                        INSERT INTO image_logs 
                        (timestamp_pc, waktu_rtc, filename_raw, filename_annotated, insect_count, threat_level, file_size_bytes)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (now_pc, latest_rtc_time, raw_filename, annotated_filename, total_insects, threat_level, len(image_buffer)))
                        conn.commit()
                        conn.close()

                    except Exception as err:
                        print(f"[ERROR] Gagal memproses deteksi serangga: {err}")

            except (serial.SerialException, OSError) as e:
                print(f"[RECEIVER DAEMON] Koneksi serial terputus: {e}. Menghubungkan ulang...")
                try:
                    ser.close()
                except Exception:
                    pass
                break
            except Exception as e:
                # Abaikan noise byte
                pass


if __name__ == "__main__":
    run_receiver()
