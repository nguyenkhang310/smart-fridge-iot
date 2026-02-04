# Smart Fridge IoT System with AI

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)
![YOLO](https://img.shields.io/badge/YOLO-v8-orange.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**Intelligent IoT refrigerator system with integrated AI using YOLO for object detection, temperature/humidity monitoring, and control via Firebase/Wokwi**

[Documentation](#documentation) • [Quick Start](#quick-start) • [Configuration](#configuration) • [API](#api-endpoints) • [Troubleshooting](#troubleshooting)

</div>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Camera Usage](#camera-usage)
- [API Endpoints](#api-endpoints)
- [System Architecture](#system-architecture)
- [Hardware Integration](#hardware-integration)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)

---

## Overview

The **Smart Fridge IoT System** is a comprehensive solution for intelligent refrigerator management, featuring:

- **AI Detection**: Uses YOLO to detect and classify fruits and food items
- **Real-time Monitoring**: Tracks temperature and humidity via Firebase/Wokwi or physical sensors
- **Multi-Camera Support**: Choose between computer webcam or ESP32-CAM
- **Telegram Notifications**: Automatic alerts when spoiled fruits are detected
- **Database Storage**: MySQL for storing history and statistics
- **Web Interface**: Visual dashboard with responsive design and real-time updates

---

## Features

### Sensor Monitoring

| Feature | Description |
|---------|-------------|
| **Temperature** | Real-time temperature monitoring with threshold alerts |
| **Humidity** | Monitor humidity inside the refrigerator |
| **Auto Updates** | Sensor data updated every 0.2-3 seconds (SSE stream) |
| **Multiple Data Sources** | Supports Firebase/Wokwi, Raspberry Pi, or simulation mode |

### Control

- **Temperature Adjustment**: Slider to set target temperature (-2°C to 10°C)
- **Peltier Control**: Automatic PWM cooling adjustment via Firebase
- **LED Control**: Turn on/off LED lights in the refrigerator
- **Visual Interface**: Progress bars showing system status
- **Smart Alerts**: Notifications when temperature exceeds threshold

### Camera & AI Detection

#### Multi-Camera Support
- **Webcam**: Uses integrated or USB camera from computer
- **ESP32-CAM**: WiFi connection with ESP32-CAM module
- **Easy Switching**: Select camera via 2 buttons on interface

#### Advanced AI Detection
- **Detection Model**: Detects fruits (Apple, Banana, Mango, Orange, Pear)
- **Classification Model**: Classifies fruit ripeness/spoilage
- **Color Analysis**: Uses HSV to evaluate ripeness
- **Shelf Life Calculation**: Automatically calculates remaining days based on type and ripeness
- **Bounding Box Drawing**: Displays detection boxes with color coding
- **Confidence Score**: Shows accuracy percentage

#### Automatic Alerts
- **Telegram Notifications**: Sends alerts when spoiled fruits are detected
- **Cooldown System**: Prevents notification spam (60-120 seconds)
- **Image Attachments**: Includes detection images

### OLED Display (Simulated)

Displays real-time information:
- Current temperature and humidity
- System status (NORMAL/WARNING)
- Item and fruit counts
- Current time

### Statistics & Inventory

- **Total Items**: Automatic counting from detections
- **Categorization**: Fruits, Food, Other items
- **History**: Stores detection history in database
- **Visual Dashboard**: Displays statistics with color coding

### Database Integration

- **MySQL**: Stores sensor data, detection sessions, inventory
- **Firebase Realtime Database**: Syncs with Wokwi ESP32 simulation
- **History**: View sensor and detection history via API

---

## Quick Start

### Minimum Requirements

- **Python**: 3.8 or higher
- **RAM**: Minimum 2GB (recommended 4GB+)
- **Camera**: Webcam or ESP32-CAM (optional)
- **Internet**: To download YOLO models (first time)

### Quick Installation (3 Steps)

```bash
# 1. Clone repository
git clone <repository-url>
cd smart-fridge-iot

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run server
python app.py
```

Then open browser: **http://localhost:5001**

---

## Installation

### Step 1: Environment Setup

#### Windows
```bash
# Check Python version
python --version  # Must be >= 3.8

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate
```

#### Linux/macOS
```bash
# Check Python version
python3 --version  # Must be >= 3.8

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
```

### Step 2: Install Dependencies

```bash
# Install all packages
pip install -r requirements.txt
```

**Main packages:**
- `Flask==3.0.0` - Web framework
- `flask-cors==4.0.0` - CORS handling
- `ultralytics==8.1.0` - YOLO models
- `opencv-python==4.9.0.80` - Image/video processing
- `numpy==1.26.3` - Numerical computing
- `Pillow==10.2.0` - Image processing
- `mysql-connector-python==8.2.0` - MySQL connection
- `requests==2.31.0` - HTTP requests

**Optional (for Raspberry Pi):**
```bash
# Uncomment in requirements.txt if using Raspberry Pi
# Adafruit-DHT==1.4.0  # DHT22 sensor
# RPi.GPIO==0.7.1  # GPIO control
# luma.oled==3.12.0  # OLED display
```

### Step 3: Download YOLO Models

#### Default Model (Automatic)
YOLO model will automatically download on first run:
- `yolov8n.pt` - Small, fast model (default)

#### Advanced Models (Optional)
To use specialized fruit detection models:

1. Place model files in `models/` directory:
   ```
   models/
   ├── fruit_detection.pt      # Fruit detection model
   └── fruit_classification.pt  # Ripeness/spoilage classification model
   ```

2. Models will automatically load when server starts

**Note**: If advanced models are not available, system will use `yolov8n.pt` as fallback.

### Step 4: Configuration (Optional)

See [Configuration](#configuration) section to configure:
- ESP32-CAM IP address
- Database connection
- Firebase credentials
- Telegram bot token

### Step 5: Run Server

```bash
python app.py
```

**Sample output:**
```
==================================================
Smart Fridge IoT Server Starting...
==================================================
Server will run on: http://localhost:5001
YOLO Model: yolov8n.pt
Upload folder: uploads
Camera stream: /api/camera/stream
Camera with detection: /api/camera/stream/detect
==================================================
Fruit detection model loaded: models/fruit_detection.pt
Fruit classification model loaded: models/fruit_classification.pt
Firebase Realtime Database connected (Wokwi)
MySQL database initialized
 * Running on http://0.0.0.0:5001
```

### Step 6: Access Interface

Open browser and navigate to: **http://localhost:5001**

---

## Configuration

### 1. ESP32-CAM Configuration

In `app.py`, find the line:

```python
ESP32_CAM_IP = "http://192.168.137.14"  # Change to your ESP32-CAM IP
```

**How to find ESP32-CAM IP:**
1. Connect ESP32-CAM to WiFi
2. Check Serial Monitor for assigned IP
3. Or check router admin panel

**Test connection:**
```bash
# Test if ESP32-CAM is working
curl http://192.168.137.14/capture
```

### 2. Database Configuration (MySQL)

See `DATABASE_SETUP.md` for database setup instructions.

**Configuration in `database.py`:**
```python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'your_username',
    'password': 'your_password',
    'database': 'smart_fridge'
}
```

**Create database:**
```sql
CREATE DATABASE smart_fridge;
```

### 3. Firebase Configuration (Wokwi)

See `FIREBASE_WOKWI_SETUP.md` for Firebase setup.

**Configuration in `firebase_integration.py`:**
```python
# Add Firebase credentials
FIREBASE_CONFIG = {
    "apiKey": "your-api-key",
    "authDomain": "your-project.firebaseapp.com",
    "databaseURL": "https://your-project.firebaseio.com",
    # ...
}
```

### 4. Telegram Bot Configuration

**Create bot:**
1. Find `@BotFather` on Telegram
2. Send `/newbot` and follow instructions
3. Get Bot Token

**Configuration in `telegram_notify.py`:**
```python
TELEGRAM_BOT_TOKEN = "your-bot-token"
TELEGRAM_CHAT_ID = "your-chat-id"  # Your chat ID
```

**Get Chat ID:**
1. Send message to bot
2. Visit: `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Find `chat.id` in response

### 5. Port Configuration

Default server runs on port **5001**. To change:

In `app.py`, last line:
```python
app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5001)
```

Change `5001` to desired port.

---

## Camera Usage

### Selecting Camera Source

System supports 2 camera types:

#### Webcam
- Uses integrated or USB camera
- Auto-detects camera (index 0, 1)
- Supports Windows (DirectShow) and Linux/macOS

**Usage:**
1. Connect webcam to computer
2. Click **"Webcam"** button on interface
3. System will automatically start webcam

#### ESP32-CAM
- WiFi connection
- Default IP: `192.168.137.14` (can be changed)

**Usage:**
1. Ensure ESP32-CAM is connected to WiFi and running
2. Check IP address in `app.py`
3. Click **"ESP32-CAM"** button on interface

### Detection Mode

After selecting camera, stream will automatically start with **AI Detection**:
- Real-time fruit detection
- Bounding boxes with color coding:
  - **Green**: Good fruit
  - **Red**: Spoiled fruit
  - **Orange**: Other items
- Display name and confidence score

### Upload Image for Analysis

1. **Drag and drop** image into upload area
2. Or **click to select file**
3. Click **"Analyze with AI"**
4. View detection results and bounding boxes

---

## API Endpoints

### Sensor & Control

#### `GET /api/sensors`
Get current sensor data

**Response:**
```json
{
  "temperature": 4.5,
  "humidity": 65,
  "target_temperature": 4,
  "status": "normal",
  "last_update": "2025-02-04T10:30:00",
  "source": "firebase_wokwi"
}
```

#### `POST /api/temperature`
Set target temperature

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
  "pwm_sent": 120,
  "current_temp": 6.2,
  "message": "Temperature set to 5°C"
}
```

#### `GET /api/sensors/stream`
Server-Sent Events (SSE) stream for real-time updates

**Response:** Event stream with JSON data on each update

---

### Camera

#### `POST /api/camera/source`
Select camera source (webcam or esp32)

**Request:**
```json
{
  "source": "webcam"  // or "esp32"
}
```

**Response:**
```json
{
  "success": true,
  "source": "webcam",
  "message": "Camera source set to: webcam"
}
```

#### `GET /api/camera/source`
Get current camera source

**Response:**
```json
{
  "source": "webcam"
}
```

#### `POST /api/camera/start`
Start camera stream

**Response:**
```json
{
  "success": true,
  "message": "Webcam started successfully"
}
```

#### `POST /api/camera/stop`
Stop camera stream

**Response:**
```json
{
  "success": true,
  "message": "Camera stopped"
}
```

#### `GET /api/camera/status`
Check camera status

**Response:**
```json
{
  "available": true,
  "streaming": false,
  "camera_index": 0,
  "error": null,
  "message": "Camera ready"
}
```

#### `GET /api/camera/stream`
Video stream from ESP32-CAM (no detection)

**Response:** Multipart video stream

#### `GET /api/camera/stream/detect`
Video stream with AI detection (webcam or ESP32-CAM)

**Response:** Multipart video stream with bounding boxes

---

### AI Detection

#### `POST /api/detect`
Detect objects in image

**Request:** Multipart form-data with field `image`

**Response:**
```json
{
  "success": true,
  "detections": [
    {
      "class": "TAO: CHIN",
      "confidence": 0.92,
      "category": "fruit",
      "ripeness_status": "CHIN",
      "days_left": "5-7 ngay",
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
  "food_count": 1,
  "other_count": 1,
  "annotated_image": "base64_encoded_image",
  "timestamp": "2025-02-04T10:30:00",
  "advanced_mode": true
}
```

---

### Inventory & Stats

#### `GET /api/inventory`
Get current inventory information

**Response:**
```json
{
  "total_items": 12,
  "fruit_count": 8,
  "food_count": 3,
  "other_count": 1,
  "fruits": ["TAO: CHIN", "CHUOI: SONG"],
  "foods": ["milk", "cheese"],
  "other": ["bottle"],
  "last_detection": "2025-02-04T10:30:00"
}
```

#### `GET /api/stats`
Get comprehensive statistics

**Response:**
```json
{
  "sensor_data": { /* sensor data */ },
  "inventory": {
    "total": 12,
    "fruits": 8,
    "foods": 3,
    "other": 1
  },
  "item_counts": {
    "TAO: CHIN": 3,
    "CHUOI: SONG": 5
  },
  "last_update": "2025-02-04T10:30:00",
  "database_stats": { /* database stats */ },
  "database_enabled": true
}
```

#### `GET /api/oled`
Get data for OLED display

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

---

### Firebase (Wokwi)

#### `GET /api/firebase/history`
Get sensor history from Firebase

**Query Parameters:**
- `limit` (optional): Number of records (default: 50)

**Response:**
```json
{
  "success": true,
  "history": [ /* array of sensor readings */ ],
  "count": 50,
  "source": "firebase_wokwi"
}
```

#### `POST /api/firebase/control/light`
Control LED light

**Request:**
```json
{
  "value": 1  // 0 = off, 1 = on
}
```

#### `POST /api/firebase/control/peltier`
Control Peltier (cooling)

**Request:**
```json
{
  "value": 120  // 0-255 (PWM value)
}
```

#### `GET /api/firebase/control/status`
Get current control status

**Response:**
```json
{
  "success": true,
  "light": 1,
  "peltier": 120,
  "source": "firebase_wokwi"
}
```

---

### History

#### `GET /api/history/sensors`
Get sensor history from database

**Query Parameters:**
- `limit` (optional): Number of records (default: 100)

#### `GET /api/history/detections`
Get detection history from database

**Query Parameters:**
- `limit` (optional): Number of records (default: 50)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Web UI)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Dashboard   │  │   Camera     │  │   Controls   │      │
│  │   Display    │  │   Stream     │  │   & Stats    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└───────────────────────┬─────────────────────────────────────┘
                         │ HTTP/SSE
┌────────────────────────▼─────────────────────────────────────┐
│                  Flask Backend (app.py)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   YOLO AI    │  │   Camera     │  │   Sensor     │      │
│  │  Detection  │  │   Handler    │  │   Manager    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└───────┬───────────────┬───────────────┬───────────────┬─────┘
        │               │               │               │
┌───────▼──────┐ ┌──────▼──────┐ ┌─────▼──────┐ ┌─────▼──────┐
│   Webcam/    │ │  ESP32-CAM  │ │  Firebase/ │ │   MySQL   │
│   USB Cam    │ │   (WiFi)    │ │   Wokwi    │ │  Database  │
└──────────────┘ └─────────────┘ └────────────┘ └────────────┘
        │               │               │               │
┌───────▼───────────────▼───────────────▼───────────────▼─────┐
│                    Telegram Bot                              │
│              (Notifications & Alerts)                        │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Sensor Data Flow:**
   ```
   Firebase/Wokwi → Flask API → SSE Stream → Frontend
   ```

2. **Camera Stream Flow:**
   ```
   Webcam/ESP32-CAM → OpenCV → YOLO Detection → Flask Stream → Frontend
   ```

3. **Detection Flow:**
   ```
   Image Upload → YOLO Detection → Classification → Database → Telegram Alert
   ```

---

## Hardware Integration

### Raspberry Pi Setup

See `HARDWARE_SETUP.md` for hardware connection instructions.

#### DHT22 Sensor (Temperature/Humidity)

**Connection:**
```
DHT22:
├── VCC  → 3.3V (Pin 1)
├── GND  → GND (Pin 6)
└── DATA → GPIO4 (Pin 7)
```

**Sample code:**
```python
import Adafruit_DHT

sensor = Adafruit_DHT.DHT22
pin = 4

def read_temperature_sensor():
    humidity, temperature = Adafruit_DHT.read_retry(sensor, pin)
    return temperature, humidity
```

#### OLED Display (SSD1306)

**Connection (I2C):**
```
OLED SSD1306:
├── VCC → 3.3V
├── GND → GND
├── SDA → GPIO2 (SDA)
└── SCL → GPIO3 (SCL)
```

**Sample code:**
```python
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from PIL import Image, ImageDraw, ImageFont

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

### ESP32-CAM Setup

1. **Upload ESP32-CAM code** (refer to ESP32-CAM examples)
2. **Configure WiFi** in ESP32 code
3. **Get IP address** from Serial Monitor
4. **Update IP** in `app.py`:
   ```python
   ESP32_CAM_IP = "http://YOUR_ESP32_IP"
   ```

---

## Troubleshooting

### Error: "Unexpected token '<', "<!doctype "... is not valid JSON"

**Cause:** Server returning HTML instead of JSON (usually 404/500 error)

**Solution:**
1. Check if server is running: `http://localhost:5001`
2. Check server console for detailed errors
3. Ensure API route is correct (see API Endpoints section)

### Error: "Camera not available"

**Cause:** Webcam not detected or being used by another application

**Solution:**
1. **Windows:**
   - Check Device Manager → Imaging devices
   - Close apps using camera (Skype, Teams, etc.)
   - Grant camera permission to Python/Terminal

2. **Linux:**
   ```bash
   # Check camera
   lsusb | grep -i camera
   v4l2-ctl --list-devices
   ```

3. **macOS:**
   - System Settings → Privacy → Camera
   - Allow Terminal/Python to access camera

### Error: "ESP32-CAM connection failed"

**Cause:** ESP32-CAM not on same network or wrong IP

**Solution:**
1. Check ESP32-CAM is connected to WiFi
2. Check IP address in Serial Monitor
3. Test connection:
   ```bash
   curl http://192.168.137.14/capture
   ```
4. Ensure computer and ESP32-CAM are on same WiFi network

### Error: "YOLO model failed to load"

**Solution:**
```bash
# Download model manually
pip install ultralytics
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

### Error: "Port 5001 already in use"

**Solution:**
1. Find process using port:
   ```bash
   # Windows
   netstat -ano | findstr :5001
   
   # Linux/macOS
   lsof -i :5001
   ```

2. Kill process or change port in `app.py`

### Error: "Database connection failed"

**Solution:**
1. Check MySQL is running:
   ```bash
   # Windows
   services.msc → MySQL
   
   # Linux
   sudo systemctl status mysql
   ```

2. Check credentials in `database.py`
3. Create database if not exists:
   ```sql
   CREATE DATABASE smart_fridge;
   ```

### Error: "Firebase connection failed"

**Solution:**
1. Check Firebase credentials in `firebase_integration.py`
2. Verify database URL is correct
3. Check Firebase Console rules allow read/write

### Performance Issues

**YOLO Detection slow:**
- Use smaller model (`yolov8n.pt` instead of `yolov8m.pt`)
- Reduce input image resolution
- Use GPU if available (CUDA)

**Stream lag:**
- Reduce frame rate in code
- Optimize network (use LAN instead of WiFi)
- Reduce JPEG quality

---

## Documentation

### Main Documentation

- [YOLOv8 Documentation](https://docs.ultralytics.com/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [OpenCV Python Tutorials](https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html)
- [Firebase Realtime Database](https://firebase.google.com/docs/database)
- [ESP32-CAM Examples](https://github.com/espressif/arduino-esp32/tree/master/libraries/ESP32/examples/Camera)

### Project Documentation

- `DATABASE_SETUP.md` - MySQL setup guide
- `FIREBASE_WOKWI_SETUP.md` - Firebase/Wokwi setup guide
- `HARDWARE_SETUP.md` - Hardware connection guide
- `WOKWI_REALTIME_FIX.md` - Wokwi real-time updates fix

### Community & Support

- [Ultralytics Discord](https://discord.gg/ultralytics)
- [Report Issues](https://github.com/your-repo/issues)
- Email: your-email@example.com

---

## Testing

### Test API with curl

```bash
# Test sensor data
curl http://localhost:5001/api/sensors

# Test set temperature
curl -X POST http://localhost:5001/api/temperature \
  -H "Content-Type: application/json" \
  -d '{"temperature": 5}'

# Test camera source
curl -X POST http://localhost:5001/api/camera/source \
  -H "Content-Type: application/json" \
  -d '{"source": "webcam"}'

# Test detection (upload image)
curl -X POST http://localhost:5001/api/detect \
  -F "image=@test_image.jpg"
```

### Test with Python

```python
import requests

# Test sensors
response = requests.get('http://localhost:5001/api/sensors')
print(response.json())

# Test detection
with open('test_image.jpg', 'rb') as f:
    response = requests.post(
        'http://localhost:5001/api/detect',
        files={'image': f}
    )
    print(response.json())
```

---

## Production Deployment

### Using Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

### Using Docker

```bash
# Build image
docker build -t smart-fridge .

# Run container
docker run -p 5001:5001 smart-fridge
```

### Systemd Service (Linux)

See `smart-fridge.service` file for systemd service setup.

```bash
# Copy service file
sudo cp smart-fridge.service /etc/systemd/system/

# Enable and start
sudo systemctl enable smart-fridge
sudo systemctl start smart-fridge

# Check status
sudo systemctl status smart-fridge
```

---

## Security

### Production Recommendations

1. **HTTPS**: Use reverse proxy (Nginx) with SSL certificate
2. **Authentication**: Add authentication for API endpoints
3. **Rate Limiting**: Limit number of requests
4. **Input Validation**: Validate all user input
5. **File Upload Limits**: Limit file upload size

**Example Authentication:**
```python
from flask_httpauth import HTTPBasicAuth

auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    return username == 'admin' and password == 'secret'

@app.route('/api/sensors')
@auth.login_required
def get_sensors():
    # Protected endpoint
    pass
```

---

## Performance Benchmarks

| Operation | Time | Notes |
|-----------|------|-------|
| YOLO Detection (yolov8n) | ~100-300ms | CPU only |
| YOLO Detection (yolov8n + GPU) | ~20-50ms | CUDA enabled |
| API Response | <50ms | Average |
| SSE Update | Real-time | ~0.2s interval |
| Image Upload & Process | ~500ms-2s | Depends on image size |

---

## Contributing

Contributions are welcome! Please:

1. **Fork** repository
2. Create **branch** (`git checkout -b feature/AmazingFeature`)
3. **Commit** changes (`git commit -m 'Add some AmazingFeature'`)
4. **Push** to branch (`git push origin feature/AmazingFeature`)
5. Create **Pull Request**

### Code Style

- Follow Python PEP 8
- Add comments for complex code
- Write docstrings for functions
- Test code before committing

---

## License

MIT License - see `LICENSE` file for details

---

## Authors

**Ho Chi Minh City University of Technology and Engineering (HCM-UTE)**

**Team 3 - Smart Fridge IoT Project**

---

## Acknowledgments

- **Ultralytics** - YOLOv8 models and framework
- **Flask Team** - Excellent web framework
- **OpenCV Community** - Computer vision library
- **Raspberry Pi Foundation** - Hardware platform
- **Firebase/Google** - Realtime database
- **ESP32 Community** - IoT platform

---

## Contact & Support

- Email: your-email@example.com
- Issues: [GitHub Issues](https://github.com/your-repo/issues)
- Documentation: See `.md` files in project

---

<div align="center">

**Good luck with your project!**

Made by HCM-UTE Team 3

</div>
