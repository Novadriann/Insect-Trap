#include "esp_camera.h"
#include <HardwareSerial.h>
#include <Wire.h>
#include "DHT.h"
#include "RTClib.h"

// ================= PIN MAPPING =================
#define LORA_RX_PIN 14 // Ke TXD LoRa
#define LORA_TX_PIN 13 // Ke RXD LoRa

#define DHTPIN 15
#define DHTTYPE DHT22

// RTC dipindah ke U0TX & U0RX agar GPIO 4 bisa untuk Flash LED
#define I2C_SDA 1
#define I2C_SCL 3

#define FLASH_PIN 4

// Konfigurasi Kamera AI-Thinker
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

HardwareSerial LoRa(2);
DHT dht(DHTPIN, DHTTYPE);
RTC_DS3231 rtc;

void setup() {
  // Serial Monitor ditiadakan karena pin 1 & 3 dipakai RTC
  LoRa.begin(115200, SERIAL_8N1, LORA_RX_PIN, LORA_TX_PIN);

  pinMode(FLASH_PIN, OUTPUT);
  digitalWrite(FLASH_PIN, LOW);

  // 1. Inisialisasi DHT22
  dht.begin();

  // 2. Inisialisasi RTC
  Wire.begin(I2C_SDA, I2C_SCL);
  if (rtc.begin()) {
    if (rtc.lostPower()) {
      rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
    }
  }

  // 3. Inisialisasi Kamera OV3660
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
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_VGA;
  config.jpeg_quality = 10;
  config.fb_count = 1;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    LoRa.println("[ERROR] Kamera Gagal Inisialisasi!");
    delay(3000);
    ESP.restart();
    return;
  }

  sensor_t * s = esp_camera_sensor_get();
  if (s != NULL && s->id.PID == OV3660_PID) {
    s->set_vflip(s, 1);
    s->set_brightness(s, 1);
    s->set_saturation(s, -2);
  }
  delay(2000);

  // 4. Baca Sensor & Waktu
  float h = dht.readHumidity();
  float t = dht.readTemperature();
  DateTime now = rtc.now();

  if (isnan(h) || isnan(t)) {
    h = 0.0; t = 0.0;
  }

  char sensorData[150];
  snprintf(sensorData, sizeof(sensorData), "[DATA] Waktu: %04d-%02d-%02d %02d:%02d:%02d, Suhu: %.1f C, Kelembaban: %.1f %%\n",
           now.year(), now.month(), now.day(), now.hour(), now.minute(), now.second(), t, h);
  LoRa.print(sensorData);
  delay(1000);

  // 5. Nyalakan Flash dan Ambil Foto
  digitalWrite(FLASH_PIN, HIGH);
  delay(1000);

  camera_fb_t * fb = esp_camera_fb_get();
  digitalWrite(FLASH_PIN, LOW); // Matikan flash

  if (fb) {
    LoRa.printf("---START---%u\n", fb->len);
    delay(100);

    const size_t chunkSize = 150;
    for (size_t i = 0; i < fb->len; i += chunkSize) {
      size_t len = (i + chunkSize < fb->len) ? chunkSize : (fb->len - i);
      LoRa.write(fb->buf + i, len);
      delay(50);
    }
    delay(100);
    LoRa.print("---END---\n");
    esp_camera_fb_return(fb);
  }

  // 6. Masuk Deep Sleep 30 detik (Uji coba)
  uint64_t TIME_TO_SLEEP = 30;
  esp_sleep_enable_timer_wakeup(TIME_TO_SLEEP * 1000000ULL);
  digitalWrite(FLASH_PIN, LOW);
  LoRa.flush();
  esp_deep_sleep_start();
}

void loop() {}
