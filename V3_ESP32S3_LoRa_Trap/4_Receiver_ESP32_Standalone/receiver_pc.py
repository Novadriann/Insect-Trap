"""
====================================================================================
IMAGE BUILDER & SENSOR RECEIVER - LAPTOP / PC (DATA & GAMBAR MURNI)
Fitur :
  1. Menerima aliran data LoRa dari ESP32 Receiver via USB (COM Port)
  2. Menyimpan data Suhu, Kelembaban, dan Waktu RTC ke CSV (log_sensor.csv)
  3. Merekontruksi data biner foto secara utuh menjadi file gambar (.JPG)
  4. Menyimpan file gambar asli di folder 'hasil_foto/' tanpa deteksi tambahan
Lab ELINS - Universitas Gadjah Mada
====================================================================================
"""

import serial
import serial.tools.list_ports
import time
import os
import csv

# ====================================================================================
# KONFIGURASI
# ====================================================================================
SERIAL_PORT = None  # Otomatis mendeteksi port COM ESP32
BAUD_RATE = 115200

CSV_FILENAME = "log_sensor.csv"
OUTPUT_DIR = "hasil_foto"
os.makedirs(OUTPUT_DIR, exist_ok=True)


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
    """Menyiapkan file CSV pencatat sensor jika belum ada."""
    if not os.path.exists(CSV_FILENAME):
        with open(CSV_FILENAME, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp_PC", "Waktu_RTC", "Suhu_C", "Kelembaban_RH", "Status_Kipas"])


def main():
    init_csv()
    port = get_serial_port()

    if not port:
        print("[!] Port COM ESP32 tidak ditemukan. Pastikan kabel USB sudah terpasang!")
        input("Tekan Enter untuk keluar...")
        return

    print("==================================================================")
    print(f"  RECEIVER PERANGKAP HAMA AKTIF DI PC/LAPTOP ({port})")
    print("  Menunggu data Sensor (Suhu, Kelembaban, RTC) & Gambar Foto...")
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
            # 1. PARSING DAN PENYIMPANAN DATA SENSOR
            # --------------------------------------------------------------
            if b'[DATA]' in line or b'SENSOR,' in line:
                try:
                    text = line.decode('utf-8', errors='ignore').strip()
                    if "[DATA]" in text:
                        clean_data = text[text.find("[DATA]"):]
                        parts = clean_data.split(",")
                        waktu = parts[0].replace("[DATA] Waktu:", "").strip()
                        suhu = parts[1].replace("Suhu:", "").replace("C", "").strip()
                        hum = parts[2].replace("Kelembaban:", "").replace("%", "").strip()
                        fan = parts[3].replace("Kipas:", "").strip() if len(parts) > 3 else "-"
                    else:
                        clean_data = text[text.find("SENSOR,"):]
                        parts = clean_data.split(",")
                        suhu = parts[2].strip()
                        hum = parts[3].strip()
                        waktu = f"{parts[4].strip()} {parts[5].strip()}"
                        fan = "AUTO"

                    now_pc = time.strftime("%Y-%m-%d %H:%M:%S")
                    with open(CSV_FILENAME, mode='a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([now_pc, waktu, suhu, hum, fan])

                    print(f"[+] DATA SENSOR -> Suhu: {suhu} C | RH: {hum} % | Waktu: {waktu} | Kipas: {fan}")
                    print(f"    (Data tersimpan ke '{CSV_FILENAME}')\n")
                except Exception as err:
                    print(f"[!] Gagal parsing data sensor: {err}")

            # --------------------------------------------------------------
            # 2. PENERIMAAN DAN PENYUSUNAN GAMBAR (IMAGE BUILDER)
            # --------------------------------------------------------------
            elif b'---START---' in line:
                print("[*] MEMULAI PENERIMAAN FOTO DARI LORA...")
                expected_length = 0

                # Cek apakah ukuran gambar ada di baris yang sama atau baris berikutnya
                line_str = line.decode('utf-8', errors='ignore').strip()
                if "---START---" in line_str and len(line_str.split("---START---")) > 1 and line_str.split("---START---")[1].strip().isdigit():
                    expected_length = int(line_str.split("---START---")[1].strip())
                else:
                    len_line = ser.readline().decode('utf-8', errors='ignore').strip()
                    try:
                        expected_length = int(len_line)
                    except ValueError:
                        print(f"[!] Format ukuran foto tidak valid: '{len_line}'. Batal.")
                        continue

                print(f"[*] Ukuran Foto: {expected_length} Bytes. Mengunduh data biner...")

                image_data = bytearray()
                start_time = time.time()

                # Baca byte biner persis sesuai ukuran
                while len(image_data) < expected_length:
                    sisa = expected_length - len(image_data)
                    chunk = ser.read(min(200, sisa))
                    if chunk:
                        image_data.extend(chunk)
                        pct = (len(image_data) / expected_length) * 100.0
                        print(f"\r[*] Progress Download: {pct:.1f}% ({len(image_data)}/{expected_length} Bytes)", end="")
                    else:
                        if time.time() - start_time > 45:
                            print("\n[!] Timeout saat mengunduh foto.")
                            break

                print() # Baris baru

                # Bersihkan sisa buffer / marker END
                time.sleep(0.1)
                if ser.in_waiting:
                    ser.read(ser.in_waiting)

                # Simpan file gambar asli (.JPG)
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(OUTPUT_DIR, f"hama_{timestamp}.jpg")

                with open(filename, "wb") as f_img:
                    f_img.write(image_data)

                print("------------------------------------------------------")
                print(f"[SUKSES] GAMBAR DISIMPAN: {filename} ({len(image_data)} Bytes)")
                print("------------------------------------------------------\n")

        except KeyboardInterrupt:
            print("\n[*] Program dihentikan pengguna.")
            ser.close()
            break
        except Exception:
            pass


if __name__ == "__main__":
    main()
