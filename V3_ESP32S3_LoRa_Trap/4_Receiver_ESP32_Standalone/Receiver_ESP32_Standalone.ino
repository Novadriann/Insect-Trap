/**
 * ====================================================================================
 * PROGRAM RECEIVER NODE STANDALONE (TANPA RASPBERRY PI)
 * Hardware : ESP32 Dev Module + LoRa Ebyte E220-900T22D
 * Fitur    : - Menangkap transmisi LoRa dari Node Transmitter (ESP32-S3)
 *            - Mem-parsing data sensor Suhu, Kelembaban, dan Waktu RTC
 *            - Menampilkan data rapi di Serial Monitor (115200 baud)
 *            - Memantau proses penerimaan data biner gambar
 *            - Mendukung tampilan opsional ke layar I2C OLED 0.96" (SSD1306)
 * Lab ELINS - Universitas Gadjah Mada
 * ====================================================================================
 */

#include <HardwareSerial.h>
#include <Wire.h>

// --- OPSI TAMPILAN OLED 0.96" (Ubah ke true jika menggunakan layar OLED SSD1306) ---
#define USE_OLED_DISPLAY false

#if USE_OLED_DISPLAY
  #include <Adafruit_GFX.h>
  #include <Adafruit_SSD1306.h>
  #define SCREEN_WIDTH 128
  #define SCREEN_HEIGHT 64
  #define OLED_RESET    -1
  Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
#endif

// ====================================================================================
// PENGATURAN PIN LORA EBYTE E220 PADA ESP32 DEV MODULE
// ====================================================================================
#define LORA_RX_PIN 16 // Hubungkan ke TXD modul LoRa (ESP32 RX2)
#define LORA_TX_PIN 17 // Hubungkan ke RXD modul LoRa (ESP32 TX2)

HardwareSerial LoRaSerial(2);

// Variabel status penerimaan gambar
bool isReceivingImage = false;
size_t expectedImageBytes = 0;
size_t receivedImageBytes = 0;
String textBuffer = "";

void setup() {
  // Serial USB untuk Komputer / Laptop
  Serial.begin(115200);
  delay(1000);

  // Serial UART2 untuk Modul LoRa E220
  LoRaSerial.begin(115200, SERIAL_8N1, LORA_RX_PIN, LORA_TX_PIN);

  Serial.println("\n========================================================");
  Serial.println("  RECEIVER STANDALONE LORA ESP32 SIAP");
  Serial.println("  Menunggu transmisi Sensor (DHT22 & RTC) dan Gambar...");
  Serial.println("========================================================\n");

#if USE_OLED_DISPLAY
  Wire.begin(21, 22); // SDA = GPIO 21, SCL = GPIO 22 pada ESP32 Dev
  if (display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.println("INSECT TRAP RECEIVER");
    display.println("Status: Standby");
    display.println("Menunggu data...");
    display.display();
  }
#endif
}

void loop() {
  while (LoRaSerial.available()) {
    uint8_t b = LoRaSerial.read();

    if (!isReceivingImage) {
      // Modus pembacaan teks (Data sensor / Header)
      if (b == '\n' || b == '\r') {
        if (textBuffer.length() > 0) {
          processTextMessage(textBuffer);
          textBuffer = "";
        }
      } else {
        textBuffer += (char)b;
        // Mencegah overflow buffer jika ada noise
        if (textBuffer.length() > 200) {
          textBuffer = "";
        }
      }
    } else {
      // Modus pembacaan biner gambar
      receivedImageBytes++;
      // Teruskan byte biner ke port USB Serial PC (agar script PC bisa menangkapnya jika ada)
      Serial.write(b);

      // Tampilkan progress setiap kelipatan 1000 byte
      if (receivedImageBytes % 1000 == 0 || receivedImageBytes >= expectedImageBytes) {
        float pct = (expectedImageBytes > 0) ? ((float)receivedImageBytes / expectedImageBytes * 100.0) : 0;
        Serial.printf("\n[PROGRESS GAMBAR] Menerima: %u / %u bytes (%.1f%%)", 
                      receivedImageBytes, expectedImageBytes, pct);
      }

      if (receivedImageBytes >= expectedImageBytes) {
        Serial.println("\n--------------------------------------------------------");
        Serial.println("[SUKSES] Seluruh byte gambar telah lengkap diterima!");
        Serial.println("--------------------------------------------------------\n");
        isReceivingImage = false;
        receivedImageBytes = 0;
        expectedImageBytes = 0;
      }
    }
  }

  // Meneruskan input dari Serial Monitor PC ke LoRa (jika dibutuhkan)
  if (Serial.available()) {
    LoRaSerial.write(Serial.read());
  }
}

// ====================================================================================
// FUNGSI MEMPROSES PESAN TEKS & HEADER
// ====================================================================================
void processTextMessage(String msg) {
  msg.trim();

  // 1. Memeriksa apakah ini data sensor
  if (msg.startsWith("[DATA]") || msg.startsWith("SENSOR,")) {
    Serial.println("\n╔══════════════════════════════════════════════════════╗");
    Serial.println("║            DATA SENSOR BARU DITERIMA                 ║");
    Serial.println("╠══════════════════════════════════════════════════════╣");
    Serial.printf("║  Raw: %s\n", msg.c_str());

    // Parsing sederhana data
    // Format: [DATA] Waktu: 2026-09-10 10:30:00, Suhu: 28.5 C, Kelembaban: 75.0 %
    int idxWaktu = msg.indexOf("Waktu: ");
    int idxSuhu  = msg.indexOf("Suhu: ");
    int idxHum   = msg.indexOf("Kelembaban: ");

    String waktuStr = (idxWaktu != -1) ? msg.substring(idxWaktu + 7, (idxSuhu != -1) ? idxSuhu - 2 : msg.length()) : "-";
    String suhuStr  = (idxSuhu != -1)  ? msg.substring(idxSuhu + 6, (idxHum != -1) ? idxHum - 2 : msg.length()) : "-";
    String humStr   = (idxHum != -1)   ? msg.substring(idxHum + 12) : "-";

    waktuStr.trim();
    suhuStr.trim();
    humStr.trim();

    Serial.printf("║  Tanggal / Jam  : %s\n", waktuStr.c_str());
    Serial.printf("║  Suhu Udara     : %s\n", suhuStr.c_str());
    Serial.printf("║  Kelembaban     : %s\n", humStr.c_str());
    Serial.println("╚══════════════════════════════════════════════════════╝\n");

#if USE_OLED_DISPLAY
    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.println("MONITORING HAMA (TRAP)");
    display.drawLine(0, 10, 128, 10, SSD1306_WHITE);
    display.setCursor(0, 15);
    display.printf("Tgl : %s\n", waktuStr.substring(0, 10).c_str());
    display.printf("Jam : %s\n", waktuStr.substring(11).c_str());
    display.printf("Suhu: %s\n", suhuStr.c_str());
    display.printf("RH  : %s\n", humStr.c_str());
    display.display();
#endif
  }
  // 2. Memeriksa header mulai pengiriman gambar
  else if (msg.startsWith("---START---")) {
    // Format: ---START---<length>
    int sepIdx = msg.indexOf("---START---");
    String lenStr = msg.substring(sepIdx + 11);
    lenStr.trim();
    expectedImageBytes = lenStr.toInt();

    if (expectedImageBytes > 0) {
      Serial.println("\n[GAMBAR] >>> Menerima transmisi gambar baru...");
      Serial.printf("[GAMBAR] Ukuran yang diharapkan: %u bytes\n", expectedImageBytes);
      isReceivingImage = true;
      receivedImageBytes = 0;
    }
  }
  // 3. Pesan umum / status lain
  else {
    Serial.printf("[LOG] %s\n", msg.c_str());
  }
}
