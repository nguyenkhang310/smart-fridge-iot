# 🔧 Hướng Dẫn Tích Hợp Phần Cứng Thật

Tài liệu này hướng dẫn cách kết nối và sử dụng phần cứng thật với hệ thống Smart Fridge IoT.

## 📋 Mục Lục

1. [Yêu Cầu Phần Cứng](#yêu-cầu-phần-cứng)
2. [Sơ Đồ Kết Nối](#sơ-đồ-kết-nối)
3. [Cài Đặt Thư Viện](#cài-đặt-thư-viện)
4. [Cấu Hình](#cấu-hình)
5. [Kiểm Tra Phần Cứng](#kiểm-tra-phần-cứng)
6. [Chạy Hệ Thống](#chạy-hệ-thống)

---

## 🛠️ Yêu Cầu Phần Cứng

### Bắt Buộc:
- **Raspberry Pi 4** (hoặc Pi 3B+) với thẻ SD 16GB+
- **DHT22** - Cảm biến nhiệt độ và độ ẩm
- **Relay Module** - Điều khiển compressor tủ lạnh
- **Resistors 220Ω** (cho LED)
- **Breadboard và dây nối**

### Tùy Chọn:
- **SSD1306 OLED Display** (128x64) - Hiển thị thông tin
- **RGB LED** - Đèn báo trạng thái
- **Raspberry Pi Camera Module** - Chụp ảnh tự động

---

## 🔌 Sơ Đồ Kết Nối

### 1. DHT22 Sensor (Nhiệt Độ & Độ Ẩm)

```
DHT22          Raspberry Pi
─────────────────────────────
VCC (Pin 1)  → 3.3V (Pin 1)
GND (Pin 2)  → GND (Pin 6)
DATA (Pin 3) → GPIO4 (Pin 7)
```

**Lưu ý:** Cần thêm điện trở pull-up 10kΩ giữa DATA và VCC (nếu module DHT22 không có sẵn).

### 2. Relay Module (Điều Khiển Compressor)

```
Relay Module   Raspberry Pi
─────────────────────────────
VCC           → 5V (Pin 2)
GND           → GND (Pin 6)
IN            → GPIO17 (Pin 11)
```

**Cảnh báo:** Relay điều khiển điện áp cao! Đảm bảo cách ly an toàn và tuân thủ quy định điện.

### 3. SSD1306 OLED Display (I2C)

```
OLED Display  Raspberry Pi
─────────────────────────────
VCC           → 3.3V (Pin 1)
GND           → GND (Pin 6)
SDA           → GPIO2/SDA (Pin 3)
SCL           → GPIO3/SCL (Pin 5)
```

**Cần bật I2C:**
```bash
sudo raspi-config
# Interface Options → I2C → Enable
```

### 4. RGB LED (Status Indicator)

```
RGB LED       Raspberry Pi
─────────────────────────────
Red (Anode)   → GPIO22 (Pin 15) + 220Ω resistor
Green (Anode) → GPIO27 (Pin 13) + 220Ω resistor
Blue (Anode)  → GPIO23 (Pin 16) + 220Ω resistor
Common Cathode → GND (Pin 6)
```

### 5. Raspberry Pi Camera Module

Kết nối vào cổng Camera trên Raspberry Pi (CSI connector).

**Bật Camera:**
```bash
sudo raspi-config
# Interface Options → Camera → Enable
```

---

## 📦 Cài Đặt Thư Viện

### Trên Raspberry Pi:

```bash
# Cập nhật hệ thống
sudo apt update && sudo apt upgrade -y

# Cài đặt Python packages
pip install RPi.GPIO
pip install Adafruit_DHT
pip install luma.oled
pip install picamera2

# Hoặc cài tất cả từ requirements.txt
pip install -r requirements.txt
```

### Kiểm tra I2C:
```bash
# Kiểm tra I2C devices
sudo i2cdetect -y 1

# Nếu thấy 0x3C → OLED đã kết nối đúng
```

---

## ⚙️ Cấu Hình

### 1. Bật Hardware Mode

Có 2 cách:

**Cách 1: Environment Variable**
```bash
export USE_HARDWARE=true
python app.py
```

**Cách 2: Sửa trong code**
Mở file `hardware_integration.py`:
```python
USE_HARDWARE = True  # Thay đổi từ False sang True
```

### 2. Cấu Hình GPIO Pins

Nếu muốn thay đổi GPIO pins, sửa trong `app.py`:

```python
# Trong hàm init_hardware() hoặc khi gọi:
dht_sensor, dht_pin = setup_dht22_sensor(gpio_pin=4)  # Thay 4 bằng pin khác
relay_pin = setup_relay(gpio_pin=17)  # Thay 17 bằng pin khác
```

---

## 🧪 Kiểm Tra Phần Cứng

### Test từng component:

```bash
# Test tất cả phần cứng
python raspberry_pi_config.py test

# Hoặc test từng phần:
python -c "from raspberry_pi_config import *; test_hardware()"
```

### Test riêng lẻ:

**Test DHT22:**
```python
from raspberry_pi_config import setup_dht22_sensor, read_dht22
sensor, pin = setup_dht22_sensor()
data = read_dht22(sensor, pin)
print(data)
```

**Test OLED:**
```python
from raspberry_pi_config import setup_oled_display, update_oled
oled = setup_oled_display()
update_oled(oled, 4.5, 65, 12, 8, "TEST")
```

**Test Relay:**
```python
from raspberry_pi_config import setup_relay
import RPi.GPIO as GPIO
import time

relay = setup_relay()
GPIO.output(relay, GPIO.HIGH)  # Bật
time.sleep(2)
GPIO.output(relay, GPIO.LOW)   # Tắt
GPIO.cleanup()
```

---

## 🚀 Chạy Hệ Thống

### 1. Chế Độ Simulation (Không cần phần cứng)

```bash
python app.py
```

### 2. Chế Độ Hardware (Với phần cứng thật)

```bash
# Bật hardware mode
export USE_HARDWARE=true
python app.py
```

### 3. Chạy như Service (Tự động khởi động)

```bash
# Copy service file
sudo cp smart-fridge.service /etc/systemd/system/

# Enable và start
sudo systemctl enable smart-fridge.service
sudo systemctl start smart-fridge.service

# Kiểm tra status
sudo systemctl status smart-fridge.service
```

---

## 📝 Lưu Ý Quan Trọng

### ⚠️ An Toàn Điện:
- **KHÔNG** kết nối trực tiếp relay với tủ lạnh thật mà không có cách ly
- Sử dụng relay module có optocoupler để cách ly
- Kiểm tra điện áp và dòng điện trước khi kết nối
- Tốt nhất nên test với đèn LED trước

### 🔧 Troubleshooting:

**DHT22 không đọc được:**
- Kiểm tra kết nối dây
- Thử thêm điện trở pull-up 10kΩ
- Kiểm tra nguồn 3.3V

**OLED không hiển thị:**
- Kiểm tra I2C đã bật: `sudo raspi-config`
- Kiểm tra địa chỉ I2C: `sudo i2cdetect -y 1`
- Kiểm tra kết nối SDA/SCL

**Relay không hoạt động:**
- Kiểm tra nguồn 5V
- Kiểm tra GPIO pin
- Test với LED trước khi dùng với thiết bị thật

**Camera không hoạt động:**
- Kiểm tra camera đã enable trong raspi-config
- Kiểm tra kết nối CSI cable
- Thử: `libcamera-hello` để test camera

---

## 📚 Tài Liệu Tham Khảo

- [Raspberry Pi GPIO Pinout](https://pinout.xyz/)
- [DHT22 Datasheet](https://www.sparkfun.com/datasheets/Sensors/Temperature/DHT22.pdf)
- [SSD1306 OLED Guide](https://learn.adafruit.com/monochrome-oled-breakouts)
- [RPi.GPIO Documentation](https://sourceforge.net/projects/raspberry-gpio-python/)

---

## 🆘 Hỗ Trợ

Nếu gặp vấn đề:
1. Kiểm tra log: `tail -f /var/log/smart-fridge.log`
2. Test hardware: `python raspberry_pi_config.py test`
3. Kiểm tra GPIO: `gpio readall` (nếu đã cài wiringpi)

---

**Chúc bạn thành công! 🎉**

