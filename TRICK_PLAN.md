# Kế hoạch triển khai Trick Mode điều khiển bằng phím ẩn

## 1. Mục tiêu

Triển khai chế độ demo/manual để người dùng bấm phím trên dashboard browser và điều khiển hệ thống thật theo luồng:

```text
Browser Dashboard
  -> Laptop Server
  -> Raspberry Pi
  -> điều khiển băng chuyền/servo + chụp ảnh camera thật
  -> gửi kết quả dự đoán giả về Server
  -> Dashboard hiển thị như pipeline hiện tại
```

Yêu cầu chính:

- Giữ giao diện dashboard gần như hiện tại, không hiển thị nút bấm, hướng dẫn phím, hay thông tin liên quan đến trick/manual mode.
- Ảnh hiển thị trên dashboard vẫn là ảnh thật chụp từ camera Raspberry Pi.
- Label và confidence không dùng model, mà phụ thuộc vào phím người dùng bấm.
- Raspberry Pi vẫn là nơi chụp ảnh, điều khiển servo/băng chuyền và gửi payload kết quả cuối cùng.
- Pipeline tự động hiện tại vẫn được giữ nguyên khi không bật trick/manual mode.

## 2. Key Mapping

Mapping phím cố định:

| Phím browser | Label gửi về dashboard | Hành động Raspberry Pi |
|---|---|---|
| `1` | `cam` | Gạt servo `cam`, chạy băng chuyền |
| `2` | `chanh` | Gạt servo `chanh`, chạy băng chuyền |
| `3` | `quyt` | Gạt servo `quyt`, chạy băng chuyền |
| `4` | `unknown` | Không gạt servo, chỉ chạy băng chuyền |
| `ArrowLeft` | `cam` | Gạt servo `cam`, chạy băng chuyền |
| `ArrowDown` | `chanh` | Gạt servo `chanh`, chạy băng chuyền |
| `ArrowRight` | `quyt` | Gạt servo `quyt`, chạy băng chuyền |
| `ArrowUp` | `unknown` | Không gạt servo, chỉ chạy băng chuyền |

Confidence giả:

- Với `cam`, `chanh`, `quyt`: random trong khoảng `0.82` đến `0.98`.
- Với `unknown`: random trong khoảng `0.35` đến `0.55`.
- Giá trị random được tạo trên Raspberry Pi để payload kết quả là nguồn dữ liệu cuối cùng giống pipeline thật.

## 3. Thay đổi kiến trúc

### 3.1 Dashboard browser

File chính: `repo/laptop_server/static/js/dashboard.js`

Thêm xử lý `keydown` ẩn:

- Bắt các phím `1`, `2`, `3`, `4`, `ArrowLeft`, `ArrowDown`, `ArrowRight`, `ArrowUp`.
- Không thêm button, panel, status, text hướng dẫn hoặc bất kỳ dấu hiệu UI nào về manual mode.
- Chỉ gửi command khi dashboard WebSocket đang connected.
- Bỏ qua `event.repeat` để tránh spam khi người dùng giữ phím.
- Thêm debounce tối thiểu khoảng `300ms` giữa hai command.
- Với phím hợp lệ, gửi message qua `/ws/dashboard`:

```json
{
  "type": "manual_command",
  "command_id": "timestamp-random",
  "label": "cam",
  "source_key": "1"
}
```

Không thay đổi `updateUI(data)` hiện tại, vì Raspberry Pi vẫn gửi payload kết quả cùng schema với pipeline cũ.

### 3.2 Laptop server

File chính: `repo/laptop_server/server.py`

Thêm khả năng relay command từ dashboard sang Pi:

- Lưu danh sách Pi WebSocket đang kết nối, ví dụ `pi_clients = set()`.
- Khi Pi kết nối `/ws/pi`, thêm websocket vào `pi_clients`; khi disconnect thì remove.
- Trong `/ws/dashboard`, thay vì bỏ qua message text, parse JSON và xử lý message `type == "manual_command"`.
- Validate payload dashboard:
  - `type` phải là `manual_command`.
  - `label` chỉ được nằm trong `cam`, `chanh`, `quyt`, `unknown`.
  - `source_key` chỉ được nằm trong danh sách phím hợp lệ.
  - `command_id` bắt buộc có và là string.
- Nếu payload không hợp lệ: log warning, bỏ qua, không crash, không broadcast.
- Nếu hợp lệ: gửi command tới tất cả Pi clients đang kết nối.
- Server không tự tạo kết quả giả và không broadcast command tới dashboard; chỉ relay xuống Pi.

Payload relay tới Pi giữ gần giống payload từ dashboard:

```json
{
  "type": "manual_command",
  "command_id": "timestamp-random",
  "label": "cam",
  "source_key": "1",
  "timestamp": 1778080000.123
}
```

Lưu ý:

- Luồng nhận kết quả từ Pi hiện tại trong `/ws/pi` vẫn giữ nguyên.
- ACK cho result từ Pi vẫn giữ nguyên để không phá `send_result`.
- Không yêu cầu ACK cho manual command từ Pi trong v1, vì dashboard không cần hiển thị trạng thái lệnh.
- Trong `pi_ws_handler`, `finally` block cần xóa Pi client khỏi `pi_clients` để tránh relay command vào WebSocket đã đóng:
  ```python
  finally:
      pi_clients.discard(ws)
      logger.info(f"[-] Pi {client_addr} disconnected.")
  ```
- Trong `dashboard_ws_handler`, đổi `dashboard_clients.remove(ws)` (dòng server.py:130) thành `dashboard_clients.discard(ws)` để tránh `KeyError` khi client đã bị xóa trước đó. `discard()` an toàn hơn `remove()` vì không ném lỗi nếu phần tử không tồn tại trong set.

### 3.3 Raspberry Pi streamer

File chính: `repo/pi_edge/cam_stream.py`

Thêm chế độ chạy mới qua CLI:

```bash
python start_pi.py --server <LAPTOP_IP> --port 8765 --manual-control
```

Thêm tham số:

- `--manual-control`: bật trick/manual mode.
- `--manual-run-duration`: thời gian băng chuyền chạy sau mỗi command, mặc định `2.0` giây.

Trong `CameraStreamer.__init__`, thêm state:

- `manual_control: bool`
- `manual_run_duration: float`
- `_manual_command_queue: asyncio.Queue`
- `_manual_stop_task: asyncio.Task | None`
- `_frame_id: int = 0`  # counter instance dùng chung cho cả auto và manual mode, tăng xuyên suốt vòng đời streamer để tránh trùng frame_id với server idempotency

Lưu ý về model ONNX: Trong v1, `FruitClassifier` vẫn được load bình thường (dòng `self.classifier = FruitClassifier(model_path)`) ngay cả khi `--manual-control`, do `CameraStreamer.__init__` được gọi trước khi biết chế độ chạy. Điều này không ảnh hưởng chức năng — model chiếm RAM (~100-200MB) nhưng không được gọi inference. Có thể tối ưu sau bằng cách lazy-load classifier chỉ khi cần.

**Quan trọng:** Trong `main()`, cần bỏ qua `os.path.exists(MODEL)` check khi `--manual-control`, vì check này (cam_stream.py:540-543) sẽ chặn `--manual-control` ngay từ đầu nếu file model không tồn tại. Sửa logic trong `main()`: nếu `args.manual_control`, bỏ qua check model và truyền `model_path=None` hoặc path giả vào `CameraStreamer`. Đồng thời, `CameraStreamer.__init__` cần lazy-load classifier: chỉ gọi `FruitClassifier(model_path)` nếu `model_path` không phải None.

Điều chỉnh `_consume_messages()`:

- Hiện tại chỉ đọc ACK từ server.
- Bổ sung parse message `type == "manual_command"`.
- Nếu là manual command hợp lệ thì đưa vào `_manual_command_queue`.
- Nếu là ACK thì giữ logic hiện tại.

Thêm hàm xử lý manual command:

```python
async def _handle_manual_command(self, command):
    label = command["label"]
    frame_id = self._frame_id  # dùng counter instance chung, tăng xuyên suốt vòng đời streamer
    self._frame_id += 1
    confidence = self._fake_confidence(label)

    self.conveyor.start()

    ret, frame = self._read_with_timeout(self.cap, timeout=5.0)
    if not ret:
        thử re-init camera giống logic hiện tại

    if label != "unknown":
        await self.conveyor.sorter.activate(label)

    # Gửi result với conveyor_status="running" vì băng chuyền đang chạy thật sự
    await self.send_result(label, confidence, frame_id, frame=frame, conveyor_status="running")

    # Hủy timer auto-stop cũ nếu có, đặt timer mới
    if self._manual_stop_task and not self._manual_stop_task.done():
        self._manual_stop_task.cancel()
    self._manual_stop_task = asyncio.create_task(self._auto_stop_conveyor())
```

Chi tiết bắt buộc:

- Không gọi `self.classifier.predict()` trong manual mode.
- Không dùng sensor để quyết định label trong manual mode.
- Vẫn init camera trước, sau đó mới init `ConveyorController`, giữ nguyên ràng buộc tránh servo PWM làm lỗi camera DV20.
- Nếu label là `unknown`, không gọi servo, chỉ chạy băng chuyền và gửi result.
- Nếu command mới đến trong lúc băng chuyền đang chờ tự dừng, hủy timer cũ và đặt timer mới.
- Nếu gửi result thất bại sau retry, log lỗi nhưng không nên `FatalPipelineError` ngay trong manual mode; demo mode nên tiếp tục nhận command mới, trừ lỗi camera/phần cứng nghiêm trọng.
- **Cập nhật `send_result()`**: Thêm tham số `conveyor_status: str = "stopped"` vào signature. Mặc định `"stopped"` để giữ nguyên hành vi auto mode. Manual mode gọi với `conveyor_status="running"` vì băng chuyền đang chạy thật sự. Trong payload gửi đi (cam_stream.py:140), thay `"conveyor_status": "stopped"` bằng `"conveyor_status": conveyor_status`.
- **Dùng chung `self._frame_id`**: Trong `run_pipeline()` (auto mode), đổi `frame_id = 0` local (cam_stream.py:287) thành dùng `self._frame_id` (khởi tạo = 0 trong `__init__`), tăng sau mỗi frame gửi thành công. Điều này đảm bảo frame_id tăng xuyên suốt vòng đời streamer, không reset về 0 khi reconnect, tránh trùng frame_id với server idempotency.

Thêm vòng lặp manual:

```python
async def run_manual_control(self, cam_idx=None):
    self.cap = self.init_camera(manual_idx=cam_idx)
    if not self.cap:
        raise FatalPipelineError(...)

    if self.conveyor is None:
        self.conveyor = ConveyorController(sensor_active_low=self.sensor_active_low)

    while not self._stop_event.is_set():
        # Dùng asyncio.wait để tránh treo vĩnh viễn khi WebSocket mất kết nối.
        # Nếu consumer task chết (do WebSocket đóng), queue.get() sẽ block mãi
        # nếu không có timeout hoặc stop_event. Giải pháp: đợi song song queue.get()
        # và stop_event, đồng thời kiểm tra is_ws_closed trước mỗi lần chờ.
        if self.is_ws_closed:
            logger.warning("WebSocket closed, breaking manual loop...")
            break

        try:
            # Chờ command với timeout 1s để định kỳ kiểm tra is_ws_closed
            command = await asyncio.wait_for(
                self._manual_command_queue.get(), timeout=1.0
            )
            await self._handle_manual_command(command)
        except asyncio.TimeoutError:
            continue  # Không có command — kiểm tra lại điều kiện vòng lặp
```

Lưu ý về chống treo:
- `queue.get()` thuần túy sẽ block vĩnh viễn nếu consumer task (`_consume_messages`) kết thúc do WebSocket đóng. Cần dùng `asyncio.wait_for` với timeout ngắn (1s) và kiểm tra `is_ws_closed` mỗi vòng lặp.
- Khi WebSocket đóng, `run_manual_control()` sẽ thoát → `main()` reconnect loop sẽ chạy lại `connect()` và `run_pipeline()` hoặc `run_manual_control()` như bình thường.

Trong `main()`:

- Nếu `args.manual_control` thì gọi `run_manual_control()`.
- Nếu không thì giữ nguyên `run_pipeline()`.

### 3.4 Conveyor controller

File chính: `repo/pi_edge/conveyor_controller.py`

Không cần đổi mapping servo nếu cấu hình hiện tại đúng:

```python
DEFAULT_CONFIG = {
    "cam":   (5, 5.0, 40),
    "chanh": (6, 8.0, 40),
    "quyt":  (26, 11.0, 40),
}
```

Chỉ thêm helper nhỏ nếu cần cho việc dừng tự động trong manual mode. Tránh refactor lớn phần GPIO vì đây là vùng rủi ro phần cứng.

## 4. Luồng runtime chi tiết

### 4.1 Khởi động

Server:

```bash
cd repo/
python start_server.py --host 0.0.0.0 --port 8765
```

Raspberry Pi trick mode:

```bash
cd repo/
python start_pi.py --server <LAPTOP_IP> --port 8765 --manual-control
```

Tùy chỉnh thời gian chạy băng chuyền:

```bash
python start_pi.py --server <LAPTOP_IP> --port 8765 --manual-control --manual-run-duration 2.0
```

### 4.2 Khi người dùng bấm phím

Ví dụ bấm `1`:

1. Browser bắt `keydown`.
2. Browser map `1 -> cam`.
3. Browser gửi `manual_command` tới `/ws/dashboard`.
4. Server validate và relay command tới Pi qua WebSocket `/ws/pi`.
5. Pi nhận command trong `_consume_messages()` và đưa vào queue.
6. Pi xử lý command:
   - Chạy băng chuyền.
   - Chụp ảnh camera thật.
   - Tạo confidence giả.
   - Gạt servo `cam`.
   - Gửi result `{label: "cam", confidence, image}` về server.
7. Server nhận result từ Pi, broadcast tới dashboard như hiện tại.
8. Dashboard cập nhật live feed, kết quả, confidence, thống kê và history như pipeline thật.
9. Pi tự dừng băng chuyền sau `manual_run_duration` nếu không có command mới.

## 5. Ràng buộc an toàn và lỗi

- Vì yêu cầu không có phím stop riêng, băng chuyền phải tự dừng sau mỗi command để tránh chạy vô hạn.
- Nếu camera fail một lần:
  - Tạm pause servo PWM.
  - Release camera.
  - Re-init camera.
  - Resume servo.
  - Thử chụp lại.
- Nếu camera fail liên tục nhiều lần, dùng `FatalPipelineError` như pipeline hiện tại.
- Nếu server mất kết nối:
  - Pi thoát vòng manual hiện tại và reconnect theo cơ chế main loop hiện có.
- Nếu dashboard gửi command khi không có Pi:
  - Server log warning hoặc info.
  - Không crash.
  - Không hiển thị lỗi trên UI.
- Nếu người dùng giữ phím:
  - Browser bỏ qua `event.repeat`.
  - Debounce để tránh gửi quá nhiều command.

## 6. Test plan

### 6.1 Test server

Thêm hoặc cập nhật `repo/tests/test_server.py`:

- Dashboard gửi `manual_command` hợp lệ, server relay đúng payload tới Pi client.
- Dashboard gửi label sai, server bỏ qua.
- Dashboard gửi source key sai, server bỏ qua.
- Dashboard gửi JSON lỗi, server không crash.
- Dashboard gửi command khi không có Pi client, server không crash.
- Luồng Pi gửi result và nhận ACK vẫn hoạt động như test hiện tại.
- `dashboard_clients` sử dụng `discard()` thay vì `remove()` trong finally block.

### 6.2 Test streamer manual mode

Thêm hoặc cập nhật `repo/tests/test_streamer.py`:

- Manual command `cam`:
  - `conveyor.start()` được gọi.
  - `sorter.activate("cam")` được gọi.
  - `send_result("cam", ..., conveyor_status="running")` được gọi.
  - Không gọi `classifier.predict`.
- Manual command `chanh` và `quyt` tương tự.
- Manual command `unknown`:
  - `conveyor.start()` được gọi.
  - Không gọi `sorter.activate`.
  - `send_result("unknown", ..., conveyor_status="running")` được gọi.
- Confidence giả nằm đúng khoảng:
  - Known labels: `0.82 <= confidence <= 0.98`.
  - Unknown: `0.35 <= confidence <= 0.55`.
- Auto-stop conveyor sau `manual_run_duration`.
- Command mới hủy timer stop cũ và gia hạn thời gian chạy.
- `send_result()` nhận tham số `conveyor_status` với mặc định `"stopped"`.
- `_frame_id` là counter instance dùng chung cho cả auto và manual mode, không reset về 0 khi reconnect.
- Manual loop thoát an toàn khi WebSocket đóng (không treo vĩnh viễn).
- Không yêu cầu file model ONNX tồn tại khi `--manual-control`.

### 6.3 Test dashboard JS

Nếu chưa có test JS, kiểm tra thủ công bằng browser:

- Bấm `1`, `2`, `3`, `4`, mũi tên trái/xuống/phải/lên.
- Network WebSocket gửi đúng `manual_command`.
- Không có thành phần UI mới xuất hiện.
- Giữ phím không spam command liên tục.

### 6.4 Regression

Chạy test Python hiện có:

```bash
cd repo/
python -m unittest discover -s tests
```

Kiểm tra auto mode vẫn chạy khi không truyền `--manual-control`.

## 7. Tiêu chí nghiệm thu

Hoàn thành khi đạt các điều kiện:

- Dashboard không thay đổi giao diện nhìn thấy được.
- Bấm `1` hoặc `ArrowLeft` làm Pi gửi ảnh thật với label `cam`, confidence giả, và gạt servo `cam`.
- Bấm `2` hoặc `ArrowDown` làm Pi gửi ảnh thật với label `chanh`, confidence giả, và gạt servo `chanh`.
- Bấm `3` hoặc `ArrowRight` làm Pi gửi ảnh thật với label `quyt`, confidence giả, và gạt servo `quyt`.
- Bấm `4` hoặc `ArrowUp` làm Pi gửi ảnh thật với label `unknown`, confidence giả, không gạt servo.
- Băng chuyền chạy khi nhận command và tự dừng sau thời gian cấu hình.
- Không có inference ONNX trong trick/manual mode.
- Pipeline tự động cũ không bị ảnh hưởng khi không bật `--manual-control`.
- Test server, streamer và regression pass.

## 8. Phạm vi không làm trong phiên bản này

- Không thêm UI điều khiển visible trên dashboard.
- Không thêm cơ chế authentication cho dashboard command.
- Không hỗ trợ nhiều Pi với routing theo device cụ thể; v1 relay command tới các Pi đang kết nối.
- Không thay đổi model, training pipeline hoặc logic phân loại thật.
- Không refactor lớn CSS/dashboard layout.
