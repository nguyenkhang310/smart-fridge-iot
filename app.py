from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
import sys
import cv2
import numpy as np

# Giảm log OpenCV (tránh MSMF/obsensor spam trên Windows)
cv2.setLogLevel(3)
from ultralytics import YOLO
import json
from datetime import datetime
import os
from PIL import Image
import io
import base64
import torch
import threading
from queue import Queue

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
MODEL_PATH = 'yolov8n.pt' 
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
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

# Load YOLO model
try:
    model = YOLO(MODEL_PATH)
    print(f"✓ YOLO model loaded successfully: {MODEL_PATH}")
except Exception as e:
    print(f"⚠ Warning: Could not load YOLO model: {e}")
    print("  Download model using: pip install ultralytics")
    import traceback
    traceback.print_exc()
    model = None

# Import hardware integration (optional)
try:
    from hardware_integration import (
        init_hardware, read_sensors, set_temperature_control,
        update_display, update_status_leds, cleanup_hardware
    )
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    print("⚠ hardware_integration.py not found - using simulation mode")

# Initialize hardware if available
if HARDWARE_AVAILABLE:
    init_hardware()

# Import database integration (optional)
try:
    from database import (
        init_database, save_sensor_reading, get_latest_sensor_reading,
        save_inventory, get_latest_inventory, save_detection_session,
        save_detection, save_temperature_setting, get_statistics
    )
    DB_AVAILABLE = True
except ImportError as e:
    DB_AVAILABLE = False
    print(f"⚠ database.py not found - database features disabled: {e}")

# Initialize database if available
if DB_AVAILABLE:
    if init_database():
        print("✓ MySQL database initialized")
    else:
        print("⚠ Database initialization failed - continuing without database")
        DB_AVAILABLE = False

# Import Firebase integration (optional)
try:
    from firebase_integration import (
        init_firebase, get_latest_sensor_data, get_sensor_history as get_firebase_history,
        set_light_control, set_peltier_control, set_target_temperature as set_firebase_target_temp,
        get_control_status as get_firebase_control_status
    )
    FIREBASE_AVAILABLE = True
    if init_firebase():
        print("✓ Firebase Realtime Database connected (Wokwi)")
    else:
        print("⚠ Firebase initialization failed - continuing without Firebase")
        FIREBASE_AVAILABLE = False
except ImportError as e:
    FIREBASE_AVAILABLE = False
    print(f"⚠ firebase_integration.py not found - Firebase features disabled: {e}")

# Simulated sensor data storage
sensor_data = {
    'temperature': 4.5,
    'humidity': 65,
    'target_temperature': 4,
    'status': 'normal',
    'last_update': datetime.now().isoformat()
}

# Inventory storage
inventory = {
    'total_items': 0,
    'fruits': [],
    'foods': [],
    'other': [],
    'last_detection': None
}

# Fruit and food categories based on COCO dataset
FRUIT_CLASSES = ['apple', 'banana', 'orange', 'broccoli', 'carrot']
FOOD_CLASSES = ['sandwich', 'hot dog', 'pizza', 'donut', 'cake', 'bottle', 
                'cup', 'fork', 'knife', 'spoon', 'bowl']

# Camera stream variables
camera_stream = None
camera_lock = threading.Lock()
stream_active = False

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
    """Generate video frames for streaming"""
    global camera_stream, stream_active
    
    frame_count = 0
    print("🎬 Starting frame generation...")
    
    while stream_active:
        try:
            with camera_lock:
                if camera_stream is None or not camera_stream.isOpened():
                    print("⚠ Camera stream closed")
                    break
                
                success, frame = camera_stream.read()
                if not success:
                    print(f"⚠ Failed to read frame")
                    break
            
            if frame is not None:
                # Encode frame as JPEG
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    frame_bytes = buffer.tobytes()
                    frame_count += 1
                    if frame_count % 30 == 0:  # Log every 30 frames
                        print(f"📊 Streamed {frame_count} frames")
                    
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                else:
                    print("⚠ Failed to encode frame")
            else:
                print("⚠ Frame is None")
            
            # Small delay to control frame rate
            threading.Event().wait(0.033)  # ~30 FPS
            
        except Exception as e:
            print(f"✗ Error in generate_frames: {e}")
            import traceback
            traceback.print_exc()
            break
    
    print(f"🛑 Stream stopped. Total frames: {frame_count}")

def generate_frames_with_detection():
    """Generate video frames with YOLO detection"""
    global camera_stream, stream_active, model
    
    while stream_active:
        with camera_lock:
            if camera_stream is None or not camera_stream.isOpened():
                break
            
            success, frame = camera_stream.read()
            if not success:
                break
        
        if frame is not None and model is not None:
            try:
                # Run YOLO detection
                results = model(frame, conf=0.5, verbose=False)
                # Draw results on frame
                annotated_frame = results[0].plot()
            except:
                annotated_frame = frame
        else:
            annotated_frame = frame
        
        if annotated_frame is not None:
            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        # Small delay to control frame rate
        threading.Event().wait(0.033)  # ~30 FPS

# Don't initialize camera on startup - only when user requests it
# init_camera()  # Commented out - camera will be initialized on demand

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('.', 'smart_fridge.html')

@app.route('/logo-hcm-ute.png')
def serve_logo():
    """Serve the university logo"""
    return send_from_directory('.', 'logo-hcm-ute.png')

@app.route('/api/sensors', methods=['GET'])
def get_sensors():
    """Get current sensor readings from Firebase (Wokwi), hardware, or simulation"""
    # Ưu tiên đọc từ Firebase (Wokwi ESP32)
    if FIREBASE_AVAILABLE:
        try:
            fb_data = get_latest_sensor_data()
            if fb_data:
                sensor_data['temperature'] = fb_data.get('temperature', sensor_data['temperature'])
                sensor_data['humidity'] = fb_data.get('humidity', sensor_data['humidity'])
                sensor_data['door_state'] = fb_data.get('door', 0)
                sensor_data['pwm'] = fb_data.get('pwm', 0)
                sensor_data['last_update'] = fb_data.get('last_update', datetime.now().isoformat())
                sensor_data['source'] = 'firebase_wokwi'
                
                # Cập nhật status dựa trên nhiệt độ
                temp = sensor_data['temperature']
                if temp > 25:
                    sensor_data['status'] = 'hot'
                elif temp > 20:
                    sensor_data['status'] = 'warming'
                else:
                    sensor_data['status'] = 'normal'
        except Exception as e:
            print(f"⚠ Error reading from Firebase: {e}")
            # Fallback to hardware or simulation
    
    # Fallback to hardware if Firebase not available
    if not FIREBASE_AVAILABLE or 'source' not in sensor_data:
        if HARDWARE_AVAILABLE:
            # Read from actual hardware
            real_data = read_sensors()
            sensor_data.update(real_data)
            sensor_data['source'] = 'hardware'
        else:
            # Simulation mode - update timestamp
            sensor_data['last_update'] = datetime.now().isoformat()
            sensor_data['source'] = 'simulation'
    
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
    
    return jsonify(sensor_data)

@app.route('/api/temperature', methods=['POST'])
def set_temperature():
    """Set target temperature and control hardware / Firebase (Wokwi ESP32)"""
    data = request.json
    target_temp = data.get('temperature')
    
    if target_temp is None:
        return jsonify({'error': 'Temperature value required'}), 400
    
    target_temp = float(target_temp)
    previous_temp = sensor_data['target_temperature']
    sensor_data['target_temperature'] = target_temp
    sensor_data['last_update'] = datetime.now().isoformat()
    
    # Lấy nhiệt độ hiện tại TRỰC TIẾP từ Firebase (Wokwi) - không dùng sensor_data cũ
    current_temp = target_temp
    if FIREBASE_AVAILABLE:
        try:
            fb_data = get_latest_sensor_data()
            if fb_data and fb_data.get('temperature') is not None:
                current_temp = float(fb_data.get('temperature', target_temp))
                sensor_data['temperature'] = current_temp
        except Exception as e:
            print(f"⚠ Could not fetch current temp from Firebase: {e}")
            current_temp = sensor_data.get('temperature', target_temp)
    else:
        current_temp = sensor_data.get('temperature', target_temp)
    
    try:
        current_temp = float(current_temp)
    except (TypeError, ValueError):
        current_temp = target_temp
    
    # Gửi lệnh PWM tới Firebase (Wokwi ESP32) - ESP32 đọc /Control/Peltier
    pwm_sent = None
    firebase_error = None
    if FIREBASE_AVAILABLE:
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
    
    # Control hardware if available (Raspberry Pi thật)
    if HARDWARE_AVAILABLE:
        control_status = set_temperature_control(target_temp, current_temp)
        sensor_data['status'] = control_status
    
    # Thông báo lỗi nếu Firebase không gửi được
    msg = f'Nhiệt độ đã cài đặt: {target_temp}°C'
    if firebase_error:
        msg += f' (⚠ Lỗi Firebase: {firebase_error})'
    
    return jsonify({
        'success': True,
        'target_temperature': sensor_data['target_temperature'],
        'pwm_sent': pwm_sent,
        'current_temp': current_temp,
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
    """YOLO object detection endpoint"""
    if model is None:
        return jsonify({
            'error': 'YOLO model not loaded',
            'message': 'Please install ultralytics and download model'
        }), 500
    
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    file = request.files['image']
    
    try:
        # Read image
        image_bytes = file.read()
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Run YOLO detection
        results = model(img, conf=0.5)  # Confidence threshold 0.5
        
        # Process results
        detections = []
        fruits = []
        foods = []
        other = []
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                # Get box coordinates
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                confidence = float(box.conf[0].cpu().numpy())
                class_id = int(box.cls[0].cpu().numpy())
                class_name = model.names[class_id]
                
                # Categorize object
                if class_name.lower() in FRUIT_CLASSES:
                    category = 'fruit'
                    fruits.append(class_name)
                elif class_name.lower() in FOOD_CLASSES:
                    category = 'food'
                    foods.append(class_name)
                else:
                    category = 'other'
                    other.append(class_name)
                
                detection = {
                    'class': class_name,
                    'confidence': round(confidence, 2),
                    'category': category,
                    'bbox': {
                        'x': int(x1),
                        'y': int(y1),
                        'width': int(x2 - x1),
                        'height': int(y2 - y1)
                    }
                }
                detections.append(detection)
        
        # Update inventory
        inventory['total_items'] = len(detections)
        inventory['fruits'] = fruits
        inventory['foods'] = foods
        inventory['other'] = other
        inventory['last_detection'] = datetime.now().isoformat()
        
        # Save image to disk
        image_filename = None
        try:
            image_filename = f"detection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            image_path = os.path.join(UPLOAD_FOLDER, image_filename)
            cv2.imwrite(image_path, img)
        except Exception as e:
            print(f"⚠ Error saving image: {e}")
        
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
        
        # Draw bounding boxes on image
        annotated_img = results[0].plot()
        
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
            'saved_to_db': DB_AVAILABLE and session_id is not None
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Failed to process image'
        }), 500

@app.route('/api/camera/stream')
def video_stream():
    """Video streaming route - plain camera feed"""
    global stream_active, camera_stream
    
    print("📹 Stream endpoint called")
    
    # Ensure camera is initialized before streaming
    if camera_stream is None or not camera_stream.isOpened():
        print("⚠ Camera not initialized, trying to init...")
        if not init_camera():
            print("✗ Failed to initialize camera for stream")
            return "Camera not available", 503
    
    print("✓ Starting video stream...")
    stream_active = True
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
    """Video streaming route with YOLO detection"""
    global stream_active, camera_stream
    stream_active = True
    
    # Ensure camera is initialized before streaming (same as video_stream)
    if camera_stream is None or not camera_stream.isOpened():
        if not init_camera():
            return "Camera not available", 503
    
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
    """Start camera stream - initialize camera only when requested"""
    global camera_stream, stream_active
    
    # Initialize camera if not already initialized
    if camera_stream is None or not camera_stream.isOpened():
        success = init_camera()
        if not success:
            return jsonify({
                'success': False,
                'error': 'Camera not available',
                'message': 'Không thể khởi động camera. Vui lòng:\n' +
                          '1. Kiểm tra camera đã kết nối\n' +
                          '2. Cấp quyền truy cập camera (trên macOS: System Settings > Privacy > Camera)\n' +
                          '3. Đảm bảo không có ứng dụng khác đang sử dụng camera\n' +
                          '4. Thử restart server'
            }), 500
    
    # Verify camera is still working
    try:
        ret, frame = camera_stream.read()
        if not ret or frame is None:
            # Camera lost, try to reinitialize
            if not init_camera():
                return jsonify({
                    'success': False,
                    'error': 'Camera read failed',
                    'message': 'Không thể đọc từ camera. Vui lòng kiểm tra lại.'
                }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': f'Lỗi camera: {str(e)}'
        }), 500
    
    stream_active = True
    return jsonify({'success': True, 'message': 'Camera started successfully'})

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
    
    return jsonify({'success': True, 'message': 'Camera stopped'})

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
            from database import get_statistics
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
        from database import get_sensor_history
        limit = request.args.get('limit', 100, type=int)
        history = get_sensor_history(limit)
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
        from database import get_detection_history
        limit = request.args.get('limit', 50, type=int)
        history = get_detection_history(limit)
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
        limit = request.args.get('limit', 50, type=int)
        history = get_firebase_history(limit)
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
        data = request.json
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
        data = request.json
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
    """Background thread để check Firebase liên tục và update cache"""
    global firebase_latest_data, firebase_update_running
    
    if not FIREBASE_AVAILABLE:
        return
    
    firebase_update_running = True
    last_timestamp = None
    
    print("🔄 Firebase update worker started")
    
    while firebase_update_running:
        try:
            import time
            fb_data = get_latest_sensor_data()
            
            if fb_data:
                current_timestamp = fb_data.get('timestamp', '')
                
                # Chỉ update nếu có dữ liệu mới
                if current_timestamp and current_timestamp != last_timestamp:
                    firebase_latest_data = {
                        'temperature': round(fb_data.get('temperature', 0), 1),
                        'humidity': int(fb_data.get('humidity', 0)),
                        'door_state': fb_data.get('door', 0),
                        'pwm': fb_data.get('pwm', 0),
                        'source': 'firebase_wokwi',
                        'timestamp': current_timestamp,
                        'last_update': fb_data.get('last_update', datetime.now().isoformat())
                    }
                    last_timestamp = current_timestamp
                    # Put vào queue để SSE stream biết có dữ liệu mới
                    try:
                        firebase_update_queue.put_nowait(firebase_latest_data)
                    except:
                        pass  # Queue full, skip
            
            # Check mỗi 0.2 giây để realtime hơn (ESP32 push /Current mỗi 2s)
            time.sleep(0.2)
            
        except Exception as e:
            print(f"⚠ Error in Firebase update worker: {e}")
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
            yield f"data: {json.dumps(firebase_latest_data)}\n\n"
            last_timestamp = firebase_latest_data.get('timestamp')
        
        # Listen for updates from background thread
        while True:
            try:
                # Get data from queue (non-blocking với timeout)
                try:
                    new_data = firebase_update_queue.get(timeout=0.1)
                    if new_data and new_data.get('timestamp') != last_timestamp:
                        last_timestamp = new_data.get('timestamp')
                        yield f"data: {json.dumps(new_data)}\n\n"
                except:
                    # Queue empty, check cache directly
                    if firebase_latest_data and firebase_latest_data.get('timestamp') != last_timestamp:
                        last_timestamp = firebase_latest_data.get('timestamp')
                        yield f"data: {json.dumps(firebase_latest_data)}\n\n"
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
    
    # Start Firebase update thread
    if FIREBASE_AVAILABLE:
        firebase_update_thread = threading.Thread(target=firebase_update_worker, daemon=True)
        firebase_update_thread.start()
        print("✓ Firebase real-time update thread started")
    
    # Cleanup on exit
    import atexit
    def cleanup():
        global camera_stream, stream_active, firebase_update_running
        stream_active = False
        firebase_update_running = False
        if camera_stream is not None:
            camera_stream.release()
        if HARDWARE_AVAILABLE:
            cleanup_hardware()
    
    atexit.register(cleanup)
    
    # Run Flask app
    app.run(debug=True, host='0.0.0.0', port=5001)
