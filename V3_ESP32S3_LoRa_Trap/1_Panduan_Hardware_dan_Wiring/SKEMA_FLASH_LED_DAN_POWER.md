# Skema Driver Flash LED, Rekomendasi Lampu, & Manajemen Daya HLK 5V

Dokumen ini memuat detail teknis rekomendasi jenis lampu flash, rangkaian penggerak (*driver*) menggunakan transistor/MOSFET, penyaringan interferensi kipas, dan perlindungan suplai daya HLK 5V 2A.

---

## 💡 1. Rekomendasi Lampu Flash LED Putih

Untuk memotret lem perekat serangga di dalam kotak perangkap (*trap box*) yang tertutup rapat dan gelap, pemilihan lampu LED sangat menentukan akurasi penghitungan serangga (*image counting*).

### A. Karakteristik LED yang Dibutuhkan:
1. **Warna Cahaya:** **Pure White / Cool White (6000K – 6500K)**
   - Cahaya putih dingin memberikan kontras maksimal antara warna kuning/putih pada papan perangkap feromon dan warna serangga hama (biasanya hitam, cokelat tua, abu-abu, atau hijau tua).
2. **Pola Sorotan:** **Wide Flood / Sebaran Lebar (120° – 140°)**
   - Hindari lampu sorot (*spotlight/lensa cembung kecil*) karena akan menimbulkan titik putih menyilaukan (*hotspot glare*) di tengah foto dan sudutnya gelap.
   - Pilihlah LED dengan sudut sebaran rata agar seluruh permukaan lem perekat terang merata.
3. **Daya:** **1 Watt atau 3 Watt (Tegangan Kerja 3.2V – 3.6V, Arus 300mA – 700mA)**
   - Menghasilkan lumen berkisar 100–220 Lumen, cukup untuk menerangi ruang perangkap berjarak 10–30 cm dari kamera OV3660.

### B. Jenis Produk yang Sangat Direkomendasikan di Pasaran:
1. **Opsi 1 (Paling Direkomendasikan & Murah): High Power LED Star 1W / 3W (Cool White)**
   - Bentuk: PCB heksagonal aluminium (*Star PCB*) dengan 1 mata LED di tengah.
   - Sangat mudah dipasang dengan sekrup atau lem termal di samping lensa kamera OV3660.
2. **Opsi 2: Modul LED 5V Transistor Ready (Contoh: Keyestudio / RobotDyn 5V LED Module)**
   - Kelebihan: Sudah ada transistor dan resistor internal di modulnya, tinggal colok VCC 5V, GND, dan Signal ke GPIO 47.
3. **Opsi 3: Potongan Strip LED 5V COB (Chip-on-Board) Cool White (Panjang 5 cm)**
   - Kelebihan: Cahaya sangat merata tanpa bayangan titik, bentuk fleksibel bisa ditempel melingkari area lensa kamera.

---

## ⚡ 2. Skema Rangkaian Driver Flash LED (MOSFET)

> 🛑 **PERINGATAN BAHAYA:**
> Jangan pernah menghubungkan LED 1W/3W langsung ke pin GPIO ESP32-S3! 
> GPIO ESP32-S3 hanya mampu mengalirkan arus maksimal **12 mA - 20 mA**. Jika dipaksa menarik arus 300 mA+, pin GPIO akan terbakar permanen atau menyebabkan ESP32-S3 mengalami *Brownout Reset*.

Gunakan rangkaian driver sakelar elektronik menggunakan **N-Channel Logic-Level MOSFET** (contoh: **AOD4184, IRLZ44N, AO3400**) atau transistor NPN (**2N2222, TIP120, SS8050**).

### Rangkaian Menggunakan N-Channel MOSFET:

```text
       +5V HLK ────┬────────────────────────────────┐
                   │                                │
                   │                          ┌─────┴──────┐
                   │                          │  LED 1W    │
                   │                          │ Cool White │
                   │                          │  (Anoda +) │
                   │                          └─────┬──────┘
                   │                                │ (Katoda -)
                   │                                ▼
                   │                         [ R_drop 2.2Ω 2W ]
                   │                                │
                   │                             (DRAIN)
                   │                         ┌──────────────┐
  GPIO 47 ──[ R1: 220Ω ]───┬─────────────────┤    MOSFET    │
                           │                 │   AOD4184    │
                       [ R2: 10kΩ ]          │   IRLZ44N    │
                           │                 └──────┬───────┘
  GND     ─────────────────┴────────────────────────┴ (SOURCE)
```

### Penjelasan Komponen:
- **R1 (Gate Resistor - 220Ω):** Membatasi arus lonjakan (*inrush current*) saat kapasitansi Gate MOSFET mulai mengisi daya dari pin GPIO 47.
- **R2 (Pull-Down Resistor - 10kΩ):** Menjaga Gate tetap 0V (mati total) saat ESP32-S3 sedang booting atau berada di mode *Deep Sleep*.
- **R_drop (Current Limiting Resistor - 2.2Ω / 2 Watt):**
  - Mengurangi tegangan dari 5V ke tegangan kerja LED (~3.3V) pada arus ~350 mA:
    $$R = \frac{V_{in} - V_{LED}}{I_{LED}} = \frac{5V - 3.3V}{0.35A} \approx 4.8\Omega \text{ (atau 2.2}\Omega \text{ untuk 3W)}$$
  - Jika menggunakan Modul LED yang sudah memiliki resistor bawaan, resistor eksternal ini tidak diperlukan lagi.

---

## ❄️ 3. Kipas DC 5V (Pendinginan Box 24/7)

Karena kotak perangkat berada di kebun terbuka di bawah sinar matahari langsung, suhu di dalam box kedap air (*waterproof enclosure*) dapat mencapai 45°C - 55°C, yang dapat menyebabkan kamera buram atau ESP32 hang.

### Tips Desain Sirkulasi Udara Box:
1. **Posisi Kipas:** Pasang kipas mini 5V (ukuran 30x30 mm atau 40x40 mm) sebagai **Exhaust (penyedot udara panas ke luar)** di sisi atas kotak.
2. **Ventilasi Masuk (Intake):** Buat kisi-kisi udara masuk di sisi bawah dengan pelindung louvers/kisi miring 45° menghadap ke bawah agar air hujan dan debu tidak masuk ke dalam box.
3. **Filter Noise Kipas:** Motor DC kipas menghasilkan dengung induktif (*inductive spike*). Untuk menjaga kestabilan sinyal LoRa dan pembacaan ADC ESP32:
   - Pasang kapasitor elektrolit **100µF / 16V** secara paralel tepat di kaki VCC dan GND kipas.

---

## 🔌 4. Unit Catu Daya (HLK 5V 2A)

Modul **Hi-Link HLK 5V 2A** (contoh: HLK-10M05 atau HLK-PM01 5V 2A) adalah modul AC-to-DC terisolasi yang andal.

### Perhitungan Kebutuhan Beban Daya Maksimal:
- ESP32-S3-CAM (Kamera aktif & Wi-Fi off): ~160 mA
- LoRa Ebyte E220-900T22D (Transmisi 22 dBm): ~120 mA
- Sensor DHT22 & RTC DS3231: ~2 mA
- Kipas DC 5V (terus menyala): ~100 mA
- Lampu Flash LED (pulsa singkat ~1 detik): ~350 mA
- **Total Arus Puncak Maksimal:** **~732 mA**
- **Kapasitas HLK:** **2000 mA (2A)**. Margin keamanan catu daya sangat lega (>60%), menjamin sistem tidak akan kekurangan daya.

### Diagram Pengamanan Input AC 220V:
```text
  PLN 220V Line (L) ─────[ Sekring/Fuse 1A ]─────┐
                                                  [ HLK 5V 2A ]
  PLN 220V Neutral (N) ──────────────────────────┘
           │                                 │
           └────────[ Varistor 10D471K ]─────┘ (Proteksi Petir/Surge)
```
- **Fuse 1A:** Mencegah korsleting jika terjadi gangguan internal.
- **Varistor MOV (10D471K):** Menyerap lonjakan tegangan transien akibat sambaran petir di sekitar tiang kebun.
