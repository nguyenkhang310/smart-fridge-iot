"""
Firebase Integration Module
Kết nối với Firebase Realtime Database từ Wokwi ESP32
Sử dụng REST API trực tiếp với legacy token
"""
import requests
import time
from datetime import datetime
from typing import Dict, Optional, List
from urllib.parse import quote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Firebase Configuration từ Wokwi project
FIREBASE_DATABASE_URL = "https://testtulanh-default-rtdb.asia-southeast1.firebasedatabase.app"

# Legacy token từ Wokwi
FIREBASE_AUTH_TOKEN = "ymJAPlPa6CBPtKRvIzRvdagYggAt4e0oEJNoigWP"

# Initialize Firebase
firebase_initialized = False

# Tạo session với retry strategy
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=0.3,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "PUT"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)

# Cache dữ liệu để dùng khi lỗi (cache tối đa 30 giây)
cached_sensor_data = None
cache_timestamp = None
CACHE_MAX_AGE = 30  # Giây

def init_firebase():
    """Khởi tạo kết nối Firebase"""
    global firebase_initialized
    try:
        # Test connection bằng cách đọc root hoặc Control path (nhỏ và luôn có)
        test_url = f"{FIREBASE_DATABASE_URL}/Control.json?auth={FIREBASE_AUTH_TOKEN}"
        try:
            response = session.get(test_url, timeout=7, verify=True)
        except (requests.exceptions.SSLError, requests.exceptions.RequestException) as e:
            print(f"⚠ Firebase test connection error: {e}")
            return False
        if response.status_code == 200:
            firebase_initialized = True
            print("✓ Firebase initialized successfully")
            return True
        else:
            print(f"⚠ Firebase test connection failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"⚠ Firebase initialization error: {e}")
        return False

def get_latest_sensor_data() -> Optional[Dict]:
    """
    Lấy dữ liệu cảm biến mới nhất từ Firebase
    Ưu tiên /Current (nếu ESP32 cập nhật mỗi 2-3 giây), fallback /History
    Có retry logic và cache để xử lý lỗi kết nối
    """
    global cached_sensor_data, cache_timestamp
    
    try:
        if not firebase_initialized:
            # Trả về cache nếu có
            if cached_sensor_data:
                return cached_sensor_data
            return None
        
        # Ưu tiên đọc /Current (ESP32 cập nhật mỗi 2-3 giây) - nhanh hơn /History (30 giây)
        url_current = f"{FIREBASE_DATABASE_URL}/Current.json?auth={FIREBASE_AUTH_TOKEN}"
        try:
            resp = session.get(url_current, timeout=5, verify=True)
            if resp.status_code == 200:
                current_data = resp.json()
                if current_data and isinstance(current_data, dict) and 'Temp' in current_data:
                    result = {
                        'temperature': current_data.get('Temp', 0),
                        'humidity': current_data.get('Humi', 0),
                        'door': current_data.get('Door', 0),
                        'pwm': current_data.get('PWM', 0),
                        'timestamp': 'current',
                        'last_update': datetime.now().isoformat(),
                        'source': 'firebase_wokwi'
                    }
                    cached_sensor_data = result
                    cache_timestamp = time.time()
                    return result
        except Exception:
            pass  # Fallback to History
        
        # Fallback: đọc từ History (ESP32 push mỗi 30 giây)
        url = f"{FIREBASE_DATABASE_URL}/History.json?auth={FIREBASE_AUTH_TOKEN}"
        
        # Thử kết nối với timeout vừa phải và retry
        try:
            response = session.get(url, timeout=7, verify=True)
        except requests.exceptions.SSLError as ssl_err:
            # Chỉ log lỗi nếu không có cache hoặc cache quá cũ
            if not cached_sensor_data or (cache_timestamp and time.time() - cache_timestamp > CACHE_MAX_AGE):
                print(f"⚠ SSL Error: {ssl_err}")
            # Trả về cache nếu có và còn mới
            if cached_sensor_data and cache_timestamp and (time.time() - cache_timestamp <= CACHE_MAX_AGE):
                return cached_sensor_data
            return None
        except requests.exceptions.RequestException as req_err:
            # Chỉ log lỗi nếu không có cache hoặc cache quá cũ
            if not cached_sensor_data or (cache_timestamp and time.time() - cache_timestamp > CACHE_MAX_AGE):
                print(f"⚠ Request Error: {req_err}")
            # Trả về cache nếu có và còn mới
            if cached_sensor_data and cache_timestamp and (time.time() - cache_timestamp <= CACHE_MAX_AGE):
                return cached_sensor_data
            return None
        
        if response.status_code != 200:
            # Trả về cache nếu request failed và cache còn mới
            if cached_sensor_data and cache_timestamp and (time.time() - cache_timestamp <= CACHE_MAX_AGE):
                return cached_sensor_data
            return None
        
        data = response.json()
        if data is None or len(data) == 0:
            # Trả về cache nếu không có dữ liệu và cache còn mới
            if cached_sensor_data and cache_timestamp and (time.time() - cache_timestamp <= CACHE_MAX_AGE):
                return cached_sensor_data
            return None
        
        # Lấy record cuối cùng (key lớn nhất về mặt thời gian)
        latest_key = None
        latest_data = None
        
        # Sắp xếp keys để lấy key cuối cùng
        if isinstance(data, dict):
            sorted_keys = sorted(data.keys())
            if sorted_keys:
                latest_key = sorted_keys[-1]
                latest_data = data[latest_key]
        
        if latest_data:
            result = {
                'temperature': latest_data.get('Temp', 0),
                'humidity': latest_data.get('Humi', 0),
                'door': latest_data.get('Door', 0),
                'pwm': latest_data.get('PWM', 0),
                'timestamp': latest_key,
                'last_update': datetime.now().isoformat()
            }
            
            # Lưu vào cache
            cached_sensor_data = result
            cache_timestamp = time.time()
            
            return result
        
        # Trả về cache nếu không parse được
        if cached_sensor_data:
            return cached_sensor_data
        return None
        
    except Exception as e:
        print(f"⚠ Error reading sensor data from Firebase: {e}")
        # Trả về cache khi có lỗi
        if cached_sensor_data:
            return cached_sensor_data
        return None

def get_sensor_history(limit: int = 50) -> List[Dict]:
    """
    Lấy lịch sử dữ liệu cảm biến từ Firebase
    """
    try:
        if not firebase_initialized:
            return []
        
        # Đọc tất cả History và lấy N record cuối cùng
        url = f"{FIREBASE_DATABASE_URL}/History.json?auth={FIREBASE_AUTH_TOKEN}"
        try:
            response = session.get(url, timeout=7, verify=True)
        except (requests.exceptions.SSLError, requests.exceptions.RequestException) as e:
            print(f"⚠ Error reading history: {e}")
            return []
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        if data is None:
            return []
        
        result = []
        for key, value in data.items():
            result.append({
                'timestamp': key,
                'temperature': value.get('Temp', 0),
                'humidity': value.get('Humi', 0),
                'door': value.get('Door', 0),
                'pwm': value.get('PWM', 0)
            })
        
        # Sắp xếp theo timestamp (từ cũ đến mới) và lấy N record cuối cùng
        result.sort(key=lambda x: x['timestamp'])
        return result[-limit:] if len(result) > limit else result
    except Exception as e:
        print(f"⚠ Error reading sensor history from Firebase: {e}")
        return []

def set_light_control(value: int) -> bool:
    """
    Điều khiển đèn LED qua Firebase
    value: 0 = tắt, 1 = bật
    """
    try:
        if not firebase_initialized:
            return False
        
        url = f"{FIREBASE_DATABASE_URL}/Control/Light.json?auth={FIREBASE_AUTH_TOKEN}"
        try:
            response = session.put(url, json=value, timeout=7, verify=True)
        except (requests.exceptions.SSLError, requests.exceptions.RequestException) as e:
            print(f"⚠ Error setting light: {e}")
            return False
        
        if response.status_code == 200:
            print(f"✓ Light control set to: {value}")
            return True
        else:
            print(f"⚠ Failed to set light control: {response.status_code}")
            return False
    except Exception as e:
        print(f"⚠ Error setting light control: {e}")
        return False

def set_peltier_control(value: int) -> bool:
    """
    Điều khiển Peltier (làm lạnh) qua Firebase
    value: 0-255 (PWM value)
    """
    try:
        if not firebase_initialized:
            return False
        
        # Giới hạn giá trị PWM trong khoảng 0-255
        value = max(0, min(255, int(value)))
        
        url = f"{FIREBASE_DATABASE_URL}/Control/Peltier.json?auth={FIREBASE_AUTH_TOKEN}"
        try:
            response = session.put(url, json=value, timeout=7, verify=True)
        except (requests.exceptions.SSLError, requests.exceptions.RequestException) as e:
            print(f"⚠ Error setting peltier: {e}")
            return False
        
        if response.status_code == 200:
            print(f"✓ Peltier control set to: {value}")
            return True
        else:
            print(f"⚠ Failed to set peltier control: {response.status_code}")
            return False
    except Exception as e:
        print(f"⚠ Error setting peltier control: {e}")
        return False

def set_target_temperature(value: float) -> bool:
    """
    Ghi nhiệt độ mục tiêu lên Firebase /Control/TargetTemp
    ESP32 có thể đọc để hiển thị trên OLED (tùy chọn)
    """
    try:
        if not firebase_initialized:
            return False
        url = f"{FIREBASE_DATABASE_URL}/Control/TargetTemp.json?auth={FIREBASE_AUTH_TOKEN}"
        try:
            response = session.put(url, json=round(float(value), 1), timeout=7, verify=True)
        except (requests.exceptions.SSLError, requests.exceptions.RequestException) as e:
            print(f"⚠ Error setting target temp: {e}")
            return False
        return response.status_code == 200
    except Exception as e:
        print(f"⚠ Error in set_target_temperature: {e}")
        return False

def get_control_status() -> Dict:
    """
    Lấy trạng thái điều khiển hiện tại từ Firebase
    """
    try:
        if not firebase_initialized:
            return {'light': 0, 'peltier': 0}
        
        url = f"{FIREBASE_DATABASE_URL}/Control.json?auth={FIREBASE_AUTH_TOKEN}"
        try:
            response = session.get(url, timeout=7, verify=True)
        except (requests.exceptions.SSLError, requests.exceptions.RequestException) as e:
            print(f"⚠ Error reading control status: {e}")
            return {'light': 0, 'peltier': 0}
        
        if response.status_code == 200:
            data = response.json()
            return {
                'light': data.get('Light', 0) if data else 0,
                'peltier': data.get('Peltier', 0) if data else 0
            }
        else:
            return {'light': 0, 'peltier': 0}
    except Exception as e:
        print(f"⚠ Error reading control status: {e}")
        return {'light': 0, 'peltier': 0}

# Initialize Firebase on import
if init_firebase():
    print("✓ Firebase integration module loaded")
else:
    print("⚠ Firebase integration module loaded but initialization failed")
