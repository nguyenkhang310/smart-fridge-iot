# 🧊 Tủ Lạnh Thông Minh IoT với AI

Hệ thống tủ lạnh thông minh tích hợp IoT và AI sử dụng YOLO để nhận diện đối tượng, giám sát nhiệt độ/độ ẩm, và hiển thị thông tin trên màn hình OLED.

## ✨ Tính Năng

### 📊 Giám Sát Cảm Biến
- **Nhiệt độ**: Theo dõi nhiệt độ thời gian thực với cảnh báo
- **Độ ẩm**: Giám sát độ ẩm bên trong tủ lạnh
- **Cập nhật tự động**: Dữ liệu cảm biến được cập nhật mỗi 3 giây

### 🎛️ Điều Khiển
- **Điều chỉnh nhiệt độ**: Slider để cài đặt nhiệt độ mong muốn (-2°C đến 10°C)
- **Giao diện trực quan**: Thanh tiến trình hiển thị trạng thái
- **Cảnh báo thông minh**: Thông báo khi nhiệt độ vượt ngưỡng

### 📺 Màn Hình OLED
- Hiển thị thông tin thời gian thực
- Nhiệt độ và độ ẩm hiện tại
- Số lượng vật phẩm và trái cây
- Trạng thái hệ thống

### 🤖 AI Nhận Diện Đối Tượng (YOLO)
- **Nhận diện tự động**: Phát hiện trái cây, thực phẩm và vật phẩm khác
- **Phân loại thông minh**: Tự động phân loại các đối tượng
- **Đếm số lượng**: Theo dõi số lượng từng loại vật phẩm
- **Vẽ bounding box**: Hiển thị khung nhận diện trên ảnh
- **Độ tin cậy**: Hiển thị phần trăm độ chính xác

### 📈 Thống Kê
- Tổng số vật phẩm
- Số lượng trái cây
- Số lượng thực phẩm
- Dashboard trực quan

## 🚀 Cài Đặt

### Yêu Cầu Hệ Thống
- Python 3.8+
- Node.js (optional, cho development)
- Webcam hoặc camera (cho chức năng AI)

### Bước 1: Clone hoặc tải project

```bash
git clone <repository-url>
cd smart-fridge-iot
```

### Bước 2: Cài đặt dependencies

```bash
pip install -r requirements.txt
```

Lệnh này sẽ cài đặt:
- Flask (Web framework)
- Flask-CORS (Xử lý CORS)
- Ultralytics (YOLO model)
- OpenCV (Xử lý ảnh)
- NumPy (Tính toán)
- Pillow (Xử lý ảnh)

### Bước 3: Tải YOLO model

YOLO model sẽ tự động tải xuống khi chạy lần đầu. Bạn có thể chọn model:

- `yolov8n.pt` - Nhỏ, nhanh (mặc định)
- `yolov8s.pt` - Trung bình
- `yolov8m.pt` - Lớn, chính xác hơn
- `yolov8l.pt` - Rất lớn, chính xác nhất

Thay đổi trong `app.py`:
```python
MODEL_PATH = 'yolov8m.pt'  # Chọn model phù hợp
```

### Bước 4: Chạy server

```bash
python app.py
```

Server sẽ chạy tại: `http://localhost:5000`

### Bước 5: Mở trình duyệt

Truy cập: `http://localhost:5000`

## 🔧 Tích Hợp Phần Cứng IoT

### Cảm Biến Nhiệt Độ/Độ Ẩm (DHT22)

```python
import Adafruit_DHT

sensor = Adafruit_DHT.DHT22
pin = 4  # GPIO pin

def read_temperature_sensor():
    humidity, temperature = Adafruit_DHT.read_retry(sensor, pin)
    return temperature, humidity
```

### Màn Hình OLED (SSD1306)

```python
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from PIL import Image, ImageDraw, ImageFont

# Setup
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial)

def update_oled_display(temp, humidity, items):
    image = Image.new('1', (128, 64))
    draw = ImageDraw.Draw(image)
    
    draw.text((0, 0), f"Temp: {temp}°C", fill=255)
    draw.text((0, 10), f"Humidity: {humidity}%", fill=255)
    draw.text((0, 20), f"Items: {items}", fill=255)
    
    device.display(image)
```

### Sơ Đồ Kết Nối (Raspberry Pi)

```
DHT22 Sensor:
- VCC → 3.3V
- GND → GND
- DATA → GPIO4

OLED Display (I2C):
- VCC → 3.3V
- GND → GND
- SDA → GPIO2 (SDA)
- SCL → GPIO3 (SCL)
```

## 📡 API Endpoints

### GET /api/sensors
Lấy dữ liệu cảm biến hiện tại

**Response:**
```json
{
  "temperature": 4.5,
  "humidity": 65,
  "target_temperature": 4,
  "status": "normal",
  "last_update": "2025-01-31T10:30:00"
}
```

### POST /api/temperature
Cài đặt nhiệt độ mục tiêu

**Request:**
```json
{
  "temperature": 5
}
```

**Response:**
```json
{
  "success": true,
  "target_temperature": 5,
  "message": "Temperature set to 5°C"
}
```

### POST /api/detect
Nhận diện đối tượng trong ảnh

**Request:** Multipart form-data với file ảnh

**Response:**
```json
{
  "success": true,
  "detections": [
    {
      "class": "apple",
      "confidence": 0.92,
      "category": "fruit",
      "bbox": {
        "x": 100,
        "y": 150,
        "width": 80,
        "height": 90
      }
    }
  ],
  "total_items": 5,
  "fruit_count": 3,
  "food_count": 2,
  "annotated_image": "base64_encoded_image"
}
```

### GET /api/inventory
Lấy thông tin kho

**Response:**
```json
{
  "total_items": 12,
  "fruit_count": 8,
  "food_count": 3,
  "other_count": 1,
  "fruits": ["apple", "banana", "orange"],
  "foods": ["milk", "cheese"],
  "last_detection": "2025-01-31T10:30:00"
}
```

### GET /api/oled
Lấy dữ liệu cho màn hình OLED

**Response:**
```json
{
  "temperature": 4.5,
  "humidity": 65,
  "status": "normal",
  "total_items": 12,
  "fruit_count": 8,
  "time": "10:30:15"
}
```

## 🎨 Giao Diện

### Dashboard Chính
- **Card nhiệt độ**: Hiển thị nhiệt độ hiện tại với thanh tiến trình
- **Card độ ẩm**: Hiển thị độ ẩm với thanh tiến trình
- **Card điều khiển**: Slider điều chỉnh nhiệt độ mục tiêu
- **Card OLED**: Mô phỏng màn hình OLED thực tế
- **Thống kê kho**: Dashboard với số liệu về vật phẩm
- **Camera & AI**: Tải ảnh lên và phân tích bằng YOLO

### Tính Năng Giao Diện
- **Responsive design**: Tương thích mọi thiết bị
- **Drag & drop**: Kéo thả ảnh để upload
- **Real-time updates**: Cập nhật dữ liệu tự động
- **Visual feedback**: Hiệu ứng và animation
- **Color coding**: Màu sắc phân biệt các loại vật phẩm

## 🧪 Test Chức Năng

### Test YOLO Detection

```bash
# Tải ảnh test
wget https://example.com/fridge-contents.jpg

# Hoặc dùng Python
import requests

url = 'http://localhost:5000/api/detect'
files = {'image': open('test_image.jpg', 'rb')}
response = requests.post(url, files=files)
print(response.json())
```

### Test API với curl

```bash
# Lấy dữ liệu cảm biến
curl http://localhost:5000/api/sensors

# Cài đặt nhiệt độ
curl -X POST http://localhost:5000/api/temperature \
  -H "Content-Type: application/json" \
  -d '{"temperature": 5}'

# Lấy inventory
curl http://localhost:5000/api/inventory
```

## 📝 Tùy Chỉnh

### Thay Đổi Model YOLO

Trong `app.py`:
```python
MODEL_PATH = 'yolov8m.pt'  # Thay đổi model
```

### Thêm Loại Đối Tượng Mới

```python
FRUIT_CLASSES = ['apple', 'banana', 'orange', 'mango', 'pineapple']
FOOD_CLASSES = ['sandwich', 'pizza', 'milk', 'yogurt']
```

### Điều Chỉnh Confidence Threshold

```python
results = model(img, conf=0.7)  # Tăng từ 0.5 lên 0.7
```

### Tùy Chỉnh Màu Sắc Giao Diện

Trong `smart_fridge.html`, thay đổi CSS:
```css
background: linear-gradient(135deg, #your-color1 0%, #your-color2 100%);
```

## 🔐 Bảo Mật

- Thêm authentication cho API
- Sử dụng HTTPS trong production
- Giới hạn file upload size
- Validate input data

```python
from flask_httpauth import HTTPBasicAuth

auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    # Implement your auth logic
    pass

@app.route('/api/sensors')
@auth.login_required
def get_sensors():
    # Protected endpoint
    pass
```

## 🐛 Debug

### YOLO Model không load được

```bash
# Tải model thủ công
pip install ultralytics
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

### Lỗi Camera/OpenCV

```bash
# Cài đặt dependencies hệ thống (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install libgl1-mesa-glx libglib2.0-0
```

### Port 5000 đã được sử dụng

Thay đổi port trong `app.py`:
```python
app.run(debug=True, host='0.0.0.0', port=5001)
```

## 📊 Performance

- **YOLO Detection**: ~100-300ms (depends on model & hardware)
- **API Response**: <50ms
- **Frontend Updates**: Real-time (3s interval)

## 🚀 Production Deployment

### Sử dụng Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Sử dụng Docker

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["python", "app.py"]
```

```bash
docker build -t smart-fridge .
docker run -p 5000:5000 smart-fridge
```

## 📚 Tài Liệu Tham Khảo

- [YOLOv8 Documentation](https://docs.ultralytics.com/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [OpenCV Python](https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html)
- [Raspberry Pi GPIO](https://www.raspberrypi.com/documentation/computers/os.html#gpio)

## 🤝 Đóng Góp

Mọi đóng góp đều được hoan nghênh! Vui lòng:

1. Fork repository
2. Tạo branch mới (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Tạo Pull Request

## 📄 License

MIT License - xem file LICENSE để biết thêm chi tiết

## 👨‍💻 Tác Giả

Dự án Tủ Lạnh Thông Minh IoT

## 🙏 Cảm Ơn

- Ultralytics cho YOLOv8
- Flask team
- OpenCV community
- Raspberry Pi Foundation

---

**Chúc bạn thành công với dự án! 🎉**
