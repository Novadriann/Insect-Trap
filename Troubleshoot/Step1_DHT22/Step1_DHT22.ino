#include <HardwareSerial.h>
#include "DHT.h"

#define LORA_RX 14 // Ke TXD LoRa
#define LORA_TX 13 // Ke RXD LoRa

#define DHTPIN 15
#define DHTTYPE DHT22

HardwareSerial LoRa(2);
DHT dht(DHTPIN, DHTTYPE);

void setup() {
  Serial.begin(115200);
  LoRa.begin(115200, SERIAL_8N1, LORA_RX, LORA_TX);
  dht.begin();

  Serial.println("\n=== TAHAP 1: UJI PENGIRIMAN DHT22 VIA LORA ===");
}

void loop() {
  delay(3000); // Kirim setiap 3 detik

  float h = dht.readHumidity();
  float t = dht.readTemperature();

  if (isnan(h) || isnan(t)) {
    Serial.println("[ERROR] Gagal membaca sensor DHT22! Periksa kabel.");
    LoRa.println("[ERROR] DHT22 Tidak Terbaca");
    return;
  }

  char pesan[80];
  snprintf(pesan, sizeof(pesan), "[DHT22] Suhu: %.1f C, Kelembaban: %.1f %%\n", t, h);

  // Tampilkan di Serial Monitor Pengirim
  Serial.print("Mengirim: ");
  Serial.print(pesan);

  // Pancarkan lewat LoRa ke Receiver
  LoRa.print(pesan);
}
