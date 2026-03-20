"""
Script test kết nối Firebase từ Wokwi
Kiểm tra xem Firebase có hoạt động đúng không
"""
import requests
import json

# Firebase Configuration
FIREBASE_DATABASE_URL = "https://testtulanh-default-rtdb.asia-southeast1.firebasedatabase.app"
FIREBASE_AUTH_TOKEN = "ymJAPlPa6CBPtKRvIzRvdagYggAt4e0oEJNoigWP"

def test_firebase_connection():
    """Test kết nối Firebase"""
    print("=" * 60)
    print("🔍 Testing Firebase Connection...")
    print("=" * 60)
    
    # Test 1: Kiểm tra root database
    print("\n1. Testing root database access...")
    try:
        url = f"{FIREBASE_DATABASE_URL}/.json?auth={FIREBASE_AUTH_TOKEN}"
        response = requests.get(url, timeout=10)
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Root access successful")
            if data:
                print(f"   Available paths: {list(data.keys())}")
            else:
                print(f"   ⚠ Database is empty")
        else:
            print(f"   ✗ Failed: {response.text}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 2: Kiểm tra History path
    print("\n2. Testing /History path...")
    try:
        url = f"{FIREBASE_DATABASE_URL}/History.json?auth={FIREBASE_AUTH_TOKEN}"
        response = requests.get(url, timeout=10)
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if data:
                print(f"   ✓ History path accessible")
                # Lấy record cuối cùng
                sorted_keys = sorted(data.keys())
                if sorted_keys:
                    latest_key = sorted_keys[-1]
                    latest_data = data[latest_key]
                    print(f"   Total records: {len(data)}")
                    print(f"   Latest record:")
                    print(f"     - Timestamp: {latest_key}")
                    print(f"     - Temperature: {latest_data.get('Temp', 'N/A')}°C")
                    print(f"     - Humidity: {latest_data.get('Humi', 'N/A')}%")
                    print(f"     - Door: {latest_data.get('Door', 'N/A')}")
                    print(f"     - PWM: {latest_data.get('PWM', 'N/A')}")
            else:
                print(f"   ⚠ History path is empty (no data yet)")
        else:
            print(f"   ✗ Failed: {response.text}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 3: Kiểm tra Control path
    print("\n3. Testing /Control path...")
    try:
        url = f"{FIREBASE_DATABASE_URL}/Control.json?auth={FIREBASE_AUTH_TOKEN}"
        response = requests.get(url, timeout=10)
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if data:
                print(f"   ✓ Control path accessible")
                print(f"   Current control values:")
                print(f"     - Light: {data.get('Light', 'N/A')}")
                print(f"     - Peltier: {data.get('Peltier', 'N/A')}")
            else:
                print(f"   ⚠ Control path is empty")
        else:
            print(f"   ✗ Failed: {response.text}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 4: Test write permission (write và đọc lại)
    print("\n4. Testing write permission...")
    try:
        test_path = "/TestConnection"
        url = f"{FIREBASE_DATABASE_URL}{test_path}.json?auth={FIREBASE_AUTH_TOKEN}"
        test_data = {"test": "connection", "timestamp": "test"}
        
        # Write
        response = requests.put(url, json=test_data, timeout=10)
        print(f"   Write Status Code: {response.status_code}")
        
        if response.status_code == 200:
            # Read back
            read_response = requests.get(url, timeout=10)
            if read_response.status_code == 200:
                print(f"   ✓ Write permission OK")
                # Clean up
                requests.delete(url, timeout=10)
                print(f"   ✓ Test data cleaned up")
            else:
                print(f"   ⚠ Write OK but read failed")
        else:
            print(f"   ✗ Write failed: {response.text}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    test_firebase_connection()
