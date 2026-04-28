# Hướng dẫn Triển khai YOLO Inference trên Raspberry Pi

Tài liệu này tập trung vào khía cạnh chạy mô hình AI (ONNX) để phân loại trái cây trên Raspberry Pi.

## 🏗️ Kiến trúc Inference

Để đạt hiệu suất cao nhất trên CPU ARM, chúng ta sử dụng **ONNX Runtime** làm engine thực thi chính thay vì sử dụng full YOLO backend của Ultralytics.

### Quy trình (Pipeline)

1. **RGB Image** (320x320)
2. **Normalization** (/255.0)
3. **Inference** (ONNX Session)
4. **Argmax** (Lấy index có xác suất cao nhất)

## 📁 Chuẩn bị Model

1. **Train** mô hình trên Google Colab.
2. **Export** sang ONNX: `model.export(format='onnx', imgsz=320, simplify=True)`.
3. **Deploy**: Đảm bảo file `best.onnx` nằm tại đường dẫn `repo/pi_edge/model/best.onnx`.

## 🚀 Cách chạy (Execution)

Chúng tôi đã chuẩn bị các script khởi động nhanh tại thư mục gốc của repository.

### 1. Chạy với ảnh tĩnh (Kiểm tra Model)

```bash
source venv/bin/activate
python pi_edge/fruit_classifier.py pi_edge/model/best.onnx test_image.jpg
```

### 2. Chạy Real-time Streaming (Sản xuất)

Sử dụng script `start_pi.py` để khởi động nhanh với nhiều tùy chọn:

```bash
python start_pi.py --server <IP_LAPTOP> --device-id "Gate-01" --resolution 320x320
```

#### Các tham số quan trọng

| Tham số | Mặc định | Ý nghĩa |
| :--- | :--- | :--- |
| `--server` | `192.168.1.10` | IP của Laptop đang chạy WebSocket Server |
| `--port` | `8765` | Port của WebSocket Server |
| `--device-id` | `pi-edge-01` | ID định danh cho thiết bị Pi này |
| `--resolution` | `640x480` | Độ phân giải camera (Khuyên dùng `320x320` để khớp model) |
| `--model` | `(auto)` | Đường dẫn tùy chỉnh tới file .onnx |

## 🔍 Tối ưu hóa (Tips)

- **Resolution Matching**: Để tốc độ nhanh nhất, hãy đặt `--resolution 320x320` để bỏ qua bước resize lãng phí CPU.
- **FPS Control**: Script mặc định chạy ở ~10 FPS để tránh nóng máy Pi 4.
- **Logging**: Theo dõi terminal để thấy thông báo `📤 Sent` khi nhận diện thành công.

## 🔗 Liên kết chi tiết

- [Kế hoạch tích hợp hệ thống](./system_integration_plan.md) ⭐
- [Thiết lập Raspberry Pi](./raspberry_pi_setup_guide.md)
- [Xử lý sự cố về AI/Model](./troubleshooting.md#model-inference)
