/**
 * Smart Fridge — ESP32 báo Flask chạy /api/detect sau khi đóng cửa.
 *
 * Luồng: Reed (cửa đóng) → bật đèn → POST http://<PC>:5001/api/detect
 * → chờ phản hồi (timeout dài, server có thể mất tới ~90s inference)
 * → tắt đèn. Không gọi /capture lên chính ESP32-CAM; server sẽ gọi /capture + /view.
 *
 * Cấu hình: sửa SSID/PASSWORD, FLASK_HOST, FLASK_PORT. Chân GPIO theo mạch thực tế.
 */

#include <WiFi.h>
#include <HTTPClient.h>

// --- Wi-Fi ---
const char *WIFI_SSID = "YOUR_WIFI_SSID";
const char *WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Máy chạy Flask (same LAN as ESP32)
const char *FLASK_HOST = "192.168.1.100";
const int FLASK_PORT = 5001;

// GPIO (chỉnh theo phần cứng)
const int PIN_REED = 4;              // HIGH = cửa đóng (hoặc đảo logic dưới nếu mạch ngược)
const int PIN_LED_FRIDGE = 2;       // Đèn tủ / LED trợ sáng camera

// Debounce reed (ms)
const unsigned long REED_DEBOUNCE_MS = 80;
// Cooldown tối thiểu giữa hai lần gọi server (tránh rung tiếp điểm)
const unsigned long TRIGGER_COOLDOWN_MS = 3000;

// HTTPClient: timeout tổng (ms) — >= thời gian YOLO trên server (app.py dùng ~90s)
const int HTTP_TOTAL_TIMEOUT_MS = 120000;

bool lastReedStable = false;
unsigned long lastReedChangeMs = 0;
unsigned long lastTriggerMs = 0;

bool reedDoorClosed() {
  // Một số mạch: cửa đóng = nối GND → đọc LOW. Nếu bạn dùng pull-up và đóng = HIGH, đổi hàm này.
  return digitalRead(PIN_REED) == HIGH;
}

void setFridgeLight(bool on) {
  digitalWrite(PIN_LED_FRIDGE, on ? HIGH : LOW);
}

void triggerServerDetect() {
  WiFiClient client;
  HTTPClient http;
  String url = String("http://") + FLASK_HOST + ":" + FLASK_PORT + "/api/detect";

  // Banners UART
  Serial.println("[detect] POST " + url);

  if (!http.begin(client, url)) {
    Serial.println("[detect] http.begin failed");
    return;
  }

  http.setTimeout(HTTP_TOTAL_TIMEOUT_MS);
  // POST rỗng — Flask chấp nhận GET/POST không file; gửi POST tường minh
  int code = http.POST("");
  if (code > 0) {
    Serial.printf("[detect] HTTP %d\n", code);
  } else {
    Serial.printf("[detect] error: %s\n", http.errorToString(code).c_str());
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_REED, INPUT_PULLUP);
  pinMode(PIN_LED_FRIDGE, OUTPUT);
  setFridgeLight(false);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" OK ");
  Serial.println(WiFi.localIP());

  lastReedStable = reedDoorClosed();
  lastReedChangeMs = millis();
}

void loop() {
  bool raw = reedDoorClosed();
  unsigned long now = millis();

  if (raw != lastReedStable) {
    if (now - lastReedChangeMs >= REED_DEBOUNCE_MS) {
      lastReedStable = raw;
      lastReedChangeMs = now;

      // Cạnh: vừa đóng cửa (từ mở → đóng)
      if (lastReedStable && (now - lastTriggerMs >= TRIGGER_COOLDOWN_MS)) {
        lastTriggerMs = now;
        setFridgeLight(true);
        triggerServerDetect();
        setFridgeLight(false);
      }
    }
  } else {
    lastReedChangeMs = now;
  }

  delay(10);
}
