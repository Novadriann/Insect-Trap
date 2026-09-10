/**
 * ====================================================================================
 * PROGRAM TRANSMITTER NODE - SISTEM PEMANTAUAN PERANGKAP HAMA (INSECT TRAP)
 * Hardware : ESP32-S3-CAM (OV3660) + LoRa Ebyte E220-900T22D + DHT22 + RTC DS3231
 * Fitur    : - Pembacaan Suhu & Kelembaban (DHT22)
 *            - Pembacaan Waktu Nyata / Real-Time Clock (DS3231)
 *            - Kontrol Lampu Flash LED Otomatis (Driver MOSFET)
 *            - Pengambilan Gambar JPEG OV3660 dengan Kalibrasi Warna
 *            - Transmisi Data Sensor & Biner Gambar via LoRa E220
 *            - Mode Hemat Daya (Deep Sleep) Terjadwal Harian
 * Lab ELINS - Universitas Gadjah Mada
 * ====================================================================================
 */

#include "esp_camera.h"
#include <HardwareSerial.h>
#include <Wire.h>
#include "RTClib.h"
#include "DHT.h"
#include "driver/rtc_io.h"

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

// --- Pin Pemicu Flash LED (Ke Gate Driver MOSFET AOD4184/IRLZ44N) ---
#define FLASH_PIN       47         // GPIO 47

// --- PENGATURAN RESOLUSI KAMERA ---
// Pilih FRAMESIZE_QVGA (320x240, ~7-10 KB, sangat cepat) 
// atau FRAMESIZE_VGA (640x480, ~12-18 KB, resolusi detail untuk counting serangga)
#define CAMERA_FRAME_SIZE FRAMESIZE_VGA

// --- WAKTU DEEP SLEEP ---
// Untuk pengujian di lab: 30 detik (30ULL)
// Untuk operasional di kebun: 1 hari penuh (24 * 60 * 60ULL = 86400ULL)
const uint64_t TIME_TO_SLEEP_SECONDS = 30; // Ubah ke 86400 untuk 1x sehari di kebun

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
    s->set_brightness(s, 1);   // Sedikit tingkatkan kecerahan
    s->set_contrast(s, 1);     // Tingkatkan kontras agar serangga terlihat jelas
    s->set_saturation(s, -1);  // Kurangi saturasi berlebih
    s->set_special_effect(s, 0); // No effect
    s->set_wb_mode(s, 0);      // Auto White Balance
  }
  return true;
}

// ====================================================================================
// 4. PROGRAM SETUP (DIJALANKAN 1 KALI SETIAP BANGUN DARI SLEEP)
// ====================================================================================
void setup() {
  // Inisialisasi Serial Debug (USB TTL Port)
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n========================================================");
  Serial.println("  SISTEM TRAP HAMA: ESP32-S3 CAM TRANSMITTER BANGUN");
  Serial.println("========================================================");

  // Setup Pin Flash LED
  pinMode(FLASH_PIN, OUTPUT);
  digitalWrite(FLASH_PIN, LOW); // Pastikan mati awal

  // Inisialisasi UART LoRa E220
  LoRaSerial.begin(115200, SERIAL_8N1, LORA_RX_PIN, LORA_TX_PIN);
  Serial.println("[OK] Serial LoRa E220 diinisialisasi pada baud 115200.");

  // Cek PSRAM
  if (psramFound()) {
    Serial.printf("[OK] PSRAM Terdeteksi. Ukuran bebas: %d bytes\n", ESP.getFreePsram());
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
      Serial.println("[WARNING] RTC kehilangan daya, menyetel waktu ke waktu kompilasi...");
      rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
    }
  } else {
    Serial.println("[ERROR] RTC DS3231 TIDAK DITEMUKAN! Periksa pin SDA(2) & SCL(3).");
  }

  // Inisialisasi Kamera
  if (!initCamera()) {
    Serial.println("[FATAL] Kamera gagal inisialisasi. Me-restart sistem...");
    delay(3000);
    ESP.restart();
  }
  Serial.println("[OK] Kamera OV3660 siap.");

  // ----------------------------------------------------------------------------------
  // LANGKAH 1: BACA SENSOR & WAKTU
  // ----------------------------------------------------------------------------------
  float suhu = dht.readTemperature();
  float kelembaban = dht.readHumidity();
  DateTime now = (rtcOk) ? rtc.now() : DateTime(2026, 9, 10, 0, 0, 0);

  // Validasi pembacaan DHT22
  if (isnan(suhu) || isnan(kelembaban)) {
    Serial.println("[WARNING] Gagal membaca data DHT22. Menggunakan nilai default.");
    suhu = 0.0;
    kelembaban = 0.0;
  }

  // Format string data sensor untuk stasiun penerima
  char sensorData[160];
  snprintf(sensorData, sizeof(sensorData), 
           "[DATA] Waktu: %04d-%02d-%02d %02d:%02d:%02d, Suhu: %.1f C, Kelembaban: %.1f %%",
           now.year(), now.month(), now.day(),
           now.hour(), now.minute(), now.second(),
           suhu, kelembaban);

  Serial.printf("\n[SISTEM] Data Siap Kirim -> %s\n", sensorData);

  // Kirim data sensor via LoRa
  LoRaSerial.println(sensorData);
  delay(1200); // Jeda penting agar paket teks selesai ditransmisikan sebelum transmisi gambar biner

  // ----------------------------------------------------------------------------------
  // LANGKAH 2: NYALAKAN FLASH LED & AMBIL FOTO
  // ----------------------------------------------------------------------------------
  Serial.println("[SISTEM] Menyalakan Lampu Flash LED...");
  digitalWrite(FLASH_PIN, HIGH);
  delay(500); // Berikan jeda 500ms agar sensor kamera menyesuaikan pencahayaan (Auto-Exposure)

  Serial.println("[SISTEM] Mengambil gambar perangkap hama...");
  camera_fb_t *fb = esp_camera_fb_get();

  // Matikan lampu flash segera setelah capture selesai agar hemat daya
  digitalWrite(FLASH_PIN, LOW);
  Serial.println("[SISTEM] Lampu Flash dimatikan.");

  if (!fb) {
    Serial.println("[ERROR] Pengambilan gambar gagal!");
  } else {
    Serial.printf("[OK] Foto berhasil diambil! Ukuran buffer: %u bytes\n", fb->len);

    // ----------------------------------------------------------------------------------
    // LANGKAH 3: TRANSMISI GAMBAR VIA LORA DALAM BENTUK CHUNK
    // ----------------------------------------------------------------------------------
    Serial.println("[SISTEM] Memulai pengiriman gambar via LoRa...");
    
    // Header transmisi gambar berisi panjang file
    LoRaSerial.printf("---START---%u\n", fb->len);
    delay(100);

    // Pemotongan data gambar menjadi potongan kecil (chunk 150 byte)
    const size_t CHUNK_SIZE = 150;
    size_t totalBytes = fb->len;
    size_t sentBytes = 0;

    for (size_t offset = 0; offset < totalBytes; offset += CHUNK_SIZE) {
      size_t currentChunk = (offset + CHUNK_SIZE < totalBytes) ? CHUNK_SIZE : (totalBytes - offset);
      LoRaSerial.write(fb->buf + offset, currentChunk);
      sentBytes += currentChunk;

      // Log progress di Serial Monitor
      if (sentBytes % 1500 == 0 || sentBytes == totalBytes) {
        Serial.printf("[LORA] Terkirim: %u / %u bytes (%.1f%%)\n", 
                      sentBytes, totalBytes, (float)sentBytes / totalBytes * 100.0);
      }
      delay(40); // Jeda 40ms per paket agar buffer transmisi LoRa E220 tidak overflow
    }

    delay(150);
    LoRaSerial.print("\n---END---\n");
    Serial.println("[OK] Seluruh data gambar berhasil dikirimkan.");

    // Kembalikan frame buffer memori
    esp_camera_fb_return(fb);
  }

  // ----------------------------------------------------------------------------------
  // LANGKAH 4: MASUK KE MODE DEEP SLEEP
  // ----------------------------------------------------------------------------------
  digitalWrite(FLASH_PIN, LOW); // Pengaman ekstra memastikan LED padam
  LoRaSerial.flush();
  
  Serial.printf("\n[SISTEM] Transmisi selesai. Masuk ke Deep Sleep selama %llu detik...\n", TIME_TO_SLEEP_SECONDS);
  Serial.println("========================================================\n");
  Serial.flush();

  // Setel timer bangun
  esp_sleep_enable_timer_wakeup(TIME_TO_SLEEP_SECONDS * 1000000ULL);
  esp_deep_sleep_start();
}

void loop() {
  // Loop tidak digunakan karena mikrokontroler langsung masuk ke mode Deep Sleep di akhir setup()
}
