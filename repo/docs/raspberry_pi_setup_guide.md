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

## 📦 3. Thiết lập Môi trường (Environment)

```bash
# Cập nhật hệ thống
sudo apt update && sudo apt upgrade -y

# Cài đặt system dependencies cho OpenCV & ONNX
sudo apt install -y libatlas-base-dev libopenjp2-7 libtiff5 libjpeg-dev

# Tạo thư mục dự án
mkdir -p ~/pbl5_system
cd ~/pbl5_system

# Tạo môi trường ảo
python -m venv venv
source venv/bin/activate

# Cài đặt Python packages
pip install --upgrade pip
pip install onnxruntime opencv-python-headless numpy websockets
```

## ⚙️ 4. Tối ưu hóa (Optimization)

### Tăng Swap Size (Dành cho bản 1GB/2GB RAM)

```bash
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Đổi CONF_SWAPSIZE=2048
sudo dphys-swapfile swapon
```

## 🔗 Các bước tiếp theo

- [Hướng dẫn lập trình trên Pi](./raspberry_pi_coding_guide.md)
- [Triển khai Inference AI](./raspberry_pi_inference_guide.md)
- [Kế hoạch tích hợp hệ thống](./system_integration_plan.md)
