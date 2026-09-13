"""
====================================================================================
IMAGE BUILDER & SENSOR RECEIVER - LAPTOP / PC (MULTI-NODE SUPPORT)
Fitur :
  1. Menerima aliran data LoRa dari ESP32 Receiver via USB (COM Port)
  2. Mendukung banyak node transmitter (NODE_01, NODE_02, dst)
  3. Menyimpan data Suhu, Kelembaban, RTC, dan Node ID ke CSV (log_sensor.csv)
  4. Merekontruksi data biner foto secara utuh menjadi file gambar (.JPG)
  5. Menyimpan file gambar rapi ke subfolder masing-masing node (hasil_foto/NODE_01/)
Lab ELINS - Universitas Gadjah Mada
====================================================================================
"""

import serial
import serial.tools.list_ports
import time
import os
import csv
import re

# ====================================================================================
# KONFIGURASI
# ====================================================================================
SERIAL_PORT = None  # None = Otomatis mendeteksi port COM ESP32
BAUD_RATE = 115200

CSV_FILENAME = "log_sensor.csv"
OUTPUT_BASE_DIR = "hasil_foto"
os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)


def get_serial_port():
    """Mencari port COM ESP32 secara otomatis di Windows."""
    if SERIAL_PORT:
        return SERIAL_PORT

    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = p.description.lower()
        if "cp210" in desc or "ch340" in desc or "usb-serial" in desc or "uart" in desc:
            return p.device
    if ports:
        return ports[0].device
    return None


def init_csv():
    """Menyiapkan file CSV pencatat sensor dengan header Node_ID."""
    if not os.path.exists(CSV_FILENAME):
        with open(CSV_FILENAME, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp_PC", "Node_ID", "Waktu_RTC", "Suhu_C", "Kelembaban_RH", "Status_Kipas"])
    else:
        # Periksa apakah header lama belum memiliki Node_ID
        try:
            with open(CSV_FILENAME, mode='r') as f:
                first_line = f.readline()
                if "Node_ID" not in first_line:
                    # Backup file lama dan buat baru dengan header lengkap
                    backup_name = f"log_sensor_backup_{int(time.time())}.csv"
                    os.rename(CSV_FILENAME, backup_name)
                    print(f"[*] File CSV lama di-backup ke '{backup_name}' karena pembaruan format multi-node.")
                    with open(CSV_FILENAME, mode='w', newline='') as f_new:
                        writer = csv.writer(f_new)
                        writer.writerow(["Timestamp_PC", "Node_ID", "Waktu_RTC", "Suhu_C", "Kelembaban_RH", "Status_Kipas"])
        except Exception:
            pass


def parse_sensor_line(line_str):
    """
    Mem-parse baris data sensor yang mungkin berasal dari format baru (Multi-Node)
    maupun format lama (Single Node).
    Contoh Format Baru:
      [DATA] Node: NODE_01, Waktu: 2026-09-11 12:00:00, Suhu: 26.5 C, Kelembaban: 58.0 %, Kipas: ON
    Contoh Format Lama:
      [DATA] Waktu: 2026-09-11 12:00:00, Suhu: 26.5 C, Kelembaban: 58.0 %, Kipas: ON
    """
    node_id = "NODE_01"
    waktu = time.strftime("%Y-%m-%d %H:%M:%S")
    suhu = "0.0"
    hum = "0.0"
    fan = "-"

    clean_str = line_str[line_str.find("[DATA]"):] if "[DATA]" in line_str else line_str
    parts = [p.strip() for p in clean_str.split(",")]

    for p in parts:
        if "Node:" in p:
            node_id = p.replace("[DATA]", "").replace("Node:", "").strip()
        elif "Waktu:" in p:
            waktu = p.replace("[DATA]", "").replace("Waktu:", "").strip()
        elif "Suhu:" in p:
            suhu = p.replace("Suhu:", "").replace("C", "").strip()
        elif "Kelembaban:" in p:
            hum = p.replace("Kelembaban:", "").replace("%", "").strip()
        elif "Kipas:" in p:
            fan = p.replace("Kipas:", "").strip()

    return node_id, waktu, suhu, hum, fan


def extract_node_from_start_header(header_str):
    """
    Mengekstrak Node ID dari tag ---START:NODE_XX---
    Jika hanya ---START---, default ke NODE_01
    """
    match = re.search(r'---START:(NODE_\w+)---', header_str, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return "NODE_01"


def main():
    init_csv()
    port = get_serial_port()

    if not port:
        print("[!] Port COM ESP32 tidak ditemukan. Pastikan kabel USB sudah terpasang!")
        input("Tekan Enter untuk keluar...")
        return

    print("==================================================================")
    print(f"  RECEIVER MULTI-NODE PERANGKAP HAMA AKTIF DI PC ({port})")
    print("  Mendukung: NODE_01, NODE_02, dst.")
    print("  Menunggu data Sensor & Aliran Gambar LoRa...")
    print("==================================================================\n")

    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=2)
    except Exception as e:
        print(f"[!] Gagal membuka {port}: {e}")
        print("Pastikan Serial Monitor Arduino IDE sudah DITUTUP terlebih dahulu!")
        return

    while True:
        try:
            line = ser.readline()
            if not line:
                continue

            # --------------------------------------------------------------
            # 1. PARSING DAN PENYIMPANAN DATA SENSOR MULTI-NODE
            # --------------------------------------------------------------
            if b'[DATA]' in line or b'SENSOR,' in line:
                try:
                    text = line.decode('utf-8', errors='ignore').strip()
                    node_id, waktu, suhu, hum, fan = parse_sensor_line(text)

                    now_pc = time.strftime("%Y-%m-%d %H:%M:%S")
                    with open(CSV_FILENAME, mode='a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([now_pc, node_id, waktu, suhu, hum, fan])

                    print(f"[+] SENSOR [{node_id}] -> Suhu: {suhu} C | RH: {hum} % | Waktu: {waktu} | Kipas: {fan}")
                    print(f"    (Data dicatat ke '{CSV_FILENAME}')\n")
                except Exception as err:
                    print(f"[!] Gagal parsing data sensor: {err}")

            # --------------------------------------------------------------
            # 2. PENERIMAAN DAN PENYUSUNAN GAMBAR MULTI-NODE
            # --------------------------------------------------------------
            elif b'---START' in line:
                line_str = line.decode('utf-8', errors='ignore').strip()
                node_id = extract_node_from_start_header(line_str)

                print(f"\n[*] MEMULAI PENERIMAAN FOTO DARI LORA [{node_id}]...")
                expected_length = 0

                # Cek apakah ukuran gambar ada di baris header atau baris berikutnya
                # Format 1: ---START:NODE_01---12500
                after_tag = line_str.split("---")[-1].strip()
                if after_tag.isdigit():
                    expected_length = int(after_tag)
                else:
                    len_line = ser.readline().decode('utf-8', errors='ignore').strip()
                    try:
                        expected_length = int(len_line)
                    except ValueError:
                        print(f"[!] Format ukuran foto tidak valid: '{len_line}'. Batal.")
                        continue

                print(f"[*] Ukuran Foto [{node_id}]: {expected_length} Bytes. Mengunduh data biner...")

                image_data = bytearray()
                start_time = time.time()

                # Baca byte biner persis sesuai ukuran
                while len(image_data) < expected_length:
                    sisa = expected_length - len(image_data)
                    chunk = ser.read(min(200, sisa))
                    if chunk:
                        image_data.extend(chunk)
                        pct = (len(image_data) / expected_length) * 100.0
                        print(f"\r[*] Progress [{node_id}]: {pct:.1f}% ({len(image_data)}/{expected_length} Bytes)", end="")
                    else:
                        if time.time() - start_time > 45:
                            print(f"\n[!] Timeout saat mengunduh foto [{node_id}].")
                            break

                print()  # Baris baru

                # Bersihkan sisa buffer / marker END
                time.sleep(0.1)
                if ser.in_waiting:
                    ser.read(ser.in_waiting)

                # Siapkan subfolder khusus per Node
                node_dir = os.path.join(OUTPUT_BASE_DIR, node_id)
                os.makedirs(node_dir, exist_ok=True)

                # Simpan file gambar asli (.JPG)
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(node_dir, f"hama_{node_id}_{timestamp}.jpg")

                with open(filename, "wb") as f_img:
                    f_img.write(image_data)

                print("------------------------------------------------------------------")
                print(f"[SUKSES] GAMBAR DISIMPAN [{node_id}]: {filename} ({len(image_data)} Bytes)")
                print("------------------------------------------------------------------\n")

        except KeyboardInterrupt:
            print("\n[*] Program dihentikan pengguna.")
            ser.close()
            break
        except Exception:
            pass


if __name__ == "__main__":
    main()
