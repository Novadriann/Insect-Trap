# Skema Rangkaian Flash LED Pentol 5mm, Sakelar Kipas RTC, & Daya HLK

Dokumen ini memuat detail teknis rangkaian lampu flash menggunakan **LED Pentol Putih 5mm biasa**, rangkaian sakelar elektronik **Kipas DC 5V dengan pemicu waktu RTC (07:00 – 17:00)**, dan suplai daya HLK 5V 2A.

---

## 💡 1. Lampu Flash LED Pentol Putih 5mm (Langsung GPIO 47)

Sesuai permintaan, sistem disederhanakan menggunakan **LED pentol putih biasa (DIP 5mm / Through-Hole)** sehingga **tidak memerlukan driver MOSFET besar atau modul 1–3 Watt**.

### A. Karakteristik Listrik:
- **Tegangan Maju ($V_F$):** 3.0V – 3.2V
- **Arus Kerja ($I_F$):** 15 mA – 20 mA
- **Kemampuan Pin GPIO ESP32-S3:** Mampu mengalirkan arus hingga 20 mA. Karena kebutuhan arus LED pentol hanya ~15 mA, LED dapat **dihubungkan langsung ke pin GPIO 47** dengan penambahan satu buah resistor pembatas arus (*current limiting resistor*).

### B. Perhitungan Resistor Pembatas Arus:
$$R = \frac{V_{GPIO} - V_{LED}}{I_{LED}} = \frac{3.3\text{V} - 3.0\text{V}}{0.015\text{A}} \approx 20\Omega$$
Untuk menjaga keawetan LED dan kestabilan mikrokontroler, gunakan nilai standar:
- **R = 150Ω atau 220Ω (1/4 Watt)**

### C. Skema Pengkabelan Flash LED:
```text
  ESP32-S3 GPIO 47 ─────[ Resistor 150Ω - 220Ω ]─────(+) [ LED Pentol 5mm ] (─)─────► GND
                                                    (Kaki Panjang)   (Kaki Pendek)
```

---

## ❄️ 2. Rangkaian Sakelar Kipas DC 5V (Trigger Waktu RTC 07:00 - 17:00)

Kipas mini DC 5V mengonsumsi arus sekitar **100 mA – 150 mA**. Karena arus ini melebihi kapasitas pin GPIO (maks. 20 mA), kipas **TIDAK BOLEH** dihubungkan langsung ke pin mikrokontroler. Kita menggunakan **1 buah transistor NPN kecil serbaguna** (seperti **2N2222, SS8050, atau BC547**) sebagai sakelar otomatis.

### A. Komponen Rangkaian Kipas:
1. **Transistor NPN:** 2N2222 / SS8050 / BD139 (kemasan TO-92 kecil dan murah)
2. **Resistor Basis:** 1 kΩ (1/4 Watt)
3. **Dioda Proteksi (Flyback):** 1N4148 atau 1N4007 (mencegah lonjakan tegangan induksi saat kipas mati)

### B. Skema Rangkaian Sakelar Kipas:
```text
                    +5V HLK ────┬─────────────────────────────┐
                                │                             │
                                │                      ┌──────┴──────┐
                                │                      │   Kipas 5V  │
                                │                   (+)│ (Kabel Merah│
                                │                      └──────┬──────┘
                                │                             │ (─) Kabel Hitam
                        [ Dioda 1N4007 ]                      │
                        (Katoda / Garis)                      │
                                ▲                             │
                                └─────────────────────────────┤ (KOLEKTOR)
                                                              │
                                                       ┌──────┴──────┐
  GPIO 21 ─────────────[ Resistor 1kΩ ]───────────────┤  Transistor │
  (ESP32-S3)                                   (BASIS)│   2N2222    │
                                                      │  (EMITOR)   │
                                                      └──────┬──────┘
  GND ───────────────────────────────────────────────────────┴────────► GND
```

### C. Cara Kerja Otomatisasi Waktu RTC:
1. Saat ESP32-S3 bangun, program membaca jam dari RTC DS3231:
   ```cpp
   int jamSekarang = now.hour();
   bool fanShouldBeOn = (jamSekarang >= 7 && jamSekarang < 17);
   ```
2. **Jika Pukul 07:00 – 17:00:**
   - Program menyetel `GPIO 21 = HIGH (3.3V)`.
   - Transistor 2N2222 aktif jenuh (*saturation*), menghubungkan kutub negatif kipas ke GND. Kipas menyala berputar.
   - Program memanggil fungsi `gpio_hold_en((gpio_num_t)FAN_PIN);` dan `gpio_deep_sleep_hold_en();`.
   - **Kipas tetap berputar mendinginkan box meskipun ESP32-S3 sedang berada dalam kondisi Deep Sleep!**
3. **Jika Pukul 17:01 – 06:59 (Malam Hari):**
   - Suhu lingkungan di kebun sudah dingin dan tidak ada terik matahari.
   - Program menyetel `GPIO 21 = LOW (0V)`.
   - Transistor mati (*cutoff*), kipas berhenti berputar untuk menghemat daya dan memperpanjang umur motor kipas.

---

## 🔌 3. Unit Catu Daya (HLK 5V 2A)

Modul **Hi-Link HLK 5V 2A** (Input 220V AC, Output 5V DC 2A / 10 Watt) menyuplai seluruh sistem dengan sangat aman.

### Rekap Konsumsi Arus Sistem:
- ESP32-S3-CAM aktif: ~160 mA
- LoRa Ebyte E220 transmisi: ~120 mA
- Sensor DHT22 + RTC DS3231: ~2 mA
- Lampu Flash LED Pentol 5mm: ~15 mA (hanya saat jepret ~0.4 detik)
- Kipas DC 5V (jam 07:00–17:00): ~120 mA
- **Total Arus Beban Puncak:** **~417 mA**
- **Kapasitas HLK:** **2000 mA (2A)**. Beban riil hanya menggunakan sekitar **20%** dari kapasitas maksimal HLK, sehingga adaptor bekerja sangat dingin dan awet 24/7.
