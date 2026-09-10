"""
====================================================================================
WEB DASHBOARD SERVER - RASPBERRY PI 5 (FLASK & REST API)
Fitur    : - Web Dashboard responsif pemantauan perangkap hama real-time
           - Visualisasi grafik suhu, kelembaban, dan tren populasi hama (Chart.js)
           - Perbandingan foto perangkap asli vs hasil deteksi AI (Bounding Box)
           - Galeri riwayat foto dan ekspor laporan CSV
           - Menjalankan receiver LoRa secara otomatis di background thread
Lab ELINS - Universitas Gadjah Mada
====================================================================================
"""

import os
import sqlite3
import threading
from flask import Flask, render_template, jsonify, send_file, request
from receiver_daemon import run_receiver, init_database, DB_PATH, CSV_PATH, CAPTURES_DIR, ANNOTATED_DIR

app = Flask(__name__, static_folder="static", template_folder="templates")


def get_db_connection():
    """Membuka koneksi ke SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def index():
    """Halaman Utama Web Dashboard."""
    return render_template("index.html")


@app.route("/api/latest")
def api_latest():
    """Mengembalikan pembacaan sensor dan hasil deteksi serangga terbaru."""
    conn = get_db_connection()
    c = conn.cursor()

    # Ambil sensor terbaru
    c.execute("SELECT * FROM sensor_logs ORDER BY id DESC LIMIT 1")
    latest_sensor = c.fetchone()

    # Ambil gambar & deteksi hama terbaru
    c.execute("SELECT * FROM image_logs ORDER BY id DESC LIMIT 1")
    latest_image = c.fetchone()

    conn.close()

    sensor_data = {
        "suhu": latest_sensor["suhu"] if latest_sensor else 0.0,
        "kelembaban": latest_sensor["kelembaban"] if latest_sensor else 0.0,
        "waktu_rtc": latest_sensor["waktu_rtc"] if latest_sensor else "Menunggu data...",
        "timestamp_pc": latest_sensor["timestamp_pc"] if latest_sensor else "-"
    }

    image_data = {
        "has_image": latest_image is not None,
        "raw_url": f"/static/captures/{latest_image['filename_raw']}" if latest_image else "",
        "annotated_url": f"/static/annotated/{latest_image['filename_annotated']}" if latest_image else "",
        "insect_count": latest_image["insect_count"] if latest_image else 0,
        "threat_level": latest_image["threat_level"] if latest_image else "Normal",
        "waktu_rtc": latest_image["waktu_rtc"] if latest_image else "-",
        "size_kb": round(latest_image["file_size_bytes"] / 1024, 1) if latest_image else 0
    }

    return jsonify({
        "status": "success",
        "sensor": sensor_data,
        "image": image_data
    })


@app.route("/api/history")
def api_history():
    """Mengembalikan riwayat sensor (30 data terakhir) untuk grafik Chart.js."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM sensor_logs ORDER BY id DESC LIMIT 30")
    rows = c.fetchall()
    conn.close()

    # Urutkan kronologis (terlama ke terbaru)
    rows = list(reversed(rows))

    labels = [r["waktu_rtc"] for r in rows]
    suhu_list = [r["suhu"] for r in rows]
    hum_list = [r["kelembaban"] for r in rows]

    return jsonify({
        "labels": labels,
        "suhu": suhu_list,
        "kelembaban": hum_list
    })


@app.route("/api/detections")
def api_detections():
    """Mengembalikan riwayat seluruh tangkapan gambar dan populasi serangga."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM image_logs ORDER BY id DESC LIMIT 20")
    rows = c.fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "timestamp": r["waktu_rtc"],
            "raw_url": f"/static/captures/{r['filename_raw']}",
            "annotated_url": f"/static/annotated/{r['filename_annotated']}",
            "count": r["insect_count"],
            "threat": r["threat_level"],
            "size_kb": round(r["file_size_bytes"] / 1024, 1)
        })

    # Data tren serangga harian
    reversed_rows = list(reversed(rows))
    trend_labels = [r["waktu_rtc"] for r in reversed_rows]
    trend_counts = [r["insect_count"] for r in reversed_rows]

    return jsonify({
        "detections": results,
        "trend_labels": trend_labels,
        "trend_counts": trend_counts
    })


@app.route("/export/csv")
def export_csv():
    """Mengunduh file log CSV."""
    if os.path.exists(CSV_PATH):
        return send_file(CSV_PATH, as_attachment=True, download_name="sensor_hama_history.csv")
    return "Data CSV belum tersedia", 404


def start_background_receiver():
    """Memulai service pembacaan serial LoRa di thread latar belakang."""
    t = threading.Thread(target=run_receiver, daemon=True)
    t.start()
    print("[APP] Background Receiver LoRa Thread berhasil dijalankan.")


if __name__ == "__main__":
    init_database()
    
    # Jalankan background receiver LoRa jika tidak dinonaktifkan
    if os.environ.get("NO_SERIAL_DAEMON") != "1":
        start_background_receiver()

    print("\n========================================================")
    print("  WEB DASHBOARD PEMANTAUAN HAMA RASPBERRY PI 5 AKTIF")
    print("  Akses melalui browser lokal: http://localhost:5000")
    print("  Atau dari perangkat lain di LAN : http://<IP_RASPBERRY_PI>:5000")
    print("========================================================\n")

    # Jalankan Flask Server di port 5000 dapat diakses dari jaringan lokal (0.0.0.0)
    app.run(host="0.0.0.0", port=5000, debug=False)
