# Báo cáo: Kiến trúc và Nguyên lý hoạt động của Trợ lý Ảo (Chatbot)

## 1. Tổng quan về Chatbot trong hệ thống
Mặc dù đồ án có cài đặt thư viện `google-generativeai` (Gemini), tuy nhiên để đảm bảo thời gian phản hồi (latency) cực nhanh, tự chủ hoàn toàn 100% không phụ thuộc vào Internet (API của Google bị giới hạn truy vấn), và phản ứng chính xác với phần cứng, hệ thống Smart Fridge đang áp dụng mô hình Chatbot **Local Intent-Based (Xử lý và Nhận diện Ý định theo luồng cục bộ)**. 

Toàn bộ logic của Chatbot được phát triển độc lập trong mã nguồn `app.py` tại endpoint `/api/chat`, không cần gửi dữ liệu ra bên ngoài.

## 2. Quản lý Phiên trò chuyện (Session Management)
Hệ thống tạo ra trải nghiệm liền mạch và ghi nhớ bối cảnh hội thoại:
- Thông qua Dictionary nội bộ `_chat_sessions = {}` và bảo vệ chồng chéo dữ liệu bằng `_chat_lock = threading.Lock()`.
- Lịch sử trò chuyện được giới hạn tối đa 30 tin nhắn gần nhất (`del hist[:-30]`) thông qua hàm `_append_session_history`. Cơ chế này loại bỏ hiện tượng tràn bộ nhớ máy chủ khi người dùng chat quá nhiều.
- Các tin nhắn được gán định danh vai trò rõ ràng: `user` (người dùng) và `assistant` (hệ thống).

## 3. Bộ phân tích Ý định (Intent Classifier & Regex Parsing)
Chatbot hoạt động như một Trợ lý điều khiển phần cứng thực thụ nhờ việc dùng RegEx và quét từ khóa (Keyword matching). Khi nhận văn bản từ người dùng (ví dụ: *"giảm nhiệt độ xuống 4 độ"*), bộ vi xử lý thực hiện đối soát theo thứ tự ưu tiên:

**Ý định 1: Tìm kiếm Lệnh điều khiển Nhiệt độ Phần cứng**
- Dùng chuỗi Regex: `r'(chỉnh|đặt|thay|set|giảm|tăng|hạ|cho).*?(-?\d+\.?\d*)'` kết hợp các từ khóa `nhiệt, độ, °c, c`.
- Nếu khớp: Bot trích xuất chính xác con số mục tiêu (Target Temperature) và chuyển tiếp cho hàm giả lập `_tool_set_temperature(target)`. 
- **Bảo mật:** Hệ thống chặn triệt để luồng đi này nếu `session.get('role') != 'admin'`. Chỉ quản trị viên mới được phép ra lệnh cho phần cứng qua Chatbot.

**Ý định 2: Truy vấn Cảm biến (Sensor)**
- Quét các từ khóa: `nhiệt độ, độ ẩm, lạnh, nóng`.
- Nếu khớp: Gọi hàm `_tool_get_sensors()`, lấy dữ liệu theo Real-time và trả kết quả tổng hợp (Nhiệt độ hiện tại, Độ ẩm, Mục tiêu đang đặt).

**Ý định 3: Truy vấn Trạng thái cửa (Door Monitor)**
- Quét từ khóa: `cửa, door`.
- Nếu khớp: Bot kiểm tra tham số `door_state` từ hàm quét cảm biến và đưa ra kết luận (cửa đang ĐÓNG hay MỞ).

**Ý định 4: Truy vấn Khoang chứa thực phẩm bằng AI Vision (Inventory)**
- Quét từ khóa: `trong tủ, có gì, trái cây, táo, chuối, cam, hỏng, bao nhiêu`.
- Nếu khớp: Gọi hàm `_tool_get_inventory()` để tương tác với DB Detections gần nhất. Bóc tách trái cây/tủ lạnh và đếm số lượng thông qua `collections.Counter`.
- Đặc biệt, hệ thống chứa luồng Dịch giả nội bộ: Chuyển đổi nhãn tiếng Anh của YOLOAI (VD: `fresh apple`, `rotten banana`) sang tiếng Việt thuần túy.
- **Tính năng Cảnh báo:** Nếu đếm được bất cứ phần tử nào chứa chuỗi `rotten`, `hư`, `hỏng`, Bot sẽ tự động nhúng thêm 1 dòng cảnh báo người dùng dọn dẹp tủ lạnh.

*(Nếu tất cả các Intent không khớp, Bot có Fallback về câu trả lời hướng dẫn Menu các chức năng cơ bản mặc định).*

## 4. Tóm lược Ưu điểm
Bên cạnh việc là một hệ thống phản hồi Text thông thường, cách thiết kế Chatbot Local này mang lại 3 ưu điểm vô đối:
1. **Zero-Latency (Độ trễ bằng 0):** Hoạt động bằng CPU máy trạm không cần chờ phản hồi HTTP Request của LLM (Large Language Model) như Gemini/ChatGPT.
2. **Deterministic (Tính tất định cao):** Việc tích hợp AI Large-Model thường dính rủi ro "ảo giác" (Hallucination) — Bot không thể tự quyết định set nhiệt độ nếu hiểu nhầm. Với Intent-based/RegEx, tham số được kiểm soát %100 chính xác và an toàn để áp dụng lên môi trường IoT công nghiệp (Tủ lạnh vật lý).
3. **Phân quyền Tích hợp:** Bot tự biết ai đang chat để đưa ra quyền hạn (Role check), điểm mù thường xuyên gây lọt dữ liệu rủi ro của các phần mềm Assistant hiện tại.
