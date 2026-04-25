# 🍎 API Reference: `pi_inference.py`

Tài liệu tham khảo API cho script phân loại trái cây sử dụng ONNX Runtime trên Raspberry Pi.

## Tổng Quan

`pi_inference.py` là script độc lập dùng để chạy inference (dự đoán) trên mô hình YOLO đã được export sang định dạng ONNX. Script được thiết kế tối ưu cho Raspberry Pi 4, sử dụng CPUExecutionProvider để đảm bảo ổn định.

## 📁 Cấu Trúc Code

### Lớp `FruitClassifier`

Lớp chính xử lý toàn bộ pipeline inference.

### Constructor: `__init__(model_path, imgsz=320)`

Khởi tạo bộ phân loại với đường dẫn model và kích thước ảnh đầu vào.

**Tham số:**

- `model_path` (str): Đường dẫn tới file `.onnx` (ví dụ: `model/best.onnx`)
- `imgsz` (int): Kích thước ảnh đầu vào. Mặc định: `320`

**Thuộc tính:**

- `self.session`: ONNX Runtime Inference Session
- `self.input_name`: Tên input tensor
- `self.class_names`: Danh sách tên lớp [`'cam'`, `'chanh'`, `'quyt'`]
- `self.imgsz`: Kích thước ảnh

**Ví dụ:**

```python
from pi_inference import FruitClassifier

classifier = FruitClassifier('model/best.onnx')
```

---

### Phương thức: `preprocess(img)`

Tiền xử lý ảnh đầu vào thành tensor chuẩn cho model.

**Tham số:**

- `img` (numpy.ndarray): Ảnh BGR từ OpenCV (`cv2.imread()`)

**Quy trình xử lý:**

1. Chuyển BGR → RGB (`cv2.COLOR_BGR2RGB`)
2. Resize về `(imgsz, imgsz)` → `(320, 320)`
3. Chuyển `uint8` → `float32` và normalize `[0, 255]` → `[0.0, 1.0]`
4. Chuyển HWC (Height-Width-Channel) → CHW (Channel-Height-Width)
5. Thêm batch dimension: `(C, H, W)` → `(1, C, H, W)`

**Trả về:**

- `blob` (numpy.ndarray): Tensor shape `(1, 3, 320, 320)` dtype `float32`

---

### Phương thức: `predict(img_path, confidence_threshold=0.5)`

Dự đoán lớp của ảnh từ file.

**Tham số:**

- `img_path` (str): Đường dẫn tới file ảnh (JPEG/PNG)
- `confidence_threshold` (float): Ngưỡng confidence. Mặc định: `0.5`

**Quy trình:**

1. Đọc ảnh bằng `cv2.imread()`
2. Gọi `preprocess()` tạo tensor
3. Chạy inference: `session.run()`
4. Lấy xác suất từ output tensor
5. Áp dụng ngưỡng confidence
6. Trả về nhãn và độ tin cậy

**Trả về:**

- `label` (str): Tên lớp (`'cam'`, `'chanh'`, `'quyt'`, hoặc `'unknown'`)
- `confidence` (float): Xác suất (0.0 - 1.0)

**Ví dụ:**

```python
label, score = classifier.predict('test_image.jpg', confidence_threshold=0.6)
print(f"{label}: {score:.2%}")
# Output: cam: 95.32%
```

---

## 🖥️ Chế Độ Command-Line

Script có thể chạy trực tiếp từ terminal:

```bash
python pi_inference.py <model_path.onnx> <image_path>
```

**Tham số bắt buộc:**

1. `model_path.onnx`: File mô hình ONNX (ví dụ: `model/best.onnx`)
2. `image_path`: File ảnh đầu vào (ví dụ: `test.jpg`)

**Kiểm tra tồn tại file:**

- Script sẽ validate `model_file` tồn tại trước khi chạy
- Nếu file không tồn tại: `Error: Model file not found.`

**Output chuẩn ra màn hình:**

```text
--- Result ---
Predicted: CAM
Confidence: 98.45%
Inference time: 125.30 ms
```

**Ví dụ thực tế:**

```bash
# Chạy inference trên Raspberry Pi
cd ~/pbl5_system
source venv/bin/activate
python pi_inference.py model/best.onnx test_images/cam_01.jpg
```

---

## 🔧 Sử Dụng Trong Code (Integration)

### Ví dụ 1: Inference cơ bản

```python
import sys
sys.path.append('repo')
from pi_inference import FruitClassifier

# Khởi tạo classifier
classifier = FruitClassifier('model/best.onnx')

# Phân loại ảnh
label, confidence = classifier.predict('test.jpg')

if label != 'unknown':
    print(f"Phân loại: {label} (độ tin cậy: {confidence:.1%})")
else:
    print("Không nhận diện được")
```

### Ví dụ 2: Batch inference (nhiều ảnh)

```python
import glob
from pi_inference import FruitClassifier

classifier = FruitClassifier('model/best.onnx')
results = {}

for img_path in glob.glob('test_images/*.jpg'):
    label, score = classifier.predict(img_path)
    results[img_path] = {'label': label, 'confidence': score}
    print(f"{img_path}: {label} ({score:.2%})")
```

### Ví dụ 3: Real-time với ngưỡng cao

```python
from pi_inference import FruitClassifier

classifier = FruitClassifier('model/best.onnx')

# Chỉ chấp nhận dự đoán rất chắc chắn
label, score = classifier.predict('image.jpg', confidence_threshold=0.8)

if score >= 0.8:
    print(f"Chắc chắn: {label}")
else:
    print(f"Không chắc chắn ({score:.1%}), cần chụp lại")
```

---

## 📊 Định Dạng Output

### Output Tensor (ONNX Model)

- **Shape**: `(1, 3)` - Batch size × Số lớp
- **Ý nghĩa**: Xác suất cho mỗi lớp `[cam, chanh, quyt]`
- **Activation**: Softmax (đã được áp dụng trong model)
- **Range**: `[0.0, 1.0]`, tổng = 1.0

### Return Values

| Giá trị trả về | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `label` | `str` | Tên lớp hoặc `'unknown'` |
| `confidence` | `float` | Xác suất (0.0 - 1.0) |

### Exit Codes (Command-line)

| Code | Ý nghĩa |
| :--- | :--- |
| `0` | Thành công |
| `1` | Thiếu tham số hoặc file model không tồn tại |

---

## ⚡ Performance Benchmarks

**Raspberry Pi 4 (4GB) - ONNX Runtime CPU:**

- Kích thước ảnh đầu vào: 320×320
- Thời gian inference (không I/O): ~100-150ms
- RAM sử dụng: ~200-300MB
- CPU load: ~60-80% trên 1 core

**Lưu ý:** Thời gian thực tế bao gồm cả I/O đọc ảnh (~50-100ms thêm)

---

## 🚨 Xử Lý Lỗi (Error Handling)

### Lỗi thường gặp

1. **File ảnh không tồn tại**

   ```python
   label, score = classifier.predict('nonexistent.jpg')
   # Trả về: (None, 0.0)
   ```

2. **Model file không tồn tại**

   ```bash
   python pi_inference.py wrong_path.onnx image.jpg
   # Error: Model file wrong_path.onnx not found.
   # Exit code: 1
   ```

3. **Confidence thấp**

   ```python
   label, score = classifier.predict('blurry.jpg')
   # Trả về: ('unknown', 0.35) nếu threshold=0.5
   ```

### Best Practices

```python
# Luôn validate input
import os
if not os.path.exists(img_path):
    print(f"Lỗi: File {img_path} không tồn tại")
    sys.exit(1)

# Handle 'unknown' predictions
label, score = classifier.predict(img_path)
if label == 'unknown':
    print("⚠️  Độ tin cậy thấp, chụp lại ảnh")
    # Trigger: chụp lại hoặc báo lỗi
```

---

## 🔗 Liên Kết Mở Rộng

- **Workflow hoàn chỉnh**: [System Integration Plan](../system_integration_plan.md)
- **Camera Streaming**: [cam_stream.md](./cam_stream.md)
- **WebSocket Client**: [raspberry_pi_setup_guide.md](../raspberry_pi_setup_guide.md)
- **Setup Raspberry Pi**: [raspberry_pi_setup_guide.md](../raspberry_pi_setup_guide.md)

## 📝 Phiên Bản

| Phiên Bản | Ngày | Mô Tả |
| :--- | :--- | :--- |
| 1.0.0 | 2026-04-24 | Bản phát hành đầu tiên |
| 1.1.0 | 2026-04-25 | Cập nhật ONNX Runtime & Preprocessing |

---

*© 2026 - PBL5 Green Fruit Classification Project*  
*Generated from `repo/pi_inference.py`*
