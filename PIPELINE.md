# PIPELINE HỆ THỐNG PHÂN LOẠI TRÁI CÂY XANH PBL5

## 1. Tổng quan Hệ thống

Hệ thống phân loại trái cây xanh PBL5 sử dụng kiến trúc **Edge Inference + Remote Monitoring**, bao gồm hai pipeline chính:

1. **Pipeline Huấn luyện (Training Pipeline)** - Chạy trên Google Colab: chuẩn bị dữ liệu, huấn luyện mô hình YOLO, xuất ONNX
2. **Pipeline Triển khai (Deployment Pipeline)** - Chạy trên Raspberry Pi + Laptop: suy luận biên, phân loại thời gian thực, điều khiển phần cứng

```
┌──────────────────────────────────────────────────────────────────────┐
│                        TỔNG QUAN HỆ THỐNG                            │
│                                                                      │
│  ┌─────────────────────┐         WebSocket         ┌────────────────┐│
│  │    Raspberry Pi 5    │◄────────────────────────►│   Laptop Server ││
│  │    (Edge Device)     │    ws://<IP>:8765/ws/pi   │   (Monitoring)  ││
│  │                     │                           │                ││
│  │  • Camera Streamer   │                           │  • WebSocket    ││
│  │  • Fruit Classifier  │                           │    Server       ││
│  │  • Conveyor Control  │                           │  • Dashboard    ││
│  │  • Servo Sorter      │                           │    Web UI       ││
│  └─────────────────────┘                           └────────────────┘│
│           │                                                     │     │
│           │ GPIO                                                │     │
│           ▼                                                     ▼     │
│  ┌─────────────────┐                                  ┌────────────┐ │
│  │ L298N | E18-D80NK│                                 │ Browser    │ │
│  │ MG996R x3| DV20  │                                 │ Dashboard  │ │
│  └─────────────────┘                                  └────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### Phân loại

Hệ thống phân loại 3 loại trái cây xanh:

| Label | Tên | Icon |
|-------|-----|------|
| `cam` | Cam (Orange) | 🍊 |
| `chanh` | Chanh (Lime) | 🍋 |
| `quyt` | Quýt (Mandarin) | 🟠 |
| `unknown` | Không xác định | ❓ |

---

## 2. Pipeline Huấn luyện (Training Pipeline)

Pipeline huấn luyện chạy trên Google Colab, sử dụng YOLOv8/v11/v12 với chiến lược **SSD-first** để tránh thắt cổ chai I/O của Google Drive.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TRAINING PIPELINE (Google Colab)                  │
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────┐  │
│  │ 1. Mount │───►│ 2. Copy  │───►│ 3. Train  │───►│ 4. Validate  │  │
│  │  Drive   │    │ to SSD   │    │  YOLO     │    │ & Test       │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────────┘  │
│                                                          │         │
│                                                          ▼         │
│                                                   ┌──────────────┐  │
│                                                   │ 5. Export    │  │
│                                                   │    ONNX      │  │
│                                                   └──────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Bước 1: Mount Google Drive & Sao chép dữ liệu sang SSD
- Mount Google Drive chứa dataset và checkpoint
- Copy toàn bộ dữ liệu từ Drive sang SSD cục bộ của Colab (`/content/`)
- **Lý do**: SSD cục bộ có tốc độ I/O cao hơn nhiều so với Google Drive FUSE, tránh làm chậm DataLoader

### Bước 2: Chuẩn bị dữ liệu
- Dataset tổ chức theo cấu trúc YOLO classification:
  ```
  dataset/
  ├── train/
  │   ├── cam/       # Ảnh cam xanh
  │   ├── chanh/     # Ảnh chanh xanh
  │   └── quyt/      # Ảnh quýt xanh
  ├── val/
  │   ├── cam/
  │   ├── chanh/
  │   └── quyt/
  └── test/
      ├── cam/
      ├── chanh/
      └── quyt/
  ```
- Data augmentation: tự động bởi YOLO (mosaic, flip, HSV adjustment, scale, translate)

### Bước 3: Huấn luyện YOLO
- Sử dụng Ultralytics YOLO (v8/v11/v12) với task `classify`
- Hyperparameters chính:
  - `imgsz`: 320 (tối ưu cho Raspberry Pi CPU)
  - `epochs`: 100+
  - `batch`: 32 (tùy thuộc vào VRAM Colab)
  - `optimizer`: AdamW
- **Resume training**: Tự động phát hiện checkpoint từ Drive và tiếp tục huấn luyện

### Bước 4: Validate & Test
- Đánh giá trên tập validation sau mỗi epoch
- Test cuối cùng trên tập test riêng
- Metrics: Accuracy, Precision, Recall, F1-Score, Confusion Matrix

### Bước 5: Export ONNX
- Xuất mô hình sang định dạng **ONNX** với `opset=12`
- ONNX Simplifier để tối ưu đồ thị tính toán
- File output: `best.onnx`
- **Lý do dùng ONNX**: ONNX Runtime trên Raspberry Pi nhanh hơn đáng kể so với PyTorch nguyên bản, đặc biệt khi chỉ dùng CPU

### Bước 6: Đồng bộ về Drive
- Sao chép tất cả kết quả (weights, ONNX, metrics) từ SSD về Google Drive
- Đảm bảo checkpoint được lưu an toàn ngay cả khi Colab bị ngắt kết nối

---

## 3. Pipeline Triển khai (Deployment Pipeline)

### 3.1 Kiến trúc Tổng thể

```
┌───────────────────────────────────────────────────────────────────┐
│                     DEPLOYMENT PIPELINE                            │
│                                                                   │
│   Raspberry Pi 5                          Laptop Server            │
│   ┌─────────────────────┐               ┌─────────────────────┐   │
│   │                     │   WebSocket   │                     │   │
│   │  cam_stream.py      │◄─────────────►│  server.py          │   │
│   │  (CameraStreamer)   │   JSON+Base64  │  (aiohttp)          │   │
│   │                     │               │                     │   │
│   │  ┌───────────────┐  │               │  ┌───────────────┐  │   │
│   │  │FruitClassifier│  │               │  │  Dashboard    │  │   │
│   │  │(ONNX Runtime) │  │               │  │  Web UI       │  │   │
│   │  └───────────────┘  │               │  └───────────────┘  │   │
│   │  ┌───────────────┐  │               │  ┌───────────────┐  │   │
│   │  │ConveyorCtrl   │  │               │  │  Browser      │  │   │
│   │  │+ ServoSorter  │  │               │  │  Clients      │  │   │
│   │  └───────────────┘  │               │  └───────────────┘  │   │
│   └─────────────────────┘               └─────────────────────┘   │
└───────────────────────────────────────────────────────────────────┘
```

### 3.2 Cấu trúc Mã nguồn

```
repo/
├── start_pi.py                     # Entry point cho Raspberry Pi
├── start_server.py                 # Entry point cho Laptop Server
├── requirements.txt                # opencv, onnxruntime, aiohttp, websockets, numpy, gpiozero
├── pi_edge/
│   ├── cam_stream.py               # Bộ điều phối pipeline chính (CameraStreamer)
│   ├── fruit_classifier.py         # Phân loại ảnh bằng ONNX Runtime (FruitClassifier)
│   ├── conveyor_controller.py      # Điều khiển phần cứng (ConveyorController + ServoSorter)
│   ├── check_hardware.py           # Công cụ chẩn đoán phần cứng
│   └── model/
│       └── best.onnx               # Mô hình ONNX đã huấn luyện
├── laptop_server/
│   ├── server.py                   # WebSocket server (aiohttp)
│   └── static/
│       ├── index.html              # Dashboard HTML
│       └── js/
│           └── dashboard.js        # Dashboard logic (WebSocket client)
└── tests/
    ├── test_streamer.py            # Unit test cho CameraStreamer
    └── test_conveyor_controller.py # Unit test cho ConveyorController
```

---

## 4. Vòng lặp Chính - `CameraStreamer.run_pipeline()`

Đây là trái tim của hệ thống. Mỗi lần phát hiện một quả, pipeline thực hiện đúng 10 bước:

```
┌──────────────────────────────────────────────────────────────────────┐
│                    MAIN PIPELINE LOOP (10 BƯỚC)                       │
│                                                                      │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐    │
│  │B1:   │ │B2:   │ │B3:   │ │B4:   │ │B5:   │ │B6:   │ │B7:   │    │
│  │Chạy   │ │Đợi   │ │Dừng  │ │Chụp  │ │Phân  │ │Gửi   │ │Gạt   │    │
│  │băng   │►│vật   │►│băng  │►│ảnh   │►│loại  │►│kết   │►│servo │    │
│  │chuyền │ │cản  │ │chuyền│ │      │ │      │ │quả   │ │      │    │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘    │
│                                                             │       │
│                                          ┌──────┐ ┌──────┐  │       │
│                                          │B10:  │ │B9:   │  │       │
│                                          │Đợi   │◄│Đợi   │◄┘       │
│                                          │servo │ │clear │          │
│                                          │thu về│ │sensor│          │
│                                          └──────┘ └──────┘          │
│                                              │                      │
│                                              ▼                      │
│                                          ┌──────┐                   │
│                                          │B8:   │                   │
│                                          │Chạy  │                   │
│                                          │lại   │                   │
│                                          │băng  │                   │
│                                          └──────┘                   │
└──────────────────────────────────────────────────────────────────────┘
```

### Chi tiết từng bước (dựa trên `cam_stream.py` dòng 296-398):

#### Bước 0: Khởi tạo (trước vòng lặp)
```python
# QUAN TRỌNG: Camera init TRƯỚC, Conveyor init SAU
# Lý do: Servo software PWM gây nhiễu USB isochronous transfer
#        → làm camera DV20 không stream được
self.cap = self.init_camera(manual_idx=cam_idx)
if self.conveyor is None:
    self.conveyor = ConveyorController(sensor_active_low=self.sensor_active_low)
self.conveyor.start()  # Băng chuyền chạy ngược → đưa quả về sensor
await asyncio.sleep(2.0)  # Chờ ổn định phần cứng
```

#### Bước 1: Đảm bảo băng chuyền đang chạy
```python
if not self.conveyor._running:
    self.conveyor.start()
```
- Kiểm tra và khởi động lại băng chuyền nếu cần
- Băng chuyền chạy chiều NGƯỢC để đưa quả về phía cảm biến

#### Bước 2: Chờ cảm biến phát hiện trái cây
```python
if not await self.conveyor.wait_for_object(timeout=30.0):
    continue  # Timeout → quay lại bước 1
```
- Sử dụng debouncing: yêu cầu **2 lần đọc liên tiếp** (cách nhau 50ms) sensor bị chặn
- Timeout mặc định 30 giây, sau đó tiếp tục vòng lặp
- Cảm biến E18-D80NK: **active-low** (GPIO LOW = có vật cản, GPIO HIGH = trống)

#### Bước 3: Dừng băng chuyền để chụp ảnh ổn định
```python
self.conveyor.stop()
await asyncio.sleep(self.capture_delay)  # Mặc định 0.2s
```
- Dừng motor L298N hoàn toàn (cả 2 chân IN1, IN2 = LOW)
- Chờ 200ms để camera ổn định, tránh motion blur

#### Bước 4: Chụp ảnh
```python
ret, frame = self._read_with_timeout(self.cap, timeout=5.0)
```
- Sử dụng `cv2.VideoCapture.read()` với timeout 5 giây qua thread riêng
- Nếu thất bại:
  - Tăng `cam_fail_count`
  - **Tạm dừng servo PWM** (tránh nhiễu USB)
  - Release camera và **re-init từ đầu** (blocking read với V4L2 timeout ~10s)
  - Kích hoạt lại servo
  - Nếu fail 3 lần liên tiếp → `FatalPipelineError` → dừng toàn bộ hệ thống
- Sau khi re-init, đợi sensor clear trước khi tiếp tục (tránh chụp lại cùng quả)

#### Bước 5: Chạy inference (phân loại trái cây)
```python
label, confidence = await loop.run_in_executor(
    self.executor, self.classifier.predict, frame, self.confidence_thresh
)
```
- Chạy trong **ThreadPoolExecutor** (max_workers=1) để không block event loop
- `FruitClassifier.predict()` thực hiện:
  1. Resize ảnh về `320x320` (BGR)
  2. Chuyển BGR → RGB
  3. Normalize [0, 1] float32
  4. Chuyển HWC → CHW, thêm batch dimension → (1, 3, 320, 320)
  5. ONNX Runtime inference (CPUExecutionProvider)
  6. Softmax → argmax → (label, confidence)
  7. Nếu confidence < threshold (mặc định 0.5): trả về `("unknown", confidence)`

#### Bước 6: Gửi kết quả lên server & chờ ACK
```python
for retry in range(3):
    if await self.send_result(label, confidence, frame_id, frame=frame):
        break
    await asyncio.sleep(1)
```
- **Retry tối đa 3 lần** nếu gửi thất bại hoặc không nhận được ACK
- Sau 3 lần thất bại → `FatalPipelineError` (bảo vệ chống mất dữ liệu)
- Chi tiết cơ chế gửi (xem Mục 5)

#### Bước 7: Kích hoạt servo gạt
```python
if label and label != "unknown":
    servo_task = await self.conveyor.sorter.activate(label)
```
- Servo gạt theo góc đã cấu hình (mặc định 40°)
- Tạo `asyncio.Task` để tự động thu servo về 0° sau khoảng delay:
  - `cam`: 5 giây
  - `chanh`: 8 giây
  - `quyt`: 11 giây
- Nếu servo cho label đó đang trong quá trình reset, task cũ bị cancel để tránh xung đột

#### Bước 8: Chạy lại băng chuyền
```python
self.conveyor.start()
```
- Motor L298N chạy chiều ngược (IN1=LOW, IN2=HIGH)
- Quả di chuyển trên băng → gặp chắn nghiêng của servo → trượt/rớt vào rổ phân loại

#### Bước 9: Đợi quả rời khỏi vùng sensor
```python
await asyncio.sleep(self.resume_delay)  # Mặc định 1.0s
if not await self._wait_for_clear_safe():
    raise FatalPipelineError("Cảm biến vẫn bị che sau khi phân loại.")
```
- `_wait_for_clear_safe()` có debouncing: yêu cầu **3 lần đọc liên tiếp** sensor trống
- Thử tối đa `max_retries` lần (mặc định 3), mỗi lần chờ `wait_clear_timeout` giây (mặc định 10s)
- Nếu sensor vẫn kẹt sau `sensor_bypass_timeout` giây (mặc định 20s):
  - **Mặc định**: Dừng băng chuyền, trả về `False` → `FatalPipelineError`
  - **Nếu bật `--enable-sensor-bypass`**: Cảnh báo nhưng vẫn tiếp tục pipeline
- Safety check: Đảm bảo băng chuyền đang CHẠY trong suốt quá trình chờ (nếu không, tự động khởi động lại)

#### Bước 10: Đợi servo thu chắn nghiêng về
```python
if servo_task:
    try:
        await servo_task
    except asyncio.CancelledError:
        pass
```
- Đợi servo tự động reset về 0° (nếu chưa xong)
- Mục đích: tránh quả tiếp theo bị chắn nhầm
- Nếu task bị cancel (do có lệnh activate mới), bỏ qua

---

## 5. Giao thức WebSocket

### 5.1 Kết nối

```
Raspberry Pi ─── ws://<IP>:8765/ws/pi ───► Laptop Server
Browser      ─── ws://<IP>:8765/ws/dashboard ───► Laptop Server
```

- **Pi WebSocket**: `ws://<server_ip>:8765/ws/pi` (gửi kết quả, nhận ACK)
- **Dashboard WebSocket**: `ws://<server_ip>:8765/ws/dashboard` (nhận broadcast)
- **Dashboard HTTP**: `http://<server_ip>:8765/` (trang web)
- Keep-alive: `ping_interval=20s`, `ping_timeout=10s`

### 5.2 Payload từ Pi → Server

```json
{
    "device_id": "pi-edge-01",
    "frame_id": 123,
    "timestamp": 1715030400.456,
    "label": "cam",
    "confidence": 0.95,
    "conveyor_status": "stopped",
    "image": "<base64_encoded_jpeg>"
}
```

| Field | Type | Mô tả |
|-------|------|-------|
| `device_id` | string | ID duy nhất của Pi (mặc định: `pi-edge-01`) |
| `frame_id` | int | Số thứ tự frame (tăng dần, dùng cho idempotency) |
| `timestamp` | float | Unix timestamp lúc chụp ảnh |
| `label` | string | Nhãn dự đoán: `cam`, `chanh`, `quyt`, `unknown` |
| `confidence` | float | Độ tin cậy [0.0, 1.0] |
| `conveyor_status` | string | Trạng thái băng chuyền: `stopped` hoặc `running` |
| `image` | string \| null | Ảnh JPEG base64 (quality=50, độ phân giải 640x480) |

### 5.3 Cơ chế ACK (Acknowledgment)

Để đảm bảo dữ liệu không bị mất, hệ thống sử dụng cơ chế **ACK 3 bước**:

```
Pi                                          Server
 |─────── send(payload + frame_id) ────────►|
 |                                          |
 |  (đăng ký future cho frame_id)            |
 |                                          |
 |◄────── {"status":"success",              |
 |         "ack_frame": frame_id} ──────────|
 |                                          |
 |  (resolve future → gửi thành công)        |
```

**Chi tiết (theo `cam_stream.py` dòng 128-169):**

1. **Đăng ký Future TRƯỚC khi gửi** - Tránh race condition: nếu server phản hồi quá nhanh, message ACK có thể đến trước khi Future được đăng ký
2. **Gửi dữ liệu** qua WebSocket
3. **Đợi ACK** với timeout 3 giây (`asyncio.wait_for`)
4. **Dọn dẹp** Future trong `finally` block để tránh memory leak

**Phía Server (theo `server.py` dòng 65-72):**

- Kiểm tra **idempotency**: nếu `frame_id` đã được xử lý → chỉ gửi ACK, không broadcast lại
- Validate schema: kiểm tra đầy đủ các field bắt buộc và kiểu dữ liệu
- Broadcast kết quả tới tất cả Dashboard clients song song (`asyncio.gather`)
- Gửi ACK về Pi

### 5.4 Broadcast tới Dashboard

Server broadcast nguyên payload từ Pi tới tất cả Dashboard clients đang kết nối:

```
Pi ──send──► Server ──broadcast──► Dashboard Client 1
                             ────► Dashboard Client 2
                             ────► Dashboard Client N
```

Dashboard (`dashboard.js`) xử lý payload:
- Hiển thị ảnh trực tiếp (`live-feed`)
- Cập nhật kết quả phân loại hiện tại (icon, label, confidence bar)
- Cập nhật thống kê (số lượng từng loại quả)
- Thêm vào bảng lịch sử (tối đa 50 mục)
- Tính toán latency: `Date.now() - timestamp*1000`
- Tự động reconnect sau 3 giây nếu mất kết nối

---

## 6. Phần cứng & GPIO

### 6.1 Sơ đồ chân GPIO (Raspberry Pi)

```
                        Raspberry Pi 5 GPIO
    ┌──────────────────────────────────────────────┐
    │                                              │
    │  GPIO 17 (Input, Pull-Up)                     │
    │     └── E18-D80NK Proximity Sensor (OUT)      │
    │         • Active-Low: LOW = vật cản            │
    │         • Khoảng cách phát hiện: 3-80cm        │
    │                                              │
    │  GPIO 22 (Output)                             │
    │     └── L298N IN2 (Motor Chiều Ngược)          │
    │                                              │
    │  GPIO 23 (Output)                             │
    │     └── L298N IN1 (Motor Chiều Thuận)          │
    │                                              │
    │  GPIO 5 (PWM - Software)                      │
    │     └── MG996R Servo #1 ── CAM (Orange)       │
    │         • Góc gạt: 40°, Delay reset: 5s       │
    │                                              │
    │  GPIO 6 (PWM - Software)                      │
    │     └── MG996R Servo #2 ── CHANH (Lime)      │
    │         • Góc gạt: 40°, Delay reset: 8s       │
    │                                              │
    │  GPIO 26 (PWM - Software)                     │
    │     └── MG996R Servo #3 ── QUYT (Mandarin)   │
    │         • Góc gạt: 40°, Delay reset: 11s      │
    │                                              │
    └──────────────────────────────────────────────┘
```

### 6.2 Linh kiện

| Linh kiện | Model | Chức năng | GPIO |
|-----------|-------|-----------|------|
| Camera | Jieli Technology DV20 (USB) | Chụp ảnh trái cây | USB |
| Motor Driver | L298N | Điều khiển băng chuyền | 22, 23 |
| Cảm biến | E18-D80NK (IR Proximity) | Phát hiện vật cản | 17 |
| Servo 1 | MG996R | Gạt cam vào rổ | 5 |
| Servo 2 | MG996R | Gạt chanh vào rổ | 6 |
| Servo 3 | MG996R | Gạt quýt vào rổ | 26 |

### 6.3 Logic Cảm biến (E18-D80NK)

Cảm biến sử dụng wiring **active-low** với pull-up nội:

```python
# conveyor_controller.py dòng 147
self.sensor = DigitalInputDevice(sensor_pin, pull_up=True)
```

- **GPIO LOW** (0V) = Cảm biến phát hiện vật cản → `sensor.is_active = True` → `has_object = True`
- **GPIO HIGH** (3.3V) = Không có vật cản → `sensor.is_active = False` → `has_object = False`

Hỗ trợ cả active-high qua flag `--sensor-active-high` (đảo logic).

### 6.4 Điều khiển Motor (L298N)

```python
# conveyor_controller.py dòng 170-182
def start(self):
    self.motor_fwd.off()   # IN1 = LOW
    self.motor_bwd.on()    # IN2 = HIGH  → Chạy chiều ngược
    self._running = True

def stop(self):
    self.motor_fwd.off()   # IN1 = LOW
    self.motor_bwd.off()   # IN2 = LOW  → Dừng hoàn toàn
    self._running = False
```

- Băng chuyền chạy **chiều ngược** để đưa quả từ vị trí thả về phía cảm biến
- Sử dụng `DigitalOutputDevice` (ON/OFF) thay vì PWM để tránh lỗi tương thích với driver Native/LGPIO trên Pi 5

### 6.5 Điều khiển Servo (MG996R)

```python
# conveyor_controller.py dòng 58-108
class ServoSorter:
    DEFAULT_CONFIG = {
        "cam":   (5,  5.0,  40),   # (GPIO pin, delay reset, góc gạt)
        "chanh": (6,  8.0,  40),
        "quyt":  (26, 11.0, 40),
    }
```

Cơ chế gạt:
1. Servo gạt đến **40°** → tạo chắn nghiêng trên băng chuyền
2. Quả trượt theo chắn nghiêng → rơi vào rổ phân loại
3. Sau delay (5/8/11 giây tùy loại quả), servo tự động thu về **0°** (vị trí nghỉ)
4. Sử dụng `AngularServo` với `min_pulse_width=0.0005`, `max_pulse_width=0.0025`

**Lưu ý quan trọng về Software PWM:**
- Servo sử dụng software PWM của gpiozero
- PWM này gây **nhiễu USB isochronous transfer**, làm camera DV20 không stream được
- **Giải pháp**: Khởi tạo camera TRƯỚC, ConveyorController (có servo) SAU
- Khi re-init camera: tạm dừng servo PWM (`servo.value = None`), init camera, rồi kích hoạt lại

### 6.6 Camera (DV20 USB)

```python
# cam_stream.py dòng 197-246
def init_camera(self, manual_idx=None):
    # 1. Thử V4L2 backend trước (ổn định hơn trên Linux)
    cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
    
    # 2. Ép MJPEG format (YUYV quá nặng bandwidth)
    fourcc = cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')
    cap.set(cv2.CAP_PROP_FOURCC, fourcc)
    
    # 3. BLOCKING read — đợi frame đầu tiên
    #    Camera DV20 cần 6-9 giây warm up
    ret, frame = cap.read()
```

- Backend: V4L2 (ổn định nhất trên Raspberry Pi)
- Format: **MJPEG** (bắt buộc - YUYV quá nặng bandwidth USB, gây `select() timeout`)
- Độ phân giải: 640x480 (có thể tùy chỉnh qua `--resolution`)
- Warm-up: **6-9 giây** cho frame đầu tiên → dùng blocking `cap.read()` (KHÔNG dùng thread timeout)
- Fallback: thử indices 0, 1, 2; nếu manual index fail → auto-discovery

---

## 7. Xử lý Lỗi & An toàn

### 7.1 FatalPipelineError

`FatalPipelineError` là exception đặc biệt đánh dấu các lỗi **không thể tự phục hồi**, yêu cầu dừng toàn bộ hệ thống:

| Tình huống | Hành động |
|------------|-----------|
| Camera không mở được sau tất cả chiến lược | `sys.exit(1)` |
| Camera fail 3 lần liên tiếp | Dừng motor, raise FatalPipelineError |
| Camera fail + sensor kẹt | Dừng motor, raise FatalPipelineError |
| Không gửi được dữ liệu sau 3 lần retry | Dừng motor, raise FatalPipelineError |
| Sensor không clear sau khi phân loại | Dừng motor, raise FatalPipelineError |

### 7.2 Cơ chế An toàn

#### Camera Recovery
```
Camera fail → cam_fail_count++
           → Tạm dừng servo PWM
           → Release camera
           → Re-init từ đầu (blocking read)
           → Kích hoạt lại servo
           → Nếu vẫn fail: đợi sensor clear rồi continue
           → Nếu fail 3 lần: FatalPipelineError
```

#### Sensor Stuck Protection (`_wait_for_clear_safe`)
```
wait_until_clear(timeout=10s)
  ├── Thất bại → retry (tối đa 3 lần)
  ├── Tổng thời gian >= sensor_bypass_timeout (20s)
  │     ├── bypass_enabled=False → DỪNG motor, return False → FATAL
  │     └── bypass_enabled=True  → CẢNH BÁO, return True → tiếp tục
  └── Đảm bảo băng chuyền LUÔN chạy trong khi chờ
```

#### WebSocket Reconnection
```
main() vòng lặp ngoài:
  while True:
      if connect() thành công:
          run_pipeline()  ← có thể raise FatalPipelineError
          cleanup()
      else:
          sleep 5s → retry connect
```

#### Idempotency (Server-side)
```python
# server.py dòng 70-72
if last_processed_frames.get(device_id) == frame_id:
    await send_ack(frame_id)  # Vẫn gửi ACK
    continue                   # Nhưng không broadcast lại
```

### 7.3 Debouncing

| Thao tác | Số lần đọc liên tiếp | Khoảng cách | Mục đích |
|----------|---------------------|-------------|----------|
| `wait_for_object` | 2 lần | 50ms | Tránh false positive do nhiễu |
| `wait_until_clear` | 3 lần | 50ms | Đảm bảo quả đã đi qua hẳn |

### 7.4 Signal Handling

```python
# cam_stream.py dòng 585-600
for sig in (signal.SIGINT, signal.SIGTERM):
    signal.signal(sig, lambda *_: handle_exit())
```
- Bắt cả Ctrl+C (SIGINT) và Systemd SIGTERM
- Shutdown conveyor đúng cách trong `finally` block của `main()`

---

## 8. Các Lớp Chính

### 8.1 `FruitClassifier` (`fruit_classifier.py`)

```
┌──────────────────────────────────────┐
│          FruitClassifier              │
│                                       │
│  __init__(model_path, imgsz=320)      │
│    └── ONNX Runtime InferenceSession │
│        (CPUExecutionProvider)         │
│    └── Auto-detect class names        │
│        từ model metadata (YOLO)       │
│                                       │
│  preprocess(img: np.ndarray)          │
│    BGR → Resize 320x320 → RGB        │
│    → Float32 / 255.0 → CHW → Batch  │
│    → shape: (1, 3, 320, 320)        │
│                                       │
│  predict(input, threshold=0.5)        │
│    → ONNX session.run()              │
│    → Softmax → argmax                │
│    → (label, confidence)             │
│    → "unknown" nếu < threshold       │
└──────────────────────────────────────┘
```

### 8.2 `ConveyorController` (`conveyor_controller.py`)

```
┌──────────────────────────────────────┐
│        ConveyorController             │
│                                       │
│  __init__(motor_fwd=22, motor_bwd=23, │
│           sensor=17, active_low=True) │
│    └── L298N Motor Driver (2 chân)   │
│    └── E18-D80NK Sensor (Pull-Up)    │
│    └── ServoSorter (3 servo MG996R)  │
│                                       │
│  start()      → Chạy băng chuyền      │
│  stop()       → Dừng băng chuyền      │
│  shutdown()   → Giải phóng GPIO      │
│  has_object   → Property: có vật cản? │
│                                       │
│  wait_for_object(timeout=30s)         │
│    → Debounce 2 lần, polling 50ms    │
│                                       │
│  wait_until_clear(timeout=5s)         │
│    → Debounce 3 lần, polling 50ms    │
└──────────────────────────────────────┘
```

### 8.3 `ServoSorter` (`conveyor_controller.py`)

```
┌──────────────────────────────────────┐
│            ServoSorter                │
│                                       │
│  DEFAULT_CONFIG:                      │
│    "cam"   → GPIO 5,  5.0s,  40°    │
│    "chanh" → GPIO 6,  8.0s,  40°    │
│    "quyt"  → GPIO 26, 11.0s, 40°    │
│                                       │
│  activate(label) → asyncio.Task       │
│    1. Cancel task reset cũ (nếu có)  │
│    2. Gạt servo → active_angle       │
│    3. Tạo background task reset      │
│       (đợi delay giây → về 0°)       │
│    4. Return task (để caller await)  │
│                                       │
│  reset_all() → Tất cả servo về 0°    │
│  close()     → Cancel tasks + giải   │
│                phóng GPIO            │
└──────────────────────────────────────┘
```

### 8.4 `CameraStreamer` (`cam_stream.py`)

```
┌──────────────────────────────────────────────────────┐
│                  CameraStreamer                       │
│                                                       │
│  __init__(model_path, server_url, ...)                │
│    └── FruitClassifier (ONNX)                        │
│    └── ThreadPoolExecutor(max_workers=1)              │
│    └── _acks: dict[frame_id → Future]                │
│    └── conveyor = None (hoãn khởi tạo)               │
│                                                       │
│  connect() → WebSocket + consumer task                │
│  init_camera() → MJPEG, V4L2, blocking read          │
│  send_result() → Gửi + đợi ACK (3s timeout)         │
│  run_pipeline() → Vòng lặp 10 bước chính              │
│  _wait_for_clear_safe() → Debounce + bypass logic    │
│  cleanup() → Release camera + close WS               │
└──────────────────────────────────────────────────────┘
```

---

## 9. Luồng Dữ liệu End-to-End

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    LUỒNG DỮ LIỆU END-TO-END                              │
│                                                                         │
│  ┌──────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐ │
│  │Camera│   │Fruit     │   │WebSocket │   │aiohttp   │   │Dashboard │ │
│  │DV20  │──►│Classifier│──►│Client    │──►│Server    │──►│Browser   │ │
│  │      │   │(ONNX)    │   │(Pi)      │   │(Laptop)  │   │(JS)      │ │
│  └──────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘ │
│     │             │              │              │              │        │
│     │ BGR frame   │ (label,      │ JSON payload │ Broadcast    │        │
│     │ 640x480     │  confidence) │ + base64 img │ to all       │        │
│     │             │              │ + frame_id   │ dashboards   │        │
│     │             │              │              │              │        │
│     │             │              │◄──── ACK ────│              │        │
│     │             │              │  {status:    │              │        │
│     │             │              │   "success", │              │        │
│     │             │              │   ack_frame} │              │        │
│     ▼             ▼              ▼              ▼              ▼        │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Chu kỳ đầy đủ cho 1 quả: ~8-15 giây                              │  │
│  │  • Chờ sensor:      0-30s (timeout)                              │  │
│  │  • Chụp + inference: ~200ms (ONNX CPU)                           │  │
│  │  • Gửi + ACK:        ~50-100ms (LAN)                             │  │
│  │  • Gạt + chờ clear:  5-11s (tùy loại quả)                        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Cách Chạy Hệ Thống

### 10.1 Khởi động Laptop Server

```bash
cd repo/
python start_server.py --host 0.0.0.0 --port 8765
```

hoặc trực tiếp:

```bash
cd repo/laptop_server/
python server.py --host 0.0.0.0 --port 8765
```

### 10.2 Khởi động Raspberry Pi

```bash
cd repo/
python start_pi.py --server <LAPTOP_IP> --port 8765
```

Các tham số quan trọng:

| Tham số | Mặc định | Mô tả |
|---------|----------|-------|
| `--server` | `192.168.1.10` | IP của Laptop Server |
| `--port` | `8765` | WebSocket Port |
| `--model` | `pi_edge/model/best.onnx` | Đường dẫn model ONNX |
| `--device-id` | `pi-edge-01` | ID duy nhất cho Pi này |
| `--cam-idx` | auto-detect | Ép buộc camera index cụ thể |
| `--resolution` | `640x480` | Độ phân giải camera (WxH) |
| `--capture-delay` | `0.2` | Delay sau khi dừng motor (giây) |
| `--resume-delay` | `1.0` | Thời gian tối thiểu để quả di chuyển ra (giây) |
| `--clear-timeout` | `10.0` | Timeout mỗi lần chờ sensor clear (giây) |
| `--bypass-timeout` | `20.0` | Tổng thời gian trước khi safe-stop (giây) |
| `--sensor-active-high` | (flag) | Đảo logic sensor (active-high) |
| `--enable-sensor-bypass` | (flag) | Cho phép bỏ qua sensor kẹt |

### 10.3 Chẩn đoán Phần cứng

```bash
cd repo/pi_edge/
python check_hardware.py
```

Kiểm tra:
- Dependencies (onnxruntime, websockets, numpy, gpiozero)
- Model file (`best.onnx`)
- Camera (indices 0, 1, 2)
- Servos (GPIO 5, 6, 26) - test gạt 40° rồi thu về
- Nguồn điện (`vcgencmd get_throttled`)

### 10.4 Dashboard

Mở browser truy cập: `http://<LAPTOP_IP>:8765/`

Tính năng:
- **Live Feed**: Ảnh từ camera (base64 JPEG)
- **Current Result**: Label, icon, confidence bar
- **Metadata**: Frame ID, Latency (ms), Timestamp
- **Statistics**: Tổng số lượng từng loại quả
- **History Table**: 50 kết quả gần nhất với thumbnail
- **Image Preview**: Click thumbnail để xem ảnh phóng to
- **Auto-reconnect**: Tự động kết nối lại sau 3 giây nếu mất kết nối

---

## 11. Tổng kết

Hệ thống PBL5 là một pipeline phân loại trái cây xanh hoàn chỉnh, bao gồm:

1. **Training Pipeline** (Colab): Huấn luyện YOLO → Export ONNX với chiến lược SSD-first để tối ưu I/O
2. **Deployment Pipeline** (Pi + Laptop):
   - **Edge Inference**: ONNX Runtime trên Raspberry Pi CPU
   - **Real-time Control**: GPIO điều khiển motor L298N, sensor E18-D80NK, servo MG996R
   - **Async Pipeline**: 10 bước xử lý không đồng bộ với asyncio
   - **Reliable Messaging**: WebSocket + ACK + Idempotency + Retry
   - **Safety First**: FatalPipelineError, sensor bypass, camera re-init, debouncing
   - **Remote Dashboard**: Web UI real-time với live feed và thống kê

Kiến trúc Edge-Inference giúp hệ thống hoạt động độc lập trên Raspberry Pi, chỉ cần kết nối mạng LAN để gửi kết quả về dashboard giám sát. Toàn bộ quá trình phân loại diễn ra cục bộ trên Pi, đảm bảo độ trễ thấp và không phụ thuộc vào kết nối Internet.