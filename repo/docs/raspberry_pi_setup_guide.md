# Cẩm Nang Cài Đặt Raspberry Pi 4 (Headless) & WebSocket Server

Hướng dẫn này ghi lại các bước chi tiết để biến một chiếc Raspberry Pi 4 mới thành một máy chủ WebSocket hoạt động hoàn toàn từ xa (Headless), khởi động từ USB.

---

## Giai đoạn 1: Chuẩn bị "Đồ nghề"

### Phần cứng

* **Bo mạch Raspberry Pi 4**: Kèm cáp nguồn USB-C (5V/3A).
* **Thiết bị lưu trữ**: Một chiếc USB (ví dụ: JetFlash Transcend 16GB).
* **Máy tính điều khiển**: Laptop Windows có kết nối Wifi.

### Phần mềm

* **Raspberry Pi Imager**: Tải từ [raspberrypi.com/software](https://www.raspberrypi.com/software).

---

## Giai đoạn 2: Nạp Hệ điều hành cho USB (Flashing OS)

1. Cắm USB vào Laptop và mở **Raspberry Pi Imager**.
2. **CHOOSE DEVICE**: Chọn **Raspberry Pi 4**.
3. **CHOOSE OS**: Chọn **Raspberry Pi OS (64-bit)**.
4. **CHOOSE STORAGE**: Chọn đúng USB của bạn.
5. Bấm **NEXT** để vào bảng **Tùy chỉnh (Customisation)**:
    * **General**:
        * **Hostname**: Đặt tên (ví dụ: `TCTRaspberryPi4`).
        * **User/Password**: Tạo tài khoản (ví dụ: `tctri205`).
        * **Wifi**: Nhập SSID và Password Wifi chính xác.
        * **Localisation**: Chọn `Asia/Ho_Chi_Minh` và Keyboard layout `US`.
    * **Services**:
        * Tích chọn **Enable SSH**.
        * Chọn **Use password authentication**.
    * Bấm **SAVE**.
6. Bấm **YES / WRITE** để bắt đầu nạp OS.
7. **Lưu ý**: Nếu Windows yêu cầu "Format disk", hãy bấm **Cancel/Hủy**.
8. Khi hoàn tất "Write Successful", rút USB an toàn.

---

## Giai đoạn 3: Khởi động & Kết nối từ xa (Headless Setup)

1. **Lắp ráp**: Cắm USB vào cổng **USB 3.0 (màu xanh dương)** trên Pi 4.
2. **Cấp điện**: Cắm cáp nguồn. Pi sẽ tự khởi động và kết nối Wifi (chờ khoảng 2-3 phút).
3. **Truy cập SSH**: Mở Command Prompt hoặc PowerShell trên Windows và gõ:

    ```bash
    ssh tctri205@TCTRaspberryPi4.local
    ```

4. Nhập `yes` nếu được hỏi và điền mật khẩu đã thiết lập.

---

## Giai đoạn 4: Tối ưu Hệ thống & Cấu hình Môi trường

Thực hiện các lệnh sau để chuẩn bị hệ thống:

1. **Cập nhật hệ thống**:

    ```bash
    sudo apt update && sudo apt upgrade -y
    sudo apt install htop -y
    sudo apt autoremove -y
    ```

    *(Nếu được hỏi về file cấu hình, nhấn **N** để giữ nguyên)*.

2. **Thiết lập Môi trường ảo (Virtual Environment)**:

    ```bash
    mkdir pbl5_system
    cd pbl5_system
    python3 -m venv venv
    source venv/bin/activate
    ```

    *Đảm bảo thấy chữ `(venv)` ở đầu dòng lệnh.*

3. **Cài đặt các thư viện cần thiết**:

    ```bash
    pip install websockets asyncio requests
    ```

---

## Giai đoạn 5: Khởi chạy Máy chủ WebSocket

1. **Tạo file mã nguồn**:

    ```bash
    nano server.py
    ```

2. **Viết mã server** (Copy và dán đoạn code sau):

    ```python
    import asyncio
    import websockets
    import json

    async def job_delegation_handler(websocket):
        print(f"[+] Client kết nối từ: {websocket.remote_address}")
        try:
            async for message in websocket:
                print(f"[>] Nhận: {message}")
                response = {
                    "status": "success",
                    "message": "Đã ghi nhận gợi ý phân công",
                    "task_id": "TASK-001",
                    "assigned_action": "Processing Job Assignment..."
                }
                await websocket.send(json.dumps(response))
                print(f"[<] Đã gửi phản hồi.\n")
        except websockets.exceptions.ConnectionClosed:
            print(f"[-] Client {websocket.remote_address} ngắt kết nối.")

    async def main():
        async with websockets.serve(job_delegation_handler, "0.0.0.0", 8765):
            print("🚀 [WEBSOCKET] Server đang chạy tại cổng 8765...")
            await asyncio.Future()

    if __name__ == "__main__":
        asyncio.run(main())
    ```

3. **Lưu và Chạy**:
    * `Ctrl + O` -> `Enter` để lưu.
    * `Ctrl + X` để thoát.
    * Chạy server:

        ```bash
        python3 server.py
        ```

---
*Chúc mừng! Bạn đã hoàn thành việc thiết lập Raspberry Pi 4 làm WebSocker Server.*
