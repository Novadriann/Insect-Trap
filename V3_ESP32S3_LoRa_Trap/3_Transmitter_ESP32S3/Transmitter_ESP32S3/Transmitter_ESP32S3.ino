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

// --- PENGATURAN JADWAL OPERASIONAL ---
// Interval bangun per siklus untuk mengecek jadwal kipas & kirim sensor:
// - Mode Lab / Pengujian: 30 detik (30ULL)
// - Mode Kebun          : 1800 detik (30 menit) atau 3600 detik (1 jam)
const uint64_t WAKEUP_INTERVAL_SECONDS = 30; // Ubah ke 1800 (30 menit) saat di kebun

// Jam pengambilan foto harian (0 - 23). Contoh: 8 = Pukul 08:00 pagi
#define PHOTO_TARGET_HOUR 8

// Set true jika foto hanya dikirim 1x sehari saat jam target.
// Set false jika ingin foto dikirim SETIAP KALI alat bangun (sangat berguna untuk tes di lab).
#define SEND_PHOTO_ONCE_DAILY false

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
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = CAMERA_FRAME_SIZE;
  config.jpeg_quality = 10;          // Kualitas JPEG (10 = jernih & tajam)
  config.fb_count     = 1;
  config.fb_location  = CAMERA_FB_IN_PSRAM;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("[ERROR] Inisialisasi kamera gagal! Kode: 0x%x\n", err);
    return false;
  }

  // Kalibrasi Sensor OV3660
  sensor_t *s = esp_camera_sensor_get();
  if (s != NULL) {
    s->set_vflip(s, 1);        // Balik vertikal jika terbalik
    s->set_hmirror(s, 0);      // Horizontal mirror
    s->set_brightness(s, 1);   // Tingkatkan kecerahan
    s->set_contrast(s, 1);     // Tingkatkan kontras agar serangga terlihat jelas
    s->set_saturation(s, -1);  // Kurangi saturasi berlebih
    s->set_special_effect(s, 0); // No effect
    s->set_wb_mode(s, 0);      // Auto White Balance
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
    if (rtc.lostPower()) {
      Serial.println("[WARNING] RTC kehilangan daya, menyetel ke waktu kompilasi...");
      rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
    }
  } else {
    Serial.println("[ERROR] RTC DS3231 TIDAK DITEMUKAN! Periksa pin SDA(2) & SCL(3).");
  }

  // ----------------------------------------------------------------------------------
  // LANGKAH 1: BACA SENSOR & EVALUASI JADWAL KIPAS DARI RTC
  // ----------------------------------------------------------------------------------
  DateTime now = (rtcOk) ? rtc.now() : DateTime(2026, 9, 10, 10, 0, 0);
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

  // Format string data sensor
  char sensorData[160];
  snprintf(sensorData, sizeof(sensorData), 
           "[DATA] Waktu: %04d-%02d-%02d %02d:%02d:%02d, Suhu: %.1f C, Kelembaban: %.1f %%, Kipas: %s",
           now.year(), now.month(), now.day(),
           now.hour(), now.minute(), now.second(),
           suhu, kelembaban, fanShouldBeOn ? "ON" : "OFF");

  Serial.printf("\n[SISTEM] Data Siap Kirim -> %s\n", sensorData);

  // Kirim data sensor via LoRa
  LoRaSerial.println(sensorData);
  delay(1200); // Jeda agar paket teks selesai ditransmisikan

  // ----------------------------------------------------------------------------------
  // LANGKAH 2: CEK JADWAL PENGAMBILAN & PENGIRIMAN FOTO
  // ----------------------------------------------------------------------------------
  bool takePhoto = false;

  if (!SEND_PHOTO_ONCE_DAILY) {
    // Mode Pengujian: Ambil foto setiap bangun
    takePhoto = true;
  } else {
    // Mode Kebun: Ambil foto 1x sehari pada jam target (misal jam 8 pagi)
    if (now.hour() >= PHOTO_TARGET_HOUR && lastPhotoDay != now.day()) {
      takePhoto = true;
    }
  }

  if (takePhoto) {
    Serial.println("\n[SISTEM] Memulai proses pengambilan foto harian...");

    // Inisialisasi Kamera OV3660
    if (initCamera()) {
      Serial.println("[SISTEM] Menyalakan Lampu Flash LED Pentol (GPIO 47)...");
      digitalWrite(FLASH_PIN, HIGH);
      delay(400); // Jeda adaptasi exposure kamera

      Serial.println("[SISTEM] Mengambil gambar perangkap hama...");
      camera_fb_t *fb = esp_camera_fb_get();

      // Matikan lampu flash segera setelah capture
      digitalWrite(FLASH_PIN, LOW);
      Serial.println("[SISTEM] Lampu Flash dimatikan.");

      if (!fb) {
        Serial.println("[ERROR] Pengambilan gambar gagal!");
      } else {
        Serial.printf("[OK] Foto berhasil diambil! Ukuran buffer: %u bytes\n", fb->len);

        // Header transmisi gambar (persis seperti versi lama yang terbukti sukses)
        LoRaSerial.println("---START---");
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
            Serial.printf("[LORA] Terkirim: %u / %u bytes (%.1f%%)\n", 
                          sentBytes, totalBytes, (float)sentBytes / totalBytes * 100.0);
          }
          delay(40); // Jeda 40ms per paket agar buffer LoRa E220 stabil
        }

        delay(150);
        LoRaSerial.print("\n---END---\n");
        Serial.println("[OK] Seluruh data gambar berhasil dikirimkan via LoRa.");

        esp_camera_fb_return(fb);

        // Update hari terakhir foto berhasil diambil
        lastPhotoDay = now.day();
      }
    } else {
      Serial.println("[ERROR] Inisialisasi kamera gagal.");
    }
  } else {
    Serial.printf("[INFO] Jadwal foto hari ini sudah selesai atau belum waktunya (Target Jam: %d, Terakhir: Hari ke-%d).\n", 
                  PHOTO_TARGET_HOUR, lastPhotoDay);
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
