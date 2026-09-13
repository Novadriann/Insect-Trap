"""
====================================================================================
SERVICE RECEIVER DAEMON - RASPBERRY PI 5 (MULTI-NODE SUPPORT)
Fungsi   : - Membaca aliran data serial dari ESP32 LoRa Bridge secara background
           - Mendukung banyak transmitter (NODE_01, NODE_02, dst)
           - Menyimpan data suhu, kelembaban, waktu, dan Node ID ke SQLite & CSV
           - Menangkap dan merekonstruksi aliran biner gambar JPEG per Node
           - Memicu eksekusi otomatis deteksi kupu kaper (kaper_counter_rpi5.py)
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
import re
from kaper_counter_rpi5 import RaspberryPiKaperCounter

# --- PENGATURAN DIREKTORI & DATABASE ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "trap_monitoring.db")
CSV_PATH = os.path.join(BASE_DIR, "sensor_history.csv")
CAPTURES_DIR = os.path.join(BASE_DIR, "static", "captures")
ANNOTATED_DIR = os.path.join(BASE_DIR, "static", "annotated")

os.makedirs(CAPTURES_DIR, exist_ok=True)
os.makedirs(ANNOTATED_DIR, exist_ok=True)

# Inisialisasi Detektor Serangga Kaper RPi5
counter_engine = RaspberryPiKaperCounter()


def init_database():
    """Membuat dan memutakhirkan tabel SQLite untuk multi-node."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Tabel pembacaan sensor DHT22 & RTC
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp_pc TEXT,
        node_id TEXT DEFAULT 'NODE_01',
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
        node_id TEXT DEFAULT 'NODE_01',
        waktu_rtc TEXT,
        filename_raw TEXT,
        filename_annotated TEXT,
        insect_count INTEGER,
        threat_level TEXT,
        file_size_bytes INTEGER
    )
    """)

    # Migrasi skema jika tabel lama belum memiliki kolom node_id
    try:
        cursor.execute("ALTER TABLE sensor_logs ADD COLUMN node_id TEXT DEFAULT 'NODE_01'")
    except Exception:
        pass

    try:
        cursor.execute("ALTER TABLE image_logs ADD COLUMN node_id TEXT DEFAULT 'NODE_01'")
    except Exception:
        pass

    conn.commit()
    conn.close()

    # Inisialisasi file CSV
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp_PC", "Node_ID", "Waktu_RTC", "Suhu_C", "Kelembaban_RH"])


def find_serial_port(preferred_port=None):
    """Mencari port serial ESP32 secara otomatis di Linux / Raspberry Pi / Windows."""
    if preferred_port:
        return preferred_port

    ports = serial.tools.list_ports.comports()
    for p in ports:
        p_name = p.device
        desc = p.description.lower()
        if "usb" in p_name.lower() or "acm" in p_name.lower() or "cp210" in desc or "ch340" in desc or "uart" in desc:
            return p_name

    if os.path.exists("/dev/ttyUSB0"):
        return "/dev/ttyUSB0"
    if os.path.exists("/dev/ttyACM0"):
        return "/dev/ttyACM0"

    if ports:
        return ports[0].device

    return None


def parse_sensor_line(text, fallback_time):
    """Mem-parse string sensor dan mengekstrak Node ID."""
    node_id = "NODE_01"
    suhu = 0.0
    kelembaban = 0.0
    waktu_rtc = fallback_time

    if text.startswith("[DATA]"):
        clean_str = text[text.find("[DATA]"):]
        parts = [p.strip() for p in clean_str.split(",")]
        for p in parts:
            if "Node:" in p:
                node_id = p.replace("[DATA]", "").replace("Node:", "").strip()
            elif "Waktu:" in p:
                waktu_rtc = p.replace("[DATA] Waktu:", "").strip()
            elif "Suhu:" in p:
                try:
                    suhu = float(p.replace("Suhu:", "").replace("C", "").strip())
                except ValueError:
                    pass
            elif "Kelembaban:" in p:
                try:
                    kelembaban = float(p.replace("Kelembaban:", "").replace("%", "").strip())
                except ValueError:
                    pass
    elif text.startswith("SENSOR,"):
        parts = [p.strip() for p in text.split(",")]
        if len(parts) >= 6:
            node_id = parts[1].strip()
            try:
                suhu = float(parts[2].strip())
                kelembaban = float(parts[3].strip())
            except ValueError:
                pass
            waktu_rtc = f"{parts[4].strip()} {parts[5].strip()}"

    return node_id, waktu_rtc, suhu, kelembaban


def extract_node_from_header(header_text):
    """Mengekstrak ID node dari format ---START:NODE_XX---"""
    match = re.search(r'---START:(NODE_\w+)---', header_text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return "NODE_01"


def run_receiver(port=None, baudrate=115200):
    """Loop utama penerimaan serial LoRa di Raspberry Pi 5."""
    init_database()
    print("[RECEIVER DAEMON] Memulai receiver LoRa Multi-Node Raspberry Pi 5...")

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

        latest_rtc_times = {"NODE_01": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "NODE_02": time.strftime("%Y-%m-%d %H:%M:%S")}

        while True:
            try:
                line = ser.readline()
                if not line:
                    continue

                text = line.decode('utf-8', errors='ignore').strip()

                # ------------------------------------------------------------------
                # 1. PARSING DATA SENSOR MULTI-NODE
                # ------------------------------------------------------------------
                if text.startswith("[DATA]") or text.startswith("SENSOR,"):
                    print(f"\n[+] SENSOR DATA DITERIMA: {text}")
                    now_pc = time.strftime("%Y-%m-%d %H:%M:%S")
                    node_id, waktu_rtc, suhu, kelembaban = parse_sensor_line(text, now_pc)

                    latest_rtc_times[node_id] = waktu_rtc

                    # Simpan ke SQLite
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("""
                    INSERT INTO sensor_logs (timestamp_pc, node_id, waktu_rtc, suhu, kelembaban) 
                    VALUES (?, ?, ?, ?, ?)
                    """, (now_pc, node_id, waktu_rtc, suhu, kelembaban))
                    conn.commit()
                    conn.close()

                    # Simpan ke CSV
                    with open(CSV_PATH, mode='a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([now_pc, node_id, waktu_rtc, suhu, kelembaban])

                    print(f"[OK] Sensor [{node_id}] tersimpan: Suhu={suhu}°C, RH={kelembaban}%, Waktu={waktu_rtc}")

                # ------------------------------------------------------------------
                # 2. PENERIMAAN ALIRAN GAMBAR BINER MULTI-NODE
                # ------------------------------------------------------------------
                elif "---START" in text:
                    node_id = extract_node_from_header(text)
                    print(f"\n[*] MEMULAI PENERIMAAN GAMBAR DARI LORA [{node_id}]...")
                    expected_length = 0

                    after_tag = text.split("---")[-1].strip()
                    if after_tag.isdigit():
                        expected_length = int(after_tag)
                    else:
                        next_line = ser.readline().decode('utf-8', errors='ignore').strip()
                        if next_line.isdigit():
                            expected_length = int(next_line)

                    if expected_length <= 0:
                        print(f"[ERROR] Ukuran gambar [{node_id}] tidak valid. Pembatalan.")
                        continue

                    print(f"[*] Ukuran data yang diharapkan [{node_id}]: {expected_length} bytes.")
                    image_buffer = bytearray()
                    start_time = time.time()

                    while len(image_buffer) < expected_length:
                        sisa = expected_length - len(image_buffer)
                        chunk = ser.read(min(180, sisa))
                        if chunk:
                            image_buffer.extend(chunk)
                            pct = (len(image_buffer) / expected_length) * 100.0
                            print(f"\rProgress [{node_id}]: {len(image_buffer)} / {expected_length} B ({pct:.1f}%)", end="")
                        else:
                            if time.time() - start_time > 60:
                                print(f"\n[WARNING] Timeout pengunduhan gambar [{node_id}].")
                                break

                    print()

                    time.sleep(0.1)
                    if ser.in_waiting:
                        ser.read(ser.in_waiting)

                    # Subfolder per Node
                    node_capture_dir = os.path.join(CAPTURES_DIR, node_id)
                    node_annotated_dir = os.path.join(ANNOTATED_DIR, node_id)
                    os.makedirs(node_capture_dir, exist_ok=True)
                    os.makedirs(node_annotated_dir, exist_ok=True)

                    timestamp_str = time.strftime("%Y%m%d_%H%M%S")
                    raw_filename = f"trap_{node_id}_{timestamp_str}.jpg"
                    raw_filepath = os.path.join(node_capture_dir, raw_filename)

                    with open(raw_filepath, "wb") as img_file:
                        img_file.write(image_buffer)

                    print(f"[OK] Gambar mentah [{node_id}] disimpan: {raw_filepath}")

                    # ------------------------------------------------------------------
                    # 3. PROSES PENGHITUNG KUPU KAPER
                    # ------------------------------------------------------------------
                    annotated_filename = f"trap_{node_id}_{timestamp_str}_annotated.jpg"
                    annotated_filepath = os.path.join(node_annotated_dir, annotated_filename)

                    try:
                        print(f"[*] Menjalankan deteksi kupu kaper RPi5 untuk [{node_id}]...")
                        count_result = counter_engine.process_image(raw_filepath, annotated_filepath, node_id=node_id)
                        total_insects = count_result["total_count"]
                        threat_level = count_result["threat_level"]
                        proc_time = count_result["process_time_ms"]

                        print(f"[SUKSES DETEKSI {node_id}] Kaper: {total_insects} Ekor | Status: {threat_level} ({proc_time} ms)")

                        # Simpan ke database
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        now_pc = time.strftime("%Y-%m-%d %H:%M:%S")
                        waktu_rtc = latest_rtc_times.get(node_id, now_pc)

                        # Simpan path relatif terhadap folder static untuk kemudahan web server
                        rel_raw = f"{node_id}/{raw_filename}"
                        rel_annotated = f"{node_id}/{annotated_filename}"

                        c.execute("""
                        INSERT INTO image_logs 
                        (timestamp_pc, node_id, waktu_rtc, filename_raw, filename_annotated, insect_count, threat_level, file_size_bytes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (now_pc, node_id, waktu_rtc, rel_raw, rel_annotated, total_insects, threat_level, len(image_buffer)))
                        conn.commit()
                        conn.close()

                    except Exception as err:
                        print(f"[ERROR] Gagal memproses deteksi kupu kaper: {err}")

            except (serial.SerialException, OSError) as e:
                print(f"[RECEIVER DAEMON] Koneksi serial terputus: {e}. Menghubungkan ulang...")
                try:
                    ser.close()
                except Exception:
                    pass
                break
            except Exception:
                pass


if __name__ == "__main__":
    run_receiver()
