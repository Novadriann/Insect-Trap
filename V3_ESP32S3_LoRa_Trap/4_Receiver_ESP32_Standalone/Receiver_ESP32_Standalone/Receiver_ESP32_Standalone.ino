/**
 * ====================================================================================
 * PROGRAM RECEIVER NODE ESP32 - CLEAN BRIDGE & STANDALONE (KABEL MICRO-USB)
 * Hardware : ESP32 Dev Module + LoRa Ebyte E220-900T22D + Raspberry Pi 5
 * Koneksi  : Kabel Micro-USB langsung ke port USB Raspberry Pi 5 (/dev/ttyUSB0)
 * Fitur    : - Meneruskan aliran data LoRa secara murni (transparent passthrough) ke RPi via USB
 *            - Mendukung transfer data sensor teks dan rekonstruksi file biner JPEG utuh
 *            - Mendukung downlink dua arah (sinkronisasi waktu RTC DS3231 & perintah SNAP manual)
 *            - Bebas dari konflik GPIO serial internal
 * Wiring   : 
 *   - LoRa VCC  -> 5V ESP32
 *   - LoRa GND  -> GND ESP32
 *   - LoRa TXD  -> GPIO 16 (RX2 ESP32)
 *   - LoRa RXD  -> GPIO 17 (TX2 ESP32)
 *   - LoRa M0   -> GND (Mode Normal)
 *   - LoRa M1   -> GND (Mode Normal)
 *   - Port USB  -> Kabel Micro-USB ke port USB Raspberry Pi 5
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
  // Serial USB ke Raspberry Pi / PC (115200 baud)
  Serial.begin(115200);
  delay(1000);

  // Serial UART2 ke Modul LoRa Ebyte E220
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
  // 1. DARI LORA KE RASPBERRY PI VIA KABEL USB (Murni tanpa modifikasi agar JPEG utuh)
  while (LoRaSerial.available()) {
    uint8_t b = LoRaSerial.read();
    Serial.write(b);

#if USE_OLED_DISPLAY
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

  // 2. DARI RASPBERRY PI KE LORA (Downlink perintah jepret / sinkronisasi waktu)
  while (Serial.available()) {
    uint8_t outgoingByte = Serial.read();
    LoRaSerial.write(outgoingByte);
  }
}


