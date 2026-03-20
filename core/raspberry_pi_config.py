"""
Raspberry Pi IoT Configuration for Smart Fridge
Includes sensor reading, OLED display, and GPIO control
"""

import time
from datetime import datetime

# ============================================
# DHT22 Temperature & Humidity Sensor
# ============================================

def setup_dht22_sensor(gpio_pin=4):
    """
    Setup DHT22 sensor on Raspberry Pi
    
    Installation:
    pip install Adafruit_DHT
    
    Wiring:
    DHT22 VCC  -> RPi 3.3V (Pin 1)
    DHT22 GND  -> RPi GND (Pin 6)
    DHT22 DATA -> RPi GPIO4 (Pin 7)
    """
    try:
        import Adafruit_DHT
        sensor = Adafruit_DHT.DHT22
        return sensor, gpio_pin
    except ImportError:
        print("⚠ Adafruit_DHT not installed")
        print("Install with: pip install Adafruit_DHT")
        return None, None

def read_dht22(sensor, pin):
    """Read temperature and humidity from DHT22"""
    try:
        import Adafruit_DHT
        humidity, temperature = Adafruit_DHT.read_retry(sensor, pin)
        
        if humidity is not None and temperature is not None:
            return {
                'temperature': round(temperature, 1),
                'humidity': round(humidity, 1),
                'status': 'success',
                'timestamp': datetime.now().isoformat()
            }
        else:
            return {
                'temperature': None,
                'humidity': None,
                'status': 'error',
                'error': 'Failed to read sensor'
            }
    except Exception as e:
        return {
            'temperature': None,
            'humidity': None,
            'status': 'error',
            'error': str(e)
        }

# ============================================
# OLED Display (SSD1306)
# ============================================

def setup_oled_display():
    """
    Setup SSD1306 OLED display
    
    Installation:
    pip install luma.oled
    
    Wiring (I2C):
    OLED VCC -> RPi 3.3V (Pin 1)
    OLED GND -> RPi GND (Pin 6)
    OLED SDA -> RPi GPIO2/SDA (Pin 3)
    OLED SCL -> RPi GPIO3/SCL (Pin 5)
    
    Enable I2C:
    sudo raspi-config -> Interface Options -> I2C -> Enable
    """
    try:
        from luma.core.interface.serial import i2c
        from luma.core.render import canvas
        from luma.oled.device import ssd1306
        from PIL import ImageFont
        
        # Create I2C interface
        serial = i2c(port=1, address=0x3C)
        
        # Create device
        device = ssd1306(serial, width=128, height=64)
        
        print("✓ OLED display initialized")
        return device
        
    except ImportError:
        print("⚠ luma.oled not installed")
        print("Install with: pip install luma.oled")
        return None
    except Exception as e:
        print(f"✗ OLED setup error: {e}")
        return None

def update_oled(device, temp, humidity, items, fruits, status):
    """Update OLED display with current data"""
    if device is None:
        return
    
    try:
        from luma.core.render import canvas
        from PIL import ImageFont
        
        # Try to load a font, fallback to default if not available
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 8)
        except:
            font = ImageFont.load_default()
            font_small = font
        
        with canvas(device) as draw:
            # Title
            draw.text((0, 0), "SMART FRIDGE", fill="white", font=font)
            draw.line((0, 12, 128, 12), fill="white")
            
            # Temperature
            draw.text((0, 16), f"Temp: {temp}°C", fill="white", font=font)
            
            # Humidity
            draw.text((0, 28), f"Humidity: {humidity}%", fill="white", font=font)
            
            # Items
            draw.text((0, 40), f"Items: {items} | Fruits: {fruits}", fill="white", font=font_small)
            
            # Status
            status_text = f"Status: {status}"
            draw.text((0, 52), status_text, fill="white", font=font_small)
            
    except Exception as e:
        print(f"✗ OLED update error: {e}")

# ============================================
# Relay Control for Temperature
# ============================================

def setup_relay(gpio_pin=17):
    """
    Setup relay for compressor control
    
    Installation:
    pip install RPi.GPIO
    
    Wiring:
    Relay VCC -> RPi 5V (Pin 2)
    Relay GND -> RPi GND (Pin 6)
    Relay IN  -> RPi GPIO17 (Pin 11)
    """
    try:
        import RPi.GPIO as GPIO
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(gpio_pin, GPIO.OUT)
        GPIO.output(gpio_pin, GPIO.LOW)  # Relay off initially
        
        print(f"✓ Relay initialized on GPIO{gpio_pin}")
        return gpio_pin
        
    except ImportError:
        print("⚠ RPi.GPIO not installed")
        print("Install with: pip install RPi.GPIO")
        return None
    except Exception as e:
        print(f"✗ Relay setup error: {e}")
        return None

def control_temperature(relay_pin, current_temp, target_temp):
    """Control compressor based on temperature"""
    try:
        import RPi.GPIO as GPIO
        
        # Simple on/off control with hysteresis
        HYSTERESIS = 0.5
        
        if current_temp > target_temp + HYSTERESIS:
            # Turn on compressor (cooling)
            GPIO.output(relay_pin, GPIO.HIGH)
            return "cooling"
        elif current_temp < target_temp - HYSTERESIS:
            # Turn off compressor
            GPIO.output(relay_pin, GPIO.LOW)
            return "idle"
        else:
            # Maintain current state
            return "maintaining"
            
    except Exception as e:
        print(f"✗ Temperature control error: {e}")
        return "error"

# ============================================
# LED Status Indicators
# ============================================

def setup_status_leds(red_pin=22, green_pin=27, blue_pin=23):
    """
    Setup RGB LED for status indication
    
    Wiring:
    LED Red   -> RPi GPIO22 (Pin 15) + 220Ω resistor
    LED Green -> RPi GPIO27 (Pin 13) + 220Ω resistor  
    LED Blue  -> RPi GPIO23 (Pin 16) + 220Ω resistor
    LED GND   -> RPi GND (Pin 6)
    """
    try:
        import RPi.GPIO as GPIO
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(red_pin, GPIO.OUT)
        GPIO.setup(green_pin, GPIO.OUT)
        GPIO.setup(blue_pin, GPIO.OUT)
        
        # Turn off all LEDs
        GPIO.output(red_pin, GPIO.LOW)
        GPIO.output(green_pin, GPIO.LOW)
        GPIO.output(blue_pin, GPIO.LOW)
        
        print("✓ Status LEDs initialized")
        return (red_pin, green_pin, blue_pin)
        
    except Exception as e:
        print(f"✗ LED setup error: {e}")
        return None

def set_status_color(led_pins, status):
    """Set LED color based on status"""
    if led_pins is None:
        return
    
    try:
        import RPi.GPIO as GPIO
        red_pin, green_pin, blue_pin = led_pins
        
        # Turn off all first
        GPIO.output(red_pin, GPIO.LOW)
        GPIO.output(green_pin, GPIO.LOW)
        GPIO.output(blue_pin, GPIO.LOW)
        
        # Set color based on status
        if status == "normal":
            GPIO.output(green_pin, GPIO.HIGH)  # Green
        elif status == "warning":
            GPIO.output(red_pin, GPIO.HIGH)
            GPIO.output(green_pin, GPIO.HIGH)  # Yellow
        elif status == "error":
            GPIO.output(red_pin, GPIO.HIGH)  # Red
        elif status == "cooling":
            GPIO.output(blue_pin, GPIO.HIGH)  # Blue
            
    except Exception as e:
        print(f"✗ LED control error: {e}")

# ============================================
# Main IoT Loop Example
# ============================================

def main_iot_loop():
    """
    Main loop for IoT operations
    Reads sensors, updates display, controls temperature
    """
    print("=" * 50)
    print("🧊 Smart Fridge IoT System Starting...")
    print("=" * 50)
    
    # Setup components
    print("\nInitializing hardware components...")
    
    sensor, dht_pin = setup_dht22_sensor(gpio_pin=4)
    oled_device = setup_oled_display()
    relay_pin = setup_relay(gpio_pin=17)
    led_pins = setup_status_leds(red_pin=22, green_pin=27, blue_pin=23)
    
    # Configuration
    target_temperature = 4.0
    inventory_count = 0
    fruit_count = 0
    
    print("\n✓ Hardware initialization complete!")
    print(f"Target temperature: {target_temperature}°C")
    print("\nStarting main loop... (Press Ctrl+C to stop)\n")
    
    try:
        while True:
            # Read sensors
            if sensor and dht_pin:
                sensor_data = read_dht22(sensor, dht_pin)
                
                if sensor_data['status'] == 'success':
                    temp = sensor_data['temperature']
                    humidity = sensor_data['humidity']
                    
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] " +
                          f"Temp: {temp}°C | Humidity: {humidity}%")
                    
                    # Determine status
                    if temp > target_temperature + 2:
                        status = "warning"
                    elif temp > target_temperature + 1:
                        status = "cooling"
                    else:
                        status = "normal"
                    
                    # Control temperature
                    if relay_pin:
                        compressor_status = control_temperature(relay_pin, temp, target_temperature)
                        print(f"          Compressor: {compressor_status}")
                    
                    # Update OLED
                    if oled_device:
                        update_oled(oled_device, temp, humidity, 
                                  inventory_count, fruit_count, status)
                    
                    # Update status LEDs
                    if led_pins:
                        set_status_color(led_pins, status)
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] " +
                          f"Sensor error: {sensor_data.get('error', 'Unknown')}")
            
            # Wait before next reading
            time.sleep(5)  # Read every 5 seconds
            
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
        
        # Cleanup GPIO
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup()
            print("✓ GPIO cleanup complete")
        except:
            pass
        
        print("✓ IoT system stopped")

# ============================================
# Camera Module Setup (Optional)
# ============================================

def setup_picamera():
    """
    Setup Raspberry Pi Camera Module
    
    Installation:
    pip install picamera2
    
    Enable camera:
    sudo raspi-config -> Interface Options -> Camera -> Enable
    """
    try:
        from picamera2 import Picamera2
        
        camera = Picamera2()
        config = camera.create_still_configuration()
        camera.configure(config)
        
        print("✓ Pi Camera initialized")
        return camera
        
    except ImportError:
        print("⚠ picamera2 not installed")
        print("Install with: pip install picamera2")
        return None
    except Exception as e:
        print(f"✗ Camera setup error: {e}")
        return None

def capture_image(camera, filename='fridge_contents.jpg'):
    """Capture image from Pi Camera"""
    try:
        camera.start()
        time.sleep(2)  # Warm up time
        camera.capture_file(filename)
        camera.stop()
        
        print(f"✓ Image captured: {filename}")
        return filename
        
    except Exception as e:
        print(f"✗ Image capture error: {e}")
        return None

# ============================================
# Testing Functions
# ============================================

def test_hardware():
    """Test all hardware components"""
    print("\n" + "=" * 50)
    print("Testing Hardware Components")
    print("=" * 50 + "\n")
    
    # Test DHT22
    print("1. Testing DHT22 sensor...")
    sensor, pin = setup_dht22_sensor()
    if sensor:
        data = read_dht22(sensor, pin)
        if data['status'] == 'success':
            print(f"   ✓ Temperature: {data['temperature']}°C")
            print(f"   ✓ Humidity: {data['humidity']}%")
        else:
            print(f"   ✗ Error: {data.get('error')}")
    
    # Test OLED
    print("\n2. Testing OLED display...")
    oled = setup_oled_display()
    if oled:
        update_oled(oled, 4.5, 65, 12, 8, "TEST")
        print("   ✓ OLED display updated")
        time.sleep(3)
    
    # Test Relay
    print("\n3. Testing relay...")
    relay = setup_relay()
    if relay:
        import RPi.GPIO as GPIO
        print("   Turning relay ON...")
        GPIO.output(relay, GPIO.HIGH)
        time.sleep(2)
        print("   Turning relay OFF...")
        GPIO.output(relay, GPIO.LOW)
        print("   ✓ Relay test complete")
    
    # Test LEDs
    print("\n4. Testing status LEDs...")
    leds = setup_status_leds()
    if leds:
        colors = [("normal", "Green"), ("warning", "Yellow"), 
                 ("error", "Red"), ("cooling", "Blue")]
        for status, color in colors:
            print(f"   Testing {color}...")
            set_status_color(leds, status)
            time.sleep(1)
        print("   ✓ LED test complete")
    
    # Cleanup
    try:
        import RPi.GPIO as GPIO
        GPIO.cleanup()
    except:
        pass
    
    print("\n" + "=" * 50)
    print("✓ Hardware Test Complete")
    print("=" * 50)

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        test_hardware()
    else:
        main_iot_loop()
