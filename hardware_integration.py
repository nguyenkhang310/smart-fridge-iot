"""
Hardware Integration Module for Smart Fridge IoT
Tích hợp phần cứng thật với Flask backend
"""

import os
from datetime import datetime

# Flag để bật/tắt phần cứng thật
# Set USE_HARDWARE = True khi chạy trên Raspberry Pi với phần cứng thật
USE_HARDWARE = os.getenv('USE_HARDWARE', 'False').lower() == 'true'

# Global hardware objects
dht_sensor = None
dht_pin = None
oled_device = None
relay_pin = None
led_pins = None
camera = None

def init_hardware():
    """Khởi tạo tất cả phần cứng"""
    global dht_sensor, dht_pin, oled_device, relay_pin, led_pins, camera
    
    if not USE_HARDWARE:
        print("⚠ Hardware mode disabled - using simulation")
        return False
    
    try:
        from raspberry_pi_config import (
            setup_dht22_sensor, setup_oled_display, setup_relay,
            setup_status_leds, setup_picamera
        )
        
        print("🔧 Initializing hardware components...")
        
        # Setup DHT22 sensor
        dht_sensor, dht_pin = setup_dht22_sensor(gpio_pin=4)
        if dht_sensor:
            print("✓ DHT22 sensor initialized")
        
        # Setup OLED display
        oled_device = setup_oled_display()
        
        # Setup relay for temperature control
        relay_pin = setup_relay(gpio_pin=17)
        
        # Setup status LEDs
        led_pins = setup_status_leds(red_pin=22, green_pin=27, blue_pin=23)
        
        # Setup camera (optional)
        camera = setup_picamera()
        
        print("✓ Hardware initialization complete!")
        return True
        
    except Exception as e:
        print(f"✗ Hardware initialization error: {e}")
        print("⚠ Falling back to simulation mode")
        return False

def read_sensors():
    """Đọc dữ liệu từ cảm biến thật hoặc trả về dữ liệu mô phỏng"""
    global dht_sensor, dht_pin
    
    if USE_HARDWARE and dht_sensor and dht_pin:
        try:
            from raspberry_pi_config import read_dht22
            sensor_data = read_dht22(dht_sensor, dht_pin)
            
            if sensor_data['status'] == 'success':
                return {
                    'temperature': sensor_data['temperature'],
                    'humidity': sensor_data['humidity'],
                    'status': 'normal',
                    'last_update': datetime.now().isoformat()
                }
            else:
                # Fallback to simulation on error
                return get_simulated_data()
        except Exception as e:
            print(f"✗ Sensor read error: {e}")
            return get_simulated_data()
    else:
        # Simulation mode
        return get_simulated_data()

def get_simulated_data():
    """Trả về dữ liệu mô phỏng"""
    import random
    return {
        'temperature': round(4.0 + random.uniform(-0.5, 0.5), 1),
        'humidity': round(60 + random.uniform(-5, 5), 1),
        'status': 'normal',
        'last_update': datetime.now().isoformat()
    }

def set_temperature_control(target_temp, current_temp):
    """Điều khiển nhiệt độ thật hoặc mô phỏng"""
    global relay_pin
    
    if USE_HARDWARE and relay_pin:
        try:
            from raspberry_pi_config import control_temperature
            status = control_temperature(relay_pin, current_temp, target_temp)
            return status
        except Exception as e:
            print(f"✗ Temperature control error: {e}")
            return "error"
    else:
        # Simulation - just return status
        if current_temp > target_temp + 0.5:
            return "cooling"
        elif current_temp < target_temp - 0.5:
            return "idle"
        else:
            return "maintaining"

def update_display(temp, humidity, items, fruits, status):
    """Cập nhật OLED display"""
    global oled_device
    
    if USE_HARDWARE and oled_device:
        try:
            from raspberry_pi_config import update_oled
            update_oled(oled_device, temp, humidity, items, fruits, status)
        except Exception as e:
            print(f"✗ OLED update error: {e}")

def update_status_leds(status):
    """Cập nhật LED trạng thái"""
    global led_pins
    
    if USE_HARDWARE and led_pins:
        try:
            from raspberry_pi_config import set_status_color
            set_status_color(led_pins, status)
        except Exception as e:
            print(f"✗ LED update error: {e}")

def capture_camera_image(filename='uploads/fridge_capture.jpg'):
    """Chụp ảnh từ camera thật hoặc trả về None"""
    global camera
    
    if USE_HARDWARE and camera:
        try:
            from raspberry_pi_config import capture_image
            return capture_image(camera, filename)
        except Exception as e:
            print(f"✗ Camera capture error: {e}")
            return None
    else:
        return None

def cleanup_hardware():
    """Dọn dẹp GPIO và tắt phần cứng"""
    global relay_pin, led_pins
    
    if USE_HARDWARE:
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()
            print("✓ GPIO cleanup complete")
        except:
            pass

# Initialize hardware on import
if __name__ != '__main__':
    init_hardware()

