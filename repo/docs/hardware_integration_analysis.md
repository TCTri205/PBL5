# Đánh Giá Kỹ Thuật: Phân Tích Phần Cứng & Mức Độ Tích Hợp Vào PBL5

---

## PHẦN 1: ĐÁNH GIÁ TÍNH CHÍNH XÁC CỦA BẢN PHÂN TÍCH (`raspberry_pi_hardware_analysis.md`)

### ✅ Những gì ĐÚNG

| # | Điểm | Mức độ |
|---|------|--------|
| 1 | **E18-D80NK là NPN Open Collector** — Hoàn toàn chính xác | ✅ Đúng |
| 2 | **Kết nối tín hiệu signal trực tiếp vào GPIO 17** — An toàn vì NPN không đẩy 5V | ✅ Đúng |
| 3 | **Dùng `pull_up=True`** thay vì điện trở ngoài — Hợp lệ, Pi 4 có pull-up nội bộ ~50kΩ | ✅ Đúng |
| 4 | **L298N IN1/IN2 dùng GPIO 22/23** — Đúng theo yêu cầu bài toán | ✅ Đúng |
| 5 | **Logic bảng điều khiển motor** (FWD/BWD/STOP/BRAKE) — Đúng chuẩn H-Bridge | ✅ Đúng |
| 6 | **Cảnh báo nguồn ngoài và chung GND** — Cực kỳ quan trọng, được nêu đúng | ✅ Đúng |
| 7 | **Dùng `gpiozero` thay `RPi.GPIO`** — Đây là thư viện hiện đại, được Raspberry Pi Foundation khuyến nghị chính thức | ✅ Đúng |

### ⚠️ Những điểm cần LƯU Ý THÊM

**1. Màu dây của E18-D80NK có thể khác nhau giữa các nhà sản xuất:**
- Bản phân tích ghi: "Dây Nâu (VCC), Dây Xanh (GND), Dây Đen (Signal)".
- Thực tế phổ biến nhất: **Nâu=VCC, Xanh lam=GND, Đen=Signal** — đúng theo chuẩn IEC.
- Tuy nhiên, một số hàng Trung Quốc có thể đảo màu. **Luôn kiểm tra datasheet của lô hàng cụ thể trước khi nối.**

**2. Cảm biến E18-D80NK hoạt động ở 5V, nhưng logic ngưỡng NPN:**
- Khi sensor "kéo xuống GND", nó kéo qua đường GND **chung** với Pi.
- Điều này **an toàn tuyệt đối** — chân GPIO không nhận điện áp nào cả.
- Bản phân tích đã mô tả đúng nguyên lý này.

**3. `gpiozero.Motor` yêu cầu chân Enable không bị ngắt:**
- Nếu trên board L298N có jumper ENA mà bạn gỡ ra (để cắm PWM), thì phải cung cấp `enable` pin trong constructor: `Motor(forward=22, backward=23, enable=XX)`.
- Nếu **để nguyên jumper ENA** (full speed), code mẫu trong phân tích hoạt động đúng.

**4. Logic cảm biến bị đảo ngược (QUAN TRỌNG):**
- Bản phân tích gốc có 1 điểm nhập nhằng:
  - `when_activated` → "Không vật cản" (HIGH/3.3V)
  - `when_deactivated` → "Có vật cản" (LOW/0V)
- Với `pull_up=True` trong `gpiozero`, `is_active` = **True khi GPIO ở mức LOW** (active-low).
- Do đó:
  - `when_activated` = cảm biến kéo GPIO xuống 0V = **có vật cản**
  - `when_deactivated` = GPIO ở 3.3V = **không có vật cản**
- **⚠️ Đây là lỗi logic trong code mẫu cần sửa lại (xem phần 3).**

---

## PHẦN 2: MỨC ĐỘ PHÙ HỢP VỚI DỰ ÁN PBL5 HIỆN TẠI

### Bức tranh toàn cảnh dự án PBL5

```
[Camera USB]
     |
     v
[Raspberry Pi 4] -- ONNX Inference (YOLO) --> [WebSocket Client] --> [Laptop Server]
     |                                                                     |
     |                                                              (Log + Monitor)
     |
  [Phần cứng mới cần tích hợp]
     |
     +-- [Motor DC via L298N] → Điều khiển băng chuyền
     +-- [E18-D80NK Sensor]  → Phát hiện trái cây đến vị trí
```

### ✅ Tính phù hợp: RẤT CAO (9/10)

| Tiêu chí | Đánh giá | Chi tiết |
|---|---|---|
| **Ngôn ngữ** | ✅ Phù hợp hoàn toàn | Dự án dùng Python, `gpiozero` là thư viện Python chuẩn |
| **Kiến trúc async** | ✅ Phù hợp | `cam_stream.py` dùng `asyncio`; `gpiozero` dùng callback-based, không block event loop |
| **Luồng dữ liệu** | ✅ Mở rộng tự nhiên | Motor/Sensor là phần cứng peripheral, tách biệt với pipeline inference |
| **Không xung đột GPIO** | ✅ An toàn | GPIO 17/22/23 chưa được dùng ở bất kỳ đâu trong codebase hiện tại |
| **Tương thích `systemd`** | ✅ Có sẵn | `pbl5_pi.service` đã có, chỉ cần thêm logic mới vào `cam_stream.py` |

### Vị trí tích hợp được đề xuất trong codebase

Tích hợp vào `cam_stream.py` là tự nhiên nhất. Kiến trúc mới sẽ là:

```
CameraStreamer (cam_stream.py)
  ├── FruitClassifier (ONNX inference)
  ├── WebSocket Client → Laptop Server
  ├── [MỚI] ConveyorController (motor + sensor)  ← Thêm vào đây
  └── Orchestration logic (kết quả AI → quyết định motor)
```

---

## PHẦN 3: CODE MẪU ĐÃ SỬA LỖI & SẴN SÀNG TÍCH HỢP

Đây là code đã sửa lỗi logic cảm biến và tích hợp cùng với kiến trúc `asyncio` của dự án:

```python
# pi_edge/conveyor_controller.py
# Module điều khiển băng chuyền - Tích hợp với cam_stream.py

from gpiozero import Motor, DigitalInputDevice
import asyncio
import logging

logger = logging.getLogger(__name__)


class ConveyorController:
    """
    Điều khiển băng chuyền và cảm biến tiệm cận.
    Thiết kế để chạy song song với pipeline camera (asyncio-compatible).
    """

    def __init__(self, motor_fwd_pin=22, motor_bwd_pin=23, sensor_pin=17):
        logger.info("⚙️ Khởi tạo ConveyorController...")
        # Motor A: IN1=GPIO22 (forward), IN2=GPIO23 (backward)
        self.motor = Motor(forward=motor_fwd_pin, backward=motor_bwd_pin)

        # pull_up=True: active-low (GPIO LOW = cảm biến kích hoạt = có vật cản)
        self.sensor = DigitalInputDevice(sensor_pin, pull_up=True)

        self._running = False
        logger.info("✅ ConveyorController sẵn sàng.")

    @property
    def has_object(self) -> bool:
        """True nếu cảm biến phát hiện có vật cản."""
        # pull_up=True: is_active=True khi GPIO bị kéo xuống LOW (có vật cản)
        return self.sensor.is_active

    def start(self):
        """Khởi động băng chuyền."""
        self._running = True
        self.motor.forward()
        logger.info("🔄 Băng chuyền CHẠY.")

    def stop(self):
        """Dừng băng chuyền."""
        self.motor.stop()
        logger.info("⏹️  Băng chuyền DỪNG.")

    def shutdown(self):
        """Giải phóng tài nguyên GPIO."""
        self._running = False
        self.motor.stop()
        self.sensor.close()
        self.motor.close()
        logger.info("🛑 ConveyorController đã giải phóng GPIO.")

    async def wait_for_object(self, timeout: float = 10.0) -> bool:
        """
        Chờ không đồng bộ cho đến khi cảm biến phát hiện vật.
        Tích hợp an toàn với asyncio event loop.

        Returns:
            True nếu phát hiện vật, False nếu timeout.
        """
        deadline = asyncio.get_event_loop().time() + timeout
        while not self.sensor.is_active:
            if asyncio.get_event_loop().time() > deadline:
                return False
            await asyncio.sleep(0.05)  # Non-blocking check mỗi 50ms
        return True
```

### Cách tích hợp vào `cam_stream.py` (hàm `run_pipeline`)

```python
# Thêm vào đầu cam_stream.py
from conveyor_controller import ConveyorController

# Trong CameraStreamer.__init__:
self.conveyor = ConveyorController()

# Thay thế vòng lặp trong run_pipeline:
async def run_pipeline(self, cam_idx=None):
    self.cap = self.init_camera(manual_idx=cam_idx)
    if not self.cap:
        return

    self.conveyor.start()  # Khởi động băng chuyền

    try:
        while True:
            # Chờ cảm biến phát hiện trái cây đến vị trí chụp
            if not await self.conveyor.wait_for_object(timeout=30):
                logger.info("⏳ Không có trái cây trong 30s, tiếp tục chờ...")
                continue

            # DỪNG băng chuyền để chụp ảnh ổn định
            self.conveyor.stop()
            await asyncio.sleep(0.2)  # Đợi vật thể ổn định

            # Chụp và phân loại
            ret, frame = self.cap.read()
            if ret:
                label, confidence = await loop.run_in_executor(
                    self.executor, self.classifier.predict, frame, self.confidence_thresh
                )
                if label and label != "unknown":
                    await self.send_result(label, confidence, frame_id)
                    frame_id += 1

            # Chạy lại băng chuyền để di chuyển trái cây ra
            self.conveyor.start()
            await asyncio.sleep(1.0)  # Thời gian vật thể thoát khỏi vùng cảm biến

    finally:
        self.conveyor.shutdown()
        await self.cleanup()
```

---


---

## PHẦN 4: QUY TRÌNH VẬN HÀNH HỆ THỐNG HOÀN CHỈNH (INTEGRATED WORKFLOW)

Hệ thống sẽ vận hành theo một chu trình khép kín, đảm bảo tính chính xác và tối ưu hiệu suất cho Raspberry Pi:

1. **Bước 1: Khởi động & Di chuyển (Conveyor Start)**
   - Hệ thống khởi tạo kết nối WebSocket với Laptop.
   - Motor L298N nhận lệnh quay thuận, băng chuyền bắt đầu di chuyển để đưa trái cây vào vùng kiểm tra.

2. **Bước 2: Kích hoạt nhận diện (Sensor Trigger)**
   - Cảm biến E18-D80NK phát hiện có vật thể đi ngang qua (Tín hiệu chuyển từ HIGH sang LOW).
   - Ngay lập tức, Raspberry Pi nhận biết sự kiện này thông qua cơ chế callback (hoặc polling) của `gpiozero`.

3. **Bước 3: Chụp ảnh ổn định (Snapshot & Control)**
   - **Dừng băng chuyền**: Pi gửi lệnh dừng motor để triệt tiêu hiện tượng nhòe ảnh do chuyển động (motion blur).
   - **Chụp ảnh**: Camera chụp một khung hình duy nhất ở độ phân giải tối ưu.
   - **Inference**: Ảnh được đưa vào pipeline AI (FruitClassifier) để nhận diện loại quả.

4. **Bước 4: Phản hồi & Truyền tải (Response & Data)**
   - Pi gửi kết quả nhận diện (Ví dụ: "Cam - 98%") về Laptop Server qua WebSocket.
   - Laptop cập nhật giao diện giám sát và lưu log.

5. **Bước 5: Hoàn tất chu kỳ (Resume)**
   - Sau khi có kết quả, Motor khởi động lại để đẩy trái cây ra khỏi vùng cảm biến, chuẩn bị cho trái cây tiếp theo.

---

## PHẦN 5: KẾT LUẬN & KHUYẾN NGHỊ


### Đánh giá tổng thể

| Hạng mục | Kết quả |
|---|---|
| Bản phân tích phần cứng có chính xác không? | **Đúng ~90%**, có 1 lỗi logic cảm biến nhỏ cần sửa |
| Có an toàn để kết nối với Pi không? | **CÓ** — NPN không đẩy 5V vào GPIO |
| Có phù hợp để tích hợp vào dự án PBL5 không? | **RẤT PHÙ HỢP** |
| Mức độ thay đổi codebase hiện tại | **Thấp** — Thêm 1 file mới + sửa nhẹ `cam_stream.py` |

### Bước tiếp theo đề xuất

1. **[Ngay bây giờ]** Tạo file `pi_edge/conveyor_controller.py` với code ở Phần 3.
2. **[Tiếp theo]** Sửa `cam_stream.py` để tích hợp logic cảm biến → dừng → chụp → chạy lại.
3. **[Tùy chọn]** Thêm trạng thái `conveyor_status` vào JSON payload gửi lên Laptop để server cũng biết trạng thái băng chuyền.
4. **[Tùy chọn]** Cập nhật `system_integration_plan.md` để bổ sung sơ đồ luồng mới có Motor/Sensor.
