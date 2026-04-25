# Hướng Dẫn Lập Trình Raspberry Pi Với Python (2024)

Raspberry Pi là một nền tảng tuyệt vời cho lập trình Python. Hầu hết các thư viện và công cụ hiện đại đều hỗ trợ Python như là ngôn ngữ chính thức.

---

## 1. Tại sao dùng Python trên Raspberry Pi?
*   **Ngôn ngữ chính thức**: Raspberry Pi OS đi kèm với Python được cài đặt sẵn.
*   **Thư viện phong phú**: Hàng ngàn thư viện hỗ trợ phần cứng (GPIO, cảm biến, camera).
*   **Cộng đồng lớn**: Dễ dàng tìm kiếm lời giải cho mọi vấn đề.

---

## 2. Các Thư viện Cốt lõi (Hardware Interfacing)

### Điều khiển Chân GPIO (Điều khiển đèn, nút bấm, relay...)
*   **gpiozero**: Thư viện tiêu chuẩn, cực kỳ dễ dùng cho người mới.
    *   *Ví dụ bật đèn LED*:
        ```python
        from gpiozero import LED
        led = LED(17)
        led.on()
        ```
*   **Adafruit-Blinka**: Nếu bạn dùng các cảm biến từ Adafruit hoặc giao tiếp I2C/SPI.

### Camera & Thị giác máy tính
*   **Picamera2**: Thư viện mới nhất cho các module camera của Raspberry Pi.
*   **OpenCV (`opencv-python`)**: Chuẩn công nghiệp cho xử lý hình ảnh và nhận diện vật thể.

---

## 3. Trí tuệ Nhân tạo & Học máy (AI/ML)

Bạn hoàn toàn có thể chạy các mô hình AI trên Raspberry Pi 4:
*   **TensorFlow Lite**: Dùng để chạy các mô hình đã được huấn luyện sẵn (nhận diện khuôn mặt, vật thể) một cách mượt mà.
*   **Ultralytics (YOLOv8)**: Rất phổ biến cho bài toán nhận diện vật thể thời gian thực.
*   **PyTorch**: Phù hợp cho nghiên cứu và triển khai các kiến trúc mạng nơ-ron tùy chỉnh.

---

## 4. Giao tiếp Mạng & IoT
*   **FastAPI / Flask**: Tạo web server hoặc dashboard để điều khiển Pi từ xa qua trình duyệt.
*   **Paho-MQTT**: Giao tiếp giữa các thiết bị IoT (ví dụ: gửi dữ liệu cảm biến lên server).
*   **WebSockets**: Giao tiếp thời gian thực (như ví dụ `server.py` chúng ta đã làm).

---

## 5. Quy trình làm việc đề xuất (Best Practices)

### Luôn sử dụng Môi trường ảo (Virtual Environment)
Để tránh xung đột thư viện giữa các dự án:
```bash
python3 -m venv my_project_venv
source my_project_venv/bin/activate
pip install <tên_thư_viện>
```

### Quản lý mã nguồn
Sử dụng **Git** để quản lý code và dễ dàng đẩy lên GitHub/GitLab.

---

## 6. Gợi ý học tập
1.  **Cơ bản**: Học cách điều khiển LED và đọc tín hiệu từ nút bấm với `gpiozero`.
2.  **Trung cấp**: Đọc dữ liệu từ cảm biến nhiệt độ/độ ẩm (DHT11/22) và hiển thị lên web bằng `Flask`.
3.  **Nâng cao**: Sử dụng `OpenCV` để phát hiện chuyển động từ Camera và gửi thông báo qua Telegram.

---
*Raspberry Pi không chỉ là một cái máy tính, nó là cánh cổng để bạn tương tác với thế giới vật lý thông qua dòng code Python của mình!*
