#include <HardwareSerial.h>

#define LORA_RX 16 // Ke TXD LoRa
#define LORA_TX 17 // Ke RXD LoRa

HardwareSerial LoRa(2);

void setup() {
  Serial.begin(115200);
  LoRa.begin(115200, SERIAL_8N1, LORA_RX, LORA_TX);
  Serial.println("=== RECEIVER SIAP (Universal Debugger) ===");
}

void loop() {
  while (LoRa.available()) {
    Serial.write(LoRa.read());
  }
  while (Serial.available()) {
    LoRa.write(Serial.read());
  }
}
