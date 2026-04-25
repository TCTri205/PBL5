# Hướng dẫn Camera Streaming & Real-time Inference

Tài liệu này hướng dẫn cách sử dụng script `cam_stream.py` để kết hợp chụp ảnh từ camera, phân loại bằng AI và gửi kết quả về máy chủ giám sát.

## 📋 Yêu cầu chuẩn bị

1. **Hardware**: Raspberry Pi 4 + USB Webcam.
2. **Software**: Đã cài đặt `opencv-python-headless`, `onnxruntime`, `websockets`.
3. **Model**: Đã có file `model/best.onnx` trên Pi.
4. **Server**: Laptop đã chạy `server.py`.

## 🚀 Cách thức hoạt động

Script `cam_stream.py` thực hiện một vòng lặp (loop) liên tục:

1. **Capture**: Sử dụng OpenCV để lấy 1 frame từ camera.
2. **Inference**: Sử dụng class `FruitClassifier` (từ `pi_inference.py`) để phân loại trái cây trong frame đó.
3. **Filter**: Chỉ lấy các kết quả có độ tin cậy (confidence) cao hơn ngưỡng quy định.
4. **Send**: Gửi kết quả dưới dạng JSON qua WebSocket tới Laptop.

## 💻 Cấu trúc tham số chính

Trong file `cam_stream.py`, bạn cần lưu ý các biến sau:

```python
# Địa chỉ server (Laptop)
SERVER = "ws://<LAPTOP_IP>:8765"

# Ngưỡng tin cậy để gửi kết quả
confidence_thresh = 0.5 

# Độ phân giải chụp ảnh
resolution = (640, 480)
```

## 🛠️ Hướng dẫn chạy

1. **Trên Laptop**:

   ```bash
   python server.py
   ```

2. **Trên Raspberry Pi**:

   ```bash
   source venv/bin/activate
   python cam_stream.py
   ```

## 📊 Định dạng dữ liệu gửi đi (JSON)

Mỗi khi nhận diện thành công, một gói tin JSON sẽ được gửi:

```json
{
    "device_id": "pi-edge-01",
    "frame_id": 124,
    "timestamp": 1713945600.123,
    "label": "cam",
    "confidence": 0.92
}
```

## 🔗 Liên kết liên quan

- [API Reference: pi_inference.py](./pi_inference.md)
- [Kế hoạch tích hợp hệ thống](../system_integration_plan.md)
- [Xử lý sự cố về camera](../troubleshooting.md#camera-issues)
