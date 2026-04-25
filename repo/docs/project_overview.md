# Tổng quan Dự án: Hệ thống Phân loại Trái cây Thông minh

Tài liệu này trình bày ý tưởng cốt lõi, mục tiêu hệ thống và các mốc phát triển hiện tại cho dự án băng chuyền phân loại trái cây sử dụng Raspberry Pi 4.

## 💡 Ý tưởng Dự án

Dự án nhằm xây dựng một hệ thống tự động hóa quá khứ phân loại trái cây dựa trên hình ảnh. Hệ thống sử dụng trí tuệ nhân tạo (AI) để nhận diện các loại trái cây khi chúng đi qua băng chuyền và đưa ra quyết định xử lý tương ứng.

### Các thành phần chính

- **Băng chuyền**: Di chuyển trái cây qua trạm kiểm tra.
- **Raspberry Pi 4 (`pi_edge/`)**: Bộ não xử lý tại chỗ, kết nối camera và thực hiện nhận diện.
- **Camera**: Thu thập hình ảnh thời gian thực của trái cây.
- **Laptop (`laptop_server/`)**: Trạm quản lý, giám sát và điều khiển.

### Cấu trúc Thư mục Đề xuất

```text
/repo
  ├── pi_edge/          # Chứa code và model chạy trên Raspberry Pi
  │   ├── model/        # Thư mục lưu trữ model .onnx
  │   ├── cam_stream.py # Script xử lý luồng camera và gửi kết quả
  │   ├── fruit_classifier.py # Logic nhận diện (đã tối ưu hóa bộ nhớ)
  │   └── requirements.txt
  ├── laptop_server/    # Chứa code chạy trên Laptop
  │   └── server.py     # WebSocket server nhận dữ liệu từ Pi
  └── docs/             # Tài liệu hướng dẫn
```

## 🎯 Mục tiêu Hệ thống

1. **Nhận diện chính xác**: Phân loại các loại trái cây mục tiêu (ví dụ: Cam, Chanh, Quýt) bằng mô hình YOLO đã được tối ưu hóa (ONNX).
2. **Xử lý các loại khác (Thresholding)**: Sử dụng ngưỡng tin cậy (threshold) để phân loại các vật thể không nằm trong danh sách nhận diện vào nhóm "Other" (Khác). Điều này giúp hệ thống linh hoạt và không bị nhầm lẫn khi gặp vật thể lạ.
3. **Quản lý tập trung**: Dễ dàng điều khiển và theo dõi trạng thái hệ thống từ Laptop thông qua giao thức WebSocket.
4. **Tốc độ đáp ứng**: Đảm bảo thời gian nhận diện và gửi kết quả đủ nhanh để tích hợp với cơ cấu chấp hành trên băng chuyền.

## 🚀 Mục tiêu Hiện tại (Milestones)

Mục tiêu trọng tâm trong giai đoạn này là thiết lập luồng dữ liệu cơ bản từ thiết bị đầu cuối đến trạm giám sát:

- [ ] **Chạy Model trên Raspberry Pi**: Tối ưu hóa và thực thi mô hình nhận diện (ONNX Runtime) trực tiếp trên phần cứng Pi 4.
- [ ] **Thu thập hình ảnh từ Camera**: Capture frame từ camera gắn trên Pi với độ trễ thấp.
- [ ] **Thực hiện Nhận diện**: Xử lý hình ảnh và đưa ra kết quả phân loại (Label + Confidence).
- [ ] **Gửi kết quả về Laptop**: Thiết lập kênh truyền thông (WebSocket) để gửi kết quả nhận diện từ Pi về Laptop ngay lập tức.

---
*Tài liệu này sẽ được cập nhật liên tục theo tiến độ của dự án.*
