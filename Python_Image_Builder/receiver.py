import serial
import time
import os

# ==========================================
# KONFIGURASI PORT - SESUAIKAN DENGAN PC KAMU
# ==========================================
# Ganti dengan port COM ESP32 Receiver kamu (cek di Device Manager, misal 'COM3' atau 'COM5')
SERIAL_PORT = 'COM5' 
BAUD_RATE = 115200

def main():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
        print(f"[*] Terhubung ke {SERIAL_PORT}. Menunggu transmisi gambar harian...")
    except Exception as e:
        print(f"[!] Gagal membuka port {SERIAL_PORT}: {e}")
        print("Pastikan IDE Arduino / Serial Monitor ditutup, lalu coba lagi.")
        return

    while True:
        try:
            # Membaca output serial secara berlanjut
            line = ser.readline()
            
            if b'---START---' in line:
                print("\n[+] Menerima transmisi gambar baru...")
                image_data = bytearray()
                
                # Baris selanjutnya adalah ukuran panjang file gambar
                len_line = ser.readline().decode('utf-8', errors='ignore').strip()
                try:
                    expected_length = int(len_line)
                    print(f"[*] Menunggu data sebesar: {expected_length} bytes")
                except ValueError:
                    print("[!] Gagal membaca format ukuran file. Proses dibatalkan.")
                    continue
                
                # Baca byte data biner tepat sebesar expected_length
                # Hal ini dilakukan karena binary image memiliki byte acak, readline() tidak efektif.
                while len(image_data) < expected_length:
                    # Baca sisa byte yang diperlukan
                    chunk = ser.read(expected_length - len(image_data))
                    if chunk:
                        image_data.extend(chunk)
                        # Opsional: Tampilkan persentase download
                        progress = (len(image_data) / expected_length) * 100
                        print(f"\r[*] Mendownload: {progress:.1f}%", end="")
                    else:
                        # Timeout
                        break
                        
                print() # Baris baru
                
                # Baca sisa buffer untuk mencari marker ---END---
                end_marker = ser.readline() + ser.readline()
                if b'---END---' in end_marker:
                    print("[+] Marker END ditemukan. Gambar valid.")
                else:
                    print("[-] Peringatan: Marker END tidak ditemukan dengan sempurna, namun ukuran file sudah terpenuhi.")

                # Membuat nama file unik berdasarkan timestamp
                filename = f"hama_trap_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
                
                # Menyimpan gambar
                with open(filename, "wb") as f:
                    f.write(image_data)
                
                print(f"[SUCCESS] Gambar berhasil direkonstruksi dan disimpan sebagai: {filename}")
                print("[*] Menunggu transmisi untuk besok...\n")

        except KeyboardInterrupt:
            print("\n[*] Program dihentikan pengguna.")
            ser.close()
            break
        except Exception as e:
            pass # Hiraukan error minor dari serial parsing

if __name__ == "__main__":
    # Buat folder 'images' jika ingin merapikan (Opsional)
    main()
