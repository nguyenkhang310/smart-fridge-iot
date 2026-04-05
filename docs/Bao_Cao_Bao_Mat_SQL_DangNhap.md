# Báo cáo: Bảo mật hệ thống, Đăng nhập, Đăng ký và Quản lý Mật khẩu

## 1. Tổng quan về kiến trúc bảo mật
Hệ thống đồ án (Smart Fridge IoT) được xây dựng dựa trên framework web **Flask (Python)** kết hợp với cơ sở dữ liệu **MySQL**. Các biện pháp bảo mật hiện tại được thiết kế theo mô hình "Phòng thủ chiều sâu" (Defense in Depth), tập trung vào việc xác thực người dùng, bảo vệ dữ liệu nhạy cảm bằng mã hóa một chiều, chống tấn công dò mật khẩu (brute-force) và bảo vệ cơ sở dữ liệu khỏi lỗi truy vấn SQL Injection.

## 2. Các điểm sáng nổi bật trong kiến trúc bảo mật (Security Highlights)
So với các đồ án thông thường, hệ thống này triển khai nhiều cơ chế bảo mật nâng cao đáng chú ý:

- **Cơ chế "Zero-Hardcode Password" (Bootstrap Admin):** Ngăn chặn triệt để thói quen xấu là "code cứng" tài khoản/mật khẩu Admin vào mã nguồn ứng dụng. Lần chạy đầu tiên, hệ thống đọc biến môi trường để cấp quyền khởi tạo 1 tài khoản duy nhất. Sau đó mật khẩu gốc bị quên lãng khỏi logic code.
- **Bảo vệ Brute-force có hỗ trợ Đa luồng (Thread-safe):** Cơ chế chống dò mật khẩu không chỉ lưu trữ trong bộ nhớ mà còn sử dụng khóa `threading.Lock()` khi tương tác với danh sách nỗ lực đăng nhập sai (`_login_attempts`). Điều này giúp hệ thống chống lại được các cuộc tấn công Brute-force song song (Concurrent Attacks) – nơi hacker gửi hàng chục yêu cầu cùng lúc để gây lỗi ghi đè dữ liệu.
- **Tiêu chuẩn mã hóa công nghiệp tiên tiến (`scrypt`):** Thay vì dùng SHA1, MD5 hay PBKDF2 cũ, dữ liệu được băm bằng thuật toán `scrypt` (tiêu chuẩn mặc định mới nhất của thư viện `werkzeug.security`). Thuật toán chuyên biệt này không chỉ tạo mã nhiễu (salting) độc lập mà cực kỳ tiêu tốn RAM (memory-hard). Điều này khiến việc dùng siêu máy tính hay Card đồ họa (GPU/ASIC) để bẻ khóa (qua Rainbow Tables hay Brute-force) trở nên gần như bất khả thi.
- **Phòng chống kiệt quệ tài nguyên DB (Connection Pooling):** Bằng cách sử dụng Pool kết nối `pool_size=5` kết hợp với Context Manager (`@contextmanager`), nếu có các luồng truy cập hay tấn công xấu nhắm vào, hệ thống chỉ chấp nhận số kết nối tối đa. Không bị Crash do tràn kết nối. Đồng thời các Transaction luôn được Rollback nếu xuất hiện lỗi nhằm bảo vệ toàn vẹn dữ liệu.

## 3. Cơ chế Xác thực và Ủy quyền (Authentication & Authorization)
Hệ thống sử dụng cơ chế bảo mật xác thực dựa trên **Session (Phiên làm việc)**:
- Sau khi đăng nhập thành công, thông tin phiên người dùng được lưu trữ an toàn trong đối tượng `session` của Flask.
- Cookie của Session được bảo mật với các cấu hình khép kín:
  - `SESSION_COOKIE_HTTPONLY = True`: Ngăn chặn hoàn toàn các script phía client đọc được Cookie, loại trừ rủi ro đánh cắp qua tấn công XSS.
  - `SESSION_COOKIE_SAMESITE = 'Lax'`: Giới hạn việc gửi cookie cùng với các luồng yêu cầu chéo trang, đóng vai trò then chốt trong việc giảm rủi ro tấn công giả mạo (CSRF). 
  - Tích hợp thêm rào chắn `SESSION_COOKIE_SECURE`: Có thể được kích hoạt trên hệ thống máy chủ thật để bắt buộc truyền tải HTTPS.
- Route Decorator `@login_required`: Một "người gác cổng" được khai báo cho tất cả các Controller cần bảo vệ. Bất cứ request nào không có Session ID hợp lệ sẽ lập tức bị đá văng về `/login`.

## 4. Luồng Đăng nhập, Đăng ký và Quản lý Người dùng

### 4.1. Đăng ký (Register)
- **API: `/api/auth/register`**
- Người dùng truyền các thông tin cần thiết: `username`, `password`, `email`, `full_name`.
- **Luồng xử lý:** Ngay khi nhận mật khẩu rõ (plain-text) ở Backend, hệ thống gọi hàm `generate_password_hash` sinh ra một đoạn mã hash hoàn chỉnh. Hệ thống **không bao giờ** làm rò rỉ hay lưu trữ chuỗi gốc vào File Log hay Database. Tốc độ sinh băm được điều chỉnh đủ chậm để phòng ngừa tấn công giải mã.

### 4.2. Đăng nhập (Login)
- **API: `/api/auth/login`**
- **Luồng hoạt động:**
  1. Người dùng gửi `username` và `password`.
  2. Hệ thống kiểm tra trong Database để nhận chuỗi `password_hash` đang lưu của `username` tương ứng.
  3. Hàm `verify_password` tính toán trực tiếp với `check_password_hash`, nếu hàm băm trả về True -> xác nhận cung cấp Session hợp lệ.
  4. Trạng thái thời gian đăng nhập lần cuối (`last_login`) được cập nhật realtime để admin lưu trữ phân tích (Auditing).

### 4.3. Cơ chế Chống tấn công dò mật khẩu (Anti Brute-force Lockout)
Hệ thống sử dụng hằng số môi trường (Environment variables) nhằm tùy biến thông số giám sát mà không cần viết lại mã:
  - `MAX_LOGIN_ATTEMPTS` (Mặc định: 5 lần)
  - `LOGIN_ATTEMPT_WINDOW_SECONDS` (Thời gian theo dõi, ví dụ: 15 phút)
  - `LOCKOUT_SECONDS` (Thời lượng bị ban tạm thời, không giải quyết bất cứ request Login nào).
- Tất cả đều được giám sát cẩn thận với khóa `_login_attempt_lock` (hạn chế điểm yếu Data Race Condition).

## 5. Cơ chế lưu trữ tại Cơ sở dữ liệu (MySQL Database)
Dữ liệu người dùng lưu trong bảng thông tin `users`.

**Thiết kế cấu trúc bảng:**
```sql
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) DEFAULT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) DEFAULT NULL,
    role ENUM('admin', 'user') DEFAULT 'user',
    is_active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL DEFAULT NULL,
    INDEX idx_username (username)
)
```
**Kiểm soát SQL Injection:** 
Rủi ro bị chèn SQL (SQLi) để bypass đăng nhập (vd: `admin' OR '1'='1`) được giải quyết tận gốc. Phương pháp Parameterized Queries (hay câu lệnh chuẩn bị sẵn) với chuỗi `$s` từ Driver `mysql.connector.pooling` sẽ tách biệt logic của câu truy vấn và các tham số truyền vào. Tham số nhận từ mạng sẽ được tự động sanitize (làm sạch/escape).

**Phân quyền Hệ thống (Role-based access control - RBAC):** 
Thông qua cột biến ENUM `role`, hệ thống dễ dàng cung cấp định nghĩa truy cập cho Admin (quản lý người dùng, setup server) và User thông thường, đảm bảo cô lập rủi ro nâng quyền trái phép.
