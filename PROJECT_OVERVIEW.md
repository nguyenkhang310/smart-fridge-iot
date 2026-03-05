## 1. Giới thiệu dự án

Dự án xây dựng một hệ thống **Tủ lạnh thông minh IoT** có khả năng:
- Giám sát nhiệt độ, độ ẩm và trạng thái tủ lạnh theo thời gian thực.
- Điều khiển quá trình làm lạnh (Peltier / máy lạnh) từ xa.
- Theo dõi số lượng và loại thực phẩm bên trong tủ.
- Nhận diện trái cây, đánh giá độ chín/hỏng bằng AI (YOLO + mô hình phân loại).
- Gửi cảnh báo qua Telegram khi phát hiện trái cây hỏng hoặc bất thường.

Hệ thống hướng đến kịch bản triển khai thực tế (ESP32, cảm biến, camera, tủ lạnh thật) nhưng vẫn có chế độ mô phỏng để demo.

---

## 2. Kiến trúc tổng quan

### 2.1 Các thành phần chính

- **Thiết bị IoT (ESP32 / Wokwi)**  
  - Đọc cảm biến nhiệt độ, độ ẩm, trạng thái cửa tủ.  
  - Điều khiển Peltier / quạt làm lạnh và đèn LED.  
  - Gửi dữ liệu thời gian thực lên Firebase Realtime Database (mục `/Current`).  
  - Nhận lệnh điều khiển từ các nút `/Control` trên Firebase (Peltier, Light, TargetTemp).

- **ESP32-CAM hoặc Webcam**  
  - Cung cấp luồng ảnh/video của bên trong tủ lạnh.  
  - Có hai chế độ camera:
    - `webcam`: dùng camera máy tính.  
    - `esp32`: dùng ESP32-CAM chụp và trả về ảnh.

- **Server Flask (file `app.py`)**  
  - Chạy trên máy tính / Raspberry Pi.  
  - Đóng vai trò:
    - API backend cho web dashboard.  
    - Cầu nối với Firebase, MySQL và phần cứng thật (qua `hardware_integration.py`).  
    - Nơi chạy mô hình YOLO (phát hiện trái cây) và mô hình phân loại (độ chín/hỏng).

- **Giao diện web (`smart_fridge.html`)**  
  - Dashboard trình duyệt, hiển thị số liệu cảm biến và tồn kho.  
  - Giao diện điều khiển nhiệt độ, xem camera, upload ảnh để phân tích.  
  - Thiết kế theo phong cách dashboard hiện đại, không dùng emoji.

- **Cơ sở dữ liệu MySQL (`database.py`)**  
  - Lưu lịch sử đo cảm biến.  
  - Lưu các phiên nhận diện, từng đối tượng, tồn kho tổng hợp.  
  - Phục vụ thống kê dài hạn và xuất báo cáo.

- **Firebase Realtime Database (`firebase_integration.py`)**  
  - Kênh giao tiếp thời gian thực với ESP32 / Wokwi.  
  - Được dùng ưu tiên cho dữ liệu cảm biến nếu sẵn sàng.

- **Telegram Bot (`telegram_notify.py`)**  
  - Gửi tin nhắn và ảnh cảnh báo tới người dùng:
    - Khi phát hiện trái cây hỏng.  
    - Khi nhận diện được vật thể mới (có giới hạn tần suất).

### 2.2 Luồng dữ liệu chính

1. ESP32 đọc cảm biến và đẩy dữ liệu lên Firebase.  
2. Flask server gọi API Firebase, cập nhật `sensor_data` và phát SSE cho web.  
3. Web dashboard nhận sự kiện SSE, cập nhật UI, OLED ảo và các progress bar.  
4. Khi người dùng đổi nhiệt độ mục tiêu:
   - Web gửi POST `/api/temperature`.  
   - Flask ghi TargetTemp và PWM tương ứng lên Firebase, ESP32 đọc và điều chỉnh phần cứng.
5. Khi người dùng upload ảnh hoặc dùng camera:
   - Ảnh được gửi tới `/api/detect`.  
   - Flask chạy YOLO + phân loại, trả về danh sách đối tượng, độ chín, hạn sử dụng gợi ý, ảnh đã vẽ bounding box.  
   - Web hiển thị kết quả, cập nhật thống kê tồn kho.  
   - Nếu phát hiện trái cây hỏng, server lưu ảnh và gửi cảnh báo Telegram.

---

## 3. Phần mềm phía server (Flask)

### 3.1 Các file quan trọng

- `app.py`  
  - Khởi tạo Flask app và cấu hình CORS.  
  - Load các mô hình YOLO:  
    - `DETECTION_MODEL_PATH`: mô hình phát hiện trái cây.  
    - `CLASSIFICATION_MODEL_PATH`: mô hình phân loại độ chín/hỏng.  
    - `MODEL_PATH`: mô hình YOLO dự phòng.  
  - Quản lý kết nối camera, ESP32-CAM, Firebase, MySQL và phần cứng.

- `hardware_integration.py`  
  - Các hàm: khởi tạo phần cứng, đọc cảm biến, điều khiển nhiệt độ, cập nhật màn hình OLED thật, LED trạng thái.  
  - Cho phép chuyển đổi giữa chế độ thật và mô phỏng, tùy theo việc import có thành công hay không.

- `database.py`  
  - Hàm khởi tạo schema MySQL.  
  - Hàm ghi/lấy lịch sử cảm biến, tồn kho, thống kê theo thời gian.  
  - Hàm lưu từng phiên detect và từng vật thể detect.

- `firebase_integration.py`  
  - Kết nối Firebase Realtime Database (Wokwi).  
  - Hàm đọc dữ liệu mới nhất, lịch sử, ghi lệnh điều khiển.

- `telegram_notify.py`  
  - Cấu hình bot và chat ID.  
  - `send_text`, `send_photo`: gửi thông báo.  
  - `can_send`: cơ chế chống spam, giới hạn tần suất cho từng loại cảnh báo.

### 3.2 Các API chính

- `GET /`  
  - Trả về file `smart_fridge.html` – giao diện dashboard.

- `GET /api/sensors`  
  - Ưu tiên lấy dữ liệu cảm biến từ Firebase (`get_latest_sensor_data`).  
  - Nếu Firebase không có, fallback sang phần cứng thật hoặc mô phỏng.  
  - Có thể ghi định kỳ vào MySQL.

- `POST /api/temperature`  
  - Nhận `temperature` (mục tiêu) từ web.  
  - Đọc nhiệt độ hiện tại (ưu tiên Firebase).  
  - Tính toán PWM cho Peltier và ghi lên Firebase.  
  - Lưu lịch sử điều chỉnh nhiệt độ vào MySQL.

- `GET /api/oled`  
  - Trả về dữ liệu hiển thị cho màn hình OLED (nhiệt độ, độ ẩm, số lượng vật phẩm, trạng thái).

- `POST /api/detect`  
  - Nhận ảnh upload hoặc chụp trực tiếp từ ESP32-CAM.  
  - Chạy YOLO phát hiện trái cây/đồ ăn/đồ vật.  
  - Nếu có mô hình phân loại: xác định trái cây chín, sắp hỏng, hoặc hỏng.  
  - Tính hạn sử dụng gợi ý dựa trên loại trái cây và độ chín.  
  - Vẽ bounding box lên ảnh, lưu ảnh và thông tin vào MySQL nếu cấu hình.  
  - Gửi cảnh báo Telegram nếu phát hiện trái cây hỏng.

- `GET /api/camera/stream`, `GET /api/camera/stream/detect`  
  - Trả về luồng MJPEG từ ESP32-CAM hoặc webcam.  
  - Bản `/detect` thêm lớp xử lý YOLO trực tiếp trên luồng.

- `POST /api/camera/start`, `POST /api/camera/stop`, `GET/POST /api/camera/source`, `GET /api/camera/status`  
  - Điều khiển việc bật/tắt stream, chọn nguồn camera (webcam / esp32) và kiểm tra trạng thái.

- `GET /api/inventory`, `GET /api/stats`, các API `/api/history/...`  
  - Lấy số liệu tồn kho hiện tại, thống kê tổng hợp và lịch sử từ database.

- Nhóm API `/api/firebase/control/...`  
  - Gửi lệnh trực tiếp tới Firebase (bật/tắt đèn, đặt PWM Peltier, lấy trạng thái điều khiển).

---

## 4. Giao diện web dashboard

File `smart_fridge.html` đặt toàn bộ HTML/CSS/JS phía client:

- **Header trường và tiêu đề đồ án**  
  - Logo HCM-UTE, tên tiếng Việt và tiếng Anh của trường.  
  - Tiêu đề “Hệ thống Tủ lạnh Thông minh IoT”.

- **System Status Bar**  
  - Hiển thị trạng thái API, Firebase, Database, Camera bằng chấm màu và text.  
  - Cập nhật thời gian nhận dữ liệu cảm biến gần nhất.

- **Card Nhiệt độ, Độ ẩm, Điều chỉnh nhiệt độ, OLED**  
  - Nhiệt độ và độ ẩm: số lớn, thanh tiến độ, cảnh báo khi vượt ngưỡng.  
  - Slider điều chỉnh nhiệt độ mục tiêu, nút gửi lệnh, toast thông báo kết quả.  
  - Vùng hiển thị OLED giả lập: nhiệt độ, độ ẩm, trạng thái, số lượng vật phẩm và thời gian.

- **Thống kê tồn kho**  
  - Card tổng hợp số lượng: tổng vật phẩm, trái cây, thực phẩm, khác.  
  - Dữ liệu lấy từ kết quả nhận diện gần nhất.

- **Khu vực Camera & Nhận diện AI**  
  - Nút chọn nguồn camera (Webcam / ESP32-CAM) và nút tắt camera.  
  - Khung live-stream video.  
  - Vùng upload ảnh (kéo thả / chọn file) và canvas hiển thị ảnh đã tải lên.  
  - Nút “Phân tích bằng AI” gọi `/api/detect`, nút “Xóa ảnh” để reset.  
  - Khối “Kết quả nhận diện”:
    - Cho phép lọc theo Tất cả / Trái cây / Thực phẩm / Khác.  
    - Bảng thông tin: đối tượng, loại, độ tin cậy, trạng thái (chín/hỏng), hạn sử dụng dự kiến.  
    - Hàng trái cây hỏng được tô nền đỏ nhạt và viền đỏ.

- **Cập nhật theo thời gian thực**  
  - Dùng Server-Sent Events (`/api/sensors/stream`) để cập nhật nhiệt độ/độ ẩm và trạng thái ngay lập tức, fallback sang polling nếu SSE không hỗ trợ.

---

## 5. Xử lý AI: phát hiện và đánh giá trái cây

### 5.1 Phát hiện (YOLO)

- Sử dụng mô hình YOLO (Ultralytics) để phát hiện bounding box của trái cây và các vật thể khác trên ảnh.  
- Kết quả gồm:
  - `class_name`, `confidence`, `bbox` (x, y, width, height).  
  - Phân loại sơ bộ theo nhóm: trái cây, thực phẩm, vật dụng, khác.

### 5.2 Phân loại độ chín/hỏng

- Với mỗi bounding box thuộc nhóm trái cây:
  - Cắt vùng ảnh tương ứng.  
  - Cho qua mô hình phân loại độ chín/hỏng.  
  - Sinh ra:
    - `ripeness_status`: chín, ương, xanh, hỏng, hoặc trạng thái khác tùy mô hình.  
    - `days_left`: số ngày/hạn sử dụng gợi ý, tra trong bảng `FRUIT_SHELF_LIFE` theo loại trái cây và độ chín.

- Nếu kết quả cho thấy trái cây hỏng:
  - Gộp thông tin vào danh sách cảnh báo.  
  - Lưu ảnh annotate ra thư mục `uploads/`.  
  - Gửi tin nhắn và ảnh cảnh báo qua Telegram (có giới hạn tần suất cho từng loại trái cây).

---

## 6. Cơ sở dữ liệu và thống kê

- MySQL lưu các bảng:
  - Lịch sử đọc cảm biến (thời gian, nhiệt độ, độ ẩm, trạng thái, nhiệt độ mục tiêu).  
  - Phiên nhận diện (thời gian, số lượng đối tượng, đường dẫn ảnh annotate).  
  - Từng đối tượng trong mỗi phiên (tên lớp, độ tin cậy, loại, bounding box, trạng thái chín/hỏng).  
  - Bảng tồn kho tổng hợp theo thời điểm.

- API `/api/stats`, `/api/history/...` cho phép:
  - Lấy thống kê tổng hợp cho dashboard.  
  - Lấy lịch sử chi tiết để phục vụ phân tích và viết báo cáo.

---

## 7. Hạ tầng triển khai

- **Máy chủ chạy Flask**  
  - Có thể là máy tính cá nhân hoặc Raspberry Pi gắn gần tủ lạnh.  
  - File dịch vụ `smart-fridge.service` cho phép chạy Flask như một service trên Linux (tự khởi động cùng hệ thống).

- **Quy trình triển khai cơ bản**  
  - Cài Python, các thư viện cần thiết (Flask, ultralytics, OpenCV, Firebase, MySQL connector, v.v.).  
  - Cấu hình `database.py` kết nối tới MySQL.  
  - Cấu hình `firebase_integration.py` với URL và key của Firebase.  
  - Cấu hình `telegram_notify.py` với token bot và chat ID.  
  - Chạy `app.py` và truy cập `http://localhost:5001` (hoặc IP của máy chủ).

---

## 8. Gợi ý nội dung cho báo cáo

Từ file này, có thể xây dựng các chương trong báo cáo:

1. **Tổng quan đề tài**: lý do chọn đề tài, mục tiêu, phạm vi.  
2. **Cơ sở lý thuyết**:  
   - IoT, cảm biến nhiệt độ/độ ẩm, Peltier.  
   - Firebase Realtime Database.  
   - YOLO và phân loại ảnh.  
3. **Thiết kế hệ thống**:  
   - Sơ đồ khối phần cứng.  
   - Sơ đồ luồng dữ liệu giữa ESP32 – Firebase – Flask – Web – Database.  
4. **Thi công hệ thống**:  
   - Mô tả phần cứng: ESP32, ESP32-CAM, cảm biến, Peltier, nguồn.  
   - Mô tả phần mềm: các module Python, cấu trúc API, giao diện web.  
5. **Kiểm thử và đánh giá**:  
   - Kịch bản thử nghiệm cảm biến, điều khiển nhiệt độ.  
   - Kịch bản thử nghiệm nhận diện trái cây (nhiều loại, nhiều độ chín).  
   - Độ trễ cập nhật dữ liệu, độ ổn định kết nối.  
6. **Kết luận và hướng phát triển**:  
   - Nhận xét về hiệu quả giám sát và cảnh báo.  
   - Hướng mở rộng: thêm phân loại thực phẩm khác, tối ưu mô hình, tích hợp cloud, ứng dụng di động.

