#include <HardwareSerial.h>

// Pin untuk Modul LoRa E220 pada ESP32 Dev Board V1
#define LORA_RX_PIN 16 // Hubungkan                                                                                                                                                                                                           q)
#define LORA_TX_PIN 17 // Hubungkan ke RXD modul LoRa (Ini adalah pin TX2)

HardwareSerial LoRaSerial(2);

void setup() {
  // Serial USB untuk Komunikasi ke PC (Python)
  Serial.begin(115200); 
  
  // Konfigurasi UART untuk modul LoRa
  LoRaSerial.begin(115200, SERIAL_8N1, LORA_RX_PIN, LORA_TX_PIN);
  
  Serial.println("Receiver LoRa ESP32 Siap. Menunggu Data Gambar...");
}

void loop() {
  // Sistem Passthrough (Bypass): 
  // Apapun yang masuk dari LoRa, langsung diteruskan ke port Serial PC.
  if (LoRaSerial.available()) {
    uint8_t incomingByte = LoRaSerial.read();
    Serial.write(incomingByte);
  }
  
  // Opsional (Jika ingin kirim command dari PC ke transmitter di masa depan)
  if (Serial.available()) {
    uint8_t outgoingByte = Serial.read();
    LoRaSerial.write(outgoingByte);
  }
}
