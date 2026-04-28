# Tổng quan Dự án: Hệ thống Phân loại Trái cây Thông minh

Tài liệu này trình bày ý tưởng cốt lõi, mục tiêu hệ thống và các mốc phát triển hiện tại cho dự án băng chuyền phân loại trái cây sử dụng Raspberry Pi 4.

## 💡 Ý tưởng Dự án

Dự án nhằm xây dựng một hệ thống tự động hóa quá khứ phân loại trái cây dựa trên hình ảnh. Hệ thống sử dụng trí tuệ nhân tạo (AI) để nhận diện các loại trái cây khi chúng đi qua băng chuyền và đưa ra quyết định xử lý tương ứng.

### Các thành phần chính

- **Băng chuyền**: Di chuyển trái cây qua trạm kiểm tra.
- **Raspberry Pi 4 (`pi_edge/`)**: Bộ não xử lý tại chỗ, kết nối camera và thực hiện nhận diện.
- **Camera**: Thu thập hình ảnh thời gian thực của trái cây.
- **Laptop (`laptop_server/`)**: Trạm quản lý, giám sát và điều khiển.

### Cấu trúc Thư mục Hiện tại

```text
/repo
  ├── pi_edge/          # Chứa code và model chạy trên Raspberry Pi
  │   ├── model/        # Thư mục lưu trữ model .onnx (best.onnx)
  │   ├── cam_stream.py # Pipeline camera + inference + websocket
  │   └── fruit_classifier.py # Logic nhận diện ONNX (đã tối ưu)
  ├── laptop_server/    # Chứa code chạy trên Laptop
  │   └── server.py     # WebSocket server nhận dữ liệu
  ├── start_pi.py       # Script khởi động nhanh cho Pi
  ├── start_server.py   # Script khởi động nhanh cho Laptop
  └── docs/             # Tài liệu hướng dẫn chi tiết
```

## 🎯 Mục tiêu Hệ thống

1. **Nhận diện chính xác**: Phân loại Cam, Chanh, Quýt bằng YOLO ONNX.
2. **Xử lý vật thể lạ**: Tự động chuyển vào nhóm "unknown" nếu độ tin cậy < 0.5.
3. **Quản lý tập trung**: Giám sát qua WebSocket Server.
4. **Tốc độ đáp ứng**: Đã đạt ~10 FPS trên Raspberry Pi 4.

## ✅ Thành tựu Hiện tại (Milestones)

- [x] **Chạy Model trên Raspberry Pi**: Tối ưu hóa ONNX Runtime (CPU).
- [x] **Thu thập hình ảnh từ Camera**: Hỗ trợ camera đa chỉ số (0, 1, 2).
- [x] **Thực hiện Nhận diện**: Pipeline ThreadPool non-blocking.
- [x] **Gửi kết quả về Laptop**: Giao thức WebSocket ổn định với khả năng tự kết nối lại.

---
*Tài liệu này phản ánh trạng thái hoàn thiện cuối cùng của dự án.*
