/**
 * ====================================================================================
 * PROGRAM ESP32 LORA-TO-USB BRIDGE UNTUK RASPBERRY PI 5
 * Hardware : ESP32 Dev Module + LoRa Ebyte E220-900T22D -> Dicolok ke USB Raspberry Pi 5
 * Fitur    : - Menjembatani aliran data serial LoRa (UART2) ke USB Serial Raspberry Pi 5
 *            - Buffer RX besar (4096 bytes) untuk mencegah hilangnya byte biner gambar
 *            - Transmisi data dua arah transparan berkecepatan tinggi (115200 baud)
 * Lab ELINS - Universitas Gadjah Mada
 * ====================================================================================
 */

#include <HardwareSerial.h>

// Pin LoRa Ebyte E220 pada ESP32 Dev Module
#define LORA_RX_PIN 16 // Hubungkan ke TXD LoRa (ESP32 RX2)
#define LORA_TX_PIN 17 // Hubungkan ke RXD LoRa (ESP32 TX2)

HardwareSerial LoRaSerial(2);

void setup() {
  // Serial USB ke Raspberry Pi 5 (Baudrate 115200)
  Serial.begin(115200);
  
  // Set buffer RX yang besar pada UART LoRa agar transmisi chunk gambar biner tidak hilang
  LoRaSerial.setRxBufferSize(4096);
  LoRaSerial.begin(115200, SERIAL_8N1, LORA_RX_PIN, LORA_TX_PIN);

  // Buffer Serial USB
  Serial.setRxBufferSize(4096);
}

void loop() {
  // 1. Dari LoRa -> Teruskan langsung ke Raspberry Pi 5 via USB
  while (LoRaSerial.available()) {
    uint8_t incomingByte = LoRaSerial.read();
    Serial.write(incomingByte);
  }

  // 2. Dari Raspberry Pi 5 (USB) -> Teruskan ke LoRa jika ada perintah balik
  while (Serial.available()) {
    uint8_t outgoingByte = Serial.read();
    LoRaSerial.write(outgoingByte);
  }
}
