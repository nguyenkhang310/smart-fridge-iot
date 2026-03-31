#include <WiFi.h>
#include <HTTPClient.h>
#include <Firebase_ESP_Client.h>
#include <DHT.h>
#include <U8g2lib.h>
#include <Wire.h>


// Bổ sung thư viện hỗ trợ Token của Firebase
#include "addons/TokenHelper.h"
#include "addons/RTDBHelper.h"


// --- THÔNG TIN CẤU HÌNH ---
#define WIFI_SSID "quan"
#define WIFI_PASS "abcd0000"
#define FIREBASE_HOST "testtulanh-default-rtdb.asia-southeast1.firebasedatabase.app"
#define FIREBASE_AUTH "ymJAPlPa6CBPtKRvIzRvdagYggAt4e0oEJNoigWP"
#define CAM_CAPTURE_URL "http://172.20.10.2/capture"


// --- CẤU HÌNH PIN ---
#define DHTPIN 15
#define DHTTYPE DHT11
#define REED_PIN 14
#define LED_PIN 13
#define PWM_PIN 26


// --- CẤU HÌNH HARDWARE PWM (LEDC) ---
#define PWM_CHAN 0
#define PWM_FREQ 100
#define PWM_RES 8


// --- KHỞI TẠO ĐỐI TƯỢNG ---
DHT dht(DHTPIN, DHTTYPE);
U8G2_SH1106_128X64_NONAME_F_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE);
FirebaseData fbdo;
FirebaseAuth auth;
FirebaseConfig config;


// --- BIẾN TOÀN CỤC ---
float lastTemp = 0.0, lastHumi = 0.0;
int targetTemp = 6;     // Nhiệt độ mục tiêu mặc định (6°C)
int pwmValue = 0;       // Giá trị băm xung thực tế (0 - 255)
int fruitCount = 0;
String systemStatus = "NORMAL";


// Biến trạng thái cửa
int stableState = HIGH;
int lastRaw = HIGH;
unsigned long lastChangeTime = 0;
bool waitingToTurnOffLED = false;
unsigned long doorClosedTime = 0;


void triggerCamera() {
  HTTPClient http;
  http.begin(CAM_CAPTURE_URL);
  http.setTimeout(1000);
  http.GET();
  http.end();
}


void syncFirebase() {
  static unsigned long lastSync = 0;
  if (millis() - lastSync < 2000) return;
  lastSync = millis();


  if (Firebase.ready()) {
    // 1. Ghi dữ liệu trạng thái lên Firebase nhánh Current
    Firebase.RTDB.setFloat(&fbdo, "/Current/Temp", lastTemp);
    Firebase.RTDB.setFloat(&fbdo, "/Current/Humi", lastHumi);
    Firebase.RTDB.setInt(&fbdo, "/Current/Door", (stableState == LOW ? 0 : 1));
    Firebase.RTDB.setInt(&fbdo, "/Current/PWM", pwmValue);
   
    // 2. Kéo dữ liệu điều khiển từ Firebase về
    if (Firebase.RTDB.getInt(&fbdo, "/Current/Inventory/total_items")) {
      fruitCount = fbdo.intData();
    }
   
    // ĐỌC NHIỆT ĐỘ MỤC TIÊU TỪ WEB DASHBOARD
    if (Firebase.RTDB.getInt(&fbdo, "/Control/TargetTemp")) {
      targetTemp = fbdo.intData();
    }


    // 3. THUẬT TOÁN ĐIỀU KHIỂN SÒ LẠNH (TỰ ĐỘNG)
    if (lastTemp >= targetTemp + 2.0) {
        pwmValue = 255;
        systemStatus = "COOLING (MAX)";
    } else if (lastTemp > targetTemp) {
        pwmValue = 150;
        systemStatus = "COOLING (ECO)";
    } else {
        pwmValue = 0;  
        systemStatus = "TARGET REACHED";
    }
   
    // Cập nhật cảnh báo nếu tủ quá bất thường
    if (lastTemp > 15.0) systemStatus = "WARNING: HOT!";
  }
}


// --- GIAO DIỆN OLED 5 TẦNG TỐI ƯU ---
void updateDisplay() {
  static unsigned long lastOled = 0;
  if (millis() - lastOled < 500) return;
  lastOled = millis();


  u8g2.clearBuffer();
 
  // Tầng 1: Trạng thái hệ thống
  u8g2.setFont(u8g2_font_ncenB08_tr);
  u8g2.setCursor(0, 10);
  u8g2.print("SYS: " + systemStatus);
  u8g2.drawHLine(0, 12, 128);


  // Tầng 2 & 3: Nhiệt độ và Độ ẩm thực tế
  u8g2.setFont(u8g2_font_9x15_tf);
  u8g2.setCursor(0, 28); // Cũ là 30
  u8g2.print("Temp: " + String(lastTemp, 1) + " C");
  u8g2.setCursor(0, 43); // Cũ là 46
  u8g2.print("Humi: " + String(lastHumi, 0) + " %");


  // Tầng 4: Nhiệt độ mục tiêu đang cài đặt
  u8g2.setFont(u8g2_font_6x10_tf);
  u8g2.setCursor(0, 54); // Cũ là 56
  u8g2.print("TARGET TEMP: " + String(targetTemp) + " C");


  // Tầng 5: Số lượng vật phẩm
  u8g2.setFont(u8g2_font_6x10_tf);
  u8g2.setCursor(0, 64);
  u8g2.print("FRUITS IN STOCK: " + String(fruitCount));
 
  u8g2.sendBuffer();
}


void setup() {
  Serial.begin(115200);
  setCpuFrequencyMhz(80);
  dht.begin();
  u8g2.begin();


  pinMode(REED_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);


// --- SỬA LỖI TẠI ĐÂY: DÙNG CẤU TRÚC PWM PHIÊN BẢN 3.X ---
  ledcAttach(PWM_PIN, PWM_FREQ, PWM_RES);  // Khởi tạo và gắn PWM trực tiếp vào chân
  ledcWrite(PWM_PIN, 0);                   // Đảm bảo sò lạnh tắt lúc mới khởi động


  // Kết nối WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }


  // Kết nối Firebase
  config.host = FIREBASE_HOST;
  config.signer.tokens.legacy_token = FIREBASE_AUTH;
  Firebase.begin(&config, &auth);
  Firebase.reconnectWiFi(true);
}


void loop() {
  syncFirebase();
  updateDisplay();
 
  // --- SỬA LỖI TẠI ĐÂY: GHI PWM VÀO CHANNEL THAY VÌ PIN ---
  ledcWrite(PWM_PIN, pwmValue);


  // Đọc cảm biến định kỳ
  static unsigned long lastDHT = 0;
  if (millis() - lastDHT > 2000) {
    float t = dht.readTemperature();
    float h = dht.readHumidity();
    if (!isnan(t)) { lastTemp = t; lastHumi = h; }
    lastDHT = millis();
  }


// Logic cửa & Đèn trợ sáng cho Camera
  int raw = digitalRead(REED_PIN);
  if (raw != lastRaw) lastChangeTime = millis();
 
  if (millis() - lastChangeTime >= 50) {
    if (raw != stableState) {
      stableState = raw;
     
      if (stableState == LOW) { // ĐÓNG CỬA
        digitalWrite(LED_PIN, HIGH); // Bật đèn ngay
       
        // 1. ÉP ĐỒNG BỘ FIREBASE NGAY LẬP TỨC để tín hiệu không bị trễ
        if (Firebase.ready()) {
          Firebase.RTDB.setInt(&fbdo, "/Current/Door", 0);
        }
       
        // 2. Kích hoạt camera chụp ảnh
        triggerCamera();
       
        // 3. Đặt mốc thời gian SAU KHI GỌI CAM (để trừ hao thời gian trễ của hàm HTTP)
        waitingToTurnOffLED = true;
        doorClosedTime = millis();
       
      } else { // MỞ CỬA
        digitalWrite(LED_PIN, HIGH);
        waitingToTurnOffLED = false;
       
        // Cập nhật Firebase mở cửa ngay lập tức
        if (Firebase.ready()) {
          Firebase.RTDB.setInt(&fbdo, "/Current/Door", 1);
        }
      }
    }
  }
 
// Tự động tắt đèn sau 2 giây (tăng lên 2000ms để đảm bảo dư dả ánh sáng cho Cam lưu ảnh)
  if (waitingToTurnOffLED && (millis() - doorClosedTime >= 2000)) {
    digitalWrite(LED_PIN, LOW);
    waitingToTurnOffLED = false;
  }
  lastRaw = raw;
}


