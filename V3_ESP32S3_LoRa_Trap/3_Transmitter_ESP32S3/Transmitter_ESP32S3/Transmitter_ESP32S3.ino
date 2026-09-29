/**
 * ====================================================================================
 * PROGRAM TRANSMITTER NODE - SISTEM PEMANTAUAN PERANGKAP HAMA (INSECT TRAP) V3.1
 * Hardware : ESP32-S3-CAM (OV3660) + LoRa Ebyte E220-900T22D + DHT22 + RTC DS3231
 * Fitur Baru:
 *   1. Kipas DC 5V dikontrol otomatis berdasarkan waktu RTC:
 *      - AKTIF (ON) : Pukul 07:00 pagi s/d 17:00 sore
 *      - MATI (OFF) : Pukul 17:01 sore s/d 06:59 pagi
 *      - Status pin dipertahankan selama Deep Sleep (gpio_hold_en)
 *   2. Lampu Flash menggunakan LED Pentol Putih Biasa (DIP 5mm) + Resistor 150-220 ohm
 *      (Langsung dari GPIO 47, tanpa perlu driver MOSFET daya besar 1-3 Watt).
 *   3. Pengambilan foto 1x sehari (misal pukul 08:00 pagi) atau setiap bangun di mode tes.
 * Lab ELINS - Universitas Gadjah Mada
 * ====================================================================================
 */

#include "esp_camera.h"
#include <HardwareSerial.h>
#include <Wire.h>
#include "RTClib.h"
#include "DHT.h"
#include "driver/rtc_io.h"
#include "driver/gpio.h"
#include "esp_sleep.h"
#include <Preferences.h>

// ====================================================================================
// 1. PENGATURAN PIN HARDWARE (BEBAS KONFLIK ESP32-S3 CAM)
// ====================================================================================

// --- Pin Sensor DHT22 ---
#define DHTPIN          1          // GPIO 1 (ADC1_CH0)
#define DHTTYPE         DHT22
DHT dht(DHTPIN, DHTTYPE);

// --- Pin I2C RTC DS3231 ---
#define I2C_SDA         2          // GPIO 2
#define I2C_SCL         3          // GPIO 3
RTC_DS3231 rtc;

// --- Pin LoRa Ebyte E220-900T22D ---
#define LORA_RX_PIN     41         // Hubungkan ke TXD modul LoRa
#define LORA_TX_PIN     42         // Hubungkan ke RXD modul LoRa
HardwareSerial LoRaSerial(1);      // Menggunakan UART1 ESP32-S3

// --- Pin Lampu Flash (LED Pentol Putih 5mm + Resistor 150-220 ohm ke GND) ---
#define FLASH_PIN       47         // GPIO 47 (Langsung mengendalikan LED pentol)

// --- Pin Kendali Kipas DC 5V (Ke Basis Transistor / Gate MOSFET Kipas) ---
#define FAN_PIN         21         // GPIO 21 (Aktif HIGH pada jam 07:00 - 17:00)

// --- PENGATURAN RESOLUSI KAMERA ---
// FRAMESIZE_QVGA (320x240, ~7-10 KB, sangat cepat) atau FRAMESIZE_VGA (640x480, detail)
#define CAMERA_FRAME_SIZE FRAMESIZE_VGA

// ====================================================================================
// 0. IDENTITAS NODE TRANSMITTER (MULTI-NODE SUPPORT)
// ====================================================================================
// Beri nama unik untuk setiap node perangkap:
// - Alat 1: "NODE_01"
// - Alat 2: "NODE_02"
#define NODE_ID                 "NODE_01"

// --- PENGATURAN JADWAL OPERASIONAL ---
// Interval bangun per siklus untuk mengecek jadwal kipas & kirim sensor:
// - Mode Lab / Pengujian: 30 detik (30ULL)
// - Mode Kebun          : 1800 detik (30 menit) atau 3600 detik (1 jam)
const uint64_t WAKEUP_INTERVAL_SECONDS = 30; // Ubah ke 1800 (30 menit) saat di kebun

// Jadwal Pengambilan Foto Harian (Pencegahan Tabrakan / Anti-Collision):
// Node 01: Pukul 08:00 (PHOTO_TARGET_HOUR 8, PHOTO_TARGET_MINUTE 0)
// Node 02: Pukul 08:05 (PHOTO_TARGET_HOUR 8, PHOTO_TARGET_MINUTE 5) -> Selisih 5 menit
// Jadwal foto dinamis (bisa diubah dari dashboard via LoRa downlink)
RTC_DATA_ATTR int photoTargetHour = 8;
RTC_DATA_ATTR int photoTargetMinute = 0;
RTC_DATA_ATTR bool forceCaptureNow = false;  // Flag jepret manual dari dashboard

// Set true jika foto hanya dikirim 1x sehari saat jam target.
// Set false jika ingin foto dikirim SETIAP KALI alat bangun (sangat berguna untuk tes di lab).
#define SEND_PHOTO_ONCE_DAILY   false

// Variabel memori RTC (Tersimpan aman saat Deep Sleep)
RTC_DATA_ATTR int lastPhotoDay = -1;

// ====================================================================================
// 2. MAPPING PIN KAMERA OV3660 UNTUK ESP32-S3-CAM
// ====================================================================================
#define PWDN_GPIO_NUM    -1
#define RESET_GPIO_NUM   -1
#define XCLK_GPIO_NUM    15
#define SIOD_GPIO_NUM    4
#define SIOC_GPIO_NUM    5

#define Y9_GPIO_NUM      16 // D7
#define Y8_GPIO_NUM      17 // D6
#define Y7_GPIO_NUM      18 // D5
#define Y6_GPIO_NUM      12 // D4
#define Y5_GPIO_NUM      10 // D3
#define Y4_GPIO_NUM      8  // D2
#define Y3_GPIO_NUM      9  // D1
#define Y2_GPIO_NUM      11 // D0
#define VSYNC_GPIO_NUM   6
#define HREF_GPIO_NUM    7
#define PCLK_GPIO_NUM    13

// ====================================================================================
// 3. FUNGSI INISIALISASI KAMERA
// ====================================================================================
bool initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  // Kompatibilitas nama field antara ESP32 Arduino Library v2.x dan v3.x
  #if defined(ARDUINO_ESP32S3_DEV) && ESP_ARDUINO_VERSION_MAJOR >= 3
    config.pin_sccb_sda = SIOD_GPIO_NUM;  // Library v3.x (nama baru: sccb)
    config.pin_sccb_scl = SIOC_GPIO_NUM;
  #else
    config.pin_sscb_sda = SIOD_GPIO_NUM;  // Library v2.x (nama lama: sscb)
    config.pin_sscb_scl = SIOC_GPIO_NUM;
  #endif
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = CAMERA_FRAME_SIZE;
  config.jpeg_quality = 10;          // Kualitas JPEG (10 = jernih & tajam)
  config.fb_count     = 1;
  // Gunakan PSRAM jika tersedia, fallback ke DRAM agar tidak crash jika PSRAM belum aktif
  config.fb_location  = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[ERROR] Inisialisasi kamera gagal! Kode: 0x%x\n", err);
    return false;
  }

  // Kalibrasi Sensor OV3660 - Perbaikan warna hijau (Green Tint Fix)
  sensor_t *s = esp_camera_sensor_get();
  if (s != NULL) {
    s->set_vflip(s, 1);            // Balik vertikal jika terbalik
    s->set_hmirror(s, 0);          // Horizontal mirror
    s->set_brightness(s, 1);       // Tingkatkan kecerahan
    s->set_contrast(s, 1);         // Tingkatkan kontras agar serangga terlihat jelas
    s->set_saturation(s, 0);       // Saturasi normal (bukan -1 agar warna akurat)
    s->set_special_effect(s, 0);   // No special effect
    s->set_whitebal(s, 1);         // Aktifkan Auto White Balance
    s->set_awb_gain(s, 1);         // Aktifkan AWB Gain Control
    // KUNCI: Mode WB Sunny (1) cocok untuk pencahayaan LED putih indoor
    // 0=Auto, 1=Sunny, 2=Cloudy, 3=Office (Fluorescent), 4=Home (Incandescent)
    s->set_wb_mode(s, 1);          // Sunny Mode: tidak melenceng hijau
    s->set_exposure_ctrl(s, 1);    // Aktifkan Auto Exposure Control
    s->set_aec2(s, 1);             // Aktifkan AEC2 (Night Mode Auto Exposure)
    s->set_gain_ctrl(s, 1);        // Aktifkan Auto Gain Control
    s->set_bpc(s, 1);              // Bad Pixel Correction (mengurangi noise)
    s->set_wpc(s, 1);              // White Pixel Correction
    s->set_raw_gma(s, 1);          // Gamma Correction untuk warna lebih natural
    s->set_lenc(s, 1);             // Lens Correction (meratakan pencahayaan sudut)
  }
  return true;
}

// ====================================================================================
// 4. PROGRAM SETUP (DIJALANKAN SETIAP BANGUN DARI SLEEP)
// ====================================================================================
void setup() {
  // Lepas kunci hold pin agar bisa dikontrol kembali setelah deep sleep
  gpio_hold_dis((gpio_num_t)FAN_PIN);

  // Inisialisasi Serial Debug (Port USB TTL)
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n========================================================");
  Serial.println("  SISTEM TRAP HAMA: ESP32-S3 CAM TRANSMITTER BANGUN");
  Serial.println("========================================================");

  // Setup Pin Flash LED (LED Pentol)
  pinMode(FLASH_PIN, OUTPUT);
  digitalWrite(FLASH_PIN, LOW); // Pastikan mati awal

  // Setup Pin Kipas
  pinMode(FAN_PIN, OUTPUT);

  // Inisialisasi UART LoRa E220
  LoRaSerial.begin(115200, SERIAL_8N1, LORA_RX_PIN, LORA_TX_PIN);
  Serial.println("[OK] Serial LoRa E220 baudrate 115200.");

  // Muat jadwal foto dari NVS (Non-Volatile Storage) agar tetap tersimpan walau baterai dicabut
  Preferences prefs;
  prefs.begin("trapconf", true);  // Read-only mode
  photoTargetHour = prefs.getInt("photoHour", photoTargetHour);
  photoTargetMinute = prefs.getInt("photoMin", photoTargetMinute);
  prefs.end();
  Serial.printf("[OK] Jadwal foto dari NVS: %02d:%02d\n", photoTargetHour, photoTargetMinute);

  // Cek PSRAM
  if (psramFound()) {
    Serial.printf("[OK] PSRAM Terdeteksi: %d bytes bebas.\n", ESP.getFreePsram());
  } else {
    Serial.println("[WARNING] PSRAM TIDAK AKTIF! Kamera mungkin gagal.");
  }

  // Inisialisasi Sensor DHT22
  dht.begin();
  Serial.println("[OK] Sensor DHT22 dimulai.");

  // Inisialisasi Bus I2C & RTC DS3231
  Wire.begin(I2C_SDA, I2C_SCL);
  bool rtcOk = rtc.begin();
  if (rtcOk) {
    Serial.println("[OK] RTC DS3231 terdeteksi.");
    
    // SINKRONISASI WAKTU KE JAM SEKARANG:
    // Otomatis sinkron jika waktu RTC lebih lampau dari waktu kompilasi atau baru upload/reset
    DateTime compileTime = DateTime(F(__DATE__), F(__TIME__));
    DateTime rtcCurrent = rtc.now();
    
    if (rtcCurrent < compileTime || esp_sleep_get_wakeup_cause() == ESP_SLEEP_WAKEUP_UNDEFINED) {
      rtc.adjust(compileTime);
      Serial.printf("[OK] Waktu RTC DS3231 disinkronkan ke: %04d-%02d-%02d %02d:%02d:%02d\n",
                    compileTime.year(), compileTime.month(), compileTime.day(),
                    compileTime.hour(), compileTime.minute(), compileTime.second());
    } else {
      Serial.printf("[OK] Melanjutkan waktu dari RTC DS3231: %02d:%02d:%02d\n",
                    rtcCurrent.hour(), rtcCurrent.minute(), rtcCurrent.second());
    }
  } else {
    Serial.println("[ERROR] RTC DS3231 TIDAK DITEMUKAN! Periksa pin SDA(2) & SCL(3).");
  }

  // ----------------------------------------------------------------------------------
  // LANGKAH 1: BACA SENSOR & EVALUASI JADWAL KIPAS DARI RTC
  // ----------------------------------------------------------------------------------
  DateTime now = (rtcOk) ? rtc.now() : DateTime(2026, 9, 11, 11, 30, 0);
  float suhu = dht.readTemperature();
  float kelembaban = dht.readHumidity();

  if (isnan(suhu) || isnan(kelembaban)) {
    Serial.println("[WARNING] Gagal membaca data DHT22. Menggunakan default 0.0.");
    suhu = 0.0;
    kelembaban = 0.0;
  }

  // LOGIKA KIPAS: Aktif pukul 07:00 s/d 17:00 (Jam 7 pagi hingga 5 sore)
  int jamSekarang = now.hour();
  bool fanShouldBeOn = (jamSekarang >= 7 && jamSekarang < 17);

  if (fanShouldBeOn) {
    digitalWrite(FAN_PIN, HIGH);
    Serial.printf("[KIPAS] Jam sekarang: %02d:%02d -> Jadwal 07:00-17:00: KIPAS HIDUP (ON)\n", 
                  jamSekarang, now.minute());
  } else {
    digitalWrite(FAN_PIN, LOW);
    Serial.printf("[KIPAS] Jam sekarang: %02d:%02d -> Di luar jadwal: KIPAS MATI (OFF)\n", 
                  jamSekarang, now.minute());
  }

  // Kunci status pin kipas agar tetap HIDUP/MATI selama Deep Sleep
  gpio_hold_en((gpio_num_t)FAN_PIN);

  // Format string data sensor (Multi-Node Support)
  char sensorData[180];
  snprintf(sensorData, sizeof(sensorData), 
           "[DATA] Node: %s, Waktu: %04d-%02d-%02d %02d:%02d:%02d, Suhu: %.1f C, Kelembaban: %.1f %%, Kipas: %s",
           NODE_ID,
           now.year(), now.month(), now.day(),
           now.hour(), now.minute(), now.second(),
           suhu, kelembaban, fanShouldBeOn ? "ON" : "OFF");

  Serial.printf("\n[SISTEM] Data Siap Kirim (%s) -> %s\n", NODE_ID, sensorData);

  // Kirim data sensor via LoRa
  LoRaSerial.println(sensorData);
  delay(1200); // Jeda agar paket teks selesai ditransmisikan

  // ----------------------------------------------------------------------------------
  // LANGKAH 1.5: RECEIVE WINDOW - MENDENGAR PERINTAH DOWNLINK (2 DETIK)
  // ----------------------------------------------------------------------------------
  // Mirip LoRaWAN Class A: buka jendela dengar selama 3.5 detik setelah uplink
  // (Diperpanjang untuk menampung SETTIME + CMD secara berurutan)
  Serial.println("\n[DOWNLINK] Membuka Receive Window (3.5 detik)...");
  unsigned long rxWindowStart = millis();
  String rxBuffer = "";

  while (millis() - rxWindowStart < 3500) {
    if (LoRaSerial.available()) {
      char c = (char)LoRaSerial.read();
      rxBuffer += c;
      if (c == '\n') {
        rxBuffer.trim();
        if (rxBuffer.startsWith("CMD,")) {
          Serial.printf("[DOWNLINK] Perintah diterima: %s\n", rxBuffer.c_str());

          // Parse: CMD,NODE_XX,SNAP atau CMD,NODE_XX,SCHEDULE,HH,MM
          // Validasi Node ID
          int firstComma = rxBuffer.indexOf(',');
          int secondComma = rxBuffer.indexOf(',', firstComma + 1);
          if (secondComma > 0) {
            String cmdNodeId = rxBuffer.substring(firstComma + 1, secondComma);
            if (cmdNodeId == NODE_ID) {
              String cmdType = "";
              int thirdComma = rxBuffer.indexOf(',', secondComma + 1);
              if (thirdComma < 0) {
                cmdType = rxBuffer.substring(secondComma + 1);
              } else {
                cmdType = rxBuffer.substring(secondComma + 1, thirdComma);
              }
              cmdType.trim();

              if (cmdType == "SNAP") {
                // === PERINTAH JEPRET MANUAL ===
                forceCaptureNow = true;
                Serial.println("[DOWNLINK] >> PERINTAH JEPRET MANUAL DITERIMA!");
                // Kirim ACK konfirmasi
                LoRaSerial.printf("ACK,%s,SNAP,OK\n", NODE_ID);
                delay(100);
              }
              else if (cmdType == "SCHEDULE" && thirdComma > 0) {
                // === PERINTAH UBAH JADWAL: CMD,NODE_XX,SCHEDULE,HH,MM ===
                int fourthComma = rxBuffer.indexOf(',', thirdComma + 1);
                if (fourthComma > 0) {
                  int newHour = rxBuffer.substring(thirdComma + 1, fourthComma).toInt();
                  int newMinute = rxBuffer.substring(fourthComma + 1).toInt();

                  if (newHour >= 0 && newHour <= 23 && newMinute >= 0 && newMinute <= 59) {
                    photoTargetHour = newHour;
                    photoTargetMinute = newMinute;

                    // Simpan ke NVS agar persisten
                    Preferences prefs;
                    prefs.begin("trapconf", false);  // Read-write mode
                    prefs.putInt("photoHour", photoTargetHour);
                    prefs.putInt("photoMin", photoTargetMinute);
                    prefs.end();

                    Serial.printf("[DOWNLINK] >> JADWAL DIUBAH KE %02d:%02d & DISIMPAN KE NVS!\n", photoTargetHour, photoTargetMinute);
                    // Kirim ACK konfirmasi
                    LoRaSerial.printf("ACK,%s,SCHEDULE,%02d,%02d,OK\n", NODE_ID, photoTargetHour, photoTargetMinute);
                    delay(100);
                  } else {
                    Serial.println("[DOWNLINK] Jam/menit tidak valid, perintah diabaikan.");
                  }
                }
              }
            } else {
              Serial.printf("[DOWNLINK] Perintah bukan untuk node ini (target: %s)\n", cmdNodeId.c_str());
            }
          }
        } else if (rxBuffer.startsWith("SETTIME,")) {
          // ================================================================
          // SINKRONISASI WAKTU RTC DARI RASPBERRY PI
          // Format: SETTIME,YYYY,MM,DD,HH,MM,SS
          // Dikirim otomatis oleh receiver_daemon.py setiap ESP32 bangun
          // ================================================================
          if (rtcOk) {
            String payload = rxBuffer.substring(8); // Hapus prefix "SETTIME,"
            int vals[6] = {0};
            int vIdx = 0;
            int startPos = 0;
            for (int ci = 0; ci <= (int)payload.length() && vIdx < 6; ci++) {
              if (ci == (int)payload.length() || payload.charAt(ci) == ',') {
                vals[vIdx++] = payload.substring(startPos, ci).toInt();
                startPos = ci + 1;
              }
            }
            if (vals[0] > 2020) {
              rtc.adjust(DateTime(vals[0], vals[1], vals[2], vals[3], vals[4], vals[5]));
              Serial.printf("[RTC SYNC] >> WAKTU DISINKRONKAN DARI RASPBERRY PI: %04d-%02d-%02d %02d:%02d:%02d\n",
                            vals[0], vals[1], vals[2], vals[3], vals[4], vals[5]);
            } else {
              Serial.println("[RTC SYNC] Data waktu tidak valid, sync diabaikan.");
            }
          } else {
            Serial.println("[RTC SYNC] RTC tidak tersedia, sync diabaikan.");
          }
        }
        rxBuffer = ""; // Reset buffer untuk perintah berikutnya
      }
    }
  }
  Serial.println("[DOWNLINK] Receive Window ditutup.");

  // ----------------------------------------------------------------------------------
  // LANGKAH 2: CEK JADWAL PENGAMBILAN & PENGIRIMAN FOTO
  // ----------------------------------------------------------------------------------
  bool takePhoto = false;

  // Cek apakah ada perintah jepret manual dari dashboard
  if (forceCaptureNow) {
    takePhoto = true;
    forceCaptureNow = false;  // Reset flag setelah dieksekusi
    Serial.println("[FOTO] Mengambil foto karena PERINTAH JEPRET MANUAL dari Dashboard!");
  } else if (!SEND_PHOTO_ONCE_DAILY) {
    // Mode Pengujian: Ambil foto setiap bangun
    takePhoto = true;
  } else {
    // Mode Kebun: Ambil foto 1x sehari pada jam & menit target node (dinamis)
    if (now.hour() == photoTargetHour && now.minute() >= photoTargetMinute && lastPhotoDay != now.day()) {
      takePhoto = true;
    }
  }

  if (takePhoto) {
    Serial.printf("\n[SISTEM] Memulai proses pengambilan foto harian (%s)...\n", NODE_ID);

    // Inisialisasi Kamera OV3660
    if (initCamera()) {
      Serial.println("[SISTEM] Menyalakan Lampu Flash LED Pentol (GPIO 47)...");
      digitalWrite(FLASH_PIN, HIGH);

      // === GREEN TINT FIX: Stabilisasi AWB sebelum foto asli ===
      // Ambil & buang 2 frame dummy agar sensor stabil dulu
      Serial.println("[KAMERA] Warming up AWB - mengambil 2 frame dummy...");
      delay(500);
      camera_fb_t *fb_dummy1 = esp_camera_fb_get();
      if (fb_dummy1) esp_camera_fb_return(fb_dummy1);
      delay(500);
      camera_fb_t *fb_dummy2 = esp_camera_fb_get();
      if (fb_dummy2) esp_camera_fb_return(fb_dummy2);
      delay(500); // Total warm-up ~1500ms
      // =========================================================

      Serial.println("[SISTEM] Mengambil gambar perangkap hama...");
      camera_fb_t *fb = esp_camera_fb_get();

      // Matikan lampu flash segera setelah capture
      digitalWrite(FLASH_PIN, LOW);
      Serial.println("[SISTEM] Lampu Flash dimatikan.");

      if (!fb) {
        Serial.println("[ERROR] Pengambilan gambar gagal!");
      } else {
        Serial.printf("[OK] Foto berhasil diambil! Ukuran buffer: %u bytes\n", fb->len);

        // Header transmisi gambar dengan identitas Node (Multi-Node Compatible)
        LoRaSerial.printf("---START:%s---\n", NODE_ID);
        LoRaSerial.println(fb->len);
        delay(100);

        // Pengiriman biner dalam chunk 150 byte
        const size_t CHUNK_SIZE = 150;
        size_t totalBytes = fb->len;
        size_t sentBytes = 0;

        for (size_t offset = 0; offset < totalBytes; offset += CHUNK_SIZE) {
          size_t currentChunk = (offset + CHUNK_SIZE < totalBytes) ? CHUNK_SIZE : (totalBytes - offset);
          LoRaSerial.write(fb->buf + offset, currentChunk);
          sentBytes += currentChunk;

          if (sentBytes % 1500 == 0 || sentBytes == totalBytes) {
            Serial.printf("[LORA %s] Terkirim: %u / %u bytes (%.1f%%)\n", 
                          NODE_ID, sentBytes, totalBytes, (float)sentBytes / totalBytes * 100.0);
          }
          delay(40); // Jeda 40ms per paket agar buffer LoRa E220 stabil
        }

        delay(150);
        LoRaSerial.printf("\n---END:%s---\n", NODE_ID);
        Serial.printf("[OK] Seluruh data gambar (%s) berhasil dikirimkan via LoRa.\n", NODE_ID);

        esp_camera_fb_return(fb);

        // Update hari terakhir foto berhasil diambil
        lastPhotoDay = now.day();
      }
    } else {
      Serial.println("[ERROR] Inisialisasi kamera gagal.");
    }
  } else {
    Serial.printf("[INFO] Jadwal foto hari ini sudah selesai atau belum waktunya (Target Jam: %02d:%02d, Terakhir: Hari ke-%d).\n", 
                  photoTargetHour, photoTargetMinute, lastPhotoDay);
  }

  // ----------------------------------------------------------------------------------
  // LANGKAH 3: MASUK KE MODE DEEP SLEEP
  // ----------------------------------------------------------------------------------
  digitalWrite(FLASH_PIN, LOW); // Pengaman ekstra LED mati
  LoRaSerial.flush();
  
  // Aktifkan pemeliharaan status GPIO selama Deep Sleep (Kipas tetap ON jika statusnya HIGH)
  gpio_deep_sleep_hold_en();

  Serial.printf("\n[SISTEM] Masuk ke Deep Sleep selama %llu detik...\n", WAKEUP_INTERVAL_SECONDS);
  Serial.printf("[SISTEM] Status Kipas selama tidur: %s\n", fanShouldBeOn ? "TETAP BERPUTAR (ON)" : "MATI (OFF)");
  Serial.println("========================================================\n");
  Serial.flush();

  esp_sleep_enable_timer_wakeup(WAKEUP_INTERVAL_SECONDS * 1000000ULL);
  esp_deep_sleep_start();
}

void loop() {
  // Kosong
}
