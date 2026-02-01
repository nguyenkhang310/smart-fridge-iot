# Hướng Dẫn Kết Nối với Wokwi ESP32 qua Firebase

## Tổng Quan

Project này đã được tích hợp với Firebase Realtime Database để kết nối với project Wokwi ESP32, cho phép hiển thị dữ liệu cảm biến thời gian thực và điều khiển thiết bị mà không cần phần cứng thực.

## Cấu Hình

Firebase configuration đã được cấu hình sẵn trong `firebase_integration.py`:
- **Database URL**: `testtulanh-default-rtdb.asia-southeast1.firebasedatabase.app`
- **Auth Token**: Đã được cấu hình sẵn

## Cài Đặt

1. Cài đặt dependencies:
```bash
pip install -r requirements.txt
```

2. Khởi động server:
```bash
python app.py
```

Server sẽ tự động kết nối với Firebase khi khởi động.

## API Endpoints

### 1. Lấy Dữ Liệu Cảm Biến Thời Gian Thực
```
GET /api/sensors
```
Trả về dữ liệu cảm biến mới nhất từ Wokwi ESP32 (nhiệt độ, độ ẩm, trạng thái cửa, PWM).

### 2. Lấy Lịch Sử Dữ Liệu từ Firebase
```
GET /api/firebase/history?limit=50
```
Trả về lịch sử dữ liệu cảm biến từ Firebase (mặc định 50 records).

### 3. Điều Khiển Đèn LED
```
POST /api/firebase/control/light
Content-Type: application/json

{
  "value": 1  // 0 = tắt, 1 = bật
}
```

### 4. Điều Khiển Peltier (Làm Lạnh)
```
POST /api/firebase/control/peltier
Content-Type: application/json

{
  "value": 150  // 0-255 (PWM value)
}
```

### 5. Lấy Trạng Thái Điều Khiển
```
GET /api/firebase/control/status
```
Trả về trạng thái điều khiển hiện tại (Light và Peltier).

## Cách Hoạt Động

1. **ESP32 trên Wokwi** gửi dữ liệu cảm biến lên Firebase:
   - `/Current` – cập nhật mỗi 2–3 giây (real-time)
   - `/History` – push mỗi 30 giây (lưu lịch sử)
2. **Flask App** đọc dữ liệu từ `/Current` (nếu có) hoặc `/History`
3. **Web Interface** gửi nhiệt độ mục tiêu → API chuyển sang PWM → ghi vào `/Control/Peltier`
4. **ESP32** đọc lệnh điều khiển từ `/Control/Light` và `/Control/Peltier` và thực thi

## Cập nhật code Wokwi để web real-time hơn

Mặc định ESP32 chỉ gửi dữ liệu mỗi 30 giây nên web cập nhật chậm. Để web cập nhật nhanh hơn (2–3 giây), sửa code Wokwi như sau.

**Bước 1:** Mở project Wokwi: https://wokwi.com/projects/454774442255501313

**Bước 2:** Thêm đoạn sau vào `loop()` – cập nhật `/Current` mỗi 2 giây:

```cpp
void loop() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  int doorState = digitalRead(DOOR_PIN);

  if (Firebase.getInt(fbData, "/Control/Light")) cuongBucDen = fbData.intData();
  if (Firebase.getInt(fbData, "/Control/Peltier")) webPWM = fbData.intData();

  digitalWrite(LIGHT_PIN, (doorState == HIGH || cuongBucDen == 1) ? HIGH : LOW);
  
  int finalPWM = (webPWM > 0) ? webPWM : (t > 25.0 ? 255 : (t > 20.0 ? 150 : 0));
  ledcWrite(PELTIER_PWM_PIN, finalPWM);

  // Cập nhật /Current mỗi 2 giây - web đọc path này để hiển thị nhanh
  static unsigned long lastCurrent = 0;
  if (millis() - lastCurrent > 2000) {
    lastCurrent = millis();
    FirebaseJson json;
    json.set("Temp", t);
    json.set("Humi", h);
    json.set("Door", doorState);
    json.set("PWM", finalPWM);
    Firebase.setJSON(fbData, "/Current", json);
  }

  // Lưu lịch sử mỗi 30 giây (giữ nguyên)
  static unsigned long lastPush = 0;
  if (millis() - lastPush > 30000) {
    lastPush = millis();
    FirebaseJson json;
    json.set("Temp", t);
    json.set("Humi", h);
    json.set("Door", doorState);
    json.set("PWM", finalPWM);
    Firebase.pushJSON(fbData, "/History", json);
  }

  updateOLED(t, h, doorState, finalPWM);
}
```

**Thay đổi chính:**
- Thêm khối `lastCurrent` dùng `Firebase.setJSON(fbData, "/Current", json)` mỗi 2 giây
- Giữ nguyên push `/History` mỗi 30 giây

**Hoặc chỉ rút ngắn thời gian push History:** đổi `30000` thành `3000` (3 giây) trong dòng `if (millis() - lastPush > 30000)`.

## Điều chỉnh nhiệt độ không cập nhật trên Wokwi?

1. **Đảm bảo Wokwi simulation đang chạy** – ESP32 phải đang chạy để đọc `/Control/Peltier` từ Firebase.
2. **Kiểm tra Firebase Console** – Mở https://console.firebase.google.com, chọn project `testtulanh`, vào Realtime Database. Khi bấm "Cập Nhật Nhiệt Độ" trên web, `/Control/Peltier` và `/Control/TargetTemp` phải thay đổi.
3. **Nếu có lỗi** – Web sẽ hiển thị "⚠ Lỗi Firebase" trong thông báo. Kiểm tra server log để xem chi tiết.
4. **Logic ESP32** – ESP32 dùng PWM khi `webPWM > 0`. Nếu nhiệt độ hiện tại đã thấp hơn mục tiêu, server gửi PWM=0, ESP32 sẽ dùng logic tự động thay vì PWM cố định.

## Kiểm Tra Kết Nối

Khi khởi động server, bạn sẽ thấy:
- `✓ Firebase initialized successfully` - Kết nối thành công
- `⚠ Firebase initialization error` - Có lỗi kết nối

## Lưu Ý

- Đảm bảo project Wokwi đang chạy và kết nối WiFi
- Dữ liệu được cập nhật mỗi 30 giây từ ESP32
- Có thể test mà không cần phần cứng thực, chỉ cần chạy simulation trên Wokwi

## Link Wokwi Project

https://wokwi.com/projects/454774442255501313
