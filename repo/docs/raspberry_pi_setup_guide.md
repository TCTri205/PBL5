# Hướng dẫn Cài đặt Raspberry Pi 4 (Headless)

Hướng dẫn này giúp bạn thiết lập Raspberry Pi 4 từ đầu cho đến khi sẵn sàng triển khai hệ thống AI.

## 📥 1. Flash OS (Raspberry Pi Imager)

Sử dụng phần mềm **Raspberry Pi Imager** để cài đặt OS:

1. **CHOOSE DEVICE**: Raspberry Pi 4.
2. **CHOOSE OS**: Raspberry Pi OS (64-bit) Lite.
3. **CHOOSE STORAGE**: MicroSD hoặc USB Boot.
4. **EDIT SETTINGS**:
   - Set hostname: `pbl5-pi.local`
   - Set username & password.
   - Configure WiFi.
   - **Enable SSH** (Dùng password authentication).

## 🔑 2. Truy cập SSH

Sau khi Pi đã boot, kết nối từ terminal Laptop:

```bash
ssh <USERNAME>@pbl5-pi.local
# Hoặc dùng IP nếu không resolve được .local
ssh <USERNAME>@192.168.1.xxx
```

## ⚙️ 3. Cấu hình Phần cứng (Hardware Config)

Đây là bước quan trọng để OpenCV có thể truy cập Camera.

### Kiểm tra & Kích hoạt Camera

**Lưu ý quan trọng**: Tùy thuộc vào phiên bản OS bạn đang dùng:

- **Raspberry Pi OS (Bookworm) - Khuyên dùng**:
  - Không cần chạy `raspi-config` để bật camera cho hầu hết các loại camera (libcamera tự động).
  - Kiểm tra bằng lệnh: `libcamera-hello --list-cameras`.
  - Nếu thấy `available cameras`, hệ thống đã sẵn sàng.

- **Raspberry Pi OS (Bullseye) hoặc cũ hơn**:
  - Chạy lệnh: `sudo raspi-config`
  - Chọn: **Interface Options** -> **Camera** -> **Yes**.
  - Chọn: **Finish** và **Reboot**.
  - Kiểm tra: `vcgencmd get_camera` (Kết quả `supported=1 detected=1` là OK).

## 📦 4. Thiết lập Môi trường (Environment)

```bash
# Cập nhật hệ thống
sudo apt update && sudo apt upgrade -y

# Cài đặt system dependencies cho OpenCV & ONNX
sudo apt install -y libatlas-base-dev libopenjp2-7 libtiff5 libjpeg-dev libcap-dev libgomp1

# Clone hoặc tải dự án
git clone <URL_CUA_BAN> ~/pbl5_project
cd ~/pbl5_project/repo

# Tạo môi trường ảo
python -m venv venv
source venv/bin/activate

# Cài đặt Python packages (Sử dụng tệp yêu cầu hợp nhất)
pip install --upgrade pip
pip install -r requirements.txt
```

## 🛠️ 5. Tối ưu hóa (Optimization)

### Tăng Swap Size (Dành cho bản 1GB/2GB RAM)

Để tránh lỗi "Out of Memory" khi chạy model AI:

```bash
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Thay đổi: CONF_SWAPSIZE=2048
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

## ⚙️ 6. Cấu hình Tự động chạy (Auto-start)

Nếu bạn sử dụng tệp service tại `repo/pi_edge/deployment/pbl5_pi.service`:
- **Quan trọng**: Hãy kiểm tra và sửa lại `WorkingDirectory` và `ExecStart` để khớp với tên người dùng và đường dẫn thực tế trên Pi của bạn (mặc định là `/home/pi/...`).

## 🔗 Các bước tiếp theo

- [Hướng dẫn Triển khai Inference AI](./raspberry_pi_inference_guide.md) ⭐
- [Kế hoạch tích hợp hệ thống](./system_integration_plan.md)
- [Khắc phục sự cố](./troubleshooting.md)
