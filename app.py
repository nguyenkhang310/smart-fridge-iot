from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context, session, redirect, url_for, render_template
from flask_cors import CORS
import sys
import cv2
import numpy as np
from core.telegram_notify import send_text, send_photo, can_send
import requests

# Giảm log OpenCV (tránh MSMF/obsensor spam trên Windows)
cv2.setLogLevel(3)
from ultralytics import YOLO
import json
from datetime import datetime, timedelta
import os
from PIL import Image
import io
import base64
import torch
import threading
import secrets
import hmac
import re
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import time

app = Flask(__name__)

def _env_flag(name: str, default: bool = False) -> bool:
    value = (os.environ.get(name) or '').strip().lower()
    if value in ('1', 'true', 'yes', 'on'):
        return True
    if value in ('0', 'false', 'no', 'off'):
        return False
    return default


secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    print("⚠ SECRET_KEY is not set. Using runtime key (development only).")
    secret_key = os.urandom(32)
app.secret_key = secret_key
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
app.config['SESSION_COOKIE_SECURE'] = _env_flag('SESSION_COOKIE_SECURE', False)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=int(os.environ.get('SESSION_LIFETIME_HOURS', '12')))
CORS(app, supports_credentials=True)
# Configuration
UPLOAD_FOLDER = 'uploads'
MODEL_PATH = 'yolov8n.pt'  # Fallback model
DETECTION_MODEL_PATH = 'models/fruit_detection.pt'  # Model để detect trái cây
CLASSIFICATION_MODEL_PATH = 'models/fruit_classification.pt'  # Model để phân loại chín/hỏng
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('models', exist_ok=True)

# Door open-too-long alert (dashboard)
# Hard-coded for simplicity (seconds)
DOOR_OPEN_ALERT_SECONDS = 60
DOOR_OPEN_ALERT_COOLDOWN_SECONDS = 300

# Control mode (software=Wokwi/Firebase, hardware=real device)
CONTROL_MODE_FILE = os.path.join(os.path.dirname(__file__), 'data', 'control_mode.json')
_control_mode_lock = threading.Lock()
_control_mode = 'software'  # default: keep existing behavior

def _load_control_mode():
    global _control_mode
    try:
        if os.path.exists(CONTROL_MODE_FILE):
            with open(CONTROL_MODE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f) or {}
                mode = (data.get('mode') or '').strip().lower()
                if mode in ('software', 'hardware'):
                    _control_mode = mode
    except Exception as e:
        print(f"⚠ Could not load control mode: {e}")

def _save_control_mode(mode: str):
    try:
        with open(CONTROL_MODE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'mode': mode, 'updated_at': datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠ Could not save control mode: {e}")

def get_control_mode() -> str:
    with _control_mode_lock:
        return _control_mode

def set_control_mode(mode: str) -> str:
    global _control_mode
    mode = (mode or '').strip().lower()
    if mode not in ('software', 'hardware'):
        raise ValueError("mode must be 'software' or 'hardware'")
    with _control_mode_lock:
        _control_mode = mode
    _save_control_mode(mode)
    return mode

_load_control_mode()

# ===== AI Chatbot (local, không dùng Gemini) =====
_chat_sessions = {}
_chat_lock = threading.Lock()

# Auth guard for brute-force attempts
_login_attempts = {}
_login_attempt_lock = threading.Lock()
MAX_LOGIN_ATTEMPTS = int(os.environ.get('MAX_LOGIN_ATTEMPTS', '5'))
LOGIN_ATTEMPT_WINDOW_SECONDS = int(os.environ.get('LOGIN_ATTEMPT_WINDOW_SECONDS', '900'))
LOCKOUT_SECONDS = int(os.environ.get('LOCKOUT_SECONDS', '900'))

def _get_session_history(session_id: str):
    with _chat_lock:
        return list(_chat_sessions.get(session_id, []))

def _append_session_history(session_id: str, role: str, content: str):
    with _chat_lock:
        hist = _chat_sessions.setdefault(session_id, [])
        hist.append({'role': role, 'content': content, 'ts': datetime.now().isoformat()})
        if len(hist) > 30:
            del hist[:-30]

def _tool_get_inventory():
    return {
        'total_items': inventory.get('total_items', 0),
        'fruits': inventory.get('fruits', []),
        'foods': inventory.get('foods', []),
        'other': inventory.get('other', []),
        'last_detection': inventory.get('last_detection'),
    }

def _tool_get_sensors():
    _refresh_sensor_data()
    snap = dict(sensor_data)
    snap['mode'] = get_control_mode()
    snap['firebase_available'] = bool(FIREBASE_AVAILABLE)
    snap['hardware_available'] = bool(HARDWARE_AVAILABLE)
    return snap

def _tool_set_temperature(target_temp: float):
    target_temp = float(target_temp)
    previous_temp = sensor_data.get('target_temperature')
    sensor_data['target_temperature'] = target_temp
    sensor_data['last_update'] = datetime.now().isoformat()

    mode = get_control_mode()
    current_temp = sensor_data.get('temperature', target_temp)
    pwm_sent = None
    firebase_error = None

    if mode in ['software', 'hardware'] and FIREBASE_AVAILABLE:
        try:
            fb_data = get_latest_sensor_data()
            if fb_data and fb_data.get('temperature') is not None:
                current_temp = float(fb_data.get('temperature', current_temp))
                sensor_data['temperature'] = current_temp
        except Exception as e:
            firebase_error = str(e)

        try:
            diff = float(current_temp) - target_temp
            if diff <= 0:
                pwm = 0
            else:
                pwm = min(255, int(80 + diff * 35))
            if set_peltier_control(pwm):
                pwm_sent = pwm
                try:
                    set_firebase_target_temp(target_temp)
                except Exception:
                    pass
            else:
                firebase_error = firebase_error or "set_peltier_control returned False"
        except Exception as e:
            firebase_error = str(e)

    hardware_stub = False
    if mode == 'hardware':
        if HARDWARE_AVAILABLE:
            control_status = set_temperature_control(target_temp, float(current_temp))
            sensor_data['status'] = control_status
        else:
            hardware_stub = True

    # Lưu lịch sử điều chỉnh vào DB (chatbot giống slider)
    if DB_AVAILABLE:
        try:
            save_temperature_setting(target_temp, previous_temp, changed_by='chatbot')
        except Exception as e:
            print(f"⚠ Error saving temperature setting (chatbot): {e}")

    return {
        'success': True,
        'mode': mode,
        'target_temperature': target_temp,
        'previous_temperature': previous_temp,
        'current_temp': current_temp,
        'pwm_sent': pwm_sent,
        'firebase_error': firebase_error,
        'hardware_stub': hardware_stub,
    }

# ESP32-CAM 
ESP32_CAM_IP = "http://192.168.137.32"  # Dán tên IP của ESP32-CAM vào đây
ESP32_CAPTURE_URL = f"{ESP32_CAM_IP}/capture"
ESP32_VIEW_URL = f"{ESP32_CAM_IP}/view"

# --- CƠ CHẾ TỰ ĐỘNG CẬP NHẬT IP CAMERA ---
def update_camera_ip(new_ip):
    global ESP32_CAM_IP, ESP32_CAPTURE_URL, ESP32_VIEW_URL
    
    # Đảm bảo IP luôn có tiền tố http://
    if not str(new_ip).startswith("http://"):
        new_ip = f"http://{new_ip}"
        
    # Nếu IP trên Firebase khác với IP hiện tại thì mới cập nhật
    if ESP32_CAM_IP != new_ip:
        ESP32_CAM_IP = new_ip
        ESP32_CAPTURE_URL = f"{ESP32_CAM_IP}/capture"
        ESP32_VIEW_URL = f"{ESP32_CAM_IP}/view"
        print(f"🚀 [AUTO-UPDATE] Đã cập nhật IP Camera mới từ Firebase: {ESP32_CAM_IP}")

# Fruit shelf life information (hạn sử dụng)
FRUIT_SHELF_LIFE = {
    "TAO": {
        "LOAI_DO": "5-7 ngay",     # Táo đỏ tiêu chuẩn
        "LOAI_XANH": "5 ngay",     # Táo xanh vỏ dày
        "LOAI_VANG": "3-4 ngay",   # Táo vàng
        "SAP_HONG": "1 ngay"       # Táo sắp hỏng
    },
    "CHUOI": {
        "XANH": "5-7 ngay",        # Chuối xanh
        "CHIN": "1-2 ngay",        # Chuối chín
        "UONG": "3-4 ngay"         # Chuối ương
    },
    "XOAI": {
        "XANH": "8-10 ngay",
        "CHIN": "2-4 ngay",        # Xoài chín rất dễ hỏng
        "UONG": "5-7 ngay"
    },
    "CAM": {
        "XANH": "3-4 ngay",        # Cam vỏ dày, để lâu tốt
        "CHIN": "2 ngay",
        "UONG": "2-3 ngay"
    },
    "LE": {
        "XANH": "5-7 ngay",
        "CHIN": "1-2 ngay",        # Lê chín mềm dễ bị úng
        "UONG": "3-4 ngay"
    }
}
_original_torch_load = torch.load

def _patched_torch_load(*args, **kwargs):
    """Patched torch.load to default weights_only=False for compatibility with ultralytics"""
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)


torch.load = _patched_torch_load


try:
    import ultralytics.nn.tasks
    # Add DetectionModel and other common ultralytics classes
    safe_classes = [ultralytics.nn.tasks.DetectionModel]
    # Try to add other model types if they exist
    for class_name in ['Segment', 'Pose', 'ClassificationModel', 'OBB']:
        if hasattr(ultralytics.nn.tasks, class_name):
            safe_classes.append(getattr(ultralytics.nn.tasks, class_name))
    
    if hasattr(torch.serialization, 'add_safe_globals'):
        torch.serialization.add_safe_globals(safe_classes)
        print(f"✓ Added {len(safe_classes)} ultralytics classes to safe globals")
except Exception as e:
    print(f"⚠ Note: Could not add safe globals: {e}")

# Load YOLO models
model = None  # Fallback model (yolov8n.pt)
model_detect = None  # Fruit detection model
model_classify = None  # Fruit classification model (chín/hỏng)

# Try to load advanced models first
try:
    if os.path.exists(DETECTION_MODEL_PATH):
        model_detect = YOLO(DETECTION_MODEL_PATH)
        print(f"✓ Fruit detection model loaded: {DETECTION_MODEL_PATH}")
    else:
        print(f"⚠ Detection model not found: {DETECTION_MODEL_PATH}")
except Exception as e:
    print(f"⚠ Could not load detection model: {e}")

try:
    if os.path.exists(CLASSIFICATION_MODEL_PATH):
        model_classify = YOLO(CLASSIFICATION_MODEL_PATH)
        print(f"✓ Fruit classification model loaded: {CLASSIFICATION_MODEL_PATH}")
    else:
        print(f"⚠ Classification model not found: {CLASSIFICATION_MODEL_PATH}")
except Exception as e:
    print(f"⚠ Could not load classification model: {e}")

# Load fallback model if advanced models not available
if model_detect is None:
    try:
        model = YOLO(MODEL_PATH)
        print(f"✓ Fallback YOLO model loaded: {MODEL_PATH}")
    except Exception as e:
        print(f"⚠ Warning: Could not load fallback YOLO model: {e}")
        import traceback
        traceback.print_exc()
        model = None

# Fruit ripeness analysis functions
def analyze_ripeness_specific(img_crop, fruit_type):
    """
    Phân tích độ chín của trái cây dựa trên màu sắc HSV
    Returns: (status_display, days_left)
    """
    if img_crop is None or getattr(img_crop, "size", 0) == 0:
        return "Unknown", "?"

    # Làm mờ nhẹ
    img_crop = cv2.GaussianBlur(img_crop, (5, 5), 0)
    hsv = cv2.cvtColor(img_crop, cv2.COLOR_BGR2HSV)
    
    # Tạo mặt nạ (Mask)
    mask = cv2.inRange(hsv, np.array([0, 40, 30]), np.array([180, 255, 255]))
    
    if cv2.countNonZero(mask) < 50:
        return "No Color", "?"

    # Tính histogram
    hist = cv2.calcHist([hsv], [0], mask, [180], [0, 180])
    hue_peak = np.argmax(hist)  # Tìm màu chủ đạo

    # Giá trị mặc định
    status_display = "Unknown"
    stage_key = "BINH_THUONG"
    
    # === NHÓM 1: CHUỐI, XOÀI, LÊ ===
    if fruit_type in ['CHUOI', 'XOAI', 'LE']:
        if 35 <= hue_peak < 90:
            status_display = "SONG"
            stage_key = "XANH"
        elif 25 <= hue_peak < 35:
            status_display = "UONG"
            stage_key = "UONG"
        elif 10 <= hue_peak < 25:
            status_display = "CHIN"
            stage_key = "CHIN"
        elif hue_peak < 10 or hue_peak > 160:
            status_display = "CHIN"
            stage_key = "CHIN"
            
    # === NHÓM 2: CAM ===
    elif fruit_type == 'CAM':
        if hue_peak > 30:
            status_display = "SONG"
            stage_key = "XANH"
        elif 10 <= hue_peak <= 30:
            status_display = "CHIN"
            stage_key = "CHIN"
        else:
            status_display = "CHIN"
            stage_key = "CHIN"

    # === NHÓM 3: TÁO ===
    elif fruit_type == 'TAO':
        # Táo đỏ
        if hue_peak < 15 or hue_peak > 160:
            status_display = "CHIN"
            stage_key = "LOAI_DO"
        # Táo xanh
        elif 15 <= hue_peak < 90:
            status_display = "CHIN"
            stage_key = "LOAI_XANH"
        # Táo vàng
        else:
            status_display = "CHIN"
            stage_key = "LOAI_VANG"

    # Tra cứu hạn sử dụng
    days_left = "?"
    if fruit_type in FRUIT_SHELF_LIFE:
        days_left = FRUIT_SHELF_LIFE[fruit_type].get(stage_key, "?")
    
    return status_display, days_left

def _ripeness_to_bgr(ripeness_status: str | None, is_rotten: bool = False):
    """
    Map trạng thái trái cây -> màu BGR để vẽ bounding box + nền nhãn.

    Quy ước:
    - HONG: đỏ
    - CHIN: vàng
    - QUA CHIN: cam
    - SONG/UONG: xanh lá
    - Khác/None: xám
    """
    if is_rotten:
        return (0, 0, 255)  # Red
    if not ripeness_status:
        return (200, 200, 200)  # Gray

    s = str(ripeness_status).strip().upper()
    if s == "HONG":
        return (0, 0, 255)
    if s == "CHIN":
        return (0, 255, 255)  # Yellow
    if s in {"QUA CHIN", "QUACHIN", "QUA_CHIN"}:
        return (0, 165, 255)  # Orange
    if s in {"SONG", "UONG"}:
        return (0, 255, 0)  # Green
    return (200, 200, 200)

def preprocess_image(frame):
    """Preprocess image để cải thiện chất lượng detection"""
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    l_balanced = clahe.apply(l)
    merged_lab = cv2.merge((l_balanced, a, b))
    frame_balanced = cv2.cvtColor(merged_lab, cv2.COLOR_LAB2BGR)
    blurred = cv2.GaussianBlur(frame, (7, 7), 0)
    kernel_sharpening = np.array([[-1, -1, -1], [-1,  9, -1], [-1, -1, -1]])
    sharpened = cv2.filter2D(blurred, -1, kernel_sharpening)
    return sharpened

def fetch_image_from_esp32(timeout=5):
    """
    Gọi ESP32-CAM chụp ảnh và lấy ảnh trả về
    """
    try:
        # ESP32 chụp ảnh
        r = requests.get(ESP32_CAPTURE_URL, timeout=timeout)
        if r.status_code != 200:
            print("ESP32 capture failed")
            return None

        # Lấy ảnh vừa chụp
        img_resp = requests.get(ESP32_VIEW_URL, timeout=timeout)
        if img_resp.status_code != 200:
            print("ESP32 view failed")
            return None

        # Decode ảnh
        img_array = np.frombuffer(img_resp.content, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        return img

    except Exception as e:
        print(f"ESP32 fetch error: {e}")
        return None

# Import hardware integration (optional)
try:
    from core.hardware_integration import (
        init_hardware, read_sensors, set_temperature_control,
        update_display, update_status_leds, cleanup_hardware
    )
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    print("⚠ hardware_integration.py not found - using simulation mode")

# Initialize hardware if available
_hardware_initialized = False
if HARDWARE_AVAILABLE:
    _hardware_initialized = init_hardware()

# Import database integration (optional)
try:
    from core.database import (
        init_database, save_sensor_reading, get_latest_sensor_reading,
        save_inventory, get_latest_inventory, save_detection_session,
        save_detection, save_temperature_setting, get_statistics,
        create_user, get_user_by_username, get_user_by_id,
        update_last_login, count_users, verify_password,
        list_users, set_user_active
    )
    DB_AVAILABLE = True
except ImportError as e:
    DB_AVAILABLE = False
    print(f"⚠ database.py not found - database features disabled: {e}")

# Initialize database if available
if DB_AVAILABLE:
    if init_database():
        print("✓ MySQL database initialized")
        # Bootstrap admin account one time if DB has no users
        try:
            if count_users() == 0:
                bootstrap_username = (os.environ.get('BOOTSTRAP_ADMIN_USERNAME') or 'admin').strip() or 'admin'
                bootstrap_password = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD')
                if bootstrap_password:
                    create_user(bootstrap_username, bootstrap_password, full_name='Administrator', role='admin')
                    print(f"✓ Bootstrap admin account created ({bootstrap_username})")
                else:
                    print("⚠ No users found but BOOTSTRAP_ADMIN_PASSWORD is missing.")
                    print("⚠ Set BOOTSTRAP_ADMIN_PASSWORD and restart once to create first admin account.")
        except Exception as _e:
            print(f"⚠ Could not bootstrap admin account: {_e}")
    else:
        print("⚠ Database initialization failed - continuing without database")
        DB_AVAILABLE = False

# Import Firebase integration (optional)
try:
    from core.firebase_integration import (
        init_firebase, get_latest_sensor_data, get_sensor_history as get_firebase_sensor_history,
        set_light_control, set_peltier_control, set_target_temperature as set_firebase_target_temp,
        get_control_status as get_firebase_control_status, set_current_inventory as set_firebase_inventory,
        get_camera_ip as get_firebase_camera_ip
    )
    FIREBASE_AVAILABLE = True
    if init_firebase():
        print("✓ Firebase Realtime Database connected (Wokwi)")
    else:
        print("⚠ Firebase initialization failed - continuing without Firebase")
        FIREBASE_AVAILABLE = False
except ImportError as e:
    FIREBASE_AVAILABLE = False
    set_firebase_inventory = None
    get_firebase_camera_ip = None
    print(f"⚠ firebase_integration.py not found - Firebase features disabled: {e}")

# --- Background thread: đồng bộ IP camera từ Firebase mỗi 30 giây ---
_cam_ip_sync_running = False
_cam_ip_sync_thread = None
_CAM_IP_SYNC_INTERVAL = 30  # giây

def _camera_ip_sync_worker():
    """Polling Firebase mỗi 30 giây để lấy IP mới nhất của ESP32-CAM."""
    global _cam_ip_sync_running
    while _cam_ip_sync_running:
        try:
            if FIREBASE_AVAILABLE and get_firebase_camera_ip:
                new_ip = get_firebase_camera_ip()
                if new_ip:
                    update_camera_ip(new_ip)
        except Exception as e:
            print(f"⚠ [CamIP Sync] Lỗi: {e}")
        # Ngủ theo từng giây để có thể dừng nhanh khi cần
        for _ in range(_CAM_IP_SYNC_INTERVAL):
            if not _cam_ip_sync_running:
                break
            threading.Event().wait(1.0)

def start_camera_ip_sync():
    """Khởi động background thread đồng bộ IP camera."""
    global _cam_ip_sync_running, _cam_ip_sync_thread
    if not FIREBASE_AVAILABLE or not get_firebase_camera_ip:
        return
    # Lấy IP ngay lần đầu khi khởi động
    try:
        initial_ip = get_firebase_camera_ip()
        if initial_ip:
            update_camera_ip(initial_ip)
    except Exception as e:
        print(f"⚠ [CamIP Init] Không lấy được IP từ Firebase: {e}")
    # Bắt đầu thread background
    _cam_ip_sync_running = True
    _cam_ip_sync_thread = threading.Thread(
        target=_camera_ip_sync_worker, daemon=True, name="CamIPSync"
    )
    _cam_ip_sync_thread.start()
    print("✓ Camera IP sync thread started (interval: 30s)")

# Khởi động sau khi Firebase đã sẵn sàng
if FIREBASE_AVAILABLE:
    start_camera_ip_sync()

# Simulated sensor data storage
sensor_data = {
    'temperature': 4.5,
    'humidity': 65,
    'target_temperature': 4,
    'status': 'normal',
    'last_update': datetime.now().isoformat()
}

# Door monitoring state (for Telegram alert sync with dashboard condition)
_door_monitor_running = False
_door_monitor_thread = None
_door_open_since = None
_door_alerted_this_open = False

def _parse_firebase_sensor_payload(fb_data):
    """Chuẩn hóa dict từ get_latest_sensor_data() (temperature/humidity/...) hoặc key gốc (Temp/Humi/...)."""
    if not fb_data or not isinstance(fb_data, dict):
        return None
    t = fb_data.get('temperature')
    if t is None:
        t = fb_data.get('Temp')
    h = fb_data.get('humidity')
    if h is None:
        h = fb_data.get('Humi')
    door = fb_data.get('door')
    if door is None:
        door = fb_data.get('Door')
    pwm = fb_data.get('pwm')
    if pwm is None:
        pwm = fb_data.get('PWM')
    return {
        'temperature': t,
        'humidity': h,
        'door': door,
        'pwm': pwm,
        'last_update': fb_data.get('last_update'),
    }

def _apply_firebase_to_sensor_data(fb_data):
    """Đồng bộ sensor_data với Firebase — cùng nguồn với firebase_update_worker (SSE dashboard)."""
    v = _parse_firebase_sensor_payload(fb_data)
    if not v:
        return
    if v['temperature'] is not None:
        try:
            sensor_data['temperature'] = float(v['temperature'])
        except (TypeError, ValueError):
            pass
    if v['humidity'] is not None:
        try:
            sensor_data['humidity'] = float(v['humidity'])
        except (TypeError, ValueError):
            pass
    if v['door'] is not None:
        try:
            sensor_data['door_state'] = int(v['door'])
        except (TypeError, ValueError):
            pass
    if v['pwm'] is not None:
        try:
            sensor_data['pwm'] = int(v['pwm'])
        except (TypeError, ValueError):
            pass
    if v.get('last_update'):
        sensor_data['last_update'] = v['last_update']

def _refresh_sensor_data():
    """
    Cập nhật sensor_data từ nguồn đúng theo control mode.
    - Chế độ phần cứng + có thiết bị thật: ưu tiên đọc từ hardware.
    - Chế độ phần mềm (hoặc hardware stub): ưu tiên đọc từ Wokwi/Firebase.
    """
    mode = get_control_mode()

    if mode == 'hardware' and _hardware_initialized:
        try:
            real_data = read_sensors()
            sensor_data['temperature'] = real_data.get('temperature', sensor_data['temperature'])
            sensor_data['humidity'] = real_data.get('humidity', sensor_data['humidity'])
            sensor_data['status'] = real_data.get('status', sensor_data['status'])
            sensor_data['last_update'] = real_data.get('last_update', datetime.now().isoformat())
            sensor_data['door_state'] = real_data.get('door_state', 0)
            sensor_data['pwm'] = real_data.get('pwm', 0)
            sensor_data['source'] = 'hardware'
        except Exception as e:
            print(f"⚠ Error reading from hardware: {e}")
            if FIREBASE_AVAILABLE:
                try:
                    fb_data = get_latest_sensor_data()
                    if fb_data:
                        _apply_firebase_to_sensor_data(fb_data)
                        sensor_data['source'] = 'firebase_wokwi'
                except Exception:
                    pass
        return

    # Chế độ phần mềm hoặc hardware không có thiết bị thật → ưu tiên Wokwi/Firebase
    if FIREBASE_AVAILABLE:
        try:
            fb_data = get_latest_sensor_data()
            if fb_data:
                _apply_firebase_to_sensor_data(fb_data)
                sensor_data['source'] = 'firebase_wokwi'
        except Exception as e:
            print(f"⚠ Error reading from Firebase: {e}")

    if sensor_data.get('source') != 'firebase_wokwi':
        if _hardware_initialized:
            try:
                real_data = read_sensors()
                sensor_data.update(real_data)
                sensor_data['source'] = 'hardware'
            except Exception:
                sensor_data['last_update'] = datetime.now().isoformat()
                sensor_data['source'] = 'simulation'
        else:
            sensor_data['last_update'] = datetime.now().isoformat()
            sensor_data['source'] = 'simulation'

# Inventory storage
inventory = {
    'total_items': 0,
    'fruits': [],
    'foods': [],
    'other': [],
    'last_detection': None
}

_last_inventory_sync_payload = None
_last_inventory_sync_ts = 0.0


def _sync_inventory_to_firebase(force: bool = False):
    """Đồng bộ inventory hiện tại lên Firebase để OLED/ESP32 đọc cùng dữ liệu với web."""
    global _last_inventory_sync_payload, _last_inventory_sync_ts
    if not FIREBASE_AVAILABLE or not set_firebase_inventory:
        return

    payload = (
        int(inventory.get('total_items', 0)),
        int(len(inventory.get('fruits', []))),
        int(len(inventory.get('foods', []))),
        int(len(inventory.get('other', []))),
    )

    now = time.time()
    changed = payload != _last_inventory_sync_payload
    if not force and not changed:
        return
    if not force and (now - _last_inventory_sync_ts) < 1.0:
        return

    try:
        ok = set_firebase_inventory(*payload)
        if ok:
            _last_inventory_sync_payload = payload
            _last_inventory_sync_ts = now
    except Exception as e:
        print(f"⚠ Inventory firebase sync error: {e}")

def reset_inventory():
    """Đưa số lượng vật phẩm về 0 (dùng khi tắt camera / xóa ảnh)."""
    inventory['total_items'] = 0
    inventory['fruits'] = []
    inventory['foods'] = []
    inventory['other'] = []
    inventory['last_detection'] = None
    _sync_inventory_to_firebase(force=True)

# Latest detection details for chatbot/UX
latest_detection = {
    'updated_at': None,
    'image_filename': None,
    'detections': []
}

# Fruit and food categories based on COCO dataset
FRUIT_CLASSES = ['apple', 'banana', 'orange', 'broccoli', 'carrot']
FOOD_CLASSES = ['sandwich', 'hot dog', 'pizza', 'donut', 'cake']
# Vật dụng trong tủ lạnh
ITEM_CLASSES = ['bottle', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'water bottle', 'chai nuoc']
# Tên tiếng Việt cho vật dụng
ITEM_NAMES_VI = {
    'bottle': 'Chai nước',
    'water bottle': 'Chai nước',
    'chai nuoc': 'Chai nước',
    'cup': 'Cốc',
    'bowl': 'Bát',
    'fork': 'Nĩa',
    'knife': 'Dao',
    'spoon': 'Thìa'
}

# Camera stream variables
camera_stream = None
camera_lock = threading.Lock()
stream_active = False
selected_camera_source = "webcam"  # "webcam" or "esp32"

# Firebase real-time update thread
firebase_update_queue = Queue()
firebase_latest_data = None
firebase_update_thread = None
firebase_update_running = False

def _get_camera_backend():
    """Trên Windows dùng DirectShow - ổn định hơn MSMF, tránh lỗi -1072873821"""
    if sys.platform == 'win32':
        return cv2.CAP_DSHOW
    return cv2.CAP_ANY

def init_camera():
    """Initialize camera for streaming - try multiple camera indices"""
    global camera_stream
    try:
        # Release existing camera if any
        if camera_stream is not None:
            try:
                camera_stream.release()
            except:
                pass
            camera_stream = None
        
        backend = _get_camera_backend()
        # Windows: chỉ thử index 0,1 để tránh "Camera index out of range" (obsensor)
        # Mac/Linux: thử 0-5 (iPhone Continuity Camera)
        camera_indices = [0, 1] if sys.platform == 'win32' else list(range(6))
        last_error = None
        
        print("📷 Searching for available cameras...")
        
        for idx in camera_indices:
            try:
                print(f"📷 Trying to open camera index {idx}...")
                camera_stream = cv2.VideoCapture(idx, backend)
                
                if camera_stream.isOpened():
                    # Get camera name (helpful for debugging)
                    try:
                        backend = camera_stream.getBackendName()
                        camera_name = f" (backend: {backend})"
                    except:
                        camera_name = ""
                    
                    # Set backend properties (helpful on macOS)
                    camera_stream.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    # Try to read a frame to verify camera works
                    ret, frame = camera_stream.read()
                    if ret and frame is not None:
                        camera_stream.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                        camera_stream.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                        print(f"✓ Camera initialized successfully on index {idx}{camera_name}")
                        print(f"  Frame size: {frame.shape}")
                        # Check if it might be iPhone
                        if 'iphone' in str(camera_stream.getBackendName()).lower() or idx > 2:
                            print(f"  📱 Possibly iPhone Continuity Camera detected!")
                        return True
                    else:
                        print(f"  ⚠ Camera {idx} opened but cannot read frame{camera_name}")
                        camera_stream.release()
                        camera_stream = None
                else:
                    print(f"  ⚠ Camera {idx} failed to open")
            except Exception as e:
                last_error = str(e)
                print(f"  ✗ Error with camera index {idx}: {e}")
                if camera_stream is not None:
                    try:
                        camera_stream.release()
                    except:
                        pass
                    camera_stream = None
                continue
        
        print(f"⚠ No working camera found on any index")
        if last_error:
            print(f"  Last error: {last_error}")
        print("  💡 Tips:")
        print("     - On macOS: Grant camera permission to Terminal/Python")
        print("     - Check System Settings > Privacy > Camera")
        print("     - Make sure no other app is using the camera")
        return False
        
    except Exception as e:
        print(f"⚠ Camera initialization error: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_frames():
    """Generate video frames from ESP32-CAM"""
    global stream_active
    print(f"Starting ESP32 stream from: {ESP32_CAPTURE_URL}")
    
    # Đặt stream_active = True để vòng lặp chạy
    stream_active = True
    
    while stream_active:
        try:
            # Gọi hàm lấy ảnh từ ESP32 
            frame = fetch_image_from_esp32()
            
            if frame is not None:
                # Resize lại nếu ảnh quá to để stream mượt hơn (Tuỳ)
                # frame = cv2.resize(frame, (640, 480))

                # Encode sang JPEG
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ret:
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                else:
                    print("Failed to encode frame")
            else:
                # Nếu không lấy được ảnh, in lỗi và đợi xíu rồi thử lại
                print("ESP32 returned None (Check Connection/IP)")
                threading.Event().wait(1.0) # Đợi 1s tránh spam request làm treo ESP32

            # Quan trọng: ESP32 chụp ảnh tốn thời gian, không cần delay thêm quá nhiều
            # Nhưng cần nghỉ nhẹ để tránh quá tải mạng
            threading.Event().wait(0.1) 
            
        except Exception as e:
            print(f"Error in generate_frames: {e}")
            threading.Event().wait(1.0)

def generate_frames_with_detection():
    """Generate video frames with detection - CHỌN WEBCAM HOẶC ESP32"""
    global camera_stream, stream_active, model, model_detect, model_classify, selected_camera_source, inventory
    
    print(f"Bắt đầu luồng xử lý Detection với camera: {selected_camera_source}") # Log báo hiệu bắt đầu
    
    while stream_active:
        frame = None
        source_type = "none"

        # Chỉ lấy từ camera source được chọn
        if selected_camera_source == "webcam":
            # Lấy từ Webcam
            with camera_lock:
                if camera_stream is not None and camera_stream.isOpened():
                    success, cam_frame = camera_stream.read()
                    if success:
                        frame = cam_frame
                        source_type = "webcam"
        elif selected_camera_source == "esp32":
            # Lấy từ ESP32
            esp_frame = fetch_image_from_esp32(timeout=2) 
            if esp_frame is not None:
                frame = esp_frame
                source_type = "esp32"
        
        # Nếu không lấy được ảnh -> Chờ chút rồi thử lại
        if frame is None:
            print(f"Không lấy được ảnh từ {selected_camera_source}. Đang thử lại...")
            threading.Event().wait(0.5)
            continue

        try:
            # Preprocess
            processed_frame = preprocess_image(frame) if model_detect is not None else frame

            use_advanced = model_detect is not None and model_classify is not None
            annotated_frame = frame.copy() # Mặc định là ảnh gốc

            if use_advanced:
                # Biến tạm để lưu thống kê vật phẩm cho frame hiện tại
                frame_fruits = []
                frame_foods = []
                frame_others = []

                # Stage 1: Detection
                results = model_detect(processed_frame, conf=0.5, verbose=False)
                annotated_frame = processed_frame.copy()
                
                # Stage 2: Classification and drawing
                for result in results:
                    boxes = result.boxes
                    for box in boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                        w, h = x2 - x1, y2 - y1
                        confidence = float(box.conf[0].cpu().numpy())
                        
                        crop = processed_frame[max(0, y1):min(processed_frame.shape[0], y2), 
                                               max(0, x1):min(processed_frame.shape[1], x2)]
                        
                        if crop.size == 0: continue
                        
                        # ... Logic định danh class ...
                        try:
                            class_id = int(box.cls[0].cpu().numpy())
                            class_name = result.names[class_id]
                        except:
                            class_name = "Unknown"

                        # ... Logic check hỏng/chín (GIỮ NGUYÊN) ...
                        # (Tôi tóm tắt lại đoạn logic gửi Telegram để bạn dễ hình dung)
                        
                        # Check Fruit logic...
                        class_name_lower = class_name.lower()
                        is_fruit = (class_name_lower in FRUIT_CLASSES or 
                                   any(fruit in class_name.upper() for fruit in ['TAO', 'CHUOI', 'XOAI', 'CAM', 'LE']))
                        
                        category = 'other'
                        ripeness_status = None
                        days_left = None
                        is_rotten = False

                        if is_fruit and model_classify:
                             try:
                                res_cls = model_classify(crop, verbose=False)
                                cls_name = res_cls[0].names[res_cls[0].probs.top1]
                                parts = cls_name.split('_')
                                fruit_base = parts[0].upper()
                                is_rotten = 'khong' not in cls_name and 'hong' in cls_name

                                if is_rotten:
                                    class_name = f"{fruit_base}: HONG"
                                    ripeness_status = "HONG"
                                    days_left = "0 ngay"
                                    category = 'fruit'
                                    
                                    print(f"PHÁT HIỆN {fruit_base} HỎNG TỪ {source_type.upper()}!") 

                                    alert_key = f"stream_rotten_{fruit_base}"
                                    if can_send(alert_key, cooldown=60):
                                        timestamp = datetime.now().strftime('%H%M%S')
                                        temp_filename = f"alert_{fruit_base}_{timestamp}.jpg"
                                        temp_path = os.path.join(UPLOAD_FOLDER, temp_filename)
                                        cv2.imwrite(temp_path, annotated_frame)
                                        
                                        msg = (
                                            f"🚨 <b>CẢNH BÁO CHẤT LƯỢNG HOA QUẢ</b>\n\n"
                                            f"- Hệ thống AI phát hiện: <b>{fruit_base}</b> có dấu hiệu <b>HỎNG</b>.\n"
                                            f"- Nguồn hình ảnh: <b>{source_type.upper()}</b> (camera tủ lạnh).\n\n"
                                            f"🔍 <b>Khuyến nghị xử lý</b>:\n"
                                            f"• Kiểm tra lại quả {fruit_base.lower()} này trực tiếp, loại bỏ nếu có mùi lạ, nấm mốc hoặc mềm nhũn.\n"
                                            f"• Rà soát thêm các trái xung quanh cùng khay để tránh lây hỏng.\n"
                                            f"• Đảm bảo nhiệt độ bảo quản trong tủ đang ở mức khuyến nghị."
                                        )
                                        
                                        threading.Thread(target=send_text, args=(msg,)).start()
                                        threading.Thread(
                                            target=send_photo,
                                            args=(temp_path, f"Hình ảnh cảnh báo: {fruit_base} nghi hỏng"),
                                        ).start()
                                else:
                                    ripeness_status, days_left = analyze_ripeness_specific(crop, fruit_base)
                                    class_name = f"{fruit_base}: {ripeness_status}"
                                    category = 'fruit'
                             except Exception as e:
                                print(f"Err classify: {e}")
                                category = 'fruit'

                        # Thống kê cho inventory realtime
                        if is_fruit or category == 'fruit':
                            frame_fruits.append(class_name)
                        else:
                            if class_name_lower in FOOD_CLASSES:
                                frame_foods.append(class_name)
                            else:
                                frame_others.append(class_name)
                        
                        # Vẽ khung 
                        color = _ripeness_to_bgr(ripeness_status, is_rotten=is_rotten)
                        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                        #Vẽ text label
                        # Nền nhãn cùng màu với khung để nổi bật trên video
                        label_text = f"{class_name.split(':')[0].strip()} - {ripeness_status}" if ripeness_status else class_name
                        label_text = f"{label_text} ({confidence*100:.0f}%)" if confidence <= 1 else f"{label_text} ({confidence:.0f}%)"
                        font_scale = 0.55
                        thickness = 2
                        (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
                        y_text = y1 - 10
                        if y_text - th - 6 < 0:
                            y_text = y2 + th + 10
                        cv2.rectangle(annotated_frame, (x1, y_text - th - 6), (x1 + tw + 10, y_text + 4), color, -1)
                        cv2.putText(annotated_frame, label_text, (x1 + 5, y_text), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), thickness)

                # Cập nhật inventory toàn cục để frontend có thể đọc số lượng theo thời gian thực
                try:
                    total_items = len(frame_fruits) + len(frame_foods) + len(frame_others)
                    inventory['total_items'] = total_items
                    inventory['fruits'] = frame_fruits
                    inventory['foods'] = frame_foods
                    inventory['other'] = frame_others
                    inventory['last_detection'] = datetime.now().isoformat()
                    _sync_inventory_to_firebase()
                except Exception as e:
                    print(f"⚠ Error updating realtime inventory: {e}")

            else:
                # Fallback basic model
                if model is not None:
                    results = model(frame, conf=0.5, verbose=False)
                    annotated_frame = results[0].plot()
                else:
                    annotated_frame = frame

        except Exception as e:
            print(f"Error in detection loop: {e}")
            annotated_frame = frame
        
        # Encode và yield frame về trình duyệt
        if annotated_frame is not None:
            ret, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        # delay lâu chút để đỡ nghẽn mạng
        delay_time = 0.033 if source_type == "webcam" else 0.1 
        threading.Event().wait(delay_time)
# Don't initialize camera on startup - only when user requests it
# init_camera()  # Commented out - camera will be initialized on demand

def login_required(f):
    """Decorator: redirect to /login if not authenticated."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated


def _client_ip() -> str:
    forwarded_for = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
    if forwarded_for:
        return forwarded_for
    return request.remote_addr or 'unknown'


def _login_attempt_key(username: str) -> str:
    return f"{_client_ip()}::{(username or '').strip().lower()}"


def _check_login_lock(key: str):
    now_ts = datetime.now().timestamp()
    with _login_attempt_lock:
        state = _login_attempts.get(key)
        if not state:
            return False, 0
        if state.get('expires_at', 0) <= now_ts:
            _login_attempts.pop(key, None)
            return False, 0
        if state.get('locked_until', 0) > now_ts:
            return True, int(state['locked_until'] - now_ts)
        return False, 0


def _record_login_failure(key: str):
    now_ts = datetime.now().timestamp()
    with _login_attempt_lock:
        state = _login_attempts.get(key)
        if not state or state.get('expires_at', 0) <= now_ts:
            state = {'count': 0, 'expires_at': now_ts + LOGIN_ATTEMPT_WINDOW_SECONDS, 'locked_until': 0}
            _login_attempts[key] = state
        state['count'] += 1
        if state['count'] >= MAX_LOGIN_ATTEMPTS:
            state['locked_until'] = now_ts + LOCKOUT_SECONDS


def _clear_login_failure(key: str):
    with _login_attempt_lock:
        _login_attempts.pop(key, None)


def _ensure_csrf_token() -> str:
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf_token'] = token
    return token


def _valid_csrf_request() -> bool:
    expected = session.get('_csrf_token')
    provided = request.headers.get('X-CSRF-Token') or ''
    if not expected or not provided:
        return False
    return hmac.compare_digest(expected, provided)


@app.route('/login')
def serve_login():
    """Serve the login page. Redirect to dashboard if already logged in."""
    if session.get('user_id'):
        return redirect('/')
    return render_template('login.html')


@app.route('/')
@login_required
def index():
    """Serve the main HTML page"""
    return render_template('smart_fridge.html')


@app.route('/favicon.ico')
def favicon():
    """Avoid noisy 404 for browser favicon request."""
    return ('', 204)

# (Đã xoá các route phục vụ file tĩnh vì ảnh đã chuyển sang /static/img)


# ===== AUTH API =====

@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    """Login with username and password."""
    try:
        data = request.json or {}
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''

        if not username or not password:
            return jsonify({'success': False, 'error': 'Vui long nhap ten dang nhap va mat khau'}), 400

        attempt_key = _login_attempt_key(username)
        is_locked, retry_after = _check_login_lock(attempt_key)
        if is_locked:
            return jsonify({
                'success': False,
                'error': f'Tai khoan tam khoa do nhap sai nhieu lan. Thu lai sau {retry_after} giay'
            }), 429

        if not DB_AVAILABLE:
            return jsonify({'success': False, 'error': 'He thong dang bao tri dang nhap (database khong kha dung)'}), 503

        user = get_user_by_username(username)
        if not user:
            _record_login_failure(attempt_key)
            return jsonify({'success': False, 'error': 'Sai ten dang nhap hoac mat khau'}), 401

        if not user.get('is_active'):
            _record_login_failure(attempt_key)
            return jsonify({'success': False, 'error': 'Tai khoan da bi khoa'}), 403

        if not verify_password(password, user['password_hash']):
            _record_login_failure(attempt_key)
            return jsonify({'success': False, 'error': 'Sai ten dang nhap hoac mat khau'}), 401

        _clear_login_failure(attempt_key)

        # Regenerate session and set authenticated context
        session.clear()
        session.permanent = True
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['full_name'] = user.get('full_name') or user['username']
        session['role'] = user.get('role', 'user')
        csrf_token = _ensure_csrf_token()

        update_last_login(user['id'])

        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'full_name': user.get('full_name'),
                'role': user.get('role', 'user'),
            },
            'csrf_token': csrf_token
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/logout', methods=['POST'])
def api_auth_logout():
    """Logout current user."""
    if not session.get('user_id'):
        return jsonify({'success': False, 'error': 'Chua dang nhap'}), 401
    if not _valid_csrf_request():
        return jsonify({'success': False, 'error': 'CSRF token khong hop le'}), 403
    session.clear()
    return jsonify({'success': True})


@app.route('/api/auth/me', methods=['GET'])
def api_auth_me():
    """Get current logged-in user info."""
    if not session.get('user_id'):
        return jsonify({'success': False, 'error': 'Chua dang nhap'}), 401
    return jsonify({
        'success': True,
        'user': {
            'id': session.get('user_id'),
            'username': session.get('username'),
            'full_name': session.get('full_name'),
            'role': session.get('role', 'user'),
        },
        'csrf_token': _ensure_csrf_token()
    })


@app.route('/api/auth/register', methods=['POST'])
def api_auth_register():
    """Register a new user (admin only)."""
    try:
        if not session.get('user_id'):
            return jsonify({'success': False, 'error': 'Chua dang nhap'}), 401
        if not _valid_csrf_request():
            return jsonify({'success': False, 'error': 'CSRF token khong hop le'}), 403

        caller_role = session.get('role')
        if caller_role != 'admin':
            return jsonify({'success': False, 'error': 'Khong co quyen tao tai khoan'}), 403

        data = request.json or {}
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        full_name = (data.get('full_name') or '').strip() or None
        email = (data.get('email') or '').strip() or None
        role = data.get('role', 'user')

        if not username or not password:
            return jsonify({'success': False, 'error': 'Vui long nhap ten dang nhap va mat khau'}), 400
        if not re.fullmatch(r'[a-z0-9_]{3,32}', username):
            return jsonify({'success': False, 'error': 'Ten dang nhap chi gom chu thuong, so, dau gach duoi (3-32 ky tu)'}), 400
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'Mat khau phai co it nhat 6 ky tu'}), 400
        if role not in ('admin', 'user'):
            role = 'user'

        if not DB_AVAILABLE:
            return jsonify({'success': False, 'error': 'Database khong kha dung'}), 503

        existing = get_user_by_username(username)
        if existing:
            return jsonify({'success': False, 'error': 'Ten dang nhap da ton tai'}), 409

        user_id = create_user(username, password, full_name=full_name, email=email, role=role)
        if not user_id:
            return jsonify({'success': False, 'error': 'Khong the tao tai khoan'}), 500

        return jsonify({'success': True, 'user_id': user_id, 'username': username, 'role': role})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/auth/users', methods=['GET'])
def api_auth_users():
    """List users for account management (admin only)."""
    if not session.get('user_id'):
        return jsonify({'success': False, 'error': 'Chua dang nhap'}), 401
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Khong co quyen truy cap'}), 403
    if not DB_AVAILABLE:
        return jsonify({'success': False, 'error': 'Database khong kha dung'}), 503

    users = list_users()
    return jsonify({'success': True, 'users': users})


@app.route('/api/auth/users/<int:user_id>/active', methods=['POST'])
def api_auth_set_user_active(user_id):
    """Enable/disable account status (admin only)."""
    if not session.get('user_id'):
        return jsonify({'success': False, 'error': 'Chua dang nhap'}), 401
    if not _valid_csrf_request():
        return jsonify({'success': False, 'error': 'CSRF token khong hop le'}), 403
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'Khong co quyen truy cap'}), 403
    if not DB_AVAILABLE:
        return jsonify({'success': False, 'error': 'Database khong kha dung'}), 503
    if user_id == session.get('user_id'):
        return jsonify({'success': False, 'error': 'Khong the khoa tai khoan dang dang nhap'}), 400

    data = request.json or {}
    raw_is_active = data.get('is_active')
    if isinstance(raw_is_active, bool):
        is_active = raw_is_active
    else:
        is_active = str(raw_is_active).strip().lower() in ('1', 'true', 'yes', 'on')
    ok = set_user_active(user_id, is_active)
    if not ok:
        return jsonify({'success': False, 'error': 'Khong the cap nhat trang thai tai khoan'}), 500
    return jsonify({'success': True, 'user_id': user_id, 'is_active': is_active})



@app.route('/api/mode', methods=['GET', 'POST'])
def api_control_mode():
    """
    Get/set control mode for actuators.
    - software: keep existing Wokwi/Firebase control flow
    - hardware: prepare to control real device (stub now, wire later)
    """
    if request.method == 'GET':
        return jsonify({'success': True, 'mode': get_control_mode()})

    try:
        data = request.json or {}
        mode = data.get('mode')
        mode = set_control_mode(mode)
        return jsonify({'success': True, 'mode': mode, 'message': f'Đã chuyển sang chế độ: {mode}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/chat', methods=['POST'])
def api_chat():
    """
    Chat endpoint for UI.
    Body: { session_id: string, message: string }
    """
    try:
        data = request.json or {}
        session_id = (data.get('session_id') or 'default').strip()[:64]
        message = (data.get('message') or '').strip()
        if not message:
            return jsonify({'success': False, 'error': 'message required'}), 400

        _append_session_history(session_id, 'user', message)

        text = message.lower()
        reply = None
        temperature_set_by_chat = None

        import re

        # Ý định: Đặt nhiệt độ
        set_temp_match = re.search(r'(chỉnh|đặt|thay|set|giảm|tăng|hạ|cho).*?(-?\d+\.?\d*)', text)
        if reply is None and set_temp_match and any(k in text for k in ['nhiệt', 'độ', '°c', 'c']):
            if session.get('role') != 'admin':
                reply = "Xin lỗi, chỉ có quản trị viên mới được phép điều chỉnh nhiệt độ."
            else:
                try:
                    target = float(set_temp_match.group(2))
                    r = _tool_set_temperature(target)
                    temperature_set_by_chat = r.get('target_temperature')
                    extra = " (chế độ giả lập)" if r.get('hardware_stub') else ""
                    reply = f"Đã điều chỉnh nhiệt độ mục tiêu thành {temperature_set_by_chat}°C.{extra}"
                except ValueError:
                    pass

        # Ý định: Hỏi nhiệt độ, độ ẩm hiện tại
        if reply is None and any(k in text for k in ['nhiệt độ', 'nhiet do', 'độ ẩm', 'do am', 'lạnh', 'nóng']):
            s = _tool_get_sensors()
            reply = (
                f"Nhiệt độ hiện tại: {s.get('temperature')}°C\n"
                f"Độ ẩm: {s.get('humidity')}%\n"
                f"Mục tiêu đang đặt: {s.get('target_temperature')}°C"
            )

        # Ý định: Hỏi cửa tủ đang đóng/mở
        if reply is None and any(k in text for k in ['cửa', 'cua', 'door']):
            s = _tool_get_sensors()
            door_state = s.get('door_state')
            is_open = (door_state == 1 or door_state is True or str(door_state) == '1')
            if is_open:
                reply = "Cửa tủ hiện đang MỞ."
            else:
                reply = "Cửa tủ hiện đang ĐÓNG."

        # Ý định: Hỏi trong tủ có gì, trái cây
        if reply is None and any(k in text for k in ['trong tủ', 'trong tu', 'có gì', 'trái cây', 'trai cay', 'táo', 'chuối', 'cam', 'hỏng', 'hư', 'bao nhiêu']):
            inv = _tool_get_inventory()
            all_items = inv.get('fruits', []) + inv.get('foods', []) + inv.get('other', [])
            
            if not inv.get('last_detection'):
                reply = "Mình chưa có dữ liệu camera gần đây. Bạn hãy bật camera / quét AI trước nhé!"
            elif not all_items:
                reply = "Tủ đang trống, không phát hiện thấy trái cây hay thực phẩm nào."
            else:
                from collections import Counter
                counts = Counter(all_items)
                
                # Check for rotten
                rotten_items = [k for k in counts.keys() if 'rotten' in k.lower() or 'spoiled' in k.lower() or 'hư' in k.lower() or 'hỏng' in k.lower()]
                
                details = []
                for item, qty in counts.items():
                    name = item.replace('_', ' ').title()
                    # Translate known english classes
                    nl = name.lower()
                    if 'fresh apple' in nl: name = "Táo tươi"
                    elif 'rotten apple' in nl: name = "Táo hỏng"
                    elif 'fresh banana' in nl: name = "Chuối tươi"
                    elif 'rotten banana' in nl: name = "Chuối hỏng"
                    elif 'fresh orange' in nl: name = "Cam tươi"
                    elif 'rotten orange' in nl: name = "Cam hỏng"
                    details.append(f"- {qty} {name}")
                
                reply = f"Trong tủ hiện có {len(all_items)} món:\n" + "\n".join(details)
                if rotten_items:
                    reply += "\n\nLưu ý: Phát hiện có trái cây đang bị hỏng, bạn kiểm tra và dọn dẹp nhé!"

        if reply is None:
            reply = (
                "Chào bạn, mình có thể giúp bạn:\n"
                "- Báo cáo nhiệt độ, độ ẩm hiện tại\n"
                "- Cài đặt nhiệt độ tủ (VD: 'Chỉnh nhiệt độ 5 độ')\n"
                "- Kiểm tra số lượng và tình trạng trái cây trong tủ"
            )

        _append_session_history(session_id, 'assistant', reply)
        resp = {'success': True, 'reply': reply, 'session_id': session_id}
        if temperature_set_by_chat is not None:
            resp['target_temperature'] = temperature_set_by_chat
        return jsonify(resp)
    except Exception as e:
        msg = str(e)
        return jsonify({'success': False, 'error': msg}), 500


def _door_monitor_worker():
    """Background worker: gửi Telegram khi cửa mở quá lâu."""
    global _door_monitor_running, _door_open_since, _door_alerted_this_open
    import time

    while _door_monitor_running:
        try:
            state = None
            if firebase_latest_data and isinstance(firebase_latest_data, dict):
                state = firebase_latest_data.get('door_state')
            if state is None:
                state = sensor_data.get('door_state', 0)

            is_open = (state == 1 or state is True or str(state) == '1')
            if is_open:
                if _door_open_since is None:
                    _door_open_since = datetime.now()
                    _door_alerted_this_open = False

                elapsed = int((datetime.now() - _door_open_since).total_seconds())
                if (not _door_alerted_this_open) and elapsed >= DOOR_OPEN_ALERT_SECONDS:
                    if can_send('door_open_too_long', cooldown=DOOR_OPEN_ALERT_COOLDOWN_SECONDS):
                        msg = (
                            "🚪⚠ <b>CẢNH BÁO CỬA MỞ QUÁ LÂU</b>\n\n"
                            f"- Trạng thái: <b>Đang mở</b>\n"
                            f"- Thời gian mở: <b>{elapsed} giây</b>\n"
                            f"- Ngưỡng: <b>{DOOR_OPEN_ALERT_SECONDS} giây</b>\n\n"
                            "Vui lòng đóng cửa tủ."
                        )
                        threading.Thread(target=send_text, args=(msg,), daemon=True).start()
                    _door_alerted_this_open = True
            else:
                _door_open_since = None
                _door_alerted_this_open = False
        except Exception as e:
            print(f"⚠ Door monitor error: {e}")

        time.sleep(0.5)


def _door_metrics_snapshot(door_state):
    """Build synchronized door-open metrics for dashboard/Telegram consistency."""
    is_open = (door_state == 1 or door_state is True or str(door_state) == '1')
    open_seconds = 0
    too_long = False
    if is_open and _door_open_since is not None:
        try:
            open_seconds = max(0, int((datetime.now() - _door_open_since).total_seconds()))
        except Exception:
            open_seconds = 0
    if is_open and open_seconds >= DOOR_OPEN_ALERT_SECONDS:
        too_long = True
    return {
        'door_open_seconds': open_seconds,
        'door_open_too_long': too_long,
    }


def _enrich_with_door_metrics(payload: dict) -> dict:
    """Attach door-open metrics to outgoing sensor payload."""
    data = dict(payload or {})
    door_state = data.get('door_state')
    if door_state is None:
        door_state = sensor_data.get('door_state', 0)
    data.update(_door_metrics_snapshot(door_state))
    return data


@app.route('/api/sensors', methods=['GET'])
def get_sensors():
    """Get current sensor readings — nguồn phụ thuộc control mode (hardware vs software)."""
    _refresh_sensor_data()

    # Cập nhật status dựa trên nhiệt độ
    temp = sensor_data.get('temperature')
    if temp is not None:
        try:
            t = float(temp)
            if t > 25:
                sensor_data['status'] = 'hot'
            elif t > 20:
                sensor_data['status'] = 'warming'
            else:
                sensor_data['status'] = 'normal'
        except (TypeError, ValueError):
            pass
    
    # Save to database if available (only save periodically to avoid too many writes)
    if DB_AVAILABLE:
        try:
            # Only save every 10 seconds to avoid database overload
            import time
            if not hasattr(get_sensors, 'last_save_time'):
                get_sensors.last_save_time = 0
            
            current_time = time.time()
            if current_time - get_sensors.last_save_time > 10:  # Save every 10 seconds
                save_sensor_reading(
                    sensor_data['temperature'],
                    sensor_data['humidity'],
                    sensor_data['target_temperature'],
                    sensor_data['status']
                )
                get_sensors.last_save_time = current_time
        except Exception as e:
            print(f"⚠ Error saving sensor to database: {e}")
    
    payload = _enrich_with_door_metrics(sensor_data)
    payload['door_open_alert_seconds'] = DOOR_OPEN_ALERT_SECONDS
    return jsonify(payload)

@app.route('/api/temperature', methods=['POST'])
def set_temperature():
    """Set target temperature and control hardware / Firebase (Wokwi ESP32)"""
    data = request.json or {}
    target_temp = data.get('temperature')
    
    if target_temp is None:
        return jsonify({'error': 'Temperature value required'}), 400
    
    target_temp = float(target_temp)
    previous_temp = sensor_data['target_temperature']
    sensor_data['target_temperature'] = target_temp
    sensor_data['last_update'] = datetime.now().isoformat()
    
    # Lấy nhiệt độ hiện tại TRỰC TIẾP từ Firebase (Wokwi) — cùng key với get_latest_sensor_data()
    current_temp = target_temp
    if FIREBASE_AVAILABLE:
        try:
            fb_data = get_latest_sensor_data()
            if fb_data:
                _apply_firebase_to_sensor_data(fb_data)
                v = _parse_firebase_sensor_payload(fb_data)
                if v and v['temperature'] is not None:
                    current_temp = float(v['temperature'])
                else:
                    current_temp = float(sensor_data.get('temperature', target_temp))
        except Exception as e:
            print(f"⚠ Could not fetch current temp from Firebase: {e}")
            current_temp = sensor_data.get('temperature', target_temp)
    else:
        current_temp = sensor_data.get('temperature', target_temp)
    
    try:
        current_temp = float(current_temp)
    except (TypeError, ValueError):
        current_temp = target_temp
    
    mode = get_control_mode()

    # Gửi lệnh PWM tới Firebase (Wokwi ESP32) - ESP32 đọc /Control/Peltier (software mode)
    pwm_sent = None
    firebase_error = None
    if mode in ['software', 'hardware'] and FIREBASE_AVAILABLE:
        try:
            # Chuyển đổi target temp -> PWM: nhiệt độ cao hơn mục tiêu = cần làm lạnh = PWM cao
            diff = current_temp - target_temp
            if diff <= 0:
                pwm = 0  # Đã đủ lạnh, tắt làm lạnh
            else:
                # diff > 0: cần làm lạnh, PWM tỉ lệ với chênh lệch (max 255)
                pwm = min(255, int(80 + diff * 35))
            if set_peltier_control(pwm):
                pwm_sent = pwm
                set_firebase_target_temp(target_temp)  # Ghi TargetTemp để ESP32 có thể hiển thị
                print(f"✓ Firebase Peltier set: {pwm} (current={current_temp}°C, target={target_temp}°C)")
            else:
                firebase_error = "set_peltier_control returned False"
        except Exception as e:
            firebase_error = str(e)
            print(f"⚠ Firebase Peltier control error: {e}")
    
    # Save temperature setting to database
    if DB_AVAILABLE:
        try:
            save_temperature_setting(target_temp, previous_temp, changed_by='user')
        except Exception as e:
            print(f"⚠ Error saving temperature setting to database: {e}")
    
    # Control hardware if available (hardware mode)
    hardware_stub = False
    if mode == 'hardware':
        if HARDWARE_AVAILABLE:
            try:
                control_status = set_temperature_control(target_temp, current_temp)
                sensor_data['status'] = control_status
            except Exception as e:
                return jsonify({'success': False, 'error': f'Hardware control error: {e}'}), 500
        else:
            # Chưa gắn phần cứng: để sẵn, nhưng không đụng flow phần mềm.
            hardware_stub = True
    
    # Thông báo theo mode
    msg = f'Nhiệt độ đã cài đặt: {target_temp}°C'
    msg += f' | mode={mode}'
    if mode == 'software' and firebase_error:
        msg += f' (⚠ Lỗi Firebase: {firebase_error})'
    if hardware_stub:
        msg += ' (Chế độ phần cứng: chưa gắn phần cứng, đang để stub)'
    
    return jsonify({
        'success': True,
        'target_temperature': sensor_data['target_temperature'],
        'pwm_sent': pwm_sent,
        'current_temp': current_temp,
        'mode': mode,
        'message': msg
    })

@app.route('/api/oled', methods=['GET'])
def get_oled_data():
    """Get data to display on OLED screen"""
    oled_info = {
        'temperature': sensor_data['temperature'],
        'humidity': sensor_data['humidity'],
        'status': sensor_data['status'],
        'total_items': inventory['total_items'],
        'fruit_count': len(inventory['fruits']),
        'time': datetime.now().strftime('%H:%M:%S')
    }
    return jsonify(oled_info)

@app.route('/api/detect', methods=['POST'])
def detect_objects():
    """YOLO object detection endpoint with advanced fruit ripeness detection"""
    has_rotten = False
    rotten_fruits = set()
    # Check if models are available
    if model_detect is None and model is None:
        return jsonify({
            'error': 'YOLO model not loaded',
            'message': 'Please install ultralytics and download model'
        }), 500
    
    # Nếu có ảnh upload lên 
    if 'image' in request.files:
        file = request.files['image']
        image_bytes = file.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({'error': 'Invalid image upload'}), 400
    else:
        # Ko có ảnh thì lấy từ ESP32-CAM
        print("Fetching image from ESP32-CAM...")
        img = fetch_image_from_esp32()
        if img is None:
            print("ESP32-CAM failed")
            return jsonify({'error': 'Failed to get image from ESP32-CAM'}), 500
        print("ESP32 image received")

    DETECT_TIMEOUT = 90

    def _run_detection():
        nonlocal has_rotten, img
        if model_detect is not None:
            img = preprocess_image(img)
        # Use advanced 2-stage detection if available, otherwise fallback
        use_advanced = model_detect is not None and model_classify is not None
        
        if use_advanced:
            # Stage 1: Detection - find fruits
            results = model_detect(img, conf=0.5, verbose=False)
        else:
            # Fallback to basic model
            results = model(img, conf=0.5)
        
        # Process results
        detections = []
        fruits = []
        foods = []
        other = []
        annotated_img = img.copy()
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                # Get box coordinates
                x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                w, h = x2 - x1, y2 - y1
                confidence = float(box.conf[0].cpu().numpy())
                
                # Crop image for classification
                crop = img[max(0, y1):min(img.shape[0], y2), max(0, x1):min(img.shape[1], x2)]
                
                if crop.size == 0:
                    continue
                
                # Initialize detection info
                class_name = "Unknown"
                category = 'other'
                ripeness_status = None
                days_left = None
                is_rotten = False
                classification_confidence = 0
                is_fruit = False
                
                # First, get class name from detection model
                try:
                    if use_advanced:
                        class_id = int(box.cls[0].cpu().numpy())
                        class_name = result.names[class_id]
                    else:
                        class_id = int(box.cls[0].cpu().numpy())
                        class_name = model.names[class_id]
                except:
                    pass

                # Gửi thông báo Telegram khi phát hiện vật thể
                if class_name != "Unknown":
                    alert_key = f"detection_{class_name.lower().replace(' ', '_')}"
                    if can_send(alert_key, cooldown=30):  # Cooldown 30 giây cho mỗi loại vật thể
                        msg = (
                            f"🔎 <b>Nhận diện vật thể mới trong tủ lạnh</b>\n\n"
                            f"- Loại: <b>{class_name}</b>\n"
                            f"- Độ tin cậy: <b>{confidence*100:.0f}%</b>\n\n"
                            f"ℹ️ Bạn có thể mở giao diện Web Smart Fridge để xem chi tiết vị trí và trạng thái bảo quản."
                        )
                        
                        # Gửi trong luồng riêng để không làm chậm response
                        threading.Thread(target=send_text, args=(msg,)).start()
                        print(f"🚀 Đã gửi thông báo Telegram cho: {class_name}")
                
                # Check if it's a fruit (for classification)
                class_name_lower = class_name.lower()
                is_fruit = (class_name_lower in FRUIT_CLASSES or 
                           any(fruit in class_name.upper() for fruit in ['TAO', 'CHUOI', 'XOAI', 'CAM', 'LE']))
                
                # Only use classification for fruits
                if use_advanced and is_fruit:
                    # Stage 2: Classification - determine ripeness/spoilage for fruits only
                    try:
                        res_cls = model_classify(crop, verbose=False)
                        cls_name = res_cls[0].names[res_cls[0].probs.top1]
                        classification_confidence = res_cls[0].probs.top1conf.item() * 100
                        
                        # Parse classification result
                        parts = cls_name.split('_')
                        fruit_base = parts[0].upper()
                        is_rotten = 'khong' not in cls_name and 'hong' in cls_name
                        
                        if is_rotten:
                            # Fruit is rotten
                            class_name = f"{fruit_base} (HỎNG)"
                            category = 'fruit'
                            ripeness_status = "HONG"
                            days_left = "0 ngay"
                            has_rotten = True
                            rotten_fruits.add(fruit_base)

                        else:
                            # Analyze ripeness
                            ripeness_status, days_left = analyze_ripeness_specific(crop, fruit_base)
                            class_name = f"{fruit_base} ({ripeness_status})"
                            category = 'fruit'
            
                    except Exception as e:
                        print(f"⚠ Classification error: {e}")
                        # Keep original class_name from detection
                        category = 'fruit'
                
                # Categorize object
                if category == 'other':
                    if is_fruit:
                        category = 'fruit'
                        fruits.append(class_name)
                    elif class_name_lower in FOOD_CLASSES:
                        category = 'food'
                        foods.append(class_name)
                    elif class_name_lower in ITEM_CLASSES:
                        category = 'item'
                        # Use Vietnamese name if available
                        if class_name_lower in ITEM_NAMES_VI:
                            class_name = ITEM_NAMES_VI[class_name_lower]
                        other.append(class_name)
                    else:
                        other.append(class_name)
                elif category == 'fruit':
                    fruits.append(class_name)
                
                # Build detection object
                detection = {
                    'class': class_name,
                    'confidence': round(confidence, 2),
                    'category': category,
                    'bbox': {
                        'x': int(x1),
                        'y': int(y1),
                        'width': int(w),
                        'height': int(h)
                    }
                }
                
                # Add advanced info if available
                if ripeness_status:
                    detection['ripeness_status'] = ripeness_status
                if days_left:
                    detection['days_left'] = days_left
                if is_rotten:
                    detection['is_rotten'] = True
                if classification_confidence > 0:
                    detection['classification_confidence'] = round(classification_confidence, 2)
                
                detections.append(detection)
                
                # Draw bounding box with color coding
                if category == 'fruit':
                    color = _ripeness_to_bgr(ripeness_status, is_rotten=is_rotten)
                elif category == 'item':
                    color = (255, 165, 0)  # Orange for items/utensils
                elif category == 'food':
                    color = (255, 200, 0)  # Yellow for food
                else:
                    color = (200, 200, 200)  # Gray for unknown
                
                cv2.rectangle(annotated_img, (x1, y1), (x2, y2), color, 2)
                
                # Draw label
                label = f"{class_name} ({confidence:.0f}%)"
                if category == 'fruit' and ripeness_status:
                    base = class_name.split('(')[0].split(':')[0].strip()
                    label = f"{base} - {ripeness_status} ({confidence:.0f}%)"
                if days_left:
                    label += f" - Hạn: {days_left}"
                
                # Calculate font size
                font_scale = 0.6 if w > 150 else 0.4
                thickness = 2 if w > 150 else 1
                (w_label, h_label), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
                
                # Draw label background and text
                if y1 < 50:
                    y_draw = y2 + 20
                    cv2.rectangle(annotated_img, (x1, y2), (x1 + w_label + 10, y2 + h_label + 15), color, -1)
                    cv2.putText(annotated_img, label, (x1 + 5, y2 + h_label + 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), thickness)
                else:
                    cv2.rectangle(annotated_img, (x1, y1 - h_label - 15), (x1 + w_label + 10, y1), color, -1)
                    cv2.putText(annotated_img, label, (x1 + 5, y1 - 5), 
                               cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), thickness)
        
        # Update inventory
        inventory['total_items'] = len(detections)
        inventory['fruits'] = fruits
        inventory['foods'] = foods
        inventory['other'] = other
        inventory['last_detection'] = datetime.now().isoformat()
        _sync_inventory_to_firebase()
        
        # Save image to disk
        image_filename = None
        try:
            image_filename = f"detection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            image_path = os.path.join(UPLOAD_FOLDER, image_filename)
            cv2.imwrite(image_path, annotated_img)
        except Exception as e:
            print(f"⚠ Error saving image: {e}")

        # Update latest detection cache (for chatbot/UI)
        try:
            latest_detection['updated_at'] = datetime.now().isoformat()
            latest_detection['image_filename'] = image_filename
            latest_detection['detections'] = detections
        except Exception as e:
            print(f"⚠ Error updating latest_detection: {e}")
        
        if has_rotten and image_path:
            for fruit in rotten_fruits:
                alert_key = f"rotten_{fruit}"

                if can_send(alert_key, cooldown=120):
                    msg = (
                        f"🚨 <b>BÁO ĐỘNG TRÁI CÂY BỊ HỎNG</b>\n\n"
                        f"- Loại trái cây: <b>{fruit}</b>\n"
                        f"- Thời gian ghi nhận: <b>{datetime.now().strftime('%H:%M:%S %d/%m/%Y')}</b>\n\n"
                        f"🔍 <b>Khuyến nghị xử lý ngay</b>:\n"
                        f"• Lấy {fruit.lower()} ra khỏi tủ để tránh lây hỏng sang các trái khác.\n"
                        f"• Kiểm tra thêm toàn bộ khay/kệ đang đặt {fruit.lower()}.\n"
                        f"• Nếu tần suất phát hiện hỏng tăng cao, xem lại nhiệt độ và độ ẩm bảo quản."
                    )

                    send_text(msg)
                    send_photo(
                        image_path,
                        caption=f"Hình ảnh AI ghi nhận {fruit} bị hỏng trong tủ lạnh.",
                    )


        # Save to database if available
        session_id = None
        if DB_AVAILABLE:
            try:
                # Save detection session
                session_id = save_detection_session(
                    len(detections),
                    len(fruits),
                    len(foods),
                    len(other),
                    image_path if image_filename else None
                )
                
                # Save individual detections
                if session_id:
                    for det in detections:
                        save_detection(
                            session_id,
                            det['class'],
                            det['confidence'],
                            det['category'],
                            det['bbox']['x'],
                            det['bbox']['y'],
                            det['bbox']['width'],
                            det['bbox']['height'],
                            image_path if image_filename else None
                        )
                
                # Also update inventory table
                save_inventory(len(detections), len(fruits), len(foods), len(other))
                
            except Exception as e:
                print(f"⚠ Error saving detection to database: {e}")
        
        # Convert to base64 for returning
        _, buffer = cv2.imencode('.jpg', annotated_img)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            'success': True,
            'detections': detections,
            'total_items': len(detections),
            'fruit_count': len(fruits),
            'food_count': len(foods),
            'other_count': len(other),
            'annotated_image': img_base64,
            'timestamp': datetime.now().isoformat(),
            'session_id': session_id,
            'saved_to_db': DB_AVAILABLE and session_id is not None,
            'advanced_mode': use_advanced
        })

    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_run_detection)
            try:
                return future.result(timeout=DETECT_TIMEOUT)
            except FuturesTimeoutError:
                return jsonify({'error': 'Timeout', 'message': 'Phân tích ảnh quá lâu, vui lòng thử lại.'}), 504
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e),
            'message': 'Failed to process image'
        }), 500
    

@app.route('/api/camera/stream')
def video_stream():
    """Video streaming route - ESP32 Version"""
    global stream_active
    print("📹 Stream endpoint called (ESP32 Mode)")
    
    stream_active = True # bật cờ
    
    return Response(
        generate_frames(), 
        mimetype='multipart/x-mixed-replace; boundary=frame',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
    )
@app.route('/api/camera/stream/detect')
def video_stream_detect():
    """Video streaming route with YOLO detection - ĐÃ SỬA LỖI 503"""
    global stream_active, camera_stream
    stream_active = True
    
    if camera_stream is None or not camera_stream.isOpened():
        print("ℹ Đang thử tìm Webcam lần cuối trước khi stream...")
        init_camera() 
    
    return Response(
        generate_frames_with_detection(),
        mimetype='multipart/x-mixed-replace; boundary=frame',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
    )
@app.route('/api/camera/start', methods=['POST'])
def start_camera():
    """Start camera stream - Modified to allow ESP32 fallback"""
    global camera_stream, stream_active, selected_camera_source
    
    try:
        # Chỉ thử khởi động Webcam khi chọn webcam
        webcam_status = False
        if selected_camera_source == 'webcam':
            if camera_stream is None or not camera_stream.isOpened():
                webcam_status = init_camera()
            else:
                webcam_status = True

        stream_active = True
        
        if selected_camera_source == 'webcam':
            msg = 'Đã khởi động Webcam thành công.' if webcam_status else 'Webcam chưa sẵn sàng, thử kiểm tra kết nối.'
        else:
            msg = 'Đã chọn ESP32-CAM. Đảm bảo ESP32-CAM đang bật và cùng mạng.'

        return jsonify({
            'success': True, 
            'message': msg
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'message': str(e)}), 500
@app.route('/api/camera/stop', methods=['POST'])
def stop_camera():
    """Stop camera stream and release camera"""
    global stream_active, camera_stream
    
    stream_active = False
    
    with camera_lock:
        if camera_stream is not None:
            try:
                camera_stream.release()
            except:
                pass
            camera_stream = None
    
    # Reset inventory về 0 khi tắt camera để panel thống kê không giữ số cũ
    try:
        reset_inventory()
    except Exception as e:
        print(f"⚠ Error resetting inventory on camera stop: {e}")
    
    return jsonify({'success': True, 'message': 'Camera stopped & inventory cleared'})

@app.route('/api/camera/source', methods=['GET', 'POST'])
def camera_source():
    """Get or set camera source (webcam or esp32)"""
    global selected_camera_source, camera_stream, stream_active
    
    if request.method == 'GET':
        return jsonify({'source': selected_camera_source})
    
    try:
        data = request.get_json(silent=True) or {}
        source = data.get('source', 'webcam')
        
        if source not in ['webcam', 'esp32']:
            return jsonify({'success': False, 'error': 'Invalid source. Must be "webcam" or "esp32"'}), 400
        
        selected_camera_source = source
        
        if source == 'webcam':
            if camera_stream is None or not camera_stream.isOpened():
                init_camera()
        
        return jsonify({
            'success': True,
            'source': selected_camera_source,
            'message': f'Đã chọn camera: {source}'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'message': str(e)}), 500

@app.route('/api/camera/status', methods=['GET'])
def camera_status():
    """Get camera status and test if camera can be opened - silent check, no errors thrown"""
    global camera_stream, stream_active
    
    is_available = False
    error_message = None
    camera_index = None
    
    try:
        # Check if camera is already open
        if camera_stream is not None and camera_stream.isOpened():
            try:
                ret, frame = camera_stream.read()
                if ret and frame is not None:
                    is_available = True
                    camera_index = 0  # Assume current camera
            except Exception as e:
                is_available = False
                error_message = f"Camera read error: {str(e)}"
        else:
            # Try to detect if any camera exists
            backend = _get_camera_backend()
            indices = [0, 1] if sys.platform == 'win32' else [0, 1, 2]
            for idx in indices:
                try:
                    test_cap = cv2.VideoCapture(idx, backend)
                    if test_cap.isOpened():
                        ret, frame = test_cap.read()
                        if ret and frame is not None:
                            is_available = True
                            camera_index = idx
                            test_cap.release()
                            break
                        test_cap.release()
                except Exception as e:
                    if error_message is None:
                        error_message = str(e)
                    continue
    except Exception as e:
        error_message = str(e)
    
    return jsonify({
        'available': is_available,
        'streaming': stream_active,
        'camera_index': camera_index,
        'error': error_message,
        'message': 'Camera sẵn sàng' if is_available else 'Camera chưa khả dụng'
    })

@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    """Get current inventory status"""
    return jsonify({
        'total_items': inventory['total_items'],
        'fruit_count': len(inventory['fruits']),
        'food_count': len(inventory['foods']),
        'other_count': len(inventory['other']),
        'fruits': inventory['fruits'],
        'foods': inventory['foods'],
        'other': inventory['other'],
        'last_detection': inventory['last_detection']
    })

@app.route('/api/telegram/test', methods=['GET'])
def test_telegram_notification():
    """
    Endpoint test đơn giản để kiểm tra Telegram bot có nhận được tin nhắn không.
    Gọi: GET /api/telegram/test và xem:
    - Trên Telegram: có tin nhắn mới hay không
    - Trên console server: log lỗi nếu có vấn đề về token/chat_id/mạng
    """
    try:
        send_text("🔔 Test Telegram từ Smart Fridge IoT: kết nối bot thành công.")
        return jsonify({'success': True, 'message': 'Đã gửi yêu cầu test đến Telegram. Kiểm tra chat bot và console.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/inventory/reset', methods=['POST'])
def reset_inventory_endpoint():
    """Reset inventory về 0 theo yêu cầu từ frontend."""
    try:
        reset_inventory()
        return jsonify({'success': True, 'message': 'Inventory reset to zero'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/detections/latest', methods=['GET'])
def get_latest_detections():
    """Get latest detailed detections (for chatbot/UI)."""
    return jsonify({
        'success': True,
        'updated_at': latest_detection.get('updated_at'),
        'image_filename': latest_detection.get('image_filename'),
        'detections': latest_detection.get('detections', [])
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get comprehensive statistics"""
    # Count unique items
    from collections import Counter
    
    all_items = inventory['fruits'] + inventory['foods'] + inventory['other']
    item_counts = Counter(all_items)
    
    # Get database statistics if available
    db_stats = {}
    if DB_AVAILABLE:
        try:
            from core.database import get_statistics
            db_stats = get_statistics()
        except Exception as e:
            print(f"⚠ Error getting database statistics: {e}")
    
    return jsonify({
        'sensor_data': sensor_data,
        'inventory': {
            'total': inventory['total_items'],
            'fruits': len(inventory['fruits']),
            'foods': len(inventory['foods']),
            'other': len(inventory['other'])
        },
        'item_counts': dict(item_counts),
        'last_update': datetime.now().isoformat(),
        'database_stats': db_stats,
        'database_enabled': DB_AVAILABLE
    })

@app.route('/api/history/sensors', methods=['GET'])
def get_sensor_history():
    """Get sensor reading history from database"""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503
    
    try:
        from core.database import get_sensor_history as db_get_sensor_history
        limit = min(request.args.get('limit', 100, type=int), 500)
        history = db_get_sensor_history(limit)
        return jsonify({
            'success': True,
            'history': history,
            'count': len(history)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history/detections', methods=['GET'])
def get_detection_history():
    """Get detection history from database"""
    if not DB_AVAILABLE:
        return jsonify({'error': 'Database not available'}), 503
    
    try:
        from core.database import get_detection_history as db_get_detection_history
        limit = min(request.args.get('limit', 50, type=int), 200)
        history = db_get_detection_history(limit)
        return jsonify({
            'success': True,
            'history': history,
            'count': len(history)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Firebase (Wokwi) Integration Endpoints
@app.route('/api/firebase/history', methods=['GET'])
def get_firebase_history():
    """Get sensor history from Firebase Realtime Database (Wokwi)"""
    if not FIREBASE_AVAILABLE:
        return jsonify({'error': 'Firebase not available'}), 503
    
    try:
        limit = min(request.args.get('limit', 50, type=int) or 50, 200)
        history = get_firebase_sensor_history(limit)
        return jsonify({
            'success': True,
            'history': history,
            'count': len(history),
            'source': 'firebase_wokwi'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/firebase/control/light', methods=['POST'])
def control_light():
    """Điều khiển đèn LED qua Firebase (Wokwi)"""
    if not FIREBASE_AVAILABLE:
        return jsonify({'error': 'Firebase not available'}), 503
    
    try:
        data = request.json or {}
        value = data.get('value', 0)
        
        # Validate value (0 or 1)
        value = 1 if value else 0
        
        success = set_light_control(value)
        if success:
            return jsonify({
                'success': True,
                'light': value,
                'message': f'Đèn đã được {"bật" if value else "tắt"}'
            })
        else:
            return jsonify({'error': 'Failed to set light control'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/firebase/control/peltier', methods=['POST'])
def control_peltier():
    """Điều khiển Peltier (làm lạnh) qua Firebase (Wokwi)"""
    if not FIREBASE_AVAILABLE:
        return jsonify({'error': 'Firebase not available'}), 503
    
    try:
        data = request.json or {}
        value = data.get('value', 0)
        
        # Validate value (0-255)
        value = max(0, min(255, int(value)))
        
        success = set_peltier_control(value)
        if success:
            return jsonify({
                'success': True,
                'peltier': value,
                'message': f'Peltier đã được đặt ở mức {value}/255'
            })
        else:
            return jsonify({'error': 'Failed to set peltier control'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/firebase/control/status', methods=['GET'])
def get_control_status():
    """Lấy trạng thái điều khiển hiện tại từ Firebase (Wokwi)"""
    if not FIREBASE_AVAILABLE:
        return jsonify({'error': 'Firebase not available'}), 503
    
    try:
        status = get_firebase_control_status()
        return jsonify({
            'success': True,
            'light': status.get('light', 0),
            'peltier': status.get('peltier', 0),
            'source': 'firebase_wokwi'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def firebase_update_worker():
    """Background thread — nguồn dữ liệu theo control mode: hardware hoặc Firebase (Wokwi)."""
    global firebase_latest_data, firebase_update_running

    if not FIREBASE_AVAILABLE and not _hardware_initialized:
        return

    firebase_update_running = True
    last_state = None
    last_push_time = 0
    last_hardware_read = 0
    HARDWARE_READ_INTERVAL = 2.0  # DHT22 cần ≥2s giữa các lần đọc

    print("🔄 Sensor update worker started (mode-aware)")

    while firebase_update_running:
        try:
            import time
            mode = get_control_mode()
            current_time = time.time()

            if mode == 'hardware' and _hardware_initialized:
                if current_time - last_hardware_read >= HARDWARE_READ_INTERVAL:
                    last_hardware_read = current_time
                    try:
                        real_data = read_sensors()
                        temp = real_data.get('temperature')
                        humi = real_data.get('humidity')
                        if temp is not None and humi is not None:
                            target = sensor_data.get('target_temperature', 4)
                            current_state = f"{temp}_{humi}_0_0_{target}"
                            if current_state != last_state or (current_time - last_push_time) > 1.5:
                                firebase_latest_data = {
                                    'temperature': round(float(temp), 1),
                                    'humidity': int(float(humi)),
                                    'door_state': 0,
                                    'pwm': 0,
                                    'target_temperature': sensor_data.get('target_temperature', 4),
                                    'source': 'hardware',
                                    'timestamp': datetime.now().isoformat()
                                }
                                last_state = current_state
                                last_push_time = current_time
                                try:
                                    firebase_update_queue.put_nowait(firebase_latest_data)
                                except Exception:
                                    pass
                    except Exception as e:
                        print(f"⚠ Error reading hardware in worker: {e}")
                time.sleep(0.2)
            else:
                # Chế độ phần mềm hoặc không có hardware → đọc Firebase
                if FIREBASE_AVAILABLE:
                    fb_data = get_latest_sensor_data()
                    if fb_data:
                        cam_ip = fb_data.get('CamIP')
                        if cam_ip:
                            update_camera_ip(cam_ip)
                            
                        temp = fb_data.get('temperature', 0)
                        humi = fb_data.get('humidity', 0)
                        door = fb_data.get('door', 0)
                        pwm = fb_data.get('pwm', 0)
                        target = sensor_data.get('target_temperature', 4)
                        current_state = f"{temp}_{humi}_{door}_{pwm}_{target}"
                        if current_state != last_state or (current_time - last_push_time) > 1.5:
                            firebase_latest_data = {
                                'temperature': round(float(temp), 1),
                                'humidity': int(humi),
                                'door_state': int(door),
                                'pwm': int(pwm),
                                'target_temperature': sensor_data.get('target_temperature', 4),
                                'source': 'firebase',
                                'timestamp': datetime.now().isoformat()
                            }
                            last_state = current_state
                            last_push_time = current_time
                            try:
                                firebase_update_queue.put_nowait(firebase_latest_data)
                            except Exception:
                                pass
                time.sleep(0.2)

        except Exception as e:
            print(f"⚠ Error in sensor update worker: {e}")
            import time
            time.sleep(1)

@app.route('/api/sensors/stream')
def stream_sensors():
    """Server-Sent Events stream for real-time sensor data updates"""
    def generate():
        import time
        last_timestamp = None
        
        # Send initial data immediately from cache
        if firebase_latest_data:
            initial = _enrich_with_door_metrics(firebase_latest_data)
            initial['door_open_alert_seconds'] = DOOR_OPEN_ALERT_SECONDS
            yield f"data: {json.dumps(initial)}\n\n"
            last_timestamp = initial.get('timestamp')
        
        # Listen for updates from background thread
        while True:
            try:
                # Get data from queue (non-blocking với timeout)
                try:
                    new_data = firebase_update_queue.get(timeout=0.1)
                    if new_data and new_data.get('timestamp') != last_timestamp:
                        enriched = _enrich_with_door_metrics(new_data)
                        enriched['door_open_alert_seconds'] = DOOR_OPEN_ALERT_SECONDS
                        last_timestamp = enriched.get('timestamp')
                        yield f"data: {json.dumps(enriched)}\n\n"
                except:
                    # Queue empty, check cache directly
                    if firebase_latest_data and firebase_latest_data.get('timestamp') != last_timestamp:
                        enriched = _enrich_with_door_metrics(firebase_latest_data)
                        enriched['door_open_alert_seconds'] = DOOR_OPEN_ALERT_SECONDS
                        last_timestamp = enriched.get('timestamp')
                        yield f"data: {json.dumps(enriched)}\n\n"
                    time.sleep(0.1)  # Small delay khi không có dữ liệu mới
                    
            except Exception as e:
                print(f"⚠ Error in SSE stream: {e}")
                time.sleep(0.5)
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )

# Simulated IoT sensor updates (replace with actual sensor reading code)
def read_temperature_sensor():
    """
    Example function to read from actual temperature sensor
    Replace this with your actual sensor code
    
    For Raspberry Pi with DHT22:
    import Adafruit_DHT
    sensor = Adafruit_DHT.DHT22
    pin = 4
    humidity, temperature = Adafruit_DHT.read_retry(sensor, pin)
    return temperature, humidity
    """
    # Simulated reading with slight variation
    import random
    temp = sensor_data['temperature'] + random.uniform(-0.5, 0.5)
    humidity = sensor_data['humidity'] + random.randint(-2, 2)
    return temp, humidity

def update_oled_display(temp, humidity, items, status):
    """
    Example function to update OLED display
    Replace with your actual OLED code
    
    For SSD1306 OLED:
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1306
    from PIL import Image, ImageDraw, ImageFont
    
    serial = i2c(port=1, address=0x3C)
    device = ssd1306(serial)
    
    image = Image.new('1', (128, 64))
    draw = ImageDraw.Draw(image)
    
    draw.text((0, 0), f"Temp: {temp}°C", fill=255)
    draw.text((0, 10), f"Humidity: {humidity}%", fill=255)
    draw.text((0, 20), f"Items: {items}", fill=255)
    draw.text((0, 30), f"Status: {status}", fill=255)
    
    device.display(image)
    """
    pass

if __name__ == '__main__':
    print("=" * 50)
    print("🧊 Smart Fridge IoT Server Starting...")
    print("=" * 50)
    print(f"📡 Server will run on: http://localhost:5001")
    print(f"🤖 YOLO Model: {MODEL_PATH}")
    print(f"📁 Upload folder: {UPLOAD_FOLDER}")
    print(f"📷 Camera stream: /api/camera/stream")
    print(f"📷 Camera with detection: /api/camera/stream/detect")
    print("=" * 50)
    
    # Start sensor update thread (Firebase hoặc hardware tùy mode)
    if FIREBASE_AVAILABLE or _hardware_initialized:
        firebase_update_thread = threading.Thread(target=firebase_update_worker, daemon=True)
        firebase_update_thread.start()
        print("✓ Sensor real-time update thread started")

    # Start door monitor thread (Telegram alert sync with dashboard rule)
    _door_monitor_running = True
    _door_monitor_thread = threading.Thread(target=_door_monitor_worker, daemon=True, name="DoorMonitor")
    _door_monitor_thread.start()
    print(f"✓ Door monitor thread started (threshold={DOOR_OPEN_ALERT_SECONDS}s)")

    # Cleanup on exit
    import atexit
    def cleanup():
        global camera_stream, stream_active, firebase_update_running, _door_monitor_running
        stream_active = False
        firebase_update_running = False
        _door_monitor_running = False
        if camera_stream is not None:
            camera_stream.release()
        if HARDWARE_AVAILABLE:
            cleanup_hardware()
    
    atexit.register(cleanup)
    
    # Run Flask app
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5001)
