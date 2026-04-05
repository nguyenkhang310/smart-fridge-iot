# Phân Tích Chi Tiết Hệ Thống "Tủ Lạnh Thông Minh IoT" (Smart Fridge IoT)

Tài liệu này cung cấp cái nhìn chuyên sâu và toàn diện nhất về dự án, phân tích từng công nghệ, thuật toán, kiến trúc hệ thống và luồng hoạt động (workflow) đã được ứng dụng trong quá trình phát triển hệ thống Tủ lạnh thông minh (Smart Fridge).

---

## 1. Tổng Quan Dự Án (Project Overview)
Dự án **Smart Fridge IoT** là một ứng dụng toàn diện kết hợp giữa **Internet of Things (IoT)** và **Trí tuệ Nhân tạo (AI)**, phục vụ mục đích tự động hóa quá trình giám sát, quản lý và điều khiển tủ lạnh từ xa. Hệ thống có khả năng nhận diện các loại vật phẩm (đặc biệt là trái cây), đánh giá mức độ tươi/chín, điều khiển phần cứng (peltier, led) và cập nhật thông tin cảm biến nhiệt độ/độ ẩm theo thời gian thực (real-time) tới người dùng.

---

## 2. Kiến Trúc Hệ Thống Tổng Thể (System Architecture)
Hệ thống được thiết kế theo mô hình **Client-Server-Hardware**, tích hợp thiết bị phần cứng thật (hoặc mô phỏng Wokwi) qua dịch vụ điện toán đám mây trung gian:

*   **Lớp Hardware (Phần cứng / Mô phỏng Wokwi):** Gồm cảm biến (DHT22), các cơ cấu chấp hành (Remote Relay/Peltier, LED) và vi điều khiển/máy tính nhúng (Raspberry Pi/ESP32). Các thông số mội trường đọc được sẽ gửi lên **Firebase Realtime Database**. 
*   **Lớp Camera (ESP32-CAM / Webcam):** Đảm nhiệm việc thu thập luồng hình ảnh video (MJPEG stream) trực tiếp từ bên trong/ngoài tủ lạnh để gửi về cho Backend phân tích.
*   **Lớp Backend (Server - Flask):** Là bộ não của hệ thống. Nó lắng nghe thông số từ Firebase Firebase Realtime DB, stream và phân tích hình ảnh từ Camera, điều hành YOLO AI để nhận diện, ghi log vào cơ sở dữ liệu và cung cấp API/SSE cho Frontend.
*   **Lớp Frontend (Web Dashboard):** Trình diễn trực quan toàn bộ hệ thống (dữ liệu cảm biến, biểu đồ, video feed, cảnh báo, thống kê). Frontend sẽ kết nối tới Backend thông qua RESTful API và Server-Sent Events (SSE).
*   **Lớp Notification (Telegram Bot):** Khi hệ thống AI phát hiện trái cây/thực phẩm bị xuống cấp, nó sẽ trigger API của Telegram để gửi ảnh và tin nhắn cảnh báo đến điện thoại người dùng ngay lập tức.

---

## 3. Các Công Nghệ Trọng Tâm Được Sử Dụng (Technologies Stack)

| Lớp | Công Nghệ / Thư Viện | Vai Trò & Chức Năng |
| :--- | :--- | :--- |
| **Backend** | **Python 3.8+** | Ngôn ngữ lập trình chính cho logic backend và AI. |
| | **Flask (v3.0.0)** | Web Server Gateway Interface (WSGI) xử lý HTTP request, Routing, Session, API. |
| | **OpenCV (cv2)** | Trích xuất Khung hình (Frame), chuyển đổi hệ màu ảnh, xử lý ảnh trước khi gửi cho AI và Stream. |
| | **PyMySQL** / **mysql-connector** | Giao tiếp với Database để lưu và đọc lịch sử cảm biến, thông tin người dùng. |
| | **Firebase Admin SDK** / **Requests**| SDK/Http gọi trực tiếp tới Firebase Realtime Database (Giao tiếp với Hardware). |
| **Frontend**| **HTML5 / Vanilla CSS / JS** | Cấu trúc giao diện động với hệ thống quản lý giao diện Responsive. |
| | **Server-Sent Events (SSE)** | Kết nối một chiều duy trì liên tục từ Server đến Client để đẩy data tự động (Cảm biến). |
| | **Chart.js** | (Nếu có sử dụng biểu đồ) Trực quan hóa dữ liệu độ ẩm, nhiệt độ theo mốc thời gian. |
| **AI (Core)** | **YOLOv8 (Ultralytics)** | Deep Learning Model chuyên dùng để nhận diện đối tượng theo thời gian thực (Object Detection). |
| **Database**| **MySQL 5.7/8.0** | Relational Database Management System - chứa 6 bảng tổ chức toàn bộ Entity của dự án. |
| **Hardware**| **ESP32-CAM / Raspberry Pi** | Thu thập hình ảnh, kết nối các chân GPIO để quản lý Relay, DHT22. |
| | **Wokwi** | Simulator mô phỏng mạch điện và vi điều khiển online. |

---

## 4. Phân Tích Các Thuật Toán & Xử Lý Cốt Lõi (Core Algorithms & Processing)

### 4.1. Thuật toán Trí tuệ Nhân tạo - Nhận diện đối tượng (YOLOv8)
*   **Mô hình sử dụng**: Hệ thống sử dụng YOLOv8 (từ Ultralytics), mô hình SOTA (State OF The Art) cho tốc độ suy luận nhanh nhất với độ chính xác cao `(yolov8n.pt - bản Nano)`.
*   **Pipeline hoạt động**:
    1. Lấy Image Frame từ Stream Camera (Webcam / ESP32-CAM) dưới format của OpenCV (BGR).
    2. Chạy mô hình: `results = model(frame)`.
    3. Trích xuất **Bounding Box** (Tọa độ giới hạn khung ảnh), **Class ID** (Mã vật thể - ví dụ: Táo, Lê, Cam), **Confidence Score** (Độ tin cậy > ngưỡng threshold).
    4. Trả kết quả về để vẽ Box đè lên hình (Draw Bounding Box).

### 4.2. Thuật toán Phân tích Độ chín/Hỏng bằng Mảng Màu (HSV Color Space)
Hệ thống không đánh giá độ chín hoàn toàn dựa vào AI (do tốn tài nguyên hoặc không có dataset cho độ chín) mà kết hợp một thuật toán xử lý ảnh truyền thống cực kỳ hiệu quả: **Phân tích không gian màu HSV**.
*   **Chuyển đổi:** `hsv = cv2.cvtColor(crop_img, cv2.COLOR_BGR2HSV)` (OpenCV đọc mặc định là hệ màu Blue-Green-Red, việc chuyển qua HSV - Hue, Saturation, Value giúp máy tính hiểu màu sắc trực quan hơn, bỏ qua sự ảnh hưởng của ánh sáng bóng râm - *Value*).
*   **Thuật toán đếm Pixel:**
    1. Sau khi YOLO cắt được trái cây (`crop_img`), ảnh được chuyển tiếp qua vùng mã HSV.
    2. Định nghĩa các dải phổ màu (Color Ranges) trong HSV: Vùng màu Đỏ/Vàng (chín), Vùng Xanh (chưa chín), Vùng Nâu/Đen (Bị hỏng/thâm nhập).
    3. `cv2.inRange()` tạo ra các Mask (mặt nạ trắng đen). Đếm số lượng Pixel thuộc các vùng màu trên để tính ra Tỷ lệ phần trăm `%`.
    4. Dùng Logic `If/Else` so sánh Tỷ lệ màu để đưa ra kết luận: "Tươi", "Đang chín", "Sắp hỏng", "Hỏng".

### 4.3. Thuật toán Tính toán Hạn sử dụng (Shelf-Life Estimation)
*   Dựa vào **Bảng Mapping (Tra cứu)** nội suy: Hệ thống tổ chức sẵn một Dictionary phân tích. Đối với loại Quả X (VD: Chuối) đang ở trạng thái Y (VD: "Đang chín") -> suy ra số ngày hết hạn (VD: 3 ngày). Nếu ở trạng thái "Sắp hỏng" thì chỉ còn 1 ngày.
*   Công thức này mang tính Rule-based chuyên gia.

### 4.4. Cơ chế luồng Video Streaming (MJPEG Multiplexing)
*   Để hiển thị Camera từ Server lên web với độ mượt cao nhưng không nặng, hệ thống dùng MJPEG (Motion JPEG).
*   Thuật toán hoạt động nhờ tính năng `Generator / Yield` của Python Flask. Server sẽ liên tục mã hóa Frame ảnh sang dạng byte (`cv2.imencode('.jpg', frame)`) và `yield` chúng liên tiếp qua Response HTTP, khai báo Content-Type: `multipart/x-mixed-replace; boundary=frame`. Trình duyệt sẽ nhận ảnh vô tận, hiển thị đè lên ảnh trước đó tạo hiệu ứng Video.

### 4.5. Cơ chế Đồng bộ Dữ Liệu Thời gian thực (SSE - Server-Sent Events)
Thay vì dùng WebSocket (phức tạp) hay AJAX Polling (gây nghẽn mạng), hệ thống sử dụng **SSE** lấy dữ liệu x1 chiều từ server.
*   Frontend (Javascript `EventSource('api/sensors/stream')`) kết nối.
*   Backend mở một vòng lặp `while True`, sau mỗi `time.sleep(X)` sẽ kéo data từ Firebase / Cảm biến nội bộ rồi format dạng chuỗi `data: {"temp": 25, "hum": 60}\n\n` gửi trả cho client.

### 4.6. Thuật toán Cảnh báo & Cooldown (Chống Spam)
Khi phát hiện thực phẩm hỏng, hệ API gửi tin nhắn (cùng ảnh upload) lên Telegram Bots. Nhưng để tránh spam (do streaming là 30 FPS, sẽ gửi 30 tin nhắn mỗi giây), hệ thống áp dụng **Thuật toán Cooldown Timer**:
1. Duy trì Dictionary `last_alert_time` lưu nhãn trái cây hỏng và thời gian thực cảnh báo.
2. Kiểm tra `if (current_time - last_alert_time) > COOLDOWN_SECONDS` (Ví dụ 120s) thì mới được gửi cảnh báo tiếp theo và cập nhật lại `last_alert_time`. Điều chỉnh tối ưu hoá Network.

### 4.7. Thuật toán Bảo mật (Rate Limiting & Brute-Force Protection)
Xử lý đăng nhập: Mật khẩu được mã hóa bằng chuẩn `Werkzeug.security (PBKDF2 SHA256)`.
Hệ thống kết hợp thuật toán bảo vệ chống "Dò mật khẩu":
1. Lưu một bảng băm (hoặc biến `login_attempts` trong bộ nhớ/DB) chứa mốc thời gian và IP/User bị sai.
2. Nếu Login thất bại >= 5 lần trong vòng 15 phút, tài khoản hoặc IP đó bị đưa vào trạng thái "Khóa tạm thời" (Lockout). Phải đợi 15 phút sau (xét qua Timestamp difference) mới mở lại để nhập.

---

## 5. Tổ chức Cơ Sở Dữ Liệu (Database Schema)
Hệ thống sử dụng hệ quản trị MySQL Relational DB cho các dữ liệu cần phân tích dài hạn.

1.  **Bảng `users`**: Quản lý truy cập. Mã hóa mật khẩu bảo vệ quyền truy cập tài khoản (admin/user phân quyền qua cột roles).
2.  **Bảng `sensors`**: Lưu rải rác theo chu kỳ giá trị (Temperature, Humidity, Timestamp). Hỗ trợ trực quan hóa xu hướng bảo quản mốc nhiệt thời gian qua các chart.
3.  **Bảng `detections` & `detection_sessions`**: Ghi nhận lại các phiên xử lý ảnh AI. Chứa đường dẫn ảnh (`image_path`), Label (`class_name`), Tỷ lệ tin cậy (`confidence`), trạng thái Tươi/Hỏng (`condition`). Từ đó Backend có dữ liệu kiểm đếm (Inventory) xem trong tủ lạnh đang có tổng bao nhiêu táo, cam... 

---

## 6. Tổng Kết (Summary)
Smart Fridge IoT không chỉ là một ứng dụng CRUD đơn thuần, dự án đã tận dụng tối đa **tính liên thông hệ thống** (Cross-system Integration):
- Phía thiết bị (Mạch, Firebase, Wokwi) hoạt động thu thập.
- Server trung gian xử lý luồng nặng (AI inference bằng GPU/CPU cho Yolov8, xử lý logic màu, tính toán).
- Client Frontend trình diễn dưới dạng Web App tối ưu và giao tiếp Async thời gian thực (SSE, Ajax). 

Hệ thống hoạt động như một "Quy trình Khép Kín": **Xác định Cảm biến** -> **Scan bằng AI** -> **Đánh Giá Tình Trạng** -> **Tự Động Cảnh Báo Ra Môi Trường Ngoài (Telegram)**. Đáp ứng đầy đủ các tiêu chí đồ án công nghệ nhúng + AI đỉnh cao.
