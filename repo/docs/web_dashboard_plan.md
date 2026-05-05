# 🎯 Kế Hoạch: Web Dashboard Phân Loại Trái Cây

> **Trạng thái**: ✅ Đã xác nhận — sẵn sàng triển khai
>
> **Quyết định đã chốt**:
> - Chuyển **hoàn toàn** sang web (không giữ chế độ console log cũ)
> - Hệ thống **1 camera duy nhất** (1 Raspberry Pi)
> - Lịch sử nhận diện lưu **trong bộ nhớ** (in-memory), không persist ra file

---

## 📊 Phân Tích Hiện Trạng

### Kiến trúc hiện tại

```
📷 Webcam
    │
    ▼
🍓 Raspberry Pi  (pi_edge/cam_stream.py)
    │  ─ Chụp ảnh
    │  ─ Chạy ONNX inference → label + confidence
    │  ─ Gửi JSON qua WebSocket
    │
    ▼  ws://laptop_ip:8765
💻 Laptop Server  (laptop_server/server.py)
    │  ─ Nhận JSON
    │  ─ Kiểm tra idempotency (frame_id)
    │  ─ logger.info() ra terminal ← VẤN ĐỀ
    │  ─ Gửi ACK về Pi
    ▼
🖥️ Terminal (chỉ có text log, không có hình ảnh)
```

### Payload hiện tại Pi gửi lên Server

```json
{
    "device_id": "pi-edge-01",
    "frame_id": 42,
    "timestamp": 1714900000.123,
    "label": "cam",
    "confidence": 0.95,
    "conveyor_status": "stopped"
}
```

> **Vấn đề**: Server chỉ `logger.info()` ra terminal — không có hình ảnh, không có giao diện trực quan, khó theo dõi trong quá trình vận hành thực tế.

---

## 🏗️ Kiến Trúc Mới

```
📷 Webcam
    │
    ▼
🍓 Raspberry Pi  (pi_edge/cam_stream.py — thay đổi nhỏ)
    │  ─ Chụp ảnh
    │  ─ Chạy ONNX inference → label + confidence
    │  ─ Encode frame → JPEG base64
    │  ─ Gửi JSON (có thêm trường "image") qua WebSocket
    │
    ▼  ws://laptop_ip:8765/ws/pi
💻 Laptop Server  (laptop_server/server.py — viết lại với aiohttp)
    │  ─ Nhận JSON từ Pi
    │  ─ Kiểm tra idempotency (giữ nguyên)
    │  ─ Gửi ACK về Pi (giữ nguyên)
    │  ─ Broadcast dữ liệu tới browser clients
    │  ─ Phục vụ HTTP static files (dashboard)
    │
    ├──► GET /               → index.html (dashboard)
    ├──► WS  /ws/pi          → nhận từ Pi
    └──► WS  /ws/dashboard   → broadcast tới browser
    │
    ▼
🌐 Browser  (laptop_server/static/)
    ─ Hiển thị ảnh live từ Pi
    ─ Hiển thị nhãn + confidence bar
    ─ Bảng lịch sử nhận diện (in-memory, tối đa 50 bản ghi)
    ─ Thống kê số lượng từng loại
    ─ Trạng thái kết nối realtime
```

### Luồng dữ liệu chi tiết

```
Browser               Server                Pi
   │                    │                   │
   │── GET / ──────────►│                   │
   │◄─ index.html ──────│                   │
   │                    │                   │
   │── WS /ws/dashboard►│                   │
   │   (connected)      │◄── WS /ws/pi ─────│
   │                    │    (connected)    │
   │                    │                   │
   │              [quả đi qua băng chuyền]  │
   │                    │◄── JSON + image ──│
   │                    │    (frame_id=42)  │
   │                    │                   │
   │                    │── ACK ───────────►│
   │◄── broadcast ──────│                   │
   │  {label, conf,     │                   │
   │   image_b64, ...}  │                   │
   │                    │                   │
   │ [cập nhật UI]      │                   │
```

---

## 📝 Chi Tiết Thay Đổi Từng File

### 1. `pi_edge/cam_stream.py` — Thay đổi tối thiểu

**Thêm import:**
```python
import base64
```

**Thêm method `_encode_frame()` vào class `CameraStreamer`:**
```python
def _encode_frame(self, frame: np.ndarray, quality: int = 50) -> str:
    """Encode OpenCV frame → base64 JPEG string để gửi qua WebSocket."""
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buffer).decode('utf-8')
```

**Sửa signature `send_result()` — thêm tham số `frame`:**
```diff
-async def send_result(self, label, confidence, frame_id):
+async def send_result(self, label, confidence, frame_id, frame=None):
```

**Sửa payload trong `send_result()` — thêm trường `image`:**
```diff
 payload = {
     "device_id": self.device_id,
     "frame_id": frame_id,
     "timestamp": time.time(),
     "label": label,
     "confidence": float(confidence),
     "conveyor_status": "stopped",
+    "image": self._encode_frame(frame) if frame is not None else None,
 }
```

**Sửa lời gọi `send_result()` trong `run_pipeline()` — truyền frame:**
```diff
-if await self.send_result(label, confidence, frame_id):
+if await self.send_result(label, confidence, frame_id, frame=frame):
```

> **Lưu ý**: `frame` đã có sẵn ở bước 3 của `run_pipeline()` (sau `self.cap.read()`), chỉ cần truyền xuống.

---

### 2. `laptop_server/server.py` — Viết lại hoàn toàn

Thay thế `websockets`-only server bằng `aiohttp` server phục vụ cả HTTP lẫn WebSocket.

**Các trách nhiệm của server mới:**

| Endpoint | Phương thức | Vai trò |
|---|---|---|
| `/` | HTTP GET | Trả về `static/index.html` |
| `/static/*` | HTTP GET | Trả về CSS, JS, assets |
| `/ws/pi` | WebSocket | Nhận JSON + ảnh từ Raspberry Pi |
| `/ws/dashboard` | WebSocket | Broadcast realtime tới browser |

**Cơ chế broadcast:**
- Server duy trì một `set` các WebSocket connections từ browser (`dashboard_clients`)
- Khi nhận dữ liệu từ Pi → gửi broadcast đến **tất cả** browser đang kết nối
- Khi browser ngắt kết nối → tự động xóa khỏi `set`

**Giữ nguyên từ server cũ:**
- ✅ Logic idempotency (`last_processed_frames`)
- ✅ ACK về Pi sau khi xử lý
- ✅ Error handling và logging
- ✅ Tham số `--host` và `--port`

---

### 3. `laptop_server/requirements.txt` — Thêm dependency

```
aiohttp>=3.9
```

> `websockets` không còn cần thiết ở server sau khi chuyển sang `aiohttp` (aiohttp tự xử lý WebSocket natively).

---

### 4. `laptop_server/static/` — Toàn bộ Frontend (mới)

**Cấu trúc thư mục:**
```
laptop_server/
├── server.py
├── requirements.txt
└── static/
    ├── index.html
    ├── css/
    │   └── dashboard.css
    └── js/
        └── dashboard.js
```

**Bố cục giao diện:**

```
┌─────────────────────────────────────────────────────────┐
│  🍊 PBL5 Fruit Classification Dashboard    ● CONNECTED  │
├──────────────────────────┬──────────────────────────────┤
│                          │  KẾT QUẢ NHẬN DIỆN           │
│    📷 LIVE CAMERA FEED   │                              │
│                          │  🍊 CAM (Orange)             │
│    [ảnh JPEG từ Pi]      │  ████████████████▒▒  95.2%  │
│       640 × 480          │                              │
│                          │  Frame:    #42               │
│                          │  Latency:  23 ms             │
│                          │  Conveyor: ⏹ Stopped         │
│                          │  Device:   pi-edge-01        │
├──────────────────────────┴──────────────────────────────┤
│  📊 Tổng kết: 🍊 Cam: 15  🍋 Chanh: 8  🟠 Quýt: 19  | 42│
├─────────────────────────────────────────────────────────┤
│  📋 Lịch sử nhận diện (50 bản ghi gần nhất)            │
│  ┌──────┬──────────┬──────────┬────────────┬──────────┐ │
│  │ #    │ Thời gian│ Nhãn     │ Độ tin cậy │ Ảnh      │ │
│  ├──────┼──────────┼──────────┼────────────┼──────────┤ │
│  │ 42   │ 15:03:22 │ 🍊 Cam   │ ████ 95%   │ [thumb]  │ │
│  │ 41   │ 15:03:18 │ 🍋 Chanh │ ███░ 88%   │ [thumb]  │ │
│  │ 40   │ 15:03:14 │ 🟠 Quýt  │ ████ 91%   │ [thumb]  │ │
│  └──────┴──────────┴──────────┴────────────┴──────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Tính năng UI:**

| Tính năng | Mô tả |
|---|---|
| 📷 **Live camera feed** | Cập nhật ảnh mỗi khi Pi gửi frame mới |
| 🏷️ **Label + Confidence bar** | Thanh màu: xanh lá (>80%), vàng (50-80%), đỏ (<50%) |
| 📋 **Detection history** | Bảng cuộn, tối đa 50 bản ghi gần nhất, có ảnh thumbnail |
| 📊 **Statistics bar** | Đếm số lượng cam/chanh/quýt + tổng số |
| 🟢 **Connection status** | `● CONNECTED` / `● DISCONNECTED` / `⟳ RECONNECTING` |
| 🎨 **Dark theme** | Nền tối `#0f1117`, accent tím `#7c3aed`, dễ nhìn trong môi trường công nghiệp |
| ♻️ **Auto-reconnect** | Browser tự kết nối lại `/ws/dashboard` nếu mất kết nối |

---

## ⚡ Kế Hoạch Thực Hiện

### Phase 1 — Backend Server

| # | Task | File thay đổi |
|---|------|---------------|
| 1.1 | Viết lại `server.py` dùng `aiohttp` | `laptop_server/server.py` |
| 1.2 | Cập nhật requirements | `laptop_server/requirements.txt` |

### Phase 2 — Frontend

| # | Task | File tạo mới |
|---|------|--------------|
| 2.1 | HTML layout | `laptop_server/static/index.html` |
| 2.2 | CSS dark theme | `laptop_server/static/css/dashboard.css` |
| 2.3 | JS WebSocket client + render logic | `laptop_server/static/js/dashboard.js` |

### Phase 3 — Pi Edge

| # | Task | File thay đổi |
|---|------|---------------|
| 3.1 | Thêm `_encode_frame()`, sửa `send_result()`, sửa `run_pipeline()` | `pi_edge/cam_stream.py` |

### Phase 4 — Hoàn thiện

| # | Task |
|---|------|
| 4.1 | Cập nhật `README.md` — thêm hướng dẫn mở dashboard |
| 4.2 | Kiểm thử end-to-end trên phần cứng thực |

---

## 🔧 Dependencies Mới

```
# laptop_server/requirements.txt (sau khi cập nhật)
aiohttp>=3.9
```

**Lý do chọn `aiohttp`:**
- ✅ Async native — tương thích hoàn toàn với code `asyncio` hiện tại
- ✅ Hỗ trợ cả HTTP static files **và** WebSocket trong 1 server
- ✅ Không cần ASGI runner (uvicorn, gunicorn) riêng biệt
- ✅ Nhẹ hơn FastAPI/Django cho use case embedded dashboard này
