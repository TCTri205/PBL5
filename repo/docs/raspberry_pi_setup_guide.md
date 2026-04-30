# Hướng dẫn Cài đặt Raspberry Pi 4 (Chế độ Headless)

Hướng dẫn này giúp bạn thiết lập Raspberry Pi 4 từ con số 0 cho đến khi sẵn sàng triển khai các mô hình AI, xử lý ảnh và hệ thống tự động hóa. Đặc biệt tối ưu cho việc chạy từ **USB/SSD rời** để tăng hiệu năng và độ bền.

---

## 📥 1. Flash OS (Raspberry Pi Imager)
Sử dụng phần mềm **Raspberry Pi Imager** để nạp hệ điều hành. Đây là bước cực kỳ quan trọng để định hình tài nguyên cho máy.

1. **CHOOSE DEVICE**: Chọn **Raspberry Pi 4**.
2. **CHOOSE OS**: Chọn **Raspberry Pi OS (Other)** -> Chọn **Raspberry Pi OS (64-bit) Lite**.
   - *Giải thích*: Bản "Lite" không có giao diện đồ họa (Desktop GUI), giúp tiết kiệm khoảng 400MB RAM và tài nguyên CPU. Bản 64-bit giúp tăng tốc độ xử lý tính toán cho AI.
3. **CHOOSE STORAGE**: Chọn **USB/Ổ cứng rời** của bạn (Nếu dùng thẻ MicroSD, các bước vẫn tương tự).
   - > [!TIP]
     > **Mẹo USB 3.0**: Khi cắm vào Pi, hãy sử dụng cổng màu **xanh dương** (USB 3.0) để đạt tốc độ đọc/ghi dữ liệu tối đa, giúp model AI load nhanh hơn.

4. **BẤM NEXT ĐỂ VÀO BẢNG EDIT SETTINGS (OS Customisation)**:
   Chọn **EDIT SETTINGS** và thiết lập:
   - **Tab General**:
     - **Set hostname**: `pbl5-pi` (Chỉ điền tên, hệ thống sẽ tự thêm đuôi `.local` để bạn gọi máy).
     - **Set username and password**: User là `pi`, mật khẩu là `123456`.
     - **Configure wireless LAN**: Nhập SSID (VD: `Cong Tam-5G`) và Mật khẩu Wifi nhà bạn.
       - > [!IMPORTANT]
       - > **Bắt buộc**: Phải chọn **Wireless LAN country là VN**. Nếu không chọn quốc gia, Pi 4 sẽ không thể kết nối được với các mạng Wifi băng tần **5G**.
     - **Set locale**: Time zone: `Asia/Ho_Chi_Minh`, Keyboard: `US`.
   - **Tab Services**:
     - Tích chọn **Enable SSH**.
     - Chọn **Use password authentication**.

5. **HOÀN TẤT VÀ GHI OS**:
   - Bấm **SAVE** để lưu cấu hình.
   - Khi được hỏi có muốn áp dụng tùy chỉnh không, chọn **YES**.
   - Tại màn hình Summary (Kiểm tra lại thiết bị và OS), bấm **WRITE**.
   - **Cảnh báo Erase**: Khi hiện bảng thông báo "You are about to ERASE all data...", hãy chọn **I UNDERSTAND, ERASE AND WRITE**.
   - Đợi thanh tiến trình chạy xong và hiện thông báo **"Write Successful"**. Lúc này bạn mới rút USB/Thẻ nhớ ra khỏi máy tính.

---

## 🔑 2. Truy cập SSH (Điều khiển từ xa)
Cắm USB vào Pi, cấp nguồn và đợi khoảng 2-3 phút để máy khởi động và nhận Wifi. Trên Laptop, mở Terminal hoặc PowerShell:

```bash
ssh pi@pbl5-pi.local
```
*Nhập mật khẩu là `123456` (hoặc mật khẩu bạn đã đặt). Nếu được hỏi "Are you sure...", gõ `yes`.*

> [!NOTE]
> Nếu không nhận diện được `.local`, hãy dùng phần mềm quét IP (như Advanced IP Scanner) để tìm IP của Pi và gõ: `ssh pi@192.168.1.xxx`

---

## ⚙️ 3. Cấu hình Phần cứng (Hardware Config)
Xác định loại camera bạn đang sử dụng để có bước kiểm tra phù hợp:

### A. Nếu dùng Webcam USB (Cắm trực tiếp vào cổng USB)
Webcam USB thường được Linux nhận diện tự động mà không cần cấu hình thêm.

1. **Kiểm tra kết nối vật lý**:
   ```bash
   lsusb
   # Tìm dòng có tên Webcam của bạn (VD: Logitech, USB Composite Device...)
   ```
2. **Kiểm tra thiết bị video**:
   ```bash
   ls /dev/video*
   # Nếu hiện ra /dev/video0 là hệ thống đã nhận diện thành công.
   ```
3. **Kiểm tra chi tiết (Tùy chọn)**:
   ```bash
   # Cài đặt bộ công cụ v4l-utils
   sudo apt update && sudo apt install -y v4l-utils
   # Liệt kê các thiết bị camera
   v4l2-ctl --list-devices
   ```

### B. Nếu dùng Camera Module (Cáp dẹt CSI)
Đảm bảo bạn đã cắm cáp dẹt vào khe CSI (nằm giữa Audio Jack và Micro-HDMI). Mặt có lá đồng hướng về phía cổng HDMI.

- **Raspberry Pi OS "Bookworm" (Bản mới nhất)**:
  - Hệ thống sử dụng kiến trúc `libcamera` mới.
  - Lệnh kiểm tra: `libcamera-hello --list-cameras`
  - *Lưu ý*: Lệnh này **chỉ dành cho camera CSI**, không dùng được cho Webcam USB.

- **Raspberry Pi OS "Bullseye" hoặc cũ hơn (Legacy)**:
  - Gõ lệnh: `sudo raspi-config`
  - Chọn: **Interface Options** -> **Camera** -> **Yes**.
  - Chọn **Finish** và **Reboot**.
  - Kiểm tra lại bằng: `vcgencmd get_camera` (Kết quả `supported=1 detected=1` là chuẩn).

---

## 📦 4. Thiết lập Môi trường Lập trình (Environment)
Môi trường ảo giúp các thư viện AI không xung đột với hệ thống.

```bash
# Cập nhật hệ thống
sudo apt update && sudo apt upgrade -y

# Cài đặt các thư viện lõi hỗ trợ OpenCV & Xử lý ảnh
# (Dùng libopenblas-dev và libtiff6 cho các bản OS mới như Bookworm/Trixie)
sudo apt install -y git dphys-swapfile libopenblas-dev libopenjp2-7 libtiff6 libjpeg-dev libcap-dev libgomp1

# Tải dự án
git clone https://github.com/TCTri205/PBL5.git ~/pbl5_project
cd ~/pbl5_project/repo

# Tạo và kích hoạt môi trường ảo (Bắt buộc trên Bookworm)
python3 -m venv venv
source venv/bin/activate

# Cài đặt các gói Python
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 🛠️ 5. Tối ưu hóa: Tăng Swap Size (Chống tràn RAM)
Khi chạy các mô hình AI (như YOLO, ONNX), Pi có thể bị lỗi "Out of Memory". Ta cần mượn dung lượng ổ cứng làm RAM ảo (Swap).

> [!IMPORTANT]
> **Lưu ý về thiết bị lưu trữ**: Việc dùng Swap sẽ ghi dữ liệu liên tục. Nếu dùng thẻ **MicroSD**, nó sẽ hỏng rất nhanh. Do bạn đang sử dụng **USB/SSD**, việc này an toàn và hiệu quả hơn nhiều.

```bash
# Gỡ bỏ zram (để không tranh chấp với swap file)
sudo apt remove -y systemd-zram-generator

# Tắt Swap hiện tại
sudo dphys-swapfile swapoff

# Mở file cấu hình
sudo nano /etc/dphys-swapfile
# Tìm dòng CONF_SWAPSIZE=100 và đổi thành CONF_SWAPSIZE=2048 (2GB RAM ảo)
# Bấm Ctrl+O -> Enter (Lưu), Ctrl+X (Thoát)

# Cập nhật và bật lại
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

---

## ⚙️ 6. Cấu hình Tự động chạy (Auto-start)
Để hệ thống AI tự khởi chạy mỗi khi cắm điện, ta sử dụng **systemd service**.

1. **Kiểm tra file service**:
   Mở tệp `repo/pi_edge/deployment/pbl5_pi.service` trên máy của bạn và cập nhật các thông tin:
   - `User`: Tên người dùng của bạn (VD: `pi`).
   - `WorkingDirectory`: Đường dẫn tuyệt đối tới thư mục `repo`.
   - `ExecStart`: Đường dẫn tới python trong `venv` và lệnh chạy `start_pi.py`.

   *Ví dụ cấu hình chuẩn cho user `pi`:*
   ```ini
   [Service]
   User=pi
   WorkingDirectory=/home/pi/pbl5_project/repo
   ExecStart=/home/pi/pbl5_project/repo/venv/bin/python /home/pi/pbl5_project/repo/start_pi.py --server 192.168.1.50 --device-id "Gate-01"
   ```

2. **Cài đặt service vào hệ thống**:
```bash
# Copy file vào thư mục hệ thống (Chạy trên Pi)
sudo cp ~/pbl5_project/repo/pi_edge/deployment/pbl5_pi.service /etc/systemd/system/

# Kích hoạt
sudo systemctl daemon-reload
sudo systemctl enable pbl5_pi.service
sudo systemctl start pbl5_pi.service

# Kiểm tra trạng thái
sudo systemctl status pbl5_pi.service
```

---

## 🔗 Các bước tiếp theo
- [Hướng dẫn Triển khai Inference AI](./raspberry_pi_inference_guide.md) ⭐
- [Kế hoạch tích hợp hệ thống](./system_integration_plan.md)
- [Khắc phục sự cố](./troubleshooting.md)
