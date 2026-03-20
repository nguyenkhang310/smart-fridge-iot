"""
Script test các API endpoints của Flask app với Firebase
"""
import requests
import json
import time

BASE_URL = "http://localhost:5001"

def test_endpoints():
    """Test các API endpoints"""
    print("=" * 60)
    print("🧪 Testing Flask API Endpoints với Firebase")
    print("=" * 60)
    
    # Test 1: Lấy dữ liệu cảm biến
    print("\n1. Testing GET /api/sensors...")
    try:
        response = requests.get(f"{BASE_URL}/api/sensors", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Status: {response.status_code}")
            print(f"   📊 Dữ liệu cảm biến:")
            print(f"      - Nhiệt độ: {data.get('temperature', 'N/A')}°C")
            print(f"      - Độ ẩm: {data.get('humidity', 'N/A')}%")
            print(f"      - Nguồn: {data.get('source', 'N/A')}")
            print(f"      - Cập nhật: {data.get('last_update', 'N/A')}")
        else:
            print(f"   ✗ Failed: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"   ⚠ Server chưa chạy. Hãy chạy: python app.py")
        return
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 2: Lấy lịch sử từ Firebase
    print("\n2. Testing GET /api/firebase/history...")
    try:
        response = requests.get(f"{BASE_URL}/api/firebase/history?limit=5", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Status: {response.status_code}")
            print(f"   📈 Lịch sử: {data.get('count', 0)} records")
            if data.get('history'):
                latest = data['history'][-1]
                print(f"   Record mới nhất:")
                print(f"      - Nhiệt độ: {latest.get('temperature', 'N/A')}°C")
                print(f"      - Độ ẩm: {latest.get('humidity', 'N/A')}%")
        else:
            print(f"   ✗ Failed: {response.status_code}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 3: Lấy trạng thái điều khiển
    print("\n3. Testing GET /api/firebase/control/status...")
    try:
        response = requests.get(f"{BASE_URL}/api/firebase/control/status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Status: {response.status_code}")
            print(f"   🎛️ Trạng thái điều khiển:")
            print(f"      - Đèn: {'Bật' if data.get('light') == 1 else 'Tắt'}")
            print(f"      - Peltier: {data.get('peltier', 0)}/255")
        else:
            print(f"   ✗ Failed: {response.status_code}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 4: Điều khiển đèn (test toggle)
    print("\n4. Testing POST /api/firebase/control/light...")
    try:
        # Lấy trạng thái hiện tại
        status_resp = requests.get(f"{BASE_URL}/api/firebase/control/status", timeout=5)
        current_light = status_resp.json().get('light', 0) if status_resp.status_code == 200 else 0
        
        # Toggle đèn
        new_value = 0 if current_light == 1 else 1
        response = requests.post(
            f"{BASE_URL}/api/firebase/control/light",
            json={"value": new_value},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Status: {response.status_code}")
            print(f"   💡 Đèn đã được {'bật' if new_value == 1 else 'tắt'}")
            
            # Đợi 1 giây và kiểm tra lại
            time.sleep(1)
            status_resp = requests.get(f"{BASE_URL}/api/firebase/control/status", timeout=5)
            if status_resp.status_code == 200:
                updated_light = status_resp.json().get('light', 0)
                print(f"   ✓ Xác nhận: Đèn hiện tại {'bật' if updated_light == 1 else 'tắt'}")
        else:
            print(f"   ✗ Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Test hoàn tất!")
    print("=" * 60)
    print("\n💡 Lưu ý:")
    print("   - Đảm bảo project Wokwi đang chạy simulation")
    print("   - Dữ liệu được cập nhật mỗi 30 giây từ ESP32")
    print("   - Có thể xem web interface tại: http://localhost:5001")

if __name__ == "__main__":
    test_endpoints()
