/**
 * ====================================================================================
 * PROGRAM RECEIVER NODE ESP32 - CLEAN BRIDGE & STANDALONE
 * Hardware : ESP32 Dev Module + LoRa Ebyte E220-900T22D
 * Fitur    : - Meneruskan aliran data LoRa secara murni (transparent passthrough) ke PC
 *            - Tanpa bingkai dekoratif yang merusak parsing Python
 *            - Mendukung penerimaan data sensor teks dan data biner gambar JPEG utuh
 *            - Mendukung tampilan opsional layar I2C OLED 0.96" (SSD1306)
 * Lab ELINS - Universitas Gadjah Mada
 * ====================================================================================
 */

#include <HardwareSerial.h>
#include <Wire.h>

// --- OPSI TAMPILAN OLED 0.96" (Set true jika memasang layar OLED) ---
#define USE_OLED_DISPLAY false

#if USE_OLED_DISPLAY
  #include <Adafruit_GFX.h>
  #include <Adafruit_SSD1306.h>
  #define SCREEN_WIDTH 128
  #define SCREEN_HEIGHT 64
  Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
  String oledBuffer = "";
#endif

// Pin LoRa Ebyte E220 pada ESP32 Dev Module
#define LORA_RX_PIN 16 // Ke TXD LoRa (ESP32 RX2)
#define LORA_TX_PIN 17 // Ke RXD LoRa (ESP32 TX2)

HardwareSerial LoRaSerial(2);

void setup() {
  // Serial USB ke PC (Baudrate 115200)
  Serial.begin(115200);
  delay(500);

  // Set buffer yang besar agar data biner gambar tidak terpotong
  LoRaSerial.setRxBufferSize(4096);
  LoRaSerial.begin(115200, SERIAL_8N1, LORA_RX_PIN, LORA_TX_PIN);

#if USE_OLED_DISPLAY
  Wire.begin(21, 22);
  if (display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.println("INSECT TRAP RECEIVER");
    display.println("Status: Standby");
    display.display();
  }
#endif
}

void loop() {
  // 1. DARI LORA KE PC (Transparan murni tanpa dekorasi agar file JPEG utuh)
  while (LoRaSerial.available()) {
    uint8_t b = LoRaSerial.read();
    Serial.write(b); // Tembak langsung ke port USB PC

#if USE_OLED_DISPLAY
    // Jika menggunakan OLED, kumpulkan baris untuk ditampilkan di layar kecil
    if (b == '\n') {
      if (oledBuffer.indexOf("[DATA]") != -1) {
        display.clearDisplay();
        display.setTextSize(1);
        display.setCursor(0, 0);
        display.println("TRAP MONITORING");
        display.println("---------------------");
        display.println(oledBuffer);
        display.display();
      }
      oledBuffer = "";
    } else if (oledBuffer.length() < 100) {
      oledBuffer += (char)b;
    }
#endif
  }

  // 2. DARI PC KE LORA (Jika ada input balik)
  while (Serial.available()) {
    uint8_t outgoingByte = Serial.read();
    LoRaSerial.write(outgoingByte);
  }
}
