# Checklist Triển khai (Deployment Checklist)

Đảm bảo tất cả các bước sau được kiểm tra trước khi chạy hệ thống trong môi trường thực tế.

## 📦 1. Chuẩn bị Mô hình (Model Preparation)

- [x] Export sang định dạng ONNX (`best.onnx`) với `imgsz=320` và `simplify=True`.
- [x] File model đã được đặt tại: `repo/pi_edge/model/best.onnx`.
- [x] Kiểm tra model load thành công bằng script `fruit_classifier.py`.

## 🍓 2. Raspberry Pi OS & Environment

- [x] Sử dụng **Raspberry Pi OS 64-bit Lite**.
- [x] SSH đã được enable: `ssh <user>@pbl5-pi.local`.
- [x] Môi trường ảo (venv) đã được kích hoạt.
- [x] Cài đặt dependencies từ file tổng hợp: `pip install -r requirements.txt`.

## 📷 3. Phần cứng Camera (Hardware)

- [x] Bật giao diện Camera trong `sudo raspi-config`.
- [x] Kiểm tra camera hoạt động bằng `vcgencmd get_camera` hoặc `libcamera-hello`.
- [x] Độ phân giải camera khuyên dùng: `320x320` (khớp với model).

## 🌐 4. Kết nối mạng & WebSocket

- [x] Pi và Laptop đã kết nối chung một mạng LAN/WiFi.
- [x] Laptop đã mở port firewall **8765** (Inbound).

## ⚙️ 5. Cấu hình Runtime (Optimization)

- [x] Tăng SWAP size lên 2048MB cho Pi 4.
- [x] Sleep interval trong loop nhận diện là `0.1s` (mặc định trong code).

## 🚀 6. Chạy chính thức (Execution)

1. [ ] Chạy server trên Laptop: `python start_server.py`.
2. [ ] Chạy stream trên Pi: `python start_pi.py --server <IP_LAPTOP> --resolution 320x320`.
3. [ ] Kiểm tra log trên laptop: Dữ liệu nhận diện đổ về ổn định với độ trễ thấp.

---

## 🆘 Troubleshooting Quick Links

- [Lỗi Camera không mở được](./troubleshooting.md#camera-issues)
- [Lỗi WebSocket Connection Refused](./troubleshooting.md#network--websocket)
- [Pi bị đứng/treo](./troubleshooting.md#performance-issues)
