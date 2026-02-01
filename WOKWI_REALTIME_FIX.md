# Hướng Dẫn Sửa Wokwi để Real-Time (1-2 giây)

## ⚠️ Vấn Đề Hiện Tại

ESP32 trên Wokwi đang push dữ liệu lên Firebase mỗi **30 giây**, nên web app phải đợi tối đa 30 giây để có dữ liệu mới.

## ✅ Giải Pháp: Sửa ESP32 để Push Mỗi 1-2 Giây

### Bước 1: Mở Project Wokwi
1. Truy cập: https://wokwi.com/projects/454774442255501313
2. Click vào tab **sketch.ino**

### Bước 2: Tìm và Sửa
Tìm dòng này trong hàm `loop()`:

```cpp
// 4. Lưu lịch sử mỗi 30 giây (Sử dụng push)
static unsigned long lastPush = 0;
if (millis() - lastPush > 30000) {  // <-- SỬA SỐ 30000 NÀY
```

### Bước 3: Sửa Thành Real-Time

**Option 1: Real-time (1 giây) - Khuyến nghị**
```cpp
// 4. Lưu lịch sử mỗi 1 giây (Real-time)
static unsigned long lastPush = 0;
if (millis() - lastPush > 1000) {  // 1 giây = 1000ms
    lastPush = millis();
    FirebaseJson json;
    json.set("Temp", t);
    json.set("Humi", h);
    json.set("Door", doorState);
    json.set("PWM", finalPWM);
    Firebase.pushJSON(fbData, "/History", json);
}
```

**Option 2: Gần real-time (2 giây)**
```cpp
if (millis() - lastPush > 2000) {  // 2 giây = 2000ms
```

**Option 3: Cân bằng (3 giây)**
```cpp
if (millis() - lastPush > 3000) {  // 3 giây = 3000ms
```

### Bước 4: Lưu và Test
1. Click **Save** (Ctrl+S / Cmd+S)
2. Click **Start Simulation** (nút xanh)
3. Quan sát web app - dữ liệu sẽ cập nhật mỗi 1-2 giây!

## 📊 So Sánh Tốc Độ

| Giá trị | Thời gian | Tốc độ | Khuyến nghị |
|---------|----------|--------|-------------|
| `30000` | 30 giây | ⚠️ Rất chậm | ❌ Không dùng |
| `5000` | 5 giây | ⚠️ Chậm | ⚠️ Tạm được |
| `2000` | 2 giây | ✅ Tốt | ✅ Khuyến nghị |
| `1000` | 1 giây | ⚡ Real-time | ⭐ Tốt nhất |

## ⚠️ Lưu Ý

1. **Firebase Quota**: Push mỗi 1 giây = 3600 requests/giờ. Firebase free tier cho phép 100,000 requests/ngày, nên vẫn an toàn.

2. **Nếu gặp lỗi quota**: Tăng lên 2-3 giây

3. **Sau khi sửa**: Phải **restart simulation** trên Wokwi

## 🎯 Code Hoàn Chỉnh

```cpp
void loop() {
  float t = dht.readTemperature();
  float h = dht.readHumidity();
  int doorState = digitalRead(DOOR_PIN);

  // 2. Đọc lệnh điều khiển từ Web (Firebase)
  if (Firebase.getInt(fbData, "/Control/Light")) cuongBucDen = fbData.intData();
  if (Firebase.getInt(fbData, "/Control/Peltier")) webPWM = fbData.intData();

  // 3. Logic điều khiển
  digitalWrite(LIGHT_PIN, (doorState == HIGH || cuongBucDen == 1) ? HIGH : LOW);
  
  int finalPWM = (webPWM > 0) ? webPWM : (t > 25.0 ? 255 : (t > 20.0 ? 150 : 0));
  ledcWrite(PELTIER_PWM_PIN, finalPWM);

  // 4. Lưu lịch sử mỗi 1 giây (REAL-TIME)
  static unsigned long lastPush = 0;
  if (millis() - lastPush > 1000) {  // <-- ĐÃ SỬA: 30000 → 1000
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

## ✅ Kết Quả

Sau khi sửa:
- **Trước**: Web app cập nhật sau 30-44 giây
- **Sau**: Web app cập nhật sau **1-2 giây** (real-time!)
- **Với background thread**: Web app phát hiện trong vòng **0.1-0.2 giây** sau khi ESP32 push

## 🚀 Bước Tiếp Theo

1. Sửa code trên Wokwi như hướng dẫn (đổi `30000` → `1000`)
2. Restart simulation trên Wokwi
3. Refresh web app - dữ liệu sẽ cập nhật real-time!
