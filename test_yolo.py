"""
Test script for YOLO object detection
Run this to test if YOLO is working correctly
"""

from ultralytics import YOLO
import cv2
import numpy as np
from PIL import Image
import requests
from io import BytesIO

def test_yolo_local():
    """Test YOLO with local image"""
    print("=" * 50)
    print("Testing YOLO Object Detection")
    print("=" * 50)
    
    try:
        # Load model
        print("\n1. Loading YOLO model...")
        model = YOLO('yolov8n.pt')
        print("   ✓ Model loaded successfully!")
        
        # Create a test image with colored rectangles (simulating objects)
        print("\n2. Creating test image...")
        img = np.ones((480, 640, 3), dtype=np.uint8) * 255
        
        # Draw some colored rectangles to simulate objects
        cv2.rectangle(img, (100, 100), (200, 200), (0, 255, 0), -1)  # Green
        cv2.rectangle(img, (300, 150), (450, 300), (0, 0, 255), -1)  # Red
        cv2.rectangle(img, (500, 50), (600, 150), (255, 0, 0), -1)   # Blue
        
        cv2.imwrite('test_image.jpg', img)
        print("   ✓ Test image created: test_image.jpg")
        
        # Run detection
        print("\n3. Running object detection...")
        results = model('test_image.jpg', conf=0.25)
        print("   ✓ Detection completed!")
        
        # Process results
        print("\n4. Detection Results:")
        for result in results:
            boxes = result.boxes
            print(f"   Found {len(boxes)} objects")
            
            for i, box in enumerate(boxes):
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                class_name = model.names[class_id]
                
                print(f"   Object {i+1}:")
                print(f"      Class: {class_name}")
                print(f"      Confidence: {confidence:.2%}")
        
        # Save annotated image
        annotated = results[0].plot()
        cv2.imwrite('test_result.jpg', annotated)
        print("\n   ✓ Result saved: test_result.jpg")
        
        print("\n" + "=" * 50)
        print("✓ YOLO Test Completed Successfully!")
        print("=" * 50)
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nPlease install required packages:")
        print("   pip install ultralytics opencv-python")
        return False

def test_yolo_with_real_image():
    """Test YOLO with a real image from internet"""
    print("\n" + "=" * 50)
    print("Testing YOLO with Real Image")
    print("=" * 50)
    
    try:
        # Download sample image
        print("\n1. Downloading sample image...")
        url = "https://ultralytics.com/images/bus.jpg"
        response = requests.get(url)
        img = Image.open(BytesIO(response.content))
        img.save('sample_image.jpg')
        print("   ✓ Image downloaded: sample_image.jpg")
        
        # Load model
        print("\n2. Loading YOLO model...")
        model = YOLO('yolov8n.pt')
        print("   ✓ Model loaded!")
        
        # Run detection
        print("\n3. Running detection...")
        results = model('sample_image.jpg')
        
        # Process results
        print("\n4. Detection Results:")
        for result in results:
            boxes = result.boxes
            print(f"   Found {len(boxes)} objects:")
            
            # Count objects by class
            from collections import Counter
            classes = [model.names[int(box.cls[0])] for box in boxes]
            class_counts = Counter(classes)
            
            for class_name, count in class_counts.items():
                print(f"      - {class_name}: {count}")
        
        # Save result
        annotated = results[0].plot()
        cv2.imwrite('sample_result.jpg', annotated)
        print("\n   ✓ Result saved: sample_result.jpg")
        
        print("\n" + "=" * 50)
        print("✓ Real Image Test Completed!")
        print("=" * 50)
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

def test_api_endpoint():
    """Test the Flask API endpoint"""
    print("\n" + "=" * 50)
    print("Testing API Endpoint")
    print("=" * 50)
    
    try:
        # Check if server is running
        print("\n1. Checking if server is running...")
        response = requests.get('http://localhost:5000/api/sensors')
        
        if response.status_code == 200:
            print("   ✓ Server is running!")
            print(f"   Sensor Data: {response.json()}")
        else:
            print("   ✗ Server returned error")
            return False
        
        # Test detection endpoint
        print("\n2. Testing detection endpoint...")
        if not os.path.exists('test_image.jpg'):
            print("   Creating test image...")
            img = np.ones((480, 640, 3), dtype=np.uint8) * 255
            cv2.imwrite('test_image.jpg', img)
        
        with open('test_image.jpg', 'rb') as f:
            files = {'image': f}
            response = requests.post('http://localhost:5000/api/detect', files=files)
        
        if response.status_code == 200:
            data = response.json()
            print("   ✓ Detection successful!")
            print(f"   Total items: {data.get('total_items', 0)}")
            print(f"   Fruits: {data.get('fruit_count', 0)}")
            print(f"   Foods: {data.get('food_count', 0)}")
        else:
            print(f"   ✗ Detection failed: {response.text}")
            return False
        
        print("\n" + "=" * 50)
        print("✓ API Test Completed!")
        print("=" * 50)
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("   ✗ Cannot connect to server")
        print("   Please start the server first: python app.py")
        return False
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

if __name__ == '__main__':
    import os
    
    print("\n🧊 Smart Fridge IoT - YOLO Test Suite\n")
    
    # Run tests
    print("Running tests...\n")
    
    test1 = test_yolo_local()
    
    if test1:
        test2 = test_yolo_with_real_image()
    
    # Ask if user wants to test API
    print("\n" + "=" * 50)
    test_api = input("\nDo you want to test the API endpoint? (y/n): ")
    
    if test_api.lower() == 'y':
        test_api_endpoint()
    
    print("\n✓ All tests completed!\n")
