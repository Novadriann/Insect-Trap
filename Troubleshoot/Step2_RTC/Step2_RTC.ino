#include <HardwareSerial.h>
#include <Wire.h>
#include "RTClib.h"

#define LORA_RX 14 // Ke TXD LoRa
#define LORA_TX 13 // Ke RXD LoRa

// Gunakan GPIO 4 dan 2 agar Serial Monitor di Pin 1 & 3 tetap bisa melihat data
#define I2C_SDA 4
#define I2C_SCL 2

HardwareSerial LoRa(2);
RTC_DS3231 rtc;

void setup() {
  Serial.begin(115200);
  LoRa.begin(115200, SERIAL_8N1, LORA_RX, LORA_TX);

  Serial.println("\n=== TAHAP 2: UJI PENGIRIMAN RTC DS3231 VIA LORA ===");

  Wire.begin(I2C_SDA, I2C_SCL);
  if (!rtc.begin()) {
    Serial.println("[ERROR] Modul RTC DS3231 tidak terdeteksi!");
  } else {
    Serial.println("[OK] Modul RTC terdeteksi.");
    if (rtc.lostPower()) {
      Serial.println("RTC kehilangan daya, menyesuaikan ke waktu kompilasi...");
      rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
    }
  }
}

void loop() {
  delay(3000); // Kirim setiap 3 detik

  DateTime now = rtc.now();

  char pesan[80];
  snprintf(pesan, sizeof(pesan), "[RTC] Waktu: %04d-%02d-%02d %02d:%02d:%02d\n",
           now.year(), now.month(), now.day(), now.hour(), now.minute(), now.second());

  Serial.print("Mengirim: ");
  Serial.print(pesan);

  LoRa.print(pesan);
}
