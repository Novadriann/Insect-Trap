"""
====================================================================================
WEB DASHBOARD SERVER - RASPBERRY PI 5 (FLASK & REST API - MULTI-NODE)
Fitur    : - Web Dashboard responsif pemantauan perangkap hama real-time
           - Dukungan multi-node: Memilih data per node (NODE_01, NODE_02)
           - Visualisasi grafik suhu, kelembaban, dan tren populasi hama (Chart.js)
           - Perbandingan foto perangkap asli vs hasil deteksi AI (Bounding Box)
           - Galeri riwayat foto dan ekspor laporan CSV
           - Menjalankan receiver LoRa secara otomatis di background thread
Lab ELINS - Universitas Gadjah Mada
====================================================================================
"""

import os
import time
import sqlite3
import threading
from flask import Flask, render_template, jsonify, send_file, request, session
from receiver_daemon import run_receiver, init_database, DB_PATH, CSV_PATH, CAPTURES_DIR, ANNOTATED_DIR

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "kaper-trap-elins-ugm-2026-secret")

# --- Kredensial Login Kontrol Panel ---
AUTH_USERNAME = "petani"
AUTH_PASSWORD = "petani"


def get_db_connection():
    """Membuka koneksi ke SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def index():
    """Halaman Utama Web Dashboard."""
    return render_template("index.html")


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    """Login untuk mengakses fitur kontrol (Jepret & Jadwal)."""
    data = {}
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        try:
            data = request.get_json(force=True, silent=True) or {}
        except Exception:
            data = {}
    if not data:
        data = request.form.to_dict() or {}

    username = str(data.get("username", "")).strip().lower()
    password = str(data.get("password", "")).strip().lower()

    if username == "petani" and password == "petani":
        session["logged_in"] = True
        session["username"] = "petani"
        return jsonify({
            "status": "success",
            "message": "Login berhasil! Selamat datang, Petani.",
            "username": "petani"
        })
    else:
        return jsonify({"status": "error", "message": "Username atau password salah."}), 401


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    """Logout dari kontrol panel."""
    session.clear()
    return jsonify({"status": "success", "message": "Berhasil logout."})


@app.route("/api/auth/check")
def api_auth_check():
    """Memeriksa status login."""
    if session.get("logged_in"):
        return jsonify({"status": "success", "logged_in": True, "username": session.get("username", "")})
    return jsonify({"status": "success", "logged_in": False})


@app.route("/api/nodes")
def api_nodes():
    """Mengembalikan daftar seluruh Node ID yang aktif."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT DISTINCT node_id FROM sensor_logs UNION SELECT DISTINCT node_id FROM image_logs")
    rows = c.fetchall()
    conn.close()

    nodes = [r[0] for r in rows if r[0]]
    if not nodes:
        nodes = ["NODE_01", "NODE_02"]
    return jsonify({"status": "success", "nodes": sorted(nodes)})


import re

def clean_timestamp(ts):
    """Membersihkan format timestamp, menghapus prefix 'Waktu:' atau '[DATA]'."""
    if not ts:
        return ""
    clean = re.sub(r'^(?:\[DATA\]\s*)?Waktu:\s*', '', str(ts), flags=re.IGNORECASE).strip()
    return clean


@app.route("/api/latest")
def api_latest():
    """Mengembalikan pembacaan sensor dan hasil deteksi kaper terbaru (bisa difilter per node)."""
    node = request.args.get("node")

    conn = get_db_connection()
    c = conn.cursor()

    # Ambil sensor terbaru
    if node:
        c.execute("SELECT * FROM sensor_logs WHERE node_id = ? ORDER BY id DESC LIMIT 1", (node,))
    else:
        c.execute("SELECT * FROM sensor_logs ORDER BY id DESC LIMIT 1")
    latest_sensor = c.fetchone()

    # Ambil gambar & deteksi hama terbaru
    if node:
        c.execute("SELECT * FROM image_logs WHERE node_id = ? ORDER BY id DESC LIMIT 1", (node,))
    else:
        c.execute("SELECT * FROM image_logs ORDER BY id DESC LIMIT 1")
    latest_image = c.fetchone()

    conn.close()

    sensor_data = {
        "node_id": latest_sensor["node_id"] if latest_sensor and "node_id" in latest_sensor.keys() else (node or "NODE_01"),
        "suhu": latest_sensor["suhu"] if latest_sensor else 0.0,
        "kelembaban": latest_sensor["kelembaban"] if latest_sensor else 0.0,
        "waktu_rtc": clean_timestamp(latest_sensor["waktu_rtc"]) if latest_sensor else "Menunggu data...",
        "timestamp_pc": latest_sensor["timestamp_pc"] if latest_sensor else "-"
    }

    image_data = {
        "has_image": latest_image is not None,
        "node_id": latest_image["node_id"] if latest_image and "node_id" in latest_image.keys() else (node or "NODE_01"),
        "raw_url": f"/static/captures/{latest_image['filename_raw']}" if latest_image else "",
        "annotated_url": f"/static/annotated/{latest_image['filename_annotated']}" if latest_image else "",
        "insect_count": latest_image["insect_count"] if latest_image else 0,
        "threat_level": latest_image["threat_level"] if latest_image else "Normal",
        "waktu_rtc": clean_timestamp(latest_image["waktu_rtc"]) if latest_image else "-",
        "size_kb": round(latest_image["file_size_bytes"] / 1024, 1) if (latest_image and latest_image["file_size_bytes"]) else 0
    }

    return jsonify({
        "status": "success",
        "sensor": sensor_data,
        "image": image_data
    })


@app.route("/api/history")
def api_history():
    """Mengembalikan riwayat sensor dengan rentang waktu dinamis (1d, 3d, 7d) untuk Chart.js."""
    node = request.args.get("node")
    range_param = request.args.get("range", "1d").lower()
    limit_map = {"1d": 500, "3d": 1500, "7d": 3500}
    limit = limit_map.get(range_param, 500)

    conn = get_db_connection()
    c = conn.cursor()
    if node:
        c.execute("SELECT * FROM sensor_logs WHERE node_id = ? ORDER BY id DESC LIMIT ?", (node, limit))
    else:
        c.execute("SELECT * FROM sensor_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()

    # Urutkan kronologis (terlama ke terbaru)
    rows = list(reversed(rows))

    labels = [clean_timestamp(r["waktu_rtc"]) for r in rows]
    suhu_list = [r["suhu"] for r in rows]
    hum_list = [r["kelembaban"] for r in rows]

    return jsonify({
        "range": range_param,
        "labels": labels,
        "suhu": suhu_list,
        "kelembaban": hum_list
    })


@app.route("/api/detections")
def api_detections():
    """Mengembalikan riwayat tangkapan gambar dan populasi kupu kaper dengan rentang waktu."""
    node = request.args.get("node")
    range_param = request.args.get("range", "1d").lower()
    limit_map = {"1d": 50, "3d": 150, "7d": 350}
    limit = limit_map.get(range_param, 50)

    conn = get_db_connection()
    c = conn.cursor()
    if node:
        c.execute("SELECT * FROM image_logs WHERE node_id = ? ORDER BY id DESC LIMIT ?", (node, limit))
    else:
        c.execute("SELECT * FROM image_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "node_id": r["node_id"] if "node_id" in r.keys() else "NODE_01",
            "timestamp": clean_timestamp(r["waktu_rtc"]),
            "raw_url": f"/static/captures/{r['filename_raw']}",
            "annotated_url": f"/static/annotated/{r['filename_annotated']}",
            "count": r["insect_count"],
            "threat": r["threat_level"],
            "size_kb": round(r["file_size_bytes"] / 1024, 1) if r["file_size_bytes"] else 0
        })

    # Data tren serangga harian
    reversed_rows = list(reversed(rows))
    trend_labels = [clean_timestamp(r["waktu_rtc"]) for r in reversed_rows]
    trend_counts = [r["insect_count"] for r in reversed_rows]

    return jsonify({
        "range": range_param,
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


# ====================================================================================
# API KONTROL DUA ARAH (BIDIRECTIONAL COMMAND)
# ====================================================================================

@app.route("/api/command/trigger", methods=["POST"])
def api_command_trigger():
    """Mengirim perintah jepret manual ke node transmitter via LoRa downlink (INSTAN)."""
    # Cek autentikasi (session atau header X-Auth-User)
    auth_header = request.headers.get("X-Auth-User", "").strip().lower()
    if not session.get("logged_in") and auth_header != "petani":
        return jsonify({"status": "error", "message": "Anda harus login terlebih dahulu untuk mengakses fitur ini."}), 403

    import receiver_daemon as rd

    data = request.get_json(force=True) if request.is_json else {}
    node_id = data.get("node_id", "NODE_01").upper().strip()

    command_str = f"CMD,{node_id},SNAP"
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    # 1. Simpan ke database sebagai riwayat perintah
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
    INSERT INTO pending_commands (timestamp_created, node_id, command_type, command_payload, command_str)
    VALUES (?, ?, ?, ?, ?)
    """, (now_str, node_id, "SNAP", "", command_str))
    conn.commit()
    cmd_id = c.lastrowid

    # 2. KIRIM LANGSUNG ke serial port (Instant SNAP - Always ON Mode)
    sent_now = False
    with rd.serial_lock:
        ser = rd.serial_instance
        if ser and ser.is_open:
            try:
                ser.write((command_str + "\n").encode("utf-8"))
                ser.flush()
                # Tandai sebagai terkirim langsung
                c.execute("""
                UPDATE pending_commands SET executed = 1, executed_at = ? WHERE id = ?
                """, (now_str, cmd_id))
                conn.commit()
                sent_now = True
                print(f"[INSTAN SNAP] Perintah {command_str} langsung dikirim ke {node_id}!")
            except Exception as e:
                print(f"[INSTAN SNAP ERROR] Gagal kirim langsung: {e}")
    conn.close()

    if sent_now:
        return jsonify({
            "status":       "success",
            "message":      f"Perintah jepret dikirim SEKARANG ke {node_id}! "
                            f"Foto akan tiba dalam ~30-60 detik.",
            "command_id":   cmd_id,
            "command_str":  command_str,
            "sent_instant": True
        })
    else:
        return jsonify({
            "status":       "success",
            "message":      f"Perintah jepret untuk {node_id} masuk antrean (#{cmd_id}). "
                            f"Akan dikirim saat koneksi serial tersedia.",
            "command_id":   cmd_id,
            "command_str":  command_str,
            "sent_instant": False
        })



@app.route("/api/command/schedule", methods=["POST"])
def api_command_schedule():
    """Mengubah jadwal pengambilan foto harian node transmitter (INSTAN)."""
    # Cek autentikasi (session atau header X-Auth-User)
    auth_header = request.headers.get("X-Auth-User", "").strip().lower()
    if not session.get("logged_in") and auth_header != "petani":
        return jsonify({"status": "error", "message": "Anda harus login terlebih dahulu untuk mengakses fitur ini."}), 403

    import receiver_daemon as rd

    data = request.get_json(force=True) if request.is_json else {}
    node_id = data.get("node_id", "NODE_01").upper().strip()
    hour = data.get("hour", 8)
    minute = data.get("minute", 0)

    # Validasi input
    try:
        hour = int(hour)
        minute = int(minute)
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Jam dan menit harus berupa angka."}), 400

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return jsonify({"status": "error", "message": "Jam harus 0-23 dan menit harus 0-59."}), 400

    command_str = f"CMD,{node_id},SCHEDULE,{hour:02d},{minute:02d}"
    payload = f"{hour:02d}:{minute:02d}"
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    # 1. Simpan ke database
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
    INSERT INTO pending_commands (timestamp_created, node_id, command_type, command_payload, command_str)
    VALUES (?, ?, ?, ?, ?)
    """, (now_str, node_id, "SCHEDULE", payload, command_str))
    conn.commit()
    cmd_id = c.lastrowid

    # 2. KIRIM LANGSUNG ke serial port (Instant SCHEDULE)
    sent_now = False
    with rd.serial_lock:
        ser = rd.serial_instance
        if ser and ser.is_open:
            try:
                ser.write((command_str + "\n").encode("utf-8"))
                ser.flush()
                # Tandai sebagai terkirim langsung
                c.execute("""
                UPDATE pending_commands SET executed = 1, executed_at = ? WHERE id = ?
                """, (now_str, cmd_id))
                conn.commit()
                sent_now = True
                print(f"[INSTAN SCHEDULE] Perintah {command_str} langsung dikirim ke {node_id}!")
            except Exception as e:
                print(f"[INSTAN SCHEDULE ERROR] Gagal kirim langsung: {e}")
    conn.close()

    if sent_now:
        return jsonify({
            "status": "success",
            "message": f"Jadwal foto {node_id} BERHASIL DIUBAH ke {payload} WIB! (Terkirim langsung)",
            "command_id": cmd_id,
            "command_str": command_str,
            "sent_instant": True
        })
    else:
        return jsonify({
            "status": "success",
            "message": f"Jadwal foto {node_id} akan diubah ke {payload} WIB (antrean #{cmd_id}). "
                       f"Akan dikirim saat koneksi serial siap.",
            "command_id": cmd_id,
            "command_str": command_str,
            "sent_instant": False
        })


@app.route("/api/command/status")
def api_command_status():
    """Mengembalikan status antrean perintah terbaru."""
    node = request.args.get("node")

    conn = get_db_connection()
    c = conn.cursor()

    # Ambil 10 perintah terakhir
    if node:
        c.execute("""
        SELECT id, timestamp_created, node_id, command_type, command_payload, command_str, executed, executed_at 
        FROM pending_commands WHERE node_id = ? ORDER BY id DESC LIMIT 10
        """, (node,))
    else:
        c.execute("""
        SELECT id, timestamp_created, node_id, command_type, command_payload, command_str, executed, executed_at 
        FROM pending_commands ORDER BY id DESC LIMIT 10
        """)
    rows = c.fetchall()

    # Ambil jadwal terakhir yang berhasil dikirim
    if node:
        c.execute("""
        SELECT command_payload FROM pending_commands 
        WHERE node_id = ? AND command_type = 'SCHEDULE' AND executed = 1 
        ORDER BY id DESC LIMIT 1
        """, (node,))
    else:
        c.execute("""
        SELECT command_payload FROM pending_commands 
        WHERE command_type = 'SCHEDULE' AND executed = 1 
        ORDER BY id DESC LIMIT 1
        """)
    last_schedule = c.fetchone()
    conn.close()

    commands = []
    for r in rows:
        commands.append({
            "id": r["id"],
            "timestamp": r["timestamp_created"],
            "node_id": r["node_id"],
            "type": r["command_type"],
            "payload": r["command_payload"],
            "command": r["command_str"],
            "executed": bool(r["executed"]),
            "executed_at": r["executed_at"]
        })

    return jsonify({
        "status": "success",
        "commands": commands,
        "active_schedule": last_schedule["command_payload"] if last_schedule else "08:00",
        "pending_count": sum(1 for c in commands if not c["executed"])
    })


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

    app.run(host="0.0.0.0", port=5000, debug=False)
