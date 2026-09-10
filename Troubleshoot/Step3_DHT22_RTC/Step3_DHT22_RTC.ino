#include <HardwareSerial.h>
#include <Wire.h>
#include "DHT.h"
#include "RTClib.h"

#define LORA_RX 14 // Ke TXD LoRa
#define LORA_TX 13 // Ke RXD LoRa

#define DHTPIN 15
#define DHTTYPE DHT22

#define I2C_SDA 4
#define I2C_SCL 2

HardwareSerial LoRa(2);
DHT dht(DHTPIN, DHTTYPE);
RTC_DS3231 rtc;

void setup() {
  Serial.begin(115200);
  LoRa.begin(115200, SERIAL_8N1, LORA_RX, LORA_TX);

  Serial.println("\n=== TAHAP 3: UJI GABUNGAN DHT22 & RTC DS3231 VIA LORA ===");

  dht.begin();
  Wire.begin(I2C_SDA, I2C_SCL);

  if (!rtc.begin()) {
    Serial.println("[ERROR] RTC tidak terdeteksi!");
  } else {
    Serial.println("[OK] RTC Terhubung.");
    if (rtc.lostPower()) {
      rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
    }
  }
}

void loop() {
  delay(4000); // Kirim setiap 4 detik

  float h = dht.readHumidity();
  float t = dht.readTemperature();
  DateTime now = rtc.now();

  if (isnan(h) || isnan(t)) {
    Serial.println("[WARNING] DHT22 gagal dibaca!");
    h = 0.0; t = 0.0;
  }

  char pesan[120];
  snprintf(pesan, sizeof(pesan), "[SENSOR] Waktu: %04d-%02d-%02d %02d:%02d:%02d | Suhu: %.1f C | Lembab: %.1f %%\n",
           now.year(), now.month(), now.day(), now.hour(), now.minute(), now.second(), t, h);

  Serial.print("Mengirim: ");
  Serial.print(pesan);

  LoRa.print(pesan);
}
