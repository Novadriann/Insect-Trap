#include <HardwareSerial.h>

#define LORA_RX_PIN 16 // Ke TXD LoRa
#define LORA_TX_PIN 17 // Ke RXD LoRa

HardwareSerial LoRaSerial(2);

void setup() {
  Serial.begin(115200);
  LoRaSerial.begin(115200, SERIAL_8N1, LORA_RX_PIN, LORA_TX_PIN);
  Serial.println("Receiver LoRa V2 Siap. Menunggu Data Sensor & Gambar...");
}

void loop() {
  if (LoRaSerial.available()) {
    uint8_t incomingByte = LoRaSerial.read();
    Serial.write(incomingByte);
  }
  if (Serial.available()) {
    uint8_t outgoingByte = Serial.read();
    LoRaSerial.write(outgoingByte);
  }
}
