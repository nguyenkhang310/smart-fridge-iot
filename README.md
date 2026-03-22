<div align="center">

![Logo Trường Đại Học Công Nghệ Kỹ Thuật TP.HCM](static/img/logo-hcm-ute.png)

# 🧊 Hệ thống Tủ lạnh Thông minh IoT với AI

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)
![YOLO](https://img.shields.io/badge/YOLO-v8-orange.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**Hệ thống tủ lạnh IoT thông minh với AI nhận diện trái cây, giám sát nhiệt độ/độ ẩm thời gian thực, điều khiển qua Firebase/Wokwi**

[Giới thiệu](#-giới-thiệu-dự-án) • [Tính năng](#-tính-năng) • [Cài đặt](#-cài-đặt) • [Cấu hình](#-cấu-hình) • [API](#-api-endpoints) • [Kiến trúc](#-kiến-trúc-hệ-thống) • [Tài liệu](#-tài-liệu)

</div>

---

## 📋 Mục lục

- [Giới thiệu dự án](#-giới-thiệu-dự-án)
- [Tính năng](#-tính-năng)
- [Yêu cầu hệ thống](#-yêu-cầu-hệ-thống)
- [Cài đặt](#-cài-đặt)
- [Cấu hình](#-cấu-hình)
- [Sử dụng](#-sử-dụng)
- [API Endpoints](#-api-endpoints)
- [Cơ sở dữ liệu](#-cơ-sở-dữ-liệu)
- [Kiến trúc hệ thống](#-kiến-trúc-hệ-thống)
- [Phần cứng IoT](#-phần-cứng-iot)
- [Triển khai Production](#-triển-khai-production)
- [Xử lý sự cố](#-xử-lý-sự-cố)
- [Tài liệu](#-tài-liệu)
- [Liên hệ](#-liên-hệ)

---

## 📖 Giới thiệu dự án

**Hệ thống Tủ lạnh Thông minh IoT** là giải pháp toàn diện để quản lý tủ lạnh thông minh, tích hợp:

- **Giám sát thời gian thực**: Nhiệt độ, độ ẩm, trạng thái cửa tủ qua Firebase/Wokwi hoặc phần cứng thật
- **Điều khiển từ xa**: Điều chỉnh nhiệt độ mục tiêu (-2°C đến 10°C), điều khiển Peltier (làm lạnh), LED
- **AI nhận diện**: YOLO phát hiện trái cây (Táo, Chuối, Xoài, Cam, Lê) và đánh giá độ chín/hỏng
- **Cảnh báo tự động**: Thông báo qua Telegram khi phát hiện trái cây hỏng
- **Đa nguồn camera**: Webcam hoặc ESP32-CAM qua WiFi
- **Dashboard web**: Giao diện trực quan với cập nhật real-time qua Server-Sent Events (SSE)
- **Hệ thống xác thực**: Đăng nhập/đăng xuất, đăng ký, phân quyền admin/user, bảo vệ brute-force

Dự án hướng tới triển khai thực tế (ESP32, cảm biến, camera) nhưng có chế độ mô phỏng để demo bằng Wokwi.

---

## ✨ Tính năng

### Giám sát cảm biến

| Tính năng | Mô tả |
|-----------|-------|
| **Nhiệt độ** | Theo dõi nhiệt độ theo thời gian thực với cảnh báo khi vượt ngưỡng |
| **Độ ẩm** | Giám sát độ ẩm bên trong tủ lạnh |
| **Cập nhật tự động** | Dữ liệu cảm biến cập nhật mỗi 0.2–3 giây (SSE stream) |
| **Đa nguồn dữ liệu** | Hỗ trợ Firebase/Wokwi, Raspberry Pi, hoặc chế độ mô phỏng |

### Điều khiển

| Tính năng | Mô tả |
|-----------|-------|
| **Điều chỉnh nhiệt độ** | Slider đặt nhiệt độ mục tiêu (-2°C đến 10°C) |
| **Peltier** | Điều khiển PWM làm lạnh tự động qua Firebase |
| **LED** | Bật/tắt đèn bên trong tủ |
| **Chế độ điều khiển** | `software` (Firebase/Wokwi) hoặc `hardware` (Raspberry Pi thật) |

### Camera & AI nhận diện

#### Đa nguồn camera
- **Webcam**: Sử dụng camera máy tính (tích hợp hoặc USB)
- **ESP32-CAM**: Kết nối WiFi với module ESP32-CAM
- **Chuyển đổi dễ dàng**: Chọn nguồn qua 2 nút trên giao diện

#### AI nhận diện nâng cao
- **Mô hình phát hiện**: Nhận diện trái cây (Apple, Banana, Mango, Orange, Pear)
- **Mô hình phân loại**: Phân loại độ chín/hỏng của trái cây
- **Phân tích màu HSV**: Đánh giá độ chín qua không gian màu
- **Tính hạn sử dụng**: Ước lượng số ngày còn lại theo loại và độ chín
- **Bounding box**: Hiển thị khung nhận diện với màu (xanh = tốt, đỏ = hỏng, cam = khác)
- **Độ tin cậy**: Hiển thị phần trăm chính xác

#### Cảnh báo tự động
- **Telegram**: Gửi cảnh báo khi phát hiện trái cây hỏng
- **Cơ chế cooldown**: Tránh spam thông báo (60–120 giây)
- **Đính kèm ảnh**: Gửi kèm ảnh nhận diện

### Màn hình OLED (mô phỏng)

Hiển thị thông tin thời gian thực:
- Nhiệt độ và độ ẩm hiện tại
- Trạng thái hệ thống (NORMAL/WARNING)
- Số lượng vật phẩm và trái cây
- Thời gian hiện tại

### Thống kê & Tồn kho

- **Tổng vật phẩm**: Đếm tự động từ kết quả nhận diện
- **Phân loại**: Trái cây, Thực phẩm, Vật phẩm khác
- **Lịch sử**: Lưu phiên nhận diện vào database
- **Dashboard trực quan**: Hiển thị thống kê với màu sắc phân biệt

### Hệ thống xác thực

- **Đăng nhập/Đăng xuất**: Quản lý phiên người dùng
- **Đăng ký tài khoản**: Tạo tài khoản mới
- **Phân quyền**: Admin và User với quyền khác nhau
- **Bảo vệ brute-force**: Khóa tài khoản sau N lần đăng nhập sai (mặc định 5 lần trong 15 phút)

### Chatbot AI

- Trợ lý dựa trên rule-based (tiếng Việt)
- Hỗ trợ truy vấn: cảm biến, tồn kho, nhiệt độ
- Nút chat nổi trên giao diện

---

## 🖥️ Yêu cầu hệ thống

| Thành phần | Yêu cầu |
|------------|---------|
| **Python** | 3.8 trở lên |
| **RAM** | Tối thiểu 2GB (khuyến nghị 4GB+) |
| **Camera** | Webcam hoặc ESP32-CAM (tùy chọn) |
| **Internet** | Cần khi tải mô hình YOLO lần đầu |
| **MySQL** | Phiên bản 5.7+ hoặc 8.0+ (tùy chọn, để lưu lịch sử) |

---

## 🚀 Cài đặt

### Cách 1: Cài đặt thủ công

```bash
# 1. Clone repository
git clone <repository-url>
cd smart-fridge-iot

# 2. Tạo môi trường ảo (khuyến nghị)
python3 -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

# 3. Cài đặt dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Tải mô hình YOLO (tự động tải lần đầu chạy)
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# 5. Tạo thư mục cần thiết
mkdir -p uploads models logs

# 6. Chạy server
python app.py
```

Mở trình duyệt: **http://localhost:5001**

### Cách 2: Script tự động (Linux/macOS)

```bash
chmod +x install.sh
./install.sh
```

Script sẽ:
- Kiểm tra Python 3.8+
- Tạo virtual environment
- Cài đặt packages
- Tải mô hình YOLO
- Tạo thư mục `uploads`, `models`, `logs`
- Tạo file `start.sh` để khởi động nhanh
- Hỏi cài trên Raspberry Pi (GPIO, DHT, OLED)
- Hỏi cài systemd service (tự khởi động)

### Cách 3: Docker

```bash
# Build và chạy
docker-compose up -d

# Truy cập
# http://localhost:5000
```

**Lưu ý**: Ứng dụng gốc chạy port **5001**; Docker map ra **5000**.

---

## ⚙️ Cấu hình

### Biến môi trường (`.env`)

Tạo file `.env` tại thư mục gốc dự án:

```env
# Database MySQL
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=smart_fridge

# Session & Security
SECRET_KEY=your-secret-key-here
SESSION_COOKIE_SAMESITE=Lax
SESSION_COOKIE_SECURE=false
SESSION_LIFETIME_HOURS=12

# Brute-force protection
MAX_LOGIN_ATTEMPTS=5
LOGIN_ATTEMPT_WINDOW_SECONDS=900
LOCKOUT_SECONDS=900

# Admin mặc định (tạo khi DB trống)
BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_PASSWORD=your_admin_password

# Phần cứng thật (Raspberry Pi)
USE_HARDWARE=false
```

### 1. Cấu hình ESP32-CAM

Trong `app.py`, dòng ~191:

```python
ESP32_CAM_IP = "http://192.168.137.16"  # Thay bằng IP ESP32-CAM của bạn
```

**Cách lấy IP ESP32-CAM:**
1. Kết nối ESP32-CAM vào WiFi
2. Xem Serial Monitor để biết IP được gán
3. Hoặc xem trong trang quản trị router

**Kiểm tra kết nối:**
```bash
curl http://192.168.137.16/capture
```

### 2. Cấu hình MySQL

Xem chi tiết trong `docs/DATABASE_SETUP.md`.

```sql
CREATE DATABASE smart_fridge
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

Cấu hình trong `core/database.py` hoặc qua biến môi trường `DB_*`.

### 3. Cấu hình Firebase (Wokwi)

Xem `docs/FIREBASE_WOKWI_SETUP.md` và `docs/WOKWI_REALTIME_FIX.md`.

Cấu hình trong `core/firebase_integration.py`:
- Firebase Database URL
- Auth token hoặc credentials

### 4. Cấu hình Telegram Bot

**Tạo bot:**
1. Tìm `@BotFather` trên Telegram
2. Gửi `/newbot` và làm theo hướng dẫn
3. Lấy Bot Token

**Cấu hình trong `core/telegram_notify.py`:**
```python
TELEGRAM_BOT_TOKEN = "your-bot-token"
TELEGRAM_CHAT_ID = "your-chat-id"
```

**Lấy Chat ID:**
1. Gửi tin nhắn cho bot
2. Truy cập: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Tìm `chat.id` trong response

### 5. Mô hình YOLO tùy chỉnh (tùy chọn)

Đặt các file model vào thư mục `models/`:

```
models/
├── fruit_detection.pt      # Mô hình phát hiện trái cây
└── fruit_classification.pt # Mô hình phân loại độ chín/hỏng
```

Nếu không có, hệ thống dùng `yolov8n.pt` làm fallback.

### 6. Cấu hình cổng (port)

Mặc định server chạy port **5001**. Thay đổi trong `app.py` (dòng cuối):

```python
app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5001)
```

---

## 📱 Sử dụng

### Trang đăng nhập

- Truy cập `http://localhost:5001/login`
- Đăng nhập với tài khoản admin/user
- Admin đầu tiên được tạo từ `BOOTSTRAP_ADMIN_USERNAME` và `BOOTSTRAP_ADMIN_PASSWORD` khi DB trống

### Dashboard chính

- **System Status Bar**: Trạng thái API, Firebase, DB, Camera
- **Cards cảm biến**: Nhiệt độ, độ ẩm, thanh tiến độ, slider điều chỉnh nhiệt độ
- **OLED mô phỏng**: Hiển thị thông tin giống màn hình thật
- **Thống kê tồn kho**: Tổng vật phẩm, trái cây, thực phẩm, khác
- **Camera & AI**: Chọn nguồn (Webcam/ESP32), xem stream, upload ảnh phân tích
- **Kết quả nhận diện**: Bảng có lọc (Tất cả/Trái cây/Thực phẩm/Khác), trạng thái chín/hỏng, hạn sử dụng
- **Chat**: Nút chat nổi, gửi câu hỏi về cảm biến, tồn kho

### Chọn nguồn camera

1. **Webcam**: Nhấn nút "Webcam" → stream từ camera máy tính
2. **ESP32-CAM**: Nhấn nút "ESP32-CAM" → stream từ ESP32 (đảm bảo IP đúng và cùng mạng)

### Phân tích ảnh

1. Kéo thả ảnh vào vùng upload hoặc chọn file
2. Nhấn "Phân tích bằng AI"
3. Xem kết quả: tên đối tượng, loại, độ tin cậy, trạng thái chín/hỏng, hạn sử dụng

---

## 📡 API Endpoints

### Xác thực (Auth)

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `GET` | `/login` | Trang đăng nhập |
| `POST` | `/api/auth/login` | Đăng nhập |
| `POST` | `/api/auth/logout` | Đăng xuất |
| `GET` | `/api/auth/me` | Thông tin user hiện tại |
| `POST` | `/api/auth/register` | Đăng ký tài khoản |
| `GET` | `/api/auth/users` | Danh sách user (admin) |
| `POST` | `/api/auth/users/<id>/active` | Kích hoạt/vô hiệu hóa user |

### Trang & Chế độ

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `GET` | `/` | Dashboard (yêu cầu đăng nhập) |
| `GET` | `/api/mode` | Lấy chế độ điều khiển (software/hardware) |
| `POST` | `/api/mode` | Đặt chế độ điều khiển |

### Cảm biến & Điều khiển

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `GET` | `/api/sensors` | Dữ liệu cảm biến hiện tại |
| `POST` | `/api/temperature` | Đặt nhiệt độ mục tiêu |
| `GET` | `/api/sensors/stream` | SSE stream cập nhật real-time |
| `GET` | `/api/oled` | Dữ liệu cho màn hình OLED |

### Camera

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `GET` | `/api/camera/stream` | Stream video (không detection) |
| `GET` | `/api/camera/stream/detect` | Stream với YOLO detection |
| `POST` | `/api/camera/start` | Bật camera |
| `POST` | `/api/camera/stop` | Tắt camera |
| `GET` | `/api/camera/source` | Lấy nguồn camera hiện tại |
| `POST` | `/api/camera/source` | Đặt nguồn (webcam/esp32) |
| `GET` | `/api/camera/status` | Trạng thái camera |

### AI & Nhận diện

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `POST` | `/api/detect` | Upload ảnh, chạy YOLO + phân loại |

### Tồn kho & Thống kê

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `GET` | `/api/inventory` | Tồn kho hiện tại |
| `POST` | `/api/inventory/reset` | Reset tồn kho |
| `GET` | `/api/detections/latest` | Kết quả nhận diện gần nhất |
| `GET` | `/api/stats` | Thống kê tổng hợp |

### Lịch sử

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `GET` | `/api/history/sensors` | Lịch sử cảm biến (DB) |
| `GET` | `/api/history/detections` | Lịch sử nhận diện (DB) |
| `GET` | `/api/firebase/history` | Lịch sử cảm biến từ Firebase |

### Firebase điều khiển

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `POST` | `/api/firebase/control/light` | Bật/tắt LED |
| `POST` | `/api/firebase/control/peltier` | Điều khiển Peltier PWM |
| `GET` | `/api/firebase/control/status` | Trạng thái điều khiển |

### Chatbot

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `POST` | `/api/chat` | Gửi tin nhắn, nhận phản hồi rule-based |

### Ví dụ gọi API

```bash
# Lấy dữ liệu cảm biến
curl http://localhost:5001/api/sensors

# Đặt nhiệt độ
curl -X POST http://localhost:5001/api/temperature \
  -H "Content-Type: application/json" \
  -d '{"temperature": 5}'

# Chọn nguồn camera
curl -X POST http://localhost:5001/api/camera/source \
  -H "Content-Type: application/json" \
  -d '{"source": "webcam"}'

# Phân tích ảnh
curl -X POST http://localhost:5001/api/detect \
  -F "image=@test_image.jpg"
```

---

## 🗄️ Cơ sở dữ liệu

### Schema MySQL

| Bảng | Mô tả |
|------|-------|
| `sensors` | Lịch sử nhiệt độ, độ ẩm, nhiệt độ mục tiêu, trạng thái |
| `inventory` | Tổng vật phẩm, số trái cây/thực phẩm/khác theo thời điểm |
| `detections` | Chi tiết từng đối tượng: class_name, confidence, category, bbox, image_path |
| `detection_sessions` | Phiên nhận diện: tổng số, số trái cây/thực phẩm/khác, ảnh |
| `temperature_settings` | Lịch sử thay đổi nhiệt độ mục tiêu, người thay đổi |
| `users` | Username, email, password_hash, role (admin/user), is_active |

File schema đầy đủ: `data/schema.sql`

---

## 🏗️ Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Frontend (Web Dashboard)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │   Login     │  │  Dashboard  │  │   Camera    │  │   Chatbot   │    │
│  │   Auth      │  │   Sensors   │  │   Stream    │  │   Panel     │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ HTTP / SSE
┌──────────────────────────────▼──────────────────────────────────────────┐
│                     Flask Backend (app.py)                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │ YOLO AI     │  │   Camera    │  │   Sensor    │  │   Auth &    │    │
│  │ Detection   │  │   Handler   │  │   Manager   │  │   Session   │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
└─────┬──────────────┬──────────────┬──────────────┬──────────────┬──────┘
      │              │              │              │              │
┌─────▼──────┐ ┌─────▼──────┐ ┌────▼────┐ ┌───────▼──────┐ ┌─────▼──────┐
│  Webcam/   │ │ ESP32-CAM  │ │Firebase/│ │    MySQL     │ │  Telegram  │
│  USB Cam   │ │   (WiFi)   │ │  Wokwi  │ │   Database   │ │    Bot     │
└────────────┘ └────────────┘ └─────────┘ └──────────────┘ └────────────┘
```

### Luồng dữ liệu

1. **Cảm biến**: Firebase/Wokwi → Flask API → SSE Stream → Frontend
2. **Camera**: Webcam/ESP32-CAM → OpenCV → YOLO → Flask Stream → Frontend
3. **Nhận diện**: Upload ảnh → YOLO + Phân loại → Database → Telegram (nếu có trái cây hỏng)
4. **Điều khiển**: User đổi nhiệt độ → POST `/api/temperature` → Firebase `/Control` → ESP32 đọc và điều khiển Peltier

### Cấu trúc thư mục

```
smart-fridge-iot/
├── app.py                 # Ứng dụng Flask chính
├── core/
│   ├── database.py        # MySQL, auth, schema
│   ├── firebase_integration.py
│   ├── telegram_notify.py
│   ├── hardware_integration.py
│   └── raspberry_pi_config.py
├── data/
│   ├── control_mode.json  # software | hardware
│   └── schema.sql
├── docs/                  # Tài liệu chi tiết
├── models/                # YOLO models
├── static/img/            # Logo, hình nền
├── templates/
│   ├── login.html
│   └── smart_fridge.html
├── tests/
├── uploads/               # Ảnh nhận diện
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── install.sh
└── smart-fridge.service   # Systemd
```

---

## 🔧 Phần cứng IoT

### Firebase / Wokwi (mô phỏng)

- ESP32 đẩy dữ liệu cảm biến lên Firebase (`/Current`, `/History`)
- Flask đọc Firebase và gửi lệnh điều khiển qua `/Control/Light`, `/Control/Peltier`, `/Control/TargetTemp`

### ESP32-CAM

- Camera WiFi tại `http://192.168.137.16` (mặc định)
- URL chụp ảnh: `{IP}/capture`
- Cấu hình IP trong `app.py`

### Raspberry Pi (phần cứng thật)

Bật bằng `USE_HARDWARE=true` trong `.env`.

| Thành phần | GPIO / Giao tiếp | Ghi chú |
|------------|------------------|---------|
| DHT22 | GPIO4 | Nhiệt độ, độ ẩm |
| OLED SSD1306 | I2C (SDA/SCL) | Màn hình trạng thái |
| Relay | GPIO17 | Điều khiển nhiệt độ |
| LED trạng thái | GPIO22, 27, 23 | |
| Pi Camera | (tùy chọn) | Thay webcam |

Chi tiết: `docs/HARDWARE_SETUP.md`, `core/raspberry_pi_config.py`

---

## 🚀 Triển khai Production

### Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

### Systemd (Linux)

```bash
# Chỉnh đường dẫn trong smart-fridge.service nếu cần
sudo cp smart-fridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable smart-fridge
sudo systemctl start smart-fridge
sudo systemctl status smart-fridge
```

### Docker

```bash
docker build -t smart-fridge .
docker run -p 5001:5001 smart-fridge
```

---

## 🔍 Xử lý sự cố

### Lỗi: "Unexpected token '<', '<!doctype'... is not valid JSON"

**Nguyên nhân**: Server trả về HTML (404/500) thay vì JSON.

**Giải pháp**:
1. Kiểm tra server chạy: `http://localhost:5001`
2. Xem log console server
3. Kiểm tra đúng endpoint API

### Lỗi: "Camera not available"

**Giải pháp**:
- **Windows**: Kiểm tra Device Manager, đóng app dùng camera, cấp quyền cho Python
- **Linux**: `lsusb`, `v4l2-ctl --list-devices`
- **macOS**: System Settings → Privacy → Camera → Cho phép Terminal/Python

### Lỗi: "ESP32-CAM connection failed"

1. ESP32-CAM và máy tính cùng mạng WiFi
2. Kiểm tra IP trong Serial Monitor
3. Test: `curl http://192.168.137.16/capture`
4. Cập nhật `ESP32_CAM_IP` trong `app.py`

### Lỗi: "YOLO model failed to load"

```bash
pip install ultralytics
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

### Lỗi: "Port 5001 already in use"

```bash
# Linux/macOS
lsof -i :5001

# Windows
netstat -ano | findstr :5001
```

Tắt process hoặc đổi port trong `app.py`.

### Lỗi: "Database connection failed"

1. Kiểm tra MySQL đang chạy
2. Kiểm tra `DB_*` trong `.env` hoặc `database.py`
3. Tạo database: `CREATE DATABASE smart_fridge;`

### Lỗi: "Firebase connection failed"

1. Kiểm tra cấu hình trong `firebase_integration.py`
2. Kiểm tra Firebase Console rules cho phép đọc/ghi

---

## 📚 Tài liệu

### Tài liệu trong dự án

| File | Nội dung |
|------|----------|
| `docs/DATABASE_SETUP.md` | Hướng dẫn cài đặt MySQL |
| `docs/FIREBASE_WOKWI_SETUP.md` | Cấu hình Firebase với Wokwi |
| `docs/HARDWARE_SETUP.md` | Kết nối phần cứng |
| `docs/PROJECT_OVERVIEW.md` | Tổng quan dự án |
| `docs/WOKWI_REALTIME_FIX.md` | Sửa lỗi real-time Wokwi |

### Thư viện & tài liệu tham khảo

- [YOLOv8 Documentation](https://docs.ultralytics.com/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [OpenCV Python](https://docs.opencv.org/)
- [Firebase Realtime Database](https://firebase.google.com/docs/database)
- [ESP32-CAM Examples](https://github.com/espressif/arduino-esp32/tree/master/libraries/ESP32/examples/Camera)

---

## 📦 Dependencies chính

| Package | Phiên bản | Mục đích |
|---------|-----------|----------|
| Flask | 3.0.0 | Web framework |
| flask-cors | 4.0.0 | CORS |
| ultralytics | 8.1.0 | YOLOv8 |
| opencv-python | 4.9.0.80 | Xử lý ảnh/video |
| mysql-connector-python | 8.2.0 | MySQL |
| requests | 2.31.0 | HTTP |
| Pillow | 10.2.0 | Xử lý ảnh |
| google-generativeai | 0.8.5 | (Tùy chọn) Gemini |

**Raspberry Pi (uncomment trong requirements.txt):**
- Adafruit-DHT, RPi.GPIO, luma.oled, paho-mqtt

---

## 📄 License

MIT License – xem file `LICENSE` để biết chi tiết.

---

## 👤 Liên hệ

| Thông tin | Giá trị |
|-----------|---------|
| **Tên** | Nguyên Khang |
| **Email** | nguyenkhang031006@gmail.com |

---

<div align="center">

**Hệ thống Tủ lạnh Thông minh IoT với AI**

Đồ án – Trường Đại Học Công Nghệ Kỹ Thuật TP.HCM (HCM-UTE)

</div>
