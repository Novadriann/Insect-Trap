import serial
import time
import os
import csv

# Konfigurasi Port
SERIAL_PORT = 'COM5' # SESUAIKAN
BAUD_RATE = 115200
CSV_FILENAME = 'log_hama_sensor.csv'

def setup_csv():
    if not os.path.exists(CSV_FILENAME):
        with open(CSV_FILENAME, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp_PC", "Waktu_RTC_Alat", "Suhu_C", "Kelembaban_%"])

def main():
    setup_csv()
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
        print(f"[*] Terhubung ke {SERIAL_PORT}. Menunggu data Sensor & Gambar...")
    except Exception as e:
        print(f"[!] Gagal membuka port {SERIAL_PORT}: {e}")
        return

    receiving_image = False
    image_data = bytearray()
    expected_size = 0

    while True:
        try:
            if not receiving_image:
                line = ser.readline()
                if line:
                    try:
                        text = line.decode('utf-8', errors='ignore').strip()
                        
                        # 1. DATA SENSOR
                        if text.startswith("[DATA]"):
                            print(f"\n[+] SENSOR: {text}")
                            try:
                                parts = text.split(',')
                                waktu_rtc = parts[0].replace("[DATA] Waktu:", "").strip()
                                suhu = parts[1].replace("Suhu:", "").replace("C", "").strip()
                                kelembaban = parts[2].replace("Kelembaban:", "").replace("%", "").strip()
                                
                                with open(CSV_FILENAME, mode='a', newline='') as file:
                                    writer = csv.writer(file)
                                    writer.writerow([time.strftime('%Y-%m-%d %H:%M:%S'), waktu_rtc, suhu, kelembaban])
                                print("[*] Data CSV tersimpan.")
                            except Exception as e:
                                print(f"[!] Gagal parsing data sensor: {e}")

                        # 2. MULAI GAMBAR
                        elif text.startswith("---START---"):
                            expected_size = int(text.split("---")[2])
                            print(f"\n[*] Memulai unduhan gambar. Ukuran: {expected_size} bytes")
                            receiving_image = True
                            image_data = bytearray()
                    except Exception:
                        pass
            else:
                chunk = ser.read(min(150, expected_size - len(image_data)))
                if chunk:
                    image_data.extend(chunk)
                    print(f"\rProgress: {len(image_data)} / {expected_size} bytes", end="")

                if ser.in_waiting:
                    tail = ser.read(ser.in_waiting)
                    image_data.extend(tail)
                    
                    if b"---END---" in image_data:
                        image_data = image_data.split(b"---END---")[0]
                        filename = f"trap_V2_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
                        with open(filename, "wb") as f:
                            f.write(image_data)
                        print(f"\n[*] GAMBAR DISIMPAN: {filename}\n")
                        receiving_image = False
                        image_data = bytearray()
                        expected_size = 0
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    main()
