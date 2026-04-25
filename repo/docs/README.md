# 📚 Tài Liệu Dự Án PBL5 - Phân Loại Trái Cây Xanh

## Tổng Quan Dự Án

Dự án **PBL5 Green Fruit Classification** là hệ thống nhận diện trái cây xanh (Cam, Chanh, Quýt) sử dụng công nghệ AI (YOLO) trên nền tảng Edge Computing (Raspberry Pi).

### 🎯 Mục Tiêu

- Phân loại chính xác 3 loại trái cây: Cam, Chanh, Quýt
- Triển khai mô hình AI trên thiết bị Edge (Raspberry Pi 4)
- Tích hợp camera và giao tiếp thời gian thực qua WebSocket

### 🏗️ Kiến Trúc Hệ Thống

```mermaid
graph TD
    A[Google Colab (Training)] --> B[ONNX Model Export]
    B --> C[Raspberry Pi 4 (Inference)]
    C --> D[Camera (OpenCV)]
    C --> E[ONNX Runtime]
    C --> F[WebSocket Client]
    F --> G[Laptop/Server]
    G --> H[WebSocket Server (Monitoring)]
```

## 📄 Tài Liệu

### Tổng Quan

- **[TECH_STACK.md](./TECH_STACK.md)** - Công nghệ và kiến trúc (Tiếng Anh)
- **[system_integration_plan.md](./system_integration_plan.md)** - Kế hoạch tích hợp hệ thống

### Cài Đặt & Cấu Hình

- **[raspberry_pi_setup_guide.md](./raspberry_pi_setup_guide.md)** ⭐ - Hướng dẫn cài đặt Raspberry Pi headless + WebSocket Server

### Lập Trình & Triển Khai

- **[raspberry_pi_coding_guide.md](./raspberry_pi_coding_guide.md)** - Hướng dẫn lập trình Python trên Raspberry Pi
- **[raspberry_pi_inference_guide.md](./raspberry_pi_inference_guide.md)** - Triển khai YOLO Classification trên Pi

### Thực Thi & Tham Chiếu

- **[pi_inference.md](./implementation/pi_inference.md)** - API reference cho `pi_inference.py`
- **[cam_stream.md](./implementation/cam_stream.md)** - Hướng dẫn streaming camera real-time

## 🚀 Bắt Đầu Nhanh (Quick Start)

### Yêu Cầu Hệ Thống

- Raspberry Pi 4 (4GB+ RAM)
- MicroSD 16GB+ hoặc USB Boot
- Camera USB hoặc Pi Camera Module
- Laptop làm máy chủ giám sát (Server)
- Mạng LAN/WiFi chung

### Các Bước Thực Hiện

#### 1. Chuẩn bị Raspberry Pi

```bash
# Thực hiện theo: docs/raspberry_pi_setup_guide.md
# - Flash OS bằng Raspberry Pi Imager
# - Cấu hình SSH và WiFi
# - Cài đặt môi trường ảo
```

#### 2. Huấn luyện mô hình trên Colab

```bash
# Tải dataset lên Google Drive
# Chạy notebook training
# Export model sang ONNX format
```

#### 3. Triển khai trên Pi

```bash
# Copy model best.onnx lên Pi
cd ~/pbl5_system
source venv/bin/activate
pip install onnxruntime opencv-python-headless numpy

# Chạy inference
python pi_inference.py model/best.onnx test_image.jpg
```

#### 4. Khởi chạy WebSocket Server (trên Laptop)

```bash
python server.py
# Server lắng nghe tại cổng 8765
```

#### 5. Streaming Camera (trên Pi)

```bash
# Tích hợp camera và gửi kết quả qua WebSocket
python cam_stream.py
# Chi tiết: docs/implementation/cam_stream.md
```

## 🎓 Đường Dẫn Học Tập (Learning Path)

### Mức Độ Cơ Bản (1-2 tuần)

- Raspberry Pi OS và Python cơ bản
- Điều khiển GPIO với `gpiozero`
- Cấu hình SSH và headless setup

### Mức Độ Trung Bình (2-3 tuần)

- OpenCV và xử lý ảnh
- WebSocket và giao tiếp mạng
- ONNX Runtime và inference cơ bản

### Mức Độ Nâng Cao (1+ tháng)

- Huấn luyện YOLO trên Colab
- Tối ưu hóa model (quantization, pruning)
- Real-time streaming và multi-threading
- Edge deployment optimization

## 🔗 Liên Kết Hữu Ích

- [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) - Framework phát hiện đối tượng
- [Raspberry Pi Documentation](https://www.raspberrypi.com/documentation/) - Tài liệu chính thức
- [ONNX Runtime](https://onnxruntime.ai/) - Inference engine
- [OpenCV](https://opencv.org/) - Thư viện thị giác máy tính

## 👥 Thành Viên

- **Dự án PBL5** - Lớp TCTRI205, ĐH Công Nghệ
- **Giảng viên hướng dẫn**: [Tên giảng viên]
- **Thành viên**: [Tên các thành viên]

## 📅 Timeline Dự Kiến

| Phase | Công Việc | Thời Gian |
| :--- | :--- | :--- |
| Phase 1 | Dataset collection & preparation | Tuần 1-2 |
| Phase 2 | Model training on Colab | Tuần 3-4 |
| Phase 3 | Edge deployment on Pi | Tuần 5-6 |
| Phase 4 | System integration & testing | Tuần 7-8 |
| Phase 5 | Demo & presentation | Tuần 9 |

## 📞 Hỗ Trợ & Đóng Góp

- **Issues**: Thêm vào issues tracker
- **Questions**: Liên hệ nhóm dự án
- **Contributions**: Pull requests welcome

---

*Tài liệu được cập nhật lần cuối: 2026-04-25*
*Ngôn ngữ chính: Tiếng Việt (ngoại trừ TECH_STACK.md)*
