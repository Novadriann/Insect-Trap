"""
====================================================================================
SKRIP SIMULASI TANGKAPAN FOTO HAMA KE WEB DASHBOARD RASPBERRY PI 5
Fungsi   : Menguji tampilan foto dan hasil deteksi langsung pada Web Dashboard
Lab ELINS - Universitas Gadjah Mada
====================================================================================
"""

import os
import sys
import time
import shutil
import sqlite3
from kaper_counter_rpi5 import RaspberryPiKaperCounter
from receiver_daemon import DB_PATH, CAPTURES_DIR, ANNOTATED_DIR, init_database

def inject_test_image(image_path, node_id="NODE_01"):
    if not os.path.exists(image_path):
        print(f"[ERROR] File gambar tidak ditemukan: {image_path}")
        return False

    counter = RaspberryPiKaperCounter()
    timestamp_str = time.strftime("%Y%m%d_%H%M%S")
    now_pc = time.strftime("%Y-%m-%d %H:%M:%S")

    # Siapkan direktori per node
    node_cap_dir = os.path.join(CAPTURES_DIR, node_id)
    node_ann_dir = os.path.join(ANNOTATED_DIR, node_id)
    os.makedirs(node_cap_dir, exist_ok=True)
    os.makedirs(node_ann_dir, exist_ok=True)

    raw_filename = f"trap_{node_id}_{timestamp_str}.jpg"
    raw_filepath = os.path.join(node_cap_dir, raw_filename)
    shutil.copy(image_path, raw_filepath)

    annotated_filename = f"trap_{node_id}_{timestamp_str}_annotated.jpg"
    annotated_filepath = os.path.join(node_ann_dir, annotated_filename)

    print(f"[*] Menjalankan deteksi kaper pada: {image_path} ...")
    res = counter.process_image(raw_filepath, annotated_filepath, node_id=node_id)

    total_count = res["total_count"]
    threat_level = res["threat_level"]
    file_size = os.path.getsize(raw_filepath)

    # Masukkan ke Database SQLite agar langsung tampil di Web Dashboard
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    rel_raw = f"{node_id}/{raw_filename}"
    rel_ann = f"{node_id}/{annotated_filename}"

    c.execute("""
    INSERT INTO image_logs 
    (timestamp_pc, node_id, waktu_rtc, filename_raw, filename_annotated, insect_count, threat_level, file_size_bytes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (now_pc, node_id, now_pc, rel_raw, rel_ann, total_count, threat_level, file_size))

    # Masukkan juga data sensor dummy yang realistis
    c.execute("""
    INSERT INTO sensor_logs (timestamp_pc, node_id, waktu_rtc, suhu, kelembaban)
    VALUES (?, ?, ?, ?, ?)
    """, (now_pc, node_id, now_pc, 27.5, 62.0))

    conn.commit()
    conn.close()

    print("==================================================================")
    print(f"[SUKSES] Gambar Berhasil Diinjeksikan ke Web Dashboard!")
    print(f"  Node ID          : {node_id}")
    print(f"  Jumlah Serangga  : {total_count} ekor")
    print(f"  Tingkat Ancaman  : {threat_level}")
    print(f"  Waktu Komputasi  : {res['process_time_ms']} ms")
    print(f"  File Mentah      : {raw_filepath}")
    print(f"  File Teranotasi  : {annotated_filepath}")
    print("==================================================================")
    print("Sekarang refresh halaman Web Dashboard Anda di browser: http://100.90.201.108:5000\n")
    return True

if __name__ == "__main__":
    target = "test_lem_kuning.jpg"
    node = "NODE_01"

    if len(sys.argv) > 1:
        target = sys.argv[1]
    if len(sys.argv) > 2:
        node = sys.argv[2]

    inject_test_image(target, node)
