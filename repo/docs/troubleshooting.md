# 🔧 Hướng Dẫn Xử Lý Sự Cố (Troubleshooting)

Hướng dẫn giải quyết các vấn đề thường gặp khi phát triển và triển khai hệ thống phân loại trái cây trên Raspberry Pi.

---

## 📋 Mục Lục

1. [Raspberry Pi Hardware](#-raspberry-pi-hardware)
2. [Network & WebSocket](#-network--websocket)
3. [Model Inference](#-model-inference)
4. [Camera Issues](#-camera-issues)
5. [Python Dependencies](#-python-dependencies)
6. [Performance Issues](#-performance-issues)
7. [Permission Errors](#-permission-errors)

- **Workflow hoàn chỉnh**: [System Integration Plan](./system_integration_plan.md)
- **Camera Streaming**: [cam_stream.md](./implementation/cam_stream.md)
- **API Reference**: [fruit_classifier.md](./implementation/fruit_classifier.md)
- **Setup Raspberry Pi**: [raspberry_pi_setup_guide.md](./raspberry_pi_setup_guide.md)

---

## 🍇 Raspberry Pi Hardware

### 🚨 Pi Không Khởi Động

**Triệu chứng:**

- LED đỏ sáng nhưng không có LED xanh nhấp nháy
- Màn hình không hiển thị gì
- Pi không xuất hiện trên mạng

**Nguyên nhân có thể:**

- Nguồn không đủ (dưới 3A)
- SD card/USB bị hỏng
- OS chưa được flash đúng cách

**Cách khắc phục:**

1. **Kiểm tra nguồn:**

   ```bash
   # Sử dụng cáp USB-C chính hãng, công suất 5V/3A
   # Không dùng sạc điện thoại thông thường
   ```

2. **Reflash OS:**

   ```bash
   # Dùng Raspberry Pi Imager
   - Format lại USB/SD card
   - Flash lại Raspberry Pi OS 64-bit
   ```

3. **Kiểm tra hardware:**
   - Thử SD card/USB khác
   - Thử cáp nguồn khác
   - Kiểm tra cổng USB trên Pi (nên dùng USB 3.0 màu xanh)

---

### 🚨 Pi Quá Nhiệt (Overheating)

**Triệu chứng:**

- Hiệu suất giảm đột ngột
- Thường xuyên freeze/reboot
- `vcgencmd measure_temp` hiển thị > 80°C

**Giải pháp:**

```bash
# Kiểm tra nhiệt độ
vcgencmd measure_temp

# Monitor liên tục
watch -n 1 vcgencmd measure_temp
```

**Biện pháp hạ nhiệt:**

- Gắn tản nhiệt (heatsinks)
- Dùng quạt tản nhiệt
- Đảm bảo thông thoáng (không để trong hộp kín)
- Giảm tải CPU (giảm FPS, giảm inference frequency)

---

### 🚨 Lỗi USB Không Nhận

**Triệu chứng:**

- Camera không xuất hiện trong `lsusb`
- USB flash drive không mount

**Khắc phục:**

```bash
# Kiểm tra USB devices
lsusb

# Kiểm tra mount points
lsblk

# Mount thủ công USB
sudo mkdir /mnt/usb
sudo mount /dev/sda1 /mnt/usb

# Cấp quyền
sudo chmod 777 /mnt/usb
```

**Lưu ý:** Nên dùng USB 3.0 (cổng màu xanh) cho camera và ổ cứng

---

## 🌐 Network & WebSocket

### 🚨 SSH Không Kết Nối Được

**Triệu chứng:**

- `ssh: connect to host ... port 22: Connection refused`
- `ssh: Could not resolve hostname ...`

**Nguyên nhân:**

- SSH chưa được enable
- Pi không kết nối WiFi
- Hostname không resolve được

**Khắc phục:**

1. **Dùng IP trực tiếp thay hostname:**

   ```bash
   # Tìm IP của Pi từ router
   # Hoặc dùng ứng dụng Fing trên điện thoại
   ssh tctri205@192.168.1.xx
   ```

2. **Enable SSH trên Pi (nếu có màn hình):**

   ```bash
   sudo systemctl enable ssh
   sudo systemctl start ssh
   ```

3. **Kiểm tra WiFi:**

   ```bash
   iwconfig
   ping 8.8.8.8
   ```

---

### 🚨 WebSocket Connection Refused

**Triệu chứng:**

```text
websockets.exceptions.ConnectionClosedError
Connection refused
```

**Nguyên nhân:**

- Server chưa chạy
- Firewall blocking port
- Sai IP/port
- Mạng khác subnet

**Khắc phục:**

1. **Kiểm tra server đã chạy:**

   ```bash
   # Trên server (laptop)
   netstat -an | grep 8765
   # Hoặc
   ss -tlnp | grep 8765
   ```

2. **Kiểm tra firewall:**

   ```bash
   # Windows
   netsh advfirewall firewall add rule name="WebSocket" dir=in action=allow protocol=TCP localport=8765
   
   # Linux
   sudo ufw allow 8765/tcp
   ```

3. **Test kết nối từ Pi:**

   ```bash
   python3 -c "import socket; s = socket.socket(); s.connect(('192.168.1.100', 8765)); print('OK'); s.close()"
   ```

4. **Dùng `local` domain:**

   ```python
   # Nếu cùng mạng, dùng .local
   uri = "ws://laptop-name.local:8765"
   ```

---

### 🚨 WebSocket Disconnect Sau Vài Phút

**Triệu chứng:**

- Kết nối ban đầu OK
- Bị disconnect sau 2-5 phút

**Nguyên nhân:**

- Timeout không hoạt động (no ping/pong)
- Network sleep

**Khắc phục:**

```python
import websockets

async def connect_with_keepalive():
    async with websockets.connect(
        uri,
        ping_interval=20,  # Gửi ping mỗi 20s
        ping_timeout=10,
        close_timeout=10
    ) as websocket:
        # Sử dụng websocket...
```

---

## 🤖 Model Inference

### 🚨 File Model Không Tồn Tại

**Triệu chứng:**

```text
Error: Model file model/best.onnx not found.
```

**Khắc phục:**

```bash
# Kiểm tra đường dẫn
ls -la ~/pbl5_system/model/

# Nếu chưa có model, export từ Colab
# Tải best.onnx từ Google Drive

# Tạo thư mục nếu chưa có
mkdir -p ~/pbl5_system/model
```

---

### 🚨 Lỗi ONNX Runtime

**Triệu chứng:**

```text
RuntimeError: [ONNXRuntimeError] : 1 : FAIL : 
Load model from model/best.onnx failed
```

**Nguyên nhân:**

- Model bị corrupt
- Phiên bản ONNX Runtime không tương thích
- ONNX export lỗi

**Khắc phục:**

1. **Re-export model từ Colab:**

   ```python
   # Trong notebook Colab
   from ultralytics import YOLO
   
   model = YOLO('yolov8s-cls.pt')
   # Train...
   
   # Export sang ONNX
   success = model.export(format='onnx', simplify=True)
   ```

2. **Cài đặt lại onnxruntime:**

   ```bash
   pip uninstall onnxruntime onnxruntime-tools -y
   pip install onnxruntime==1.15.1
   ```

3. **Kiểm tra model bằng onnx checker:**

   ```python
   import onnx
   model = onnx.load('model/best.onnx')
   onnx.checker.check_model(model)
   print("Model OK!")
   ```

---

### 🚨 Kết Quả Inference Sai / Unknown Luôn

**Triệu chứng:**

- Tất cả ảnh đều trả về `unknown`
- Confidence luôn thấp (<0.3)

**Nguyên nhân:**

- Confidence threshold quá cao
- Model chưa train tốt
- Preprocess không đúng
- Class names sai thứ tự

**Khắc phục:**

1. **Giảm confidence threshold:**

   ```python
   label, score = classifier.predict(img, confidence_threshold=0.3)
   ```

2. **Kiểm tra class mapping:**

   ```python
   # Trong FruitClassifier.__init__
   # Đảm bảo đúng với training
   # 0: cam, 1: chanh, 2: quyt
   self.class_names = ['cam', 'chanh', 'quyt']
   ```

3. **Test với ảnh train:**

   ```bash
   # Dùng ảnh trong tập train để test
   python pi_edge/fruit_classifier.py pi_edge/model/best.onnx test_known_good.jpg
   ```

4. **Kiểm tra preprocessing:**
   - Ảnh đầu vào phải RGB (chuyển từ BGR)
   - Normalize [0, 255] → [0.0, 1.0]
   - Kích thước 320×320

---

### 🚨 Inference Quá Chậm

**Triệu chứng:**
>
- > 500ms / ảnh
- FPS < 2

**Nguyên nhân:**

- Model quá lớn
- Resolution quá cao
- Chạy full YOLO thay vì classification

**Khắc phục:**

```python
# Dùng model nhỏ hơn (nano/small thay vì large)
classifier = FruitClassifier('model/best_nano.onnx', imgsz=224)

# Giảm resolution
classifier = FruitClassifier('model/best.onnx', imgsz=224)

# Chỉ inference mỗi N frame
skip_frames = 2
```

---

## 📷 Camera Issues

### 🚨 Camera Không Mở Được (cv2.VideoCapture)

**Triệu chứng:**

```text
[ WARN:0] global cap_v4l.cpp:914 open VIDEOIO(V4L2): can't open camera by index
```

**Nguyên nhân:**

- Camera không kết nối
- Đang bị process khác giữ
- Thiếu permission

**Khắc phục:**

1. **Kiểm tra camera:**

   ```bash
   # Liệt kê camera
   ls /dev/video*
   
   # Test bằng fswebcam
   fswebcam -r 640x480 test.jpg
   
   # Test bằng v4l2-ctl
   v4l2-ctl --list-devices
   ```

2. **Giải phóng camera:**

   ```bash
   # Tìm process đang giữ camera
   fuser /dev/video0
   
   # Kill process
   kill -9 <PID>
   ```

3. **Cấp permission:**

   ```bash
   sudo usermod -aG video $USER
   # Logout và login lại
   ```

---

### 🚨 Ảnh Quá Tối / Quá Sáng

**Triệu chứng:**

- Ảnh đen kịt hoặc trắng xóa
- Nhận diện kém

**Giải pháp:**

```python
cap = cv2.VideoCapture(0)

# Auto exposure off
cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Manual

# Điều chỉnh exposure
cap.set(cv2.CAP_PROP_EXPOSURE, -5)  # Giá trị từ -10 đến 10

# Điều chỉnh brightness
cap.set(cv2.CAP_PROP_BRIGHTNESS, 0.5)  # 0.0 - 1.0

# Điều chỉnh contrast
cap.set(cv2.CAP_PROP_CONTRAST, 0.5)
```

---

### 🚨 Camera Lag / Giật

**Triệu chứng:**

- Stream bị giật, delay cao
- FPS không ổn định

**Giải pháp:**

```python
# Giảm resolution
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

# Dùng MJPEG format (compress)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

# Giảm FPS
cap.set(cv2.CAP_PROP_FPS, 15)
```

---

## 🐍 Python Dependencies

### 🚨 pip Install Lỗi

**Triệu chứng:**

```text
ERROR: Could not find a version that satisfies the requirement ...
```

**Nguyên nhân:**

- Network issue
- Phiên bản Python không hỗ trợ
- Thiếu system dependencies

**Khắc phục:**

```bash
# Upgrade pip
python3 -m pip install --upgrade pip

# Cài thêm system deps
sudo apt update
sudo apt install libatlas-base-dev libopenjp2-7 libtiff5 libjpeg-dev

# Dùng mirror pip
pip install --index-url https://pypi.org/simple/ <package>
```

---

### 🚨 Import Error

**Triệu chứng:**

```text
ModuleNotFoundError: No module named 'xyz'
```

**Nguyên nhân:**

- Chưa cài package
- Chưa activate venv
- PYTHONPATH sai

**Khắc phục:**

```bash
# Activate venv
source ~/pbl5_system/venv/bin/activate

# Cài package
pip install onnxruntime opencv-python-headless numpy

# Kiểm tra package đã cài
pip list | grep onnx
```

---

### 🚨 Version Conflict

**Triệu chứng:**

```text
ImportError: /lib/aarch64-linux-gnu/libstdc++.so.6: version `GLIBCXX_3.4.30' not found
```

**Nguyên nhân:**

- Thư viện C++ không tương thích
- Package wheel không đúng arch

**Khắc phục:**

```bash
# Cài bản ARM64 specific
pip install onnxruntime==1.15.1 --no-cache-dir

# Hoặc build từ source (chậm)
pip install --no-binary :all: onnxruntime
```

---

## ⚡ Performance Issues

### 🚨 CPU 100% / Pi Treo

**Triệu chứng:**

- Pi không phản hồi
- `htop` hiển thị CPU 100%

**Nguyên nhân:**

- Inference chạy quá nhanh/lặp vô hạn
- Memory leak
- Model quá nặng

**Giải pháp:**

```python
# Thêm delay giữa các inference
import time
time.sleep(0.1)  # 10 FPS max

# Giới hạn batch size
# Dùng model nhỏ hơn (nano)
```

**Emergency fix:**

```bash
# Tìm và kill process python
top  # Nhấn 'k' để kill
# Hoặc
pkill -f cam_stream.py
```

---

### 🚨 Out of Memory (OOM)

**Triệu chứng:**

```text
Killed
# Hoặc
MemoryError
```

**Nguyên nhân:**

- Swap không đủ
- Memory leak
- Batch size quá lớn

**Giải pháp:**

```bash
# Tăng swap
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile  # SET CONF_SWAPSIZE=2048
sudo dphys-swapfile swapon

# Monitor memory
free -h
```

---

## 🔐 Permission Errors

### 🚨 Permission Denied (USB, GPIO, Camera)

**Triệu chứng:**

```text
PermissionError: [Errno 13] Permission denied: '/dev/video0'
```

**Giải pháp:**

```bash
# Cấp quyền cho device
sudo chmod 666 /dev/video0

# Hoặc thêm user vào group
sudo usermod -aG video,tty,dialout $USER

# Khởi động lại hoặc relogin
```

**Lưu ý:** Cần logout và login lại để group có effect!

---

## 🚑 Emergency Recovery

### 🚨 Pi Hoàn Toàn Không Phản Hồi

**Cách cứu hộ:**

1. **Hard reset:**
   - Rút nguồn
   - Đợi 10s
   - Cắm lại

2. **Safe mode:**
   - Rút USB/SD
   - Mount trên máy tính khác
   - Sửa `/boot/cmdline.txt`
   - Thêm `init=/bin/sh` để boot single user

3. **Reflash:**

   ```bash
   # Dùng Raspberry Pi Imager
   # Format và flash lại từ đầu
   ```

### 🚨 Dữ Liệu Bị Mất

```bash
# Testdisk: Phục hồi partition
testdisk /dev/sda

# Photorec: Phục hồi file
testdisk /dev/sda
# Chọn PhotoRec
```

---

## 📞 Support & Resources

### Official Docs

- [Raspberry Pi Docs](https://www.raspberrypi.com/documentation/)
- [OpenCV Troubleshooting](https://docs.opencv.org/4.x/)
- [ONNX Runtime Issues](https://github.com/microsoft/ONNX-Runtime/issues)

### Community

- Raspberry Pi Forums: <https://forums.raspberrypi.com>
- Stack Overflow: Tag `raspberry-pi`, `opencv`, `onnx`
- GitHub Issues: Repository của project

### Debug Tools

```bash
# System info
uname -a
cat /etc/os-release

# Hardware info
vcgencmd measure_temp
vcgencmd get_config int

# Network
ip addr
iwconfig

# Logs
dmesg | tail -50
journalctl -xe
```

---

## ✅ Checklist Khắc Phục

- [ ] Đã thử restart Pi?
- [ ] Đã kiểm tra kết nối (cáp, nguồn, mạng)?
- [ ] Đã đọc log lỗi (`dmesg`, `journalctl`)?
- [ ] Đã test với ví dụ đơn giản nhất?
- [ ] Đã cập nhật OS và packages?
- [ ] Đã kiểm tra quyền (permissions)?
- [ ] Đã thử solution từ Stack Overflow?
- [ ] Đã backup dữ liệu trước khi fix?

---

*Last updated: 2026-04-25*  
*Compatible with Raspberry Pi OS 64-bit, Python 3.9+*
