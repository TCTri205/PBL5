# 🍏 PBL5: Green Fruit Classification System

Hệ thống nhận diện và phân loại trái cây xanh (Cam, Chanh, Quýt) thời gian thực sử dụng YOLOv8, ONNX Runtime trên Raspberry Pi và Dashboard giám sát trên Laptop.

---

## 🏗️ Kiến Trúc Hệ Thống

1.  **Pi Edge (Client):** Capture hình ảnh, chạy Inference AI, điều khiển phần cứng (Băng chuyền, Servo) và gửi dữ liệu qua WebSocket.
2.  **Laptop Server:** WebSocket Server nhận dữ liệu, hiển thị Real-time Dashboard và quản lý lịch sử nhận diện.

---

## 🚀 Quy Trình Triển Khai Chi Tiết

### 1. Chuẩn bị trên Laptop (Server)

*   **Truy cập thư mục dự án:**
    ```bash
    cd D:\HOC_DAI_HOC\PBL5\repo
    ```
*   **Vào môi trường ảo:**
    ```powershell
    # Windows
    .venv\Scripts\activate
    ```
*   **Cài đặt thư viện (Chỉ làm lần đầu):**
    ```bash
    pip install -r requirements.txt
    ```
*   **Khởi chạy Server:**
    ```bash
    python start_server.py --host 0.0.0.0 --port 8888
    ```
*   **Truy cập Dashboard:** Mở trình duyệt vào `http://localhost:8888`

---

### 2. Chuẩn bị trên Raspberry Pi (Client)

*   **Kết nối SSH vào Pi:**
    ```bash
    ssh pi@pbl5.local
    # Mật khẩu mặc định: 123456
    ```
*   **Truy cập thư mục dự án:**
    ```bash
    cd ~/PBL5/repo
    ```
*   **Kích hoạt môi trường ảo:**
    ```bash
    source ~/pbl5_venv/bin/activate
    ```
*   **Khởi chạy Client (Dùng script khởi tạo):**
    ```bash
    python start_pi.py --server 10.162.17.80 --port 8888
    ```
*   **Khởi chạy trực tiếp (Với tùy chỉnh màu sắc WB):**
    ```bash
    python pi_edge/cam_stream.py --server 10.162.17.189 --port 8888 --r-scale 0.80 --g-scale 0.85 --b-scale 1.20
    ```

---

## 🛠️ Quản lý Dịch vụ Tự động (Systemd)

Nếu bạn đã cài đặt service để Pi tự động chạy khi khởi động, sử dụng các lệnh sau:

*   **Khởi động:** `sudo systemctl start pbl5_pi.service`
*   **Dừng:** `sudo systemctl stop pbl5_pi.service`
*   **Kiểm tra trạng thái:** `sudo systemctl status pbl5_pi.service`
*   **Xem log thời gian thực (Debug):** `sudo journalctl -u pbl5_pi.service -f`

---

## 📊 Tham Số start_pi.py

| Tham số | Ý nghĩa | Mặc định |
| :--- | :--- | :--- |
| `--server` | IP của Laptop Server | `192.168.1.10` |
| `--port` | Cổng WebSocket của Server | `8765` |
| `--model` | Đường dẫn file .onnx | `pi_edge/model/best.onnx` |
| `--resolution` | Độ phân giải camera | `640x480` |
| `--manual-control` | Bật chế độ điều khiển thủ công | `False` |

---

## 📚 Tài Liệu Tham Khảo

*   [📘 Hướng dẫn cài đặt Pi chi tiết](./docs/raspberry_pi_setup_guide.md)
*   [🧠 Hướng dẫn Inference AI](./docs/raspberry_pi_inference_guide.md)
*   [🔧 Khắc phục sự cố](./docs/troubleshooting.md)

---
*Dự án PBL5 - Cập nhật lần cuối: 10/06/2026*
