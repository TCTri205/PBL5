# Hướng Dẫn Triển Khai YOLO Classification trên Raspberry Pi

Tài liệu này hướng dẫn cách đưa mô hình đã huấn luyện từ Google Colab về chạy trực tiếp trên Raspberry Pi 4 để nhận diện trái cây xanh (Cam, Chanh, Quýt).

## 1. Chuẩn bị Mô hình

Sau khi hoàn tất training trên Colab, bạn cần tải file mô hình đã export sang định dạng ONNX về máy tính, sau đó upload lên Raspberry Pi.

* **File cần thiết**: `best.onnx` (được tạo ra ở Cell 6 của notebook training).
* **Vị trí khuyên dùng trên Pi**: `~/pbl5_system/model/best.onnx`.

## 2. Cài đặt Thư viện trên Pi

Mở terminal trên Raspberry Pi (qua SSH) và thực hiện các lệnh sau:

```bash
# Truy cập vào môi trường ảo đã tạo ở Setup Guide
cd ~/pbl5_system
source venv/bin/activate

# Cài đặt các thư viện bổ trợ cho inference
pip install onnxruntime opencv-python-headless numpy
```

> [!NOTE]
> Chúng ta sử dụng `onnxruntime` thay vì `ultralytics` trên Pi để giảm dung lượng cài đặt và tối ưu tốc độ chạy trên CPU.

## 3. Sử dụng Script Inference

Tôi đã chuẩn bị sẵn script `pi_inference.py` trong thư mục `repo/`. Bạn có thể copy file này vào thư mục dự án trên Pi.

### Chạy kiểm tra với ảnh cụ thể

```bash
python pi_inference.py model/best.onnx test_image.jpg
```

### Script hỗ trợ

* **Tự động Pre-processing**: Resize ảnh về 320x320 và chuẩn hóa dữ liệu.

* **Confidence Threshold**: Mặc định là 0.5. Nếu độ tin cậy thấp hơn, script sẽ trả về `unknown`.
* **Tự động Pre-processing**: Resize ảnh về 320x320 và chuẩn hóa dữ liệu.
* **Confidence Threshold**: Mặc định là 0.5. Nếu độ tin cậy thấp hơn, script sẽ trả về `unknown`.
* **Tối ưu CPU**: Sử dụng `CPUExecutionProvider` của ONNX Runtime.

## 4. Tích hợp vào Hệ thống (Gợi ý)

Bạn có thể kết hợp script này với **Camera Module** hoặc **WebSocket Server**:

* **Camera**: Sử dụng `opencv` để capture frame từ camera.
* **Websocket**: Khi nhận được tín hiệu từ Server, Pi sẽ chụp ảnh, phân loại và gửi kết quả về qua WebSocket.

---
*Mẹo: Nếu bạn muốn chạy nhanh hơn nữa, hãy cân nhắc sử dụng các kit tăng tốc phần cứng như Google Coral Edge TPU.*
