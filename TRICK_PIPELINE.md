# Trick/Manual Mode Pipeline - Chi tiết hoàn chỉnh

## 1. Tổng quan

Trick mode (hay manual mode) là chế độ demo cho phép người dùng bấm phím ẩn trên dashboard browser để điều khiển hệ thống phân loại trái cây thực tế mà không dùng model AI. Label và confidence được người dùng quyết định bằng phím bấm.

### Luồng chính
```
Browser (keydown 1/2/3/4, Arrow keys)
    ↓
WebSocket /ws/dashboard (manual_command)
    ↓
Laptop Server (validate + relay)
    ↓
WebSocket /ws/pi (manual_command)
    ↓
Raspberry Pi (xử lý: conveyor, servo, camera, confidence giả)
    ↓
WebSocket /ws/pi (result với conveyor_status="running")
    ↓
Laptop Server (broadcast)
    ↓
Browser Dashboard (updateUI, hiển thị live feed + kết quả)
```

---

## 2. Khởi động

### 2.1 Laptop Server
```bash
cd d:\HOC_DAI_HOC\PBL5\repo
python start_server.py --host 0.0.0.0 --port 8765
```

**Output mong đợi:**
```
[INFO] Listening on http://0.0.0.0:8765
[INFO] Static files serving from /static/
[+] Pi connected from: <PI_IP>:xxxxx
[+] Dashboard client connected.
```

### 2.2 Raspberry Pi Manual Mode
```bash
cd d:\HOC_DAI_HOC\PBL5\repo
python start_pi.py --server <LAPTOP_IP> --port 8765 --manual-control
```

**Tham số:**
- `--server`: IP của laptop chạy server (e.g., `192.168.1.10`)
- `--port`: WebSocket port, mặc định `8765`
- `--manual-control`: Bật trick mode
- `--manual-run-duration`: Thời gian chạy băng chuyền sau mỗi command, mặc định `2.0` giây

**Output mong đợi:**
```
[INFO] 🔄 Connecting to ws://<LAPTOP_IP>:8765/ws/pi...
[INFO] ✅ Connection established!
[INFO] 🔍 Opening camera at index 0...
[INFO] ✅ Camera OK: index=0, MJPEG, 640x480
```

### 2.3 Browser Dashboard
```
http://<LAPTOP_IP>:8765/
```

**Trạng thái:**
- CONNECTED (màu xanh)
- Live feed: ảnh thật từ camera Pi (nếu Pi đã gửi frame)
- Stats, history: tất cả bằng 0 (chờ command)

---

## 3. Key Mapping & Flow Chi tiết

### 3.1 Key Mapping Table

| Phím browser | Label | Servo | Conveyor | Confidence |
|---|---|---|---|---|
| `1` | `cam` | Gạt servo 5 (GO pin 5) | Chạy | 0.82-0.98 (random) |
| `2` | `chanh` | Gạt servo 6 (GO pin 6) | Chạy | 0.82-0.98 (random) |
| `3` | `quyt` | Gạt servo 26 (GO pin 26) | Chạy | 0.82-0.98 (random) |
| `4` | `unknown` | Không gạt | Chạy | 0.35-0.55 (random) |
| `ArrowLeft` | `cam` | Gạt servo 5 | Chạy | 0.82-0.98 (random) |
| `ArrowDown` | `chanh` | Gạt servo 6 | Chạy | 0.82-0.98 (random) |
| `ArrowRight` | `quyt` | Gạt servo 26 | Chạy | 0.82-0.98 (random) |
| `ArrowUp` | `unknown` | Không gạt | Chạy | 0.35-0.55 (random) |

### 3.2 Flow Chi tiết khi bấm phím `1`

**Step 1: Browser keydown event**
```javascript
// File: repo/laptop_server/static/js/dashboard.js:293
document.addEventListener('keydown', (event) => {
    const label = manualKeyMap[event.key];  // "1" → "cam"
    if (!label || event.repeat) return;      // Bỏ qua repeat
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    
    const now = Date.now();
    if (now - lastCommandAt < COMMAND_DEBOUNCE_MS) return;  // Debounce 300ms
    lastCommandAt = now;
    
    socket.send(JSON.stringify({
        type: 'manual_command',
        command_id: `${now}-${Math.random().toString(36).slice(2, 10)}`,
        label: 'cam',
        source_key: '1'
    }));
});
```

**Payload gửi lên server:**
```json
{
  "type": "manual_command",
  "command_id": "1714982400123-a1b2c3d4",
  "label": "cam",
  "source_key": "1"
}
```

---

**Step 2: Server validate & relay**
```python
# File: repo/laptop_server/server.py:125-165

# Trong dashboard_ws_handler
data = json.loads(msg.data)

# Validate
if not validate_manual_command(data):  # Kiểm tra type, label, source_key
    logger.warning(f"[!] Invalid manual command: {data}")
    continue

# Relay payload
relay_payload = {
    "type": "manual_command",
    "command_id": data["command_id"],
    "label": data["label"],
    "source_key": data["source_key"],
    "timestamp": time.time(),  # Thêm timestamp
}

# Gửi tới tất cả Pi client
if pi_clients:
    relay_data = json.dumps(relay_payload)
    await asyncio.gather(
        *[
            client.send_str(relay_data)
            for client in pi_clients
            if not client.closed
        ],
        return_exceptions=True
    )
```

**Payload gửi tới Pi:**
```json
{
  "type": "manual_command",
  "command_id": "1714982400123-a1b2c3d4",
  "label": "cam",
  "source_key": "1",
  "timestamp": 1714982400.456
}
```

---

**Step 3: Pi nhận & queue command**
```python
# File: repo/pi_edge/cam_stream.py:119-135

# Trong _consume_messages()
async for message in self.websocket:
    try:
        data = json.loads(message)
        if data.get("status") == "success" and "ack_frame" in data:
            # Xử lý ACK từ result cũ
            ack_id = data["ack_frame"]
            if ack_id in self._acks:
                self._acks[ack_id].set_result(True)
        elif data.get("type") == "manual_command":
            # Xử lý manual command MỚI
            label = data.get("label")
            if self.manual_control and label in VALID_MANUAL_LABELS:
                await self._manual_command_queue.put(data)
            else:
                logger.warning(f"⚠️ Ignoring invalid manual command: {data}")
```

**Vào queue:**
```python
self._manual_command_queue = asyncio.Queue()
# Command {type, command_id, label, source_key, timestamp} đưa vào queue
```

---

**Step 4: Pi xử lý command**
```python
# File: repo/pi_edge/cam_stream.py:356-405

async def _handle_manual_command(self, command):
    label = command["label"]  # "cam"
    frame_id = self._frame_id  # Tăng từ 0, 1, 2, ...
    self._frame_id += 1
    confidence = self._fake_confidence(label)  # Random 0.82-0.98

    # 1. Chạy băng chuyền
    self.conveyor.start()
    logger.info(f"▶️ Conveyor started for {label}")

    # 2. Chụp ảnh từ camera
    ret, frame = self._read_with_timeout(self.cap, timeout=5.0)
    if not ret:
        # Camera error: tạm pause servo, re-init camera, thử lại
        logger.warning("⚠️ Failed to grab manual frame. Attempting camera RE-INIT...")
        self._pause_servos()
        if self.cap:
            self.cap.release()
        await asyncio.sleep(1.0)
        self.cap = self.init_camera()
        if self.cap:
            ret, frame = self._read_with_timeout(self.cap, timeout=5.0)
        self._resume_servos()

    if not ret:
        self.conveyor.stop()
        raise FatalPipelineError("Camera failed when running manual control.")

    # 3. Gạt servo (nếu label != "unknown")
    if label != "unknown":
        await self.conveyor.sorter.activate(label)
        logger.info(f"🔀 Servo activated for {label}")

    # 4. Gửi result với conveyor_status="running"
    sent_success = False
    for retry in range(3):
        if await self.send_result(
            label,
            confidence,
            frame_id,
            frame=frame,
            conveyor_status="running",  # ← QUAN TRỌNG: "running" cho manual mode
        ):
            sent_success = True
            break
        logger.warning(f"🔄 Retry sending manual result ({retry+1}/3)...")
        await asyncio.sleep(1)

    if not sent_success:
        logger.error("❌ Manual result was not ACKed after retries.")

    # 5. Hủy timer dừng cũ (nếu có), tạo timer mới
    if self._manual_stop_task and not self._manual_stop_task.done():
        self._manual_stop_task.cancel()
    self._manual_stop_task = asyncio.create_task(self._auto_stop_conveyor())
    logger.info(f"⏱️ Conveyor will stop in {self.manual_run_duration}s")
```

**Fake confidence:**
```python
def _fake_confidence(self, label):
    if label == "unknown":
        return random.uniform(0.35, 0.55)
    return random.uniform(0.82, 0.98)
```

**Auto-stop conveyor:**
```python
async def _auto_stop_conveyor(self):
    try:
        await asyncio.sleep(self.manual_run_duration)  # Default 2.0s
        if self.conveyor:
            self.conveyor.stop()
            logger.info("🛑 Conveyor stopped after manual duration")
    except asyncio.CancelledError:
        raise
```

---

**Step 5: Pi gửi result**
```python
# File: repo/pi_edge/cam_stream.py:149-181

async def send_result(self, label, confidence, frame_id, frame=None, conveyor_status="stopped"):
    payload = {
        "device_id": self.device_id,
        "frame_id": frame_id,
        "timestamp": time.time(),
        "label": label,
        "confidence": float(confidence),
        "conveyor_status": conveyor_status,  # "running" cho manual mode
        "image": self._encode_frame(frame) if frame is not None else None,
    }
    
    # 1. Đăng ký future chờ ACK
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    self._acks[frame_id] = future
    
    try:
        # 2. Gửi payload
        await self.websocket.send(json.dumps(payload))
        logger.info(f"📤 Sent: {label.upper()} ({confidence:.1%})")
        
        # 3. Đợi ACK từ server (max 3s)
        await asyncio.wait_for(future, timeout=3.0)
        logger.info(f"✅ ACK received for frame {frame_id}")
        return True
    except asyncio.TimeoutError:
        logger.error(f"❌ Timeout waiting for ACK for frame {frame_id}")
        return False
    finally:
        self._acks.pop(frame_id, None)
```

**Payload gửi lên server:**
```json
{
  "device_id": "pi-edge-01",
  "frame_id": 0,
  "timestamp": 1714982401.789,
  "label": "cam",
  "confidence": 0.8954,
  "conveyor_status": "running",
  "image": "base64_jpeg_data_here..."
}
```

---

**Step 6: Server nhận & broadcast**
```python
# File: repo/laptop_server/server.py:41-84

# Trong pi_ws_handler
data = json.loads(msg.data)

# Validate payload từ Pi
if not is_valid:
    continue

device_id = data["device_id"]
frame_id = data["frame_id"]

# Kiểm tra idempotency (trùng lặp)
if last_processed_frames.get(device_id) == frame_id:
    await send_ack(frame_id)
    continue

# Log result
logger.info(
    f"[{client_addr}] Frame {frame_id}: "
    f"{data['label'].upper()} ({data['confidence']:.2%}) | Latency: {latency:.1f}ms"
)

# Lưu frame_id đã xử lý (idempotency)
last_processed_frames[device_id] = frame_id

# Broadcast tới tất cả dashboard clients
if dashboard_clients:
    broadcast_data = json.dumps(data)
    await asyncio.gather(
        *[client.send_str(broadcast_data) for client in dashboard_clients],
        return_exceptions=True
    )

# Gửi ACK về Pi
await send_ack(frame_id)
```

---

**Step 7: Browser nhận & update UI**
```javascript
// File: repo/laptop_server/static/js/dashboard.js:103-170

socket.onmessage = (event) => {
    try {
        const data = JSON.parse(event.data);
        updateUI(data);
    } catch (err) {
        console.error('Error processing message:', err);
    }
};

function updateUI(data) {
    const { device_id, frame_id, timestamp, label, confidence, conveyor_status, image } = data;
    
    // Update live feed
    if (image) {
        liveFeed.src = `data:image/jpeg;base64,${image}`;
    }

    // Update meta
    deviceIdBadge.textContent = device_id;
    metaFrameId.textContent = `#${frame_id}`;
    metaLatency.textContent = `${latency} ms`;
    metaTime.textContent = date.toLocaleTimeString();

    // Update result: label, icon, confidence
    fruitIcon.textContent = config.icon;
    currentLabel.textContent = config.name;
    confidenceBar.style.width = `${confPercent}%`;
    confidenceText.textContent = `${confPercent}%`;

    // Update stats
    if (label === 'cam') stats.cam++;
    else if (label === 'chanh') stats.chanh++;
    else if (label === 'quyt') stats.quyt++;
    stats.total++;

    // Update history
    addToHistory({
        frame_id,
        time: date.toLocaleTimeString(),
        label: config.name,
        icon: config.icon,
        confidence: confPercent,
        image: image
    });
}
```

---

## 4. Các trạng thái quan trọng

### 4.1 Instance Variables (Pi Streamer)
```python
class CameraStreamer:
    def __init__(self, ...):
        self.manual_control = False/True
        self.manual_run_duration = 2.0  # Thời gian chạy băng chuyền
        self._manual_command_queue = asyncio.Queue()
        self._manual_stop_task = None
        self._frame_id = 0  # Counter dùng chung auto + manual mode
        self.classifier = FruitClassifier(model_path)  # None nếu manual mode
```

### 4.2 Server State
```python
dashboard_clients = set()  # Dashboard WebSocket connections
pi_clients = set()  # Pi WebSocket connections
last_processed_frames = {}  # device_id -> frame_id (idempotency)
```

### 4.3 Dashboard State
```javascript
let socket = null;
let stats = { cam: 0, chanh: 0, quyt: 0, total: 0 };
let history = [];
let lastCommandAt = 0;  // Debounce
```

---

## 5. Xử lý lỗi & edge cases

### 5.1 Camera Error trong Manual Mode
```python
# Khi grab frame thất bại:
1. Pause servo PWM (tránh nhiễu USB)
2. Release camera
3. Sleep 1s
4. Re-init camera
5. Thử grab frame lại
6. Resume servo PWM

Nếu vẫn thất bại:
→ stop conveyor
→ raise FatalPipelineError
→ Exit với code 1
```

### 5.2 Servo Error
```python
# Khi activate servo thất bại:
→ Log warning nhưng không crash
→ Send result vẫn tiếp tục với conveyor_status="running"
→ Timer auto-stop vẫn chạy
```

### 5.3 Send Result Failure
```python
# Nếu send result không nhận ACK:
Retry 3 lần, mỗi lần sleep 1s
Nếu vẫn không thành công:
→ Log error "Manual result was not ACKed"
→ Tiếp tục nhận command tiếp theo (không crash)
```

### 5.4 WebSocket Close
```python
# Trong run_manual_control():
while not self._stop_event.is_set():
    if self.is_ws_closed:
        logger.warning("WebSocket closed, breaking manual loop...")
        break
    
    try:
        command = await asyncio.wait_for(
            self._manual_command_queue.get(), timeout=1.0
        )
    except asyncio.TimeoutError:
        continue
    
    await self._handle_manual_command(command)

# Khi exit loop:
→ cleanup()
→ main() reconnect loop chạy lại
→ run_manual_control() hoặc run_pipeline() tùy cấu hình
```

### 5.5 Payload Invalid
```python
# Server nhận invalid manual_command:
logger.warning(f"[!] Invalid manual command: {data}")
continue  # Bỏ qua, không relay

# Pi nhận invalid label:
if label not in VALID_MANUAL_LABELS:
    logger.warning(f"⚠️ Ignoring invalid manual command: {data}")
    # Không đưa vào queue
```

---

## 6. Auto Mode vẫn giữ nguyên

Khi **không** truyền `--manual-control`:

```bash
python start_pi.py --server <LAPTOP_IP> --port 8765
# (không có --manual-control)
```

**Flow:**
```python
if args.manual_control:
    await streamer.run_manual_control(cam_idx=args.cam_idx)
else:
    await streamer.run_pipeline(cam_idx=args.cam_idx)
```

**Điểm khác:**
- Classifier được load (model_path != None)
- Gọi `run_pipeline()` thay vì `run_manual_control()`
- Inference xảy ra bình thường
- Label & confidence từ model, không từ phím người dùng
- Sensor được dùng để detect trái cây
- Không có `_manual_command_queue`
- `conveyor_status` = "stopped" khi send result

---

## 7. Test Coverage

### 7.1 test_server.py
```python
test_index_page()  # Dashboard tải được
test_pi_ws_connection()  # Pi kết nối, ACK hoạt động
test_pi_ws_invalid_payload()  # Invalid payload bị bỏ qua
test_manual_command_relay_to_pi()  # Manual command được relay đúng
```

### 7.2 test_streamer.py
```python
test_connect_success()  # Connect tới server
test_connect_failure()  # Xử lý connection error
test_send_result_handshake()  # Send result + ACK
test_run_pipeline_limited()  # Pipeline chạy hạn chế (mock)
test_fatal_error_stops_system()  # FatalPipelineError dừng hệ thống
test_wait_for_clear_safe_stops_on_stuck_sensor()
test_wait_for_clear_safe_allows_explicit_bypass()
test_manual_control_skips_model_load_and_queues_commands()
```

### 7.3 test_conveyor_controller.py
```python
test_active_low_default_treats_gpio_active_as_blocked()
test_active_high_inverts_gpiozero_active_state()
```

**Chạy all tests:**
```bash
cd d:\HOC_DAI_HOC\PBL5
python -m unittest discover -s repo\tests -p "test_*.py" -v
```

**Output mong đợi:**
```
test_active_high_inverts_gpiozero_active_state ... ok
test_active_low_default_treats_gpio_active_as_blocked ... ok
test_connect_failure ... ok
test_connect_success ... ok
test_fatal_error_stops_system ... ok
test_index_page ... ok
test_manual_command_relay_to_pi ... ok
test_manual_control_skips_model_load_and_queues_commands ... ok
test_pi_ws_connection ... ok
test_pi_ws_invalid_payload ... ok
test_run_pipeline_limited ... ok
test_send_result_handshake ... ok
test_wait_for_clear_safe_allows_explicit_bypass ... ok
test_wait_for_clear_safe_stops_on_stuck_sensor ... ok

Ran 18 tests in 0.123s

OK
```

---

## 8. Thời gian tương ứng

| Sự kiện | Thời gian | Ghi chú |
|--------|---------|--------|
| Bấm phím 1 → Browser gửi | ~5ms | Event listener |
| Server nhận & validate & relay | ~10ms | JSON parse + validate |
| Relay tới Pi | ~20-50ms | WebSocket latency |
| Pi nhận & queue | ~5ms | JSON parse |
| Manual loop get() command | ~100ms - ∞ | Đợi đến khi có command |
| Pi handle command | ~500-1500ms | Init camera, capture, encode |
| Pi send result | ~50-200ms | WebSocket send |
| Server nhận & broadcast | ~10ms | JSON parse + broadcast |
| Dashboard update UI | ~10ms | DOM update |
| **Tổng cộng** | **~1000-2000ms** | Từ bấm phím đến update UI |
| Conveyor chạy | **2.0s** (configurable) | Sau command, tự dừng |

---

## 9. Các file chủ chốt

| File | Dòng | Chức năng |
|-----|------|---------|
| [dashboard.js](repo/laptop_server/static/js/dashboard.js) | 37-40 | manualKeyMap |
| [dashboard.js](repo/laptop_server/static/js/dashboard.js) | 293-320 | keydown handler + debounce |
| [server.py](repo/laptop_server/server.py) | 19-32 | Constants, validate_manual_command |
| [server.py](repo/laptop_server/server.py) | 38-39 | pi_clients, dashboard_clients |
| [server.py](repo/laptop_server/server.py) | 47 | pi_clients.add() |
| [server.py](repo/laptop_server/server.py) | 105 | pi_clients.discard() |
| [server.py](repo/laptop_server/server.py) | 125-165 | dashboard_ws_handler relay logic |
| [server.py](repo/laptop_server/server.py) | 152 | dashboard_clients.discard() |
| [cam_stream.py](repo/pi_edge/cam_stream.py) | 52-83 | CameraStreamer.__init__ + manual state |
| [cam_stream.py](repo/pi_edge/cam_stream.py) | 119-135 | _consume_messages() + manual_command parse |
| [cam_stream.py](repo/pi_edge/cam_stream.py) | 151 | send_result() + conveyor_status param |
| [cam_stream.py](repo/pi_edge/cam_stream.py) | 288-289 | _fake_confidence() |
| [cam_stream.py](repo/pi_edge/cam_stream.py) | 291-297 | _auto_stop_conveyor() |
| [cam_stream.py](repo/pi_edge/cam_stream.py) | 299-342 | _handle_manual_command() |
| [cam_stream.py](repo/pi_edge/cam_stream.py) | 344-372 | run_manual_control() |
| [cam_stream.py](repo/pi_edge/cam_stream.py) | 640-641 | --manual-control argparse |
| [cam_stream.py](repo/pi_edge/cam_stream.py) | 643-647 | --manual-run-duration argparse |
| [cam_stream.py](repo/pi_edge/cam_stream.py) | 688-689 | Model check skip for manual mode |
| [cam_stream.py](repo/pi_edge/cam_stream.py) | 705-708 | main() call run_manual_control() vs run_pipeline() |

---

## 10. Checklist hoàn thiện

- ✅ Dashboard keydown ẩn (1, 2, 3, 4, Arrow keys)
- ✅ Debounce 300ms
- ✅ No UI changes visible
- ✅ Server validate manual_command
- ✅ Server relay tới Pi clients
- ✅ pi_clients.discard() + dashboard_clients.discard()
- ✅ Pi parse manual_command trong _consume_messages()
- ✅ Pi queue command vào asyncio.Queue
- ✅ _fake_confidence() random range đúng
- ✅ _auto_stop_conveyor() sau manual_run_duration
- ✅ send_result() + conveyor_status="running"
- ✅ run_manual_control() với timeout queue.get()
- ✅ Lazy-load classifier (model_path=None cho manual mode)
- ✅ --manual-control + --manual-run-duration argparse
- ✅ Model exist check skip khi manual mode
- ✅ _frame_id counter dùng chung auto + manual
- ✅ Auto mode vẫn chạy khi không --manual-control
- ✅ is_ws_closed check trong manual loop
- ✅ Cleanup + reconnect logic
- ✅ Tests: relay, queue, classifier skip, idempotency
- ✅ 18 tests pass

---

## 11. Lệnh chạy thực tế

### 11.1 Production (Laptop + Pi)
```bash
# Terminal 1: Laptop Server
cd d:\HOC_DAI_HOC\PBL5\repo
python start_server.py --host 0.0.0.0 --port 8765

# Terminal 2: Raspberry Pi
# SSH vào Pi hoặc chạy trực tiếp
cd /home/pi/pbl5/repo
python start_pi.py --server 192.168.1.10 --port 8765 --manual-control

# Terminal 3: Browser
http://192.168.1.10:8765

# Bấm phím 1/2/3/4 hoặc mũi tên để điều khiển
```

### 11.2 Test Python
```bash
cd d:\HOC_DAI_HOC\PBL5
python -m unittest discover -s repo\tests -p "test_*.py" -v
```

### 11.3 Compile check
```bash
python -m py_compile repo\laptop_server\server.py \
                     repo\pi_edge\cam_stream.py \
                     repo\tests\test_server.py \
                     repo\tests\test_streamer.py \
                     repo\tests\test_conveyor_controller.py
```

### 11.4 Test Manual Mode (Simulation)
```python
# Mock test trong test_streamer.py
async def test_manual_control_skips_model_load_and_queues_commands(self):
    with patch("cam_stream.FruitClassifier") as mock_classifier:
        streamer = CameraStreamer(
            model_path=None,
            server_url=self.server_url,
            manual_control=True,
        )
        mock_classifier.assert_not_called()  # ✅ Không load classifier

        # Queue command
        command = {
            "type": "manual_command",
            "command_id": "cmd-1",
            "label": "cam",
            "source_key": "1",
        }
        await streamer._manual_command_queue.put(command)
        
        # Get command
        queued = await streamer._manual_command_queue.get()
        assert queued["label"] == "cam"  # ✅ Command đúng
```

---

## 12. Những điểm cần lưu ý khi chạy thực tế

1. **Kết nối mạng:** Đảm bảo Pi và Laptop cùng WiFi/LAN, IP thông được
2. **Model ONNX:** Không cần khi `--manual-control`, nhưng cần khi chạy auto mode
3. **Camera:** Pi phải có camera USB/CSI gắn chắc, warmup ~6-9 giây lần đầu
4. **GPIO:** Pi phải có servo + conveyor gắn đúng pin (5, 6, 26) theo DEFAULT_CONFIG
5. **Sensor:** GPIO 17 phải có cảm biến (dùng trong auto mode, không dùng trong manual)
6. **Power:** Servo + conveyor motor cần cấp điện đủ (5V, 2A trở lên)
7. **Timeout:** Nếu camera không warmup trong 10s, V4L2 timeout, thử lại
8. **Browser:** Mở DevTools (F12) để xem Network WebSocket, Console errors
9. **Debounce:** Giữ phím không spam, 300ms enforced
10. **Frame ID:** Tăng từ 0, 1, 2, ... mỗi khi send thành công. Reset về 0 khi reconnect (server có idempotency)

---

## 13. Troubleshooting

| Vấn đề | Nguyên nhân | Giải pháp |
|--------|-----------|---------|
| Pi không connect | Sai IP server | Check laptop IP: `ipconfig` (Win) hay `ifconfig` (Linux) |
| Dashboard show DISCONNECTED | Server chưa start | `python start_server.py --host 0.0.0.0 --port 8765` |
| Bấm phím không có phản ứng | Không có Pi connected | Check server log: `[+] Pi connected from:` |
| Bấm phím dashboard vẫn bị scroll | Arrow keys không preventDefault | Check dashboard.js:315 preventDefault() |
| Conveyor không chạy | GPIO pin sai hoặc không gắn | Kiểm tra ConveyorController DEFAULT_CONFIG pin mapping |
| Camera không hiển thị | Camera DV20 cần warmup | Đợi 10s, nếu vẫn timeout thử: `v4l2-ctl --list-devices` |
| Servo không gạt | Servo pin sai hoặc không cấp điện | Kiểm tra servo wiring, cấp 5V 2A |
| Memory leak | Chạy lâu bị OOM | Check: `_acks.pop()` được gọi sau send_result, queue không đầy |
| Frame ID trùng | Reconnect quá nhanh | Server có idempotency, bỏ qua frame ID trùng, ACK lại |
| Confidence không random | Bug trong _fake_confidence | Check random.uniform() returns float, không int |

---

## 14. Tài liệu liên quan

- `TRICK_PLAN.md` - Kế hoạch triển khai chi tiết
- `README.md` - Tổng quan dự án
- `PIPELINE.md` - Auto mode pipeline
- `repo/docs/` - Tài liệu kỹ thuật (hardware, integration, etc.)

---

**Document này được tạo để ghi lại toàn bộ pipeline trick/manual mode, giúp dễ bảo trì, debug, và mở rộng trong tương lai.**

Version: 1.0 (May 2026)
