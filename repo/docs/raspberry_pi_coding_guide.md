# Hướng dẫn Lập trình Python trên Raspberry Pi (PBL5)

Tài liệu này cung cấp các nguyên tắc và mẹo nhỏ khi phát triển ứng dụng Python cho hệ thống PBL5.

## 🐍 1. Quản lý Môi trường (Virtual Environments)

Luôn sử dụng `venv` để tránh xung đột thư viện hệ thống:

```bash
# Tạo
python -m venv venv

# Kích hoạt
source venv/bin/activate

# Cài đặt từ file requirements (nếu có)
pip install -r requirements.txt
```

## ⚡ 2. Lập trình Bất đồng bộ (Asyncio)

Vì hệ thống cần thực hiện nhiều việc cùng lúc (Đọc camera, Inference, Gửi WebSocket), `asyncio` là lựa chọn tối ưu để không làm "đứng" chương trình.

**Mẫu code WebSocket Client:**

```python
import asyncio
import websockets

async def send_data(uri, data):
    async with websockets.connect(uri) as websocket:
        await websocket.send(data)

asyncio.run(send_data("ws://localhost:8765", '{"status": "ok"}'))
```

## 📷 3. Xử lý ảnh với OpenCV

Mẹo tối ưu hiệu suất:

- Đọc frame ở resolution thấp (640x480).
- Sử dụng `opencv-python-headless` trên server không có màn hình.
- Luôn giải phóng camera bằng `cap.release()` khi kết thúc.

## 🐞 4. Debugging trên Pi

1. **Check Logs**: Sử dụng `print()` hoặc thư viện `logging`.
2. **Monitor Tài nguyên**: Dùng lệnh `htop` để xem CPU/RAM usage.
3. **Nhiệt độ**: `vcgencmd measure_temp` (Nên giữ nhiệt độ < 70°C).

## 🚀 5. Chạy tự động (Autostart)

Để script chạy ngay khi Pi khởi động, sử dụng **systemd**:

```bash
sudo nano /etc/systemd/system/pbl5.service
```

Nội dung file:

```ini
[Unit]
Description=PBL5 Fruit Classification
After=network.target

[Service]
ExecStart=/home/tctri205/pbl5_system/venv/bin/python /home/tctri205/pbl5_system/cam_stream.py
WorkingDirectory=/home/tctri205/pbl5_system
StandardOutput=inherit
StandardError=inherit
Restart=always
User=tctri205

[Install]
WantedBy=multi-user.target
```

Sau đó:

```bash
sudo systemctl enable pbl5
sudo systemctl start pbl5
```

---

- [Quay lại README](../README.md)
- [Hướng dẫn cài đặt OS](./raspberry_pi_setup_guide.md)
