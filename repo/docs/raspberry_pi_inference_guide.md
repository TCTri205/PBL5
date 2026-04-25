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
3. **Tải về**: Lấy file `best.onnx` từ Colab.
4. **Deploy**: Copy file vào thư mục `~/pbl5_system/model/` trên Pi.

## 🚀 Chạy thử nghiệm

Sử dụng script `pi_inference.py` để kiểm tra với 1 ảnh tĩnh:

```bash
source venv/bin/activate
python pi_inference.py model/best.onnx test_image.jpg
```

## 🔍 Tối ưu hóa (Tips)

- **Input Size**: Sử dụng `imgsz=224` hoặc `imgsz=320` thay vì `640` để tăng tốc độ (giảm 2-3 lần latency).
- **Quantization**: Có thể sử dụng INT8 Quantization (Tuy nhiên cần calibrate để tránh giảm độ chính xác).
- **Multi-threading**: ONNX Runtime tự động tối ưu sử dụng 4 nhân của Pi 4.

## 🔗 Liên kết chi tiết

- [API Reference: pi_inference.py](./implementation/pi_inference.md)
- [Camera Stream Integration](./implementation/cam_stream.md)
- [Xử lý sự cố về AI/Model](./troubleshooting.md#model-inference)
