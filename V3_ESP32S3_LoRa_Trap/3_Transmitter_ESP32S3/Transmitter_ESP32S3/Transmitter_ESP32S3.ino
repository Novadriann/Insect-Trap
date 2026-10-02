/**
 * ====================================================================================
 * PROGRAM TRANSMITTER NODE - SISTEM PEMANTAUAN PERANGKAP HAMA (INSECT TRAP) V4.0
 * Hardware : ESP32-S3-CAM (OV3660) + LoRa Ebyte E220-900T22D + DHT22 + RTC DS3231
 * Mode     : ALWAYS ON (Tanpa Deep Sleep) - Sumber Daya PLN (HLK 5V)
 * Fitur    :
 *   1. Kirim data sensor (Suhu, Kelembaban, Kipas) setiap 60 detik via LoRa.
 *   2. Foto Harian Terjadwal: 1x sehari pada jam target yang bisa diubah dari dashboard.
 *   3. JEPRET INSTAN: Menerima perintah CMD,NODE_01,SNAP dan langsung jepret + kirim
 *      foto dalam waktu kurang dari 3 detik setelah tombol dashboard ditekan!
 *   4. Sinkronisasi waktu RTC DS3231 otomatis via downlink SETTIME dari Raspberry Pi.
 *   5. Kontrol kipas otomatis berdasarkan jam RTC (07:00 - 17:00 ON).
 *   6. Jadwal foto harian bisa diubah dinamis via perintah SCHEDULE dari dashboard.
 * Lab ELINS - Universitas Gadjah Mada
 * ====================================================================================
 */

#include "esp_camera.h"
#include <HardwareSerial.h>
#include <Wire.h>
#include "RTClib.h"
#include "DHT.h"
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
#define FLASH_PIN       47         // GPIO 47

// --- Pin Kendali Kipas DC 5V ---
#define FAN_PIN         21         // GPIO 21 (Aktif HIGH pada jam 07:00 - 17:00)

// --- PENGATURAN RESOLUSI KAMERA ---
#define CAMERA_FRAME_SIZE FRAMESIZE_VGA

// ====================================================================================
// 2. IDENTITAS NODE & PENGATURAN JADWAL
// ====================================================================================
#define NODE_ID  "NODE_01"

// Interval kirim data sensor (dalam milidetik): 60 detik
#define SENSOR_INTERVAL_MS   60000UL

// Jadwal foto harian (bisa diubah dari dashboard)
int photoTargetHour   = 8;
int photoTargetMinute = 0;

// Flag jadwal (foto 1x per hari pada jam target)
// Ubah ke false agar foto dikirim setiap siklus sensor (mode tes lab)
#define SEND_PHOTO_ONCE_DAILY   true

// ====================================================================================
// 3. VARIABEL GLOBAL (TIMER & STATE)
// ====================================================================================
unsigned long lastSensorSendMs  = 0;   // Waktu terakhir sensor dikirim (millis)
int           lastPhotoDay      = -1;  // Hari terakhir foto berhasil dikirim
bool          cameraInitialized = false;
bool          rtcOk             = false;

// ====================================================================================
// 4. MAPPING PIN KAMERA OV3660 UNTUK ESP32-S3-CAM
// ====================================================================================
#define PWDN_GPIO_NUM    -1
#define RESET_GPIO_NUM   -1
#define XCLK_GPIO_NUM    15
#define SIOD_GPIO_NUM    4
#define SIOC_GPIO_NUM    5
#define Y9_GPIO_NUM      16
#define Y8_GPIO_NUM      17
#define Y7_GPIO_NUM      18
#define Y6_GPIO_NUM      12
#define Y5_GPIO_NUM      10
#define Y4_GPIO_NUM      8
#define Y3_GPIO_NUM      9
#define Y2_GPIO_NUM      11
#define VSYNC_GPIO_NUM   6
#define HREF_GPIO_NUM    7
#define PCLK_GPIO_NUM    13

// ====================================================================================
// 5. FUNGSI INISIALISASI KAMERA
// ====================================================================================
bool initCamera() {
  if (cameraInitialized) {
    esp_camera_deinit();
    cameraInitialized = false;
    delay(100);
  }

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
#if defined(ARDUINO_ESP32S3_DEV) && ESP_ARDUINO_VERSION_MAJOR >= 3
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
#else
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
#endif
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = CAMERA_FRAME_SIZE;
  config.jpeg_quality = 10;
  config.fb_count     = 1;
  config.fb_location  = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[ERROR] Inisialisasi kamera gagal! Kode: 0x%x\n", err);
    return false;
  }

  // Kalibrasi sensor OV3660
  sensor_t *s = esp_camera_sensor_get();
  if (s != NULL) {
    s->set_vflip(s, 1);
    s->set_hmirror(s, 0);
    s->set_brightness(s, 1);
    s->set_contrast(s, 1);
    s->set_saturation(s, 0);
    s->set_special_effect(s, 0);
    s->set_whitebal(s, 1);
    s->set_awb_gain(s, 1);
    s->set_wb_mode(s, 1);
    s->set_exposure_ctrl(s, 1);
    s->set_aec2(s, 1);
    s->set_gain_ctrl(s, 1);
    s->set_bpc(s, 1);
    s->set_wpc(s, 1);
    s->set_raw_gma(s, 1);
    s->set_lenc(s, 1);
  }

  cameraInitialized = true;
  return true;
}

// ====================================================================================
// 6. FUNGSI AMBIL & KIRIM FOTO VIA LORA
// ====================================================================================
void captureAndSendPhoto(const char* alasan) {
  Serial.printf("\n[FOTO] Memulai pengambilan foto - Alasan: %s\n", alasan);

  if (!initCamera()) {
    Serial.println("[ERROR] Kamera gagal diinisialisasi!");
    return;
  }

  // Nyalakan flash, warmup AWB
  Serial.println("[KAMERA] Menyalakan Flash LED...");
  digitalWrite(FLASH_PIN, HIGH);

  Serial.println("[KAMERA] Warming up AWB - 2 frame dummy...");
  delay(500);
  camera_fb_t *fd1 = esp_camera_fb_get(); if (fd1) esp_camera_fb_return(fd1);
  delay(500);
  camera_fb_t *fd2 = esp_camera_fb_get(); if (fd2) esp_camera_fb_return(fd2);
  delay(500);

  // Ambil foto
  Serial.println("[KAMERA] Mengambil gambar...");
  camera_fb_t *fb = esp_camera_fb_get();

  // Matikan flash
  digitalWrite(FLASH_PIN, LOW);
  Serial.println("[KAMERA] Flash dimatikan.");

  if (!fb) {
    Serial.println("[ERROR] Pengambilan gambar gagal!");
    return;
  }

  Serial.printf("[OK] Foto berhasil! Ukuran: %u bytes\n", fb->len);

  // Kirim via LoRa
  LoRaSerial.printf("---START:%s---\n", NODE_ID);
  LoRaSerial.println(fb->len);
  delay(100);

  const size_t CHUNK_SIZE = 150;
  size_t totalBytes = fb->len;
  size_t sentBytes  = 0;

  for (size_t offset = 0; offset < totalBytes; offset += CHUNK_SIZE) {
    size_t currentChunk = (offset + CHUNK_SIZE < totalBytes) ? CHUNK_SIZE : (totalBytes - offset);
    LoRaSerial.write(fb->buf + offset, currentChunk);
    sentBytes += currentChunk;

    if (sentBytes % 1500 == 0 || sentBytes == totalBytes) {
      Serial.printf("[LoRa] Terkirim: %u / %u bytes (%.1f%%)\n",
                    sentBytes, totalBytes, (float)sentBytes / totalBytes * 100.0);
    }
    delay(40);
  }

  delay(150);
  LoRaSerial.printf("\n---END:%s---\n", NODE_ID);
  Serial.printf("[OK] Foto %s berhasil dikirim via LoRa!\n", NODE_ID);

  esp_camera_fb_return(fb);
}

// ====================================================================================
// 7. FUNGSI KIRIM DATA SENSOR
// ====================================================================================
void sendSensorData() {
  DateTime now = rtcOk ? rtc.now() : DateTime(2026, 1, 1, 0, 0, 0);

  float suhu       = dht.readTemperature();
  float kelembaban = dht.readHumidity();

  if (isnan(suhu) || isnan(kelembaban)) {
    Serial.println("[WARNING] Gagal baca DHT22. Default 0.0.");
    suhu = 0.0;
    kelembaban = 0.0;
  }

  // Kontrol kipas berdasarkan jam RTC
  int  jam          = now.hour();
  bool fanShouldBeOn = (jam >= 7 && jam < 17);
  digitalWrite(FAN_PIN, fanShouldBeOn ? HIGH : LOW);
  Serial.printf("[KIPAS] Jam %02d:%02d -> %s\n", jam, now.minute(), fanShouldBeOn ? "ON" : "OFF");

  // Format & kirim data sensor
  char buf[200];
  snprintf(buf, sizeof(buf),
    "[DATA] Node: %s, Waktu: %04d-%02d-%02d %02d:%02d:%02d, Suhu: %.1f C, Kelembaban: %.1f %%, Kipas: %s",
    NODE_ID,
    now.year(), now.month(), now.day(),
    now.hour(), now.minute(), now.second(),
    suhu, kelembaban, fanShouldBeOn ? "ON" : "OFF");

  Serial.printf("[SENSOR] Mengirim: %s\n", buf);
  LoRaSerial.println(buf);
  delay(1200);

  // === RECEIVE WINDOW: 3.5 detik mendengar downlink dari Raspberry Pi ===
  Serial.println("[DOWNLINK] Receive Window terbuka (3.5 detik)...");
  unsigned long rxStart = millis();
  String rxBuf = "";

  while (millis() - rxStart < 3500) {
    while (LoRaSerial.available()) {
      char c = (char)LoRaSerial.read();
      rxBuf += c;
      if (c == '\n') {
        rxBuf.trim();
        Serial.printf("[DOWNLINK] Diterima: %s\n", rxBuf.c_str());

        // --- Proses CMD,NODE_XX,SNAP ---
        if (rxBuf.startsWith("CMD,")) {
          int c1 = rxBuf.indexOf(',');
          int c2 = rxBuf.indexOf(',', c1 + 1);
          if (c2 > 0) {
            String targetNode = rxBuf.substring(c1 + 1, c2);
            if (targetNode == NODE_ID) {
              int c3 = rxBuf.indexOf(',', c2 + 1);
              String cmdType = (c3 < 0) ? rxBuf.substring(c2 + 1) : rxBuf.substring(c2 + 1, c3);
              cmdType.trim();

              if (cmdType == "SNAP") {
                // Kirim ACK dulu sebelum foto
                LoRaSerial.printf("ACK,%s,SNAP,OK\n", NODE_ID);
                delay(50);
                captureAndSendPhoto("PERINTAH JEPRET MANUAL dari Dashboard");

              } else if (cmdType == "SCHEDULE" && c3 > 0) {
                // Format: CMD,NODE_01,SCHEDULE,HH,MM
                int c4 = rxBuf.indexOf(',', c3 + 1);
                if (c4 > 0) {
                  int newHour = rxBuf.substring(c3 + 1, c4).toInt();
                  int newMin  = rxBuf.substring(c4 + 1).toInt();
                  photoTargetHour   = newHour;
                  photoTargetMinute = newMin;
                  lastPhotoDay      = -1;  // Reset agar jadwal baru langsung bisa dites di hari yang sama
                  Preferences prefs;
                  prefs.begin("trapconf", false);
                  prefs.putInt("photoHour", newHour);
                  prefs.putInt("photoMin",  newMin);
                  prefs.end();
                  LoRaSerial.printf("ACK,%s,SCHEDULE,%02d,%02d,OK\n", NODE_ID, newHour, newMin);
                  Serial.printf("[SCHEDULE] Jadwal foto diubah -> %02d:%02d (lastPhotoDay direset)\n", newHour, newMin);
                }
              }
            }
          }

        // --- Proses SETTIME,YYYY,MM,DD,HH,MM,SS ---
        } else if (rxBuf.startsWith("SETTIME,") && rtcOk) {
          String payload = rxBuf.substring(8);
          int vals[6] = {0};
          int vi = 0, pos = 0;
          for (int i = 0; i <= (int)payload.length() && vi < 6; i++) {
            if (i == (int)payload.length() || payload.charAt(i) == ',') {
              vals[vi++] = payload.substring(pos, i).toInt();
              pos = i + 1;
            }
          }
          if (vals[0] > 2020) {
            rtc.adjust(DateTime(vals[0], vals[1], vals[2], vals[3], vals[4], vals[5]));
            Serial.printf("[RTC SYNC] Waktu dari RPi: %04d-%02d-%02d %02d:%02d:%02d\n",
                          vals[0], vals[1], vals[2], vals[3], vals[4], vals[5]);
          }
        }
        rxBuf = "";
      }
    }
  }
  Serial.println("[DOWNLINK] Receive Window ditutup.");
}

// ====================================================================================
// 8. SETUP (DIJALANKAN SEKALI SAAT BOOT / RST)
// ====================================================================================
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n========================================================");
  Serial.println("  SISTEM TRAP HAMA: ESP32-S3 CAM TRANSMITTER V4.0");
  Serial.println("  MODE: ALWAYS ON - JEPRET INSTAN AKTIF");
  Serial.println("========================================================");

  // Setup pin
  pinMode(FLASH_PIN, OUTPUT);
  digitalWrite(FLASH_PIN, LOW);
  pinMode(FAN_PIN, OUTPUT);
  digitalWrite(FAN_PIN, LOW);

  // Inisialisasi LoRa UART
  LoRaSerial.begin(115200, SERIAL_8N1, LORA_RX_PIN, LORA_TX_PIN);
  Serial.println("[OK] LoRa E220 UART siap.");

  // Muat jadwal foto dari NVS
  Preferences prefs;
  prefs.begin("trapconf", true);
  photoTargetHour   = prefs.getInt("photoHour", 8);
  photoTargetMinute = prefs.getInt("photoMin",  0);
  prefs.end();
  Serial.printf("[OK] Jadwal foto: %02d:%02d\n", photoTargetHour, photoTargetMinute);

  // Cek PSRAM
  if (psramFound()) {
    Serial.printf("[OK] PSRAM: %d bytes bebas.\n", ESP.getFreePsram());
  } else {
    Serial.println("[WARNING] PSRAM TIDAK AKTIF! Kamera mungkin gagal.");
  }

  // Sensor DHT22
  dht.begin();
  Serial.println("[OK] DHT22 siap.");

  // RTC DS3231
  Wire.begin(I2C_SDA, I2C_SCL);
  rtcOk = rtc.begin();
  if (rtcOk) {
    DateTime compileTime = DateTime(F(__DATE__), F(__TIME__));
    DateTime rtcCurrent  = rtc.now();
    if (rtcCurrent < compileTime) {
      rtc.adjust(compileTime);
      Serial.printf("[OK] RTC disinkronkan ke waktu kompilasi: %04d-%02d-%02d %02d:%02d:%02d\n",
                    compileTime.year(), compileTime.month(), compileTime.day(),
                    compileTime.hour(), compileTime.minute(), compileTime.second());
    } else {
      Serial.printf("[OK] RTC: %02d:%02d:%02d\n",
                    rtcCurrent.hour(), rtcCurrent.minute(), rtcCurrent.second());
    }
  } else {
    Serial.println("[ERROR] RTC DS3231 tidak ditemukan!");
  }

  Serial.println("[SISTEM] Inisialisasi selesai. Siap menerima perintah & mengirim data.");
  Serial.println("========================================================\n");

  // Kirim data sensor pertama segera saat boot
  sendSensorData();
  lastSensorSendMs = millis();
}

// ====================================================================================
// 9. LOOP UTAMA - ALWAYS ON
// ====================================================================================
void loop() {
  unsigned long now_ms = millis();

  // ---------------------------------------------------------------------------------
  // A. Cek apakah ada perintah LoRa masuk KAPAN SAJA (Instant SNAP!)
  // ---------------------------------------------------------------------------------
  if (LoRaSerial.available()) {
    static String loraInBuf = "";
    while (LoRaSerial.available()) {
      char c = (char)LoRaSerial.read();
      loraInBuf += c;
      if (c == '\n') {
        loraInBuf.trim();
        Serial.printf("[LORA IN] %s\n", loraInBuf.c_str());

        // --- Perintah CMD (SNAP / SCHEDULE) ---
        if (loraInBuf.startsWith("CMD,")) {
          int c1 = loraInBuf.indexOf(',');
          int c2 = loraInBuf.indexOf(',', c1 + 1);
          if (c2 > 0) {
            String targetNode = loraInBuf.substring(c1 + 1, c2);
            if (targetNode == NODE_ID) {
              int c3 = loraInBuf.indexOf(',', c2 + 1);
              String cmdType = (c3 < 0) ? loraInBuf.substring(c2 + 1) : loraInBuf.substring(c2 + 1, c3);
              cmdType.trim();

              if (cmdType == "SNAP") {
                Serial.println("[SNAP] Perintah jepret instan diterima!");
                // Kirim ACK
                LoRaSerial.printf("ACK,%s,SNAP,OK\n", NODE_ID);
                delay(50);
                captureAndSendPhoto("JEPRET INSTAN dari Dashboard");

              } else if (cmdType == "SCHEDULE" && c3 > 0) {
                int c4 = loraInBuf.indexOf(',', c3 + 1);
                if (c4 > 0) {
                  int newHour = loraInBuf.substring(c3 + 1, c4).toInt();
                  int newMin  = loraInBuf.substring(c4 + 1).toInt();
                  photoTargetHour   = newHour;
                  photoTargetMinute = newMin;
                  lastPhotoDay      = -1;  // Reset agar jadwal baru langsung bisa dites di hari yang sama
                  Preferences prefs;
                  prefs.begin("trapconf", false);
                  prefs.putInt("photoHour", newHour);
                  prefs.putInt("photoMin",  newMin);
                  prefs.end();
                  LoRaSerial.printf("ACK,%s,SCHEDULE,%02d,%02d,OK\n", NODE_ID, newHour, newMin);
                  Serial.printf("[SCHEDULE] Jadwal foto diubah -> %02d:%02d (lastPhotoDay direset)\n", newHour, newMin);
                }
              }
            }
          }

        // --- SETTIME dari Raspberry Pi ---
        } else if (loraInBuf.startsWith("SETTIME,") && rtcOk) {
          String payload = loraInBuf.substring(8);
          int vals[6] = {0};
          int vi = 0, pos = 0;
          for (int i = 0; i <= (int)payload.length() && vi < 6; i++) {
            if (i == (int)payload.length() || payload.charAt(i) == ',') {
              vals[vi++] = payload.substring(pos, i).toInt();
              pos = i + 1;
            }
          }
          if (vals[0] > 2020) {
            rtc.adjust(DateTime(vals[0], vals[1], vals[2], vals[3], vals[4], vals[5]));
            Serial.printf("[RTC SYNC] %04d-%02d-%02d %02d:%02d:%02d\n",
                          vals[0], vals[1], vals[2], vals[3], vals[4], vals[5]);
          }
        }
        loraInBuf = "";
      }
    }
  }

  // ---------------------------------------------------------------------------------
  // B. Kirim data sensor setiap SENSOR_INTERVAL_MS (60 detik)
  // ---------------------------------------------------------------------------------
  if (now_ms - lastSensorSendMs >= SENSOR_INTERVAL_MS) {
    lastSensorSendMs = millis();
    sendSensorData();
  }

  // ---------------------------------------------------------------------------------
  // C. Cek jadwal foto harian (1x sehari pada jam target)
  // ---------------------------------------------------------------------------------
  if (rtcOk && SEND_PHOTO_ONCE_DAILY) {
    DateTime nowRtc = rtc.now();
    if (nowRtc.hour()   == photoTargetHour   &&
        nowRtc.minute() >= photoTargetMinute  &&
        lastPhotoDay    != nowRtc.day()) {
      Serial.printf("[JADWAL HARIAN] Jam target %02d:%02d tercapai! (RTC: %02d:%02d:%02d). Memulai jepret foto harian...\n",
                    photoTargetHour, photoTargetMinute,
                    nowRtc.hour(), nowRtc.minute(), nowRtc.second());
      lastPhotoDay = nowRtc.day();
      captureAndSendPhoto("JADWAL HARIAN TERJADWAL");
    }
  }

  // ---------------------------------------------------------------------------------
  // D. Jika SEND_PHOTO_ONCE_DAILY = false, foto setiap siklus sensor (mode lab)
  // ---------------------------------------------------------------------------------
  // (Sudah ditangani di sendSensorData jika Anda mau — aktifkan jika diperlukan)
}
