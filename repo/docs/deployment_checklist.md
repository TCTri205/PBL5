# Checklist Triển khai (Deployment Checklist)

Đảm bảo tất cả các bước sau được kiểm tra trước khi chạy hệ thống trong môi trường thực tế.

## 📦 1. Chuẩn bị Mô hình (Model Preparation)

- [x] Huấn luyện thành công trên Colab với độ chính xác (mAP hoặc Accuracy) > 85%.
- [x] Export sang định dạng ONNX (`best.onnx`) với `simplify=True`.
- [x] Kiểm tra model bằng `onnx.checker` trước khi copy lên Pi.
- [x] File model đã được đặt tại: `~/pbl5_system/model/best.onnx`.

## 🍓 2. Raspberry Pi OS & Environment

- [x] Sử dụng **Raspberry Pi OS 64-bit Lite** (Debian Bookworm khuyên dùng).
- [x] SSH đã được enable và có thể truy cập từ xa.
- [x] Môi trường ảo (venv) đã được tạo: `python -m venv venv`.
- [x] Tất cả dependencies đã được cài đặt:
  - [x] `onnxruntime` (1.15.1+)
  - [x] `opencv-python-headless`
  - [x] `numpy`
  - [x] `websockets`

## 📷 3. Phần cứng Camera (Hardware)

- [x] Camera đã được kết nối chắc chắn vào cổng USB 3.0 (màu xanh).
- [x] User hiện tại đã nằm trong group `video`: `sudo usermod -aG video $USER`.
- [x] Kiểm tra camera hoạt động: `ls /dev/video0`.
- [x] Độ phân giải camera đã được cấu hình phù hợp (khuyên dùng 640x480).

## 🌐 4. Kết nối mạng & WebSocket

- [x] Pi và Laptop đã kết nối chung một mạng LAN/WiFi.
- [x] Laptop đã mở port firewall **8765** (Inbound).
- [x] `server.py` đã được khởi chạy trên Laptop và đang ở trạng thái Listening.
- [x] Địa chỉ IP hoặc hostname trong `cam_stream.py` đã trỏ đúng về Laptop.

## ⚙️ 5. Cấu hình Runtime (Optimization)

- [ ] Tăng SWAP size lên 1024MB hoặc 2048MB (Nếu dùng Pi 4 < 4GB RAM).
- [x] Đã lắp tản nhiệt hoặc quạt cho Pi để tránh bị bóp hiệu suất (Throttling).
- [x] Confidence threshold đã được tối ưu (khuyên dùng 0.5 - 0.6).
- [x] Sleep interval trong loop nhận diện > 0.1s để tránh treo CPU.

## 🚀 6. Chạy chính thức (Execution)

- [ ] Chạy server trên Laptop: `python server.py`.
- [ ] Chạy stream trên Pi: `python cam_stream.py`.
- [ ] Kiểm tra log trên server: Kết quả nhận diện (Lớp, Confidence) được cập nhật liên tục.

---

## 🆘 Troubleshooting Quick Links

- [Lỗi Camera không mở được](./troubleshooting.md#camera-issues)
- [Lỗi WebSocket Connection Refused](./troubleshooting.md#network--websocket)
- [Pi bị đứng/treo](./troubleshooting.md#performance-issues)
