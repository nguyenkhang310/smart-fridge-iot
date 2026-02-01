# 🗄️ Hướng Dẫn Cài Đặt MySQL Database

Tài liệu này hướng dẫn cách cài đặt và cấu hình MySQL database cho hệ thống Smart Fridge IoT.

## 📋 Mục Lục

1. [Cài Đặt MySQL](#cài-đặt-mysql)
2. [Cấu Hình Database](#cấu-hình-database)
3. [Cài Đặt Python Package](#cài-đặt-python-package)
4. [Cấu Hình Kết Nối](#cấu-hình-kết-nối)
5. [Kiểm Tra](#kiểm-tra)

---

## 🛠️ Cài Đặt MySQL

### Trên macOS:

```bash
# Sử dụng Homebrew
brew install mysql

# Khởi động MySQL
brew services start mysql

# Hoặc cài đặt MySQL Server từ website chính thức
# https://dev.mysql.com/downloads/mysql/
```

### Trên Linux (Ubuntu/Debian):

```bash
sudo apt update
sudo apt install mysql-server

# Khởi động MySQL
sudo systemctl start mysql
sudo systemctl enable mysql
```

### Trên Windows:

1. Tải MySQL Installer từ: https://dev.mysql.com/downloads/installer/
2. Chạy installer và làm theo hướng dẫn
3. Ghi nhớ root password

---

## ⚙️ Cấu Hình Database

### 1. Đăng nhập MySQL:

```bash
mysql -u root -p
```

### 2. Tạo Database (nếu chưa tự động tạo):

```sql
CREATE DATABASE IF NOT EXISTS smart_fridge 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;
```

### 3. Tạo User (tùy chọn, khuyến nghị cho production):

```sql
CREATE USER 'smart_fridge_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON smart_fridge.* TO 'smart_fridge_user'@'localhost';
FLUSH PRIVILEGES;
```

### 4. Thoát MySQL:

```sql
EXIT;
```

---

## 📦 Cài Đặt Python Package

```bash
pip install mysql-connector-python
```

Hoặc cài tất cả dependencies:

```bash
pip install -r requirements.txt
```

---

## 🔧 Cấu Hình Kết Nối

### Cách 1: Environment Variables (Khuyến nghị)

Tạo file `.env` trong thư mục dự án:

```bash
# Database Configuration
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=smart_fridge
```

Hoặc export trong terminal:

```bash
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=your_password
export DB_NAME=smart_fridge
```

### Cách 2: Sửa Trực Tiếp trong `database.py`

Mở file `database.py` và sửa phần `DB_CONFIG`:

```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'your_password',  # Thay đổi password của bạn
    'database': 'smart_fridge',
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}
```

---

## 🧪 Kiểm Tra

### 1. Kiểm tra MySQL đang chạy:

```bash
# macOS/Linux
brew services list | grep mysql
# hoặc
sudo systemctl status mysql

# Kiểm tra kết nối
mysql -u root -p -e "SELECT 1"
```

### 2. Chạy Flask app:

```bash
python app.py
```

Bạn sẽ thấy trong log:
```
✓ Database initialized successfully
✓ MySQL database initialized
✓ Database tables created/verified
```

### 3. Kiểm tra tables đã tạo:

```bash
mysql -u root -p smart_fridge
```

```sql
SHOW TABLES;
```

Bạn sẽ thấy các bảng:
- `sensors` - Lưu dữ liệu cảm biến
- `inventory` - Lưu thống kê kho
- `detections` - Lưu từng vật phẩm được phát hiện
- `detection_sessions` - Lưu session phát hiện
- `temperature_settings` - Lưu lịch sử thay đổi nhiệt độ

---

## 📊 Cấu Trúc Database

### Bảng `sensors`
Lưu dữ liệu cảm biến nhiệt độ và độ ẩm:
- `id` - Primary key
- `temperature` - Nhiệt độ (°C)
- `humidity` - Độ ẩm (%)
- `target_temperature` - Nhiệt độ mục tiêu
- `status` - Trạng thái
- `created_at` - Thời gian

### Bảng `inventory`
Lưu thống kê tổng số vật phẩm:
- `id` - Primary key
- `total_items` - Tổng số vật phẩm
- `fruit_count` - Số trái cây
- `food_count` - Số thực phẩm
- `other_count` - Số khác
- `created_at` - Thời gian

### Bảng `detections`
Lưu từng vật phẩm được phát hiện:
- `id` - Primary key
- `class_name` - Tên vật phẩm (apple, banana, etc.)
- `confidence` - Độ tin cậy (0-1)
- `category` - Loại (fruit/food/other)
- `bbox_x`, `bbox_y`, `bbox_width`, `bbox_height` - Tọa độ bounding box
- `image_path` - Đường dẫn ảnh
- `created_at` - Thời gian

### Bảng `detection_sessions`
Nhóm các detections từ cùng một lần quét:
- `id` - Primary key
- `total_items` - Tổng số vật phẩm trong session
- `fruit_count`, `food_count`, `other_count`
- `image_path` - Đường dẫn ảnh
- `created_at` - Thời gian

### Bảng `temperature_settings`
Lưu lịch sử thay đổi nhiệt độ:
- `id` - Primary key
- `target_temperature` - Nhiệt độ mục tiêu mới
- `previous_temperature` - Nhiệt độ trước đó
- `changed_by` - Người thay đổi (user/system)
- `created_at` - Thời gian

---

## 🔍 Truy Vấn Dữ Liệu

### Xem dữ liệu cảm biến mới nhất:

```sql
SELECT * FROM sensors ORDER BY created_at DESC LIMIT 10;
```

### Xem thống kê vật phẩm:

```sql
SELECT * FROM inventory ORDER BY created_at DESC LIMIT 10;
```

### Xem các vật phẩm được phát hiện:

```sql
SELECT class_name, category, confidence, created_at 
FROM detections 
ORDER BY created_at DESC 
LIMIT 20;
```

### Thống kê theo loại:

```sql
SELECT category, COUNT(*) as count 
FROM detections 
GROUP BY category;
```

---

## ⚠️ Lưu Ý

1. **Bảo mật**: Không commit file `.env` hoặc `database.py` có password vào Git
2. **Backup**: Nên backup database định kỳ
3. **Performance**: Database sẽ tự động tạo tables khi khởi động app
4. **Connection Pool**: Sử dụng connection pool để tối ưu hiệu năng

---

## 🆘 Troubleshooting

### Lỗi "Access denied":
- Kiểm tra username/password
- Đảm bảo user có quyền truy cập database

### Lỗi "Can't connect to MySQL server":
- Kiểm tra MySQL đang chạy: `brew services list` hoặc `systemctl status mysql`
- Kiểm tra port (mặc định 3306)
- Kiểm tra firewall

### Lỗi "Unknown database":
- Tạo database thủ công hoặc để app tự tạo
- Kiểm tra tên database trong config

---

**Chúc bạn thành công! 🎉**

