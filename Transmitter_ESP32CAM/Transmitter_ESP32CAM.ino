#include "esp_camera.h"
#include <HardwareSerial.h>
#include "driver/rtc_io.h"

// Pin konfigurasi untuk kamera AI-Thinker
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// Pin LED Flash bawaan
#define FLASH_PIN 4

// --- SESUAI DENGAN GAMBAR PINOUT ESP32-CAM ---
// ESP32 memiliki fitur canggih "GPIO Matrix" yang bisa menyulap pin I/O biasa menjadi pin RX/TX.
// Coba lihat sisi KIRI pada gambar pinout-mu: ada pin GPIO 13 dan GPIO 14.
// Kita menggunakan pin tersebut agar pin U0R (3) dan U0T (1) tetap bebas dipakai untuk kabel USB TTL (upload).
#define LORA_RX_PIN 13 // Hubungkan pin ini ke TXD pada modul LoRa
#define LORA_TX_PIN 14 // Hubungkan pin ini ke RXD pada modul LoRa

HardwareSerial LoRaSerial(2);

void setup() {
  Serial.begin(115200);
  
  // Konfigurasi UART untuk LoRa sesuai dengan settingan di aplikasi Ebyte (115200 bps, 8N1)
  LoRaSerial.begin(115200, SERIAL_8N1, LORA_RX_PIN, LORA_TX_PIN);

  // Setup Flash LED
  pinMode(FLASH_PIN, OUTPUT);
  digitalWrite(FLASH_PIN, LOW);

  // --- DIAGNOSTIK HARDWARE ---
  delay(2000); // Beri waktu 2 detik agar arus listrik dari USB TTL stabil
  Serial.println("\n\n--- Cek Sistem ESP32-CAM ---");
  if(psramFound()){
    Serial.printf("PSRAM OK! Sisa: %d bytes\n", ESP.getFreePsram());
  } else {
    Serial.println("ERROR: PSRAM TIDAK AKTIF/TIDAK DITEMUKAN!");
    Serial.println("Silakan ke menu Tools -> PSRAM -> Ubah ke 'Enabled' di Arduino IDE.");
  }

  // Konfigurasi Kamera
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000; // UBAH KEMBALI: Sensor kamera ini ternyata menolak detak 10MHz
  
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_VGA; // UBAH: OV3660 lebih stabil di resolusi VGA, sering bug memori (DMA) jika dipaksa ke QVGA
  config.jpeg_quality = 10;          // UBAH: Penyesuaian kompresi untuk OV3660
  config.fb_count = 1; // KEMBALIKAN KE 1: Library ESP32-mu mengalami "Stack Crash" jika menggunakan 2 buffer

  // Inisialisasi Kamera
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("\n[ERROR KRITIS] Camera init failed with error 0x%x\n", err);
    Serial.println("Kamera tidak terdeteksi! Pastikan kabel pita OV3660 menancap lurus dan rapat.");
    Serial.flush();
    delay(3000);
    ESP.restart(); 
    return; // Cegah program lanjut berjalan agar tidak crash
  }

  // --- KONFIGURASI KHUSUS OV3660 ---
  // Driver ESP32 akan otomatis mendeteksi kameranya
  sensor_t * s = esp_camera_sensor_get();
  if (s != NULL && s->id.PID == OV3660_PID) {
    s->set_vflip(s, 1);       // OV3660 biasanya hasil fotonya terbalik
    s->set_brightness(s, 1);  // Diterangkan sedikit agar hama jelas
    s->set_saturation(s, -2); // Kurangi saturasi warna agar natural
    Serial.println("Sensor OV3660 Terdeteksi dan Dikalibrasi!");
  } else if (s != NULL) {
    Serial.println("Sensor OV2640 Terdeteksi.");
  }

  // --- PROSES MENGAMBIL GAMBAR ---
  Serial.println("Menghidupkan Flash LED dan mengambil gambar...");
  digitalWrite(FLASH_PIN, HIGH); // NYALAKAN LAMPU FLASH
  delay(1000); // Beri waktu 1 detik agar sensor kamera beradaptasi dengan terangnya cahaya

  camera_fb_t * fb = esp_camera_fb_get();
  
  digitalWrite(FLASH_PIN, LOW); // MATIKAN LAMPU FLASH segera setelah jepretan selesai

  if (!fb) {
    Serial.println("Gagal mengambil gambar");
  } else {
    Serial.printf("Gambar berhasil diambil. Ukuran file: %d bytes\n", fb->len);
    Serial.println("Mengirim data via LoRa...");

    // Kirim Header Penanda
    LoRaSerial.println("---START---");
    LoRaSerial.println(fb->len);
    delay(100);

    // Kirim data secara bertahap (Chunking)
    // Modul LoRa Ebyte memiliki buffer sekitar 400 bytes. 
    // Jika dikirim sekaligus akan membuat buffer overflow.
    const int chunkSize = 150; 
    for(size_t i = 0; i < fb->len; i += chunkSize) {
      size_t chunk = (i + chunkSize < fb->len) ? chunkSize : (fb->len - i);
      LoRaSerial.write(fb->buf + i, chunk);
      
      // Sangat penting: Jeda transmisi agar hardware radio LoRa sempat mentransmisikan data ke udara
      // Berdasarkan air data rate 62.5Kbps, delay 50ms sangat cukup.
      delay(50); 
    }
    
    delay(100);
    LoRaSerial.println("\n---END---");
    
    // Kembalikan memori buffer
    esp_camera_fb_return(fb);
    Serial.println("Pengiriman selesai.");
  }

  // --- DEEP SLEEP ---
  Serial.println("Masuk ke mode Deep Sleep untuk menghemat baterai...");
  
  // Konfigurasi waktu tidur 
  // UBAH KEMBALI KE 24*60*60 JIKA SUDAH DIPASANG DI KEBUN.
  // Untuk TESTING sekarang, kita set 30 detik saja:
  uint64_t TIME_TO_SLEEP = 30; 
  esp_sleep_enable_timer_wakeup(TIME_TO_SLEEP * 1000000ULL);
  
  // Agar flash LED benar-benar mati dan tidak bocor arusnya saat deep sleep
  rtc_gpio_hold_en((gpio_num_t)FLASH_PIN); 
  
  delay(1000);
  esp_deep_sleep_start();
}

void loop() {
  // Tidak ada loop karena menggunakan Deep Sleep
}
