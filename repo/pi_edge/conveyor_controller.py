# pi_edge/conveyor_controller.py
# Module điều khiển băng chuyền - Tích hợp với cam_stream.py

import logging

logger = logging.getLogger(__name__)

import sys
import os

def is_raspberry_pi():
    """Kiểm tra xem đang chạy trên Raspberry Pi thật hay không."""
    try:
        with open('/proc/device-tree/model', 'r') as f:
            return 'Raspberry Pi' in f.read()
    except Exception:
        return False

try:
    from gpiozero import DigitalOutputDevice
except ImportError:
    # Cho phép mock fallback nếu:
    # 1. Không phải Raspberry Pi thật
    # 2. Hoặc đang trong chế độ TESTING
    if not is_raspberry_pi() or os.environ.get("TESTING") == "1":
        print("WARNING: gpiozero not found or not on RPi. Using Mock hardware classes.")
        class DigitalOutputDevice:
            def __init__(self, *args, **kwargs): self.is_active = False
            def on(self): pass
            def off(self): pass
            def close(self): pass
    else:
        logger.error("❌ gpiozero not found on Raspberry Pi! Hardware integration will not work.")
        raise

try:
    from gpiozero import AngularServo
except ImportError:
    if not is_raspberry_pi() or os.environ.get("TESTING") == "1":
        class AngularServo:
            def __init__(self, *args, **kwargs): self.angle = 0
            def close(self): pass
    else:
        raise

import asyncio

class ServoSorter:
    """Điều khiển servo phân loại trái cây (MG996R)."""

    # Mapping: label -> (GPIO pin, delay, active_angle)
    DEFAULT_CONFIG = {
        "cam":   (5, 5.0, -60),    # Servo 1: 5s, gạt -60 độ
        "chanh": (6, 8.0, -60),    # Servo 2: 8s, gạt -60 độ
        "quyt":  (26, 11.0, -60),  # Servo 3: 11s, gạt -60 độ
    }

    def __init__(self, config=None):
        self.servos = {}
        self.delays = {}
        self.active_angles = {}
        self._deadlines = {}  # label -> timestamp
        self._active_tasks = set()
        
        # Nếu không có config truyền vào, dùng mặc định
        conf = config or self.DEFAULT_CONFIG
        logger.info(f"⚙️ Khởi tạo ServoSorter với config: {conf}")
        for label, (pin, delay, active_angle) in conf.items():
            try:
                # Không set min_angle=0, max_angle=180 để dùng mặc định (-90 đến 90)
                # Khi đó angle=0 sẽ tương ứng với pulse 1.5ms (vị trí giữa chuẩn của servo)
                self.servos[label] = AngularServo(
                    pin,
                    min_pulse_width=0.0005,
                    max_pulse_width=0.0025,
                )
                self.delays[label] = delay
                self.active_angles[label] = active_angle
                self.servos[label].angle = 0
                import time
                time.sleep(0.2)  # Delay nhỏ để tránh sụt áp đồng loạt khi khởi tạo
            except Exception as e:
                logger.error(f"❌ Không thể khởi tạo servo cho {label} trên pin {pin}: {e}")

    async def activate(self, label: str, hold_duration: float = 2.0):
        """
        Kích hoạt servo gạt trái cây sau một khoảng thời gian chờ (travel delay).
        """
        if label in self.servos:
            travel_delay = self.delays.get(label, 5.0)
            active_angle = self.active_angles.get(label, -60)
            
            # Tính toán thời điểm quả sẽ thoát khỏi vùng gạt
            arrival_time = asyncio.get_event_loop().time() + travel_delay
            close_time = arrival_time + hold_duration
            
            # Cập nhật deadline xa nhất cho servo này (để xử lý nhiều quả cùng loại nối đuôi)
            self._deadlines[label] = max(self._deadlines.get(label, 0), close_time)
            
            # Chạy task xử lý gạt (không cancel task cũ để hỗ trợ dồn toa)
            task = asyncio.create_task(self._sorting_sequence(label, travel_delay, active_angle))
            self._active_tasks.add(task)
            task.add_done_callback(self._active_tasks.discard)
            return task
        else:
            if label != "unknown":
                logger.warning(f"⚠️ Không tìm thấy servo cho label: {label}")
            return None

    async def _sorting_sequence(self, label, travel_delay, active_angle):
        """Trình tự logic: Chờ -> Mở -> Đợi hết deadline -> Đóng."""
        try:
            # 1. Chờ trái cây di chuyển đến cổng (trừ 0.3s trừ hao thời gian servo quay)
            wait_time = max(0, travel_delay - 0.3)
            await asyncio.sleep(wait_time)
            
            # 2. Mở servo
            if self.servos[label].angle != active_angle:
                logger.info(f"🔧 ACTION: Mở Servo {label.upper()} ({active_angle}°).")
                self.servos[label].angle = active_angle
            
            # 3. Chờ cho đến khi vượt qua deadline (có thể đã được kéo dài bởi quả sau)
            while True:
                now = asyncio.get_event_loop().time()
                remaining = self._deadlines.get(label, 0) - now
                if remaining <= 0:
                    break
                await asyncio.sleep(remaining)
            
            # 4. Thu về (chỉ khi không có quả nào khác đang chờ deadline mới)
            if asyncio.get_event_loop().time() >= self._deadlines.get(label, 0):
                logger.info(f"🔄 ACTION: Thu Servo {label.upper()} về vị trí 0°.")
                self.servos[label].angle = 0
            
        except asyncio.CancelledError:
            pass

    def reset_all(self):
        """Thu tất cả servo về vị trí nghỉ ngay lập tức."""
        for s in self.servos.values():
            s.angle = 0

    def close(self):
        """Giải phóng tài nguyên."""
        # Cancel các task đang đợi reset nếu có
        for task in list(self._active_tasks):
            task.cancel()
        for s in self.servos.values():
            s.close()


class ConveyorController:
    """
    Điều khiển băng chuyền (L298N) và cảm biến tiệm cận (E18-D80NK).
    Thiết kế để chạy song song với pipeline camera (asyncio-compatible).
    """

    def __init__(self, motor_fwd_pin=22, motor_bwd_pin=23, sensor_pin=17, sensor_active_low=True, sorter_config=None):
        logger.info("⚙️ Khởi tạo ConveyorController...")
        self.sensor_active_low = sensor_active_low
        # Sử dụng DigitalOutputDevice thay cho Motor để tránh lỗi PWM trên driver Native/LGPIO
        self.motor_fwd = DigitalOutputDevice(motor_fwd_pin)
        self.motor_bwd = DigitalOutputDevice(motor_bwd_pin)

        # pull_up=True: active-low (GPIO LOW = cảm biến kích hoạt = có vật cản)
        try:
            from gpiozero import DigitalInputDevice
            self.sensor = DigitalInputDevice(sensor_pin, pull_up=True)
        except ImportError:
            # Mock cho cảm biến nếu cần - cho phép inject state để test
            class MockSensor:
                def __init__(self, is_active_state=False):
                    self._is_active = is_active_state
                @property
                def is_active(self):
                    return self._is_active
                @is_active.setter
                def is_active(self, value):
                    self._is_active = value
                def close(self): pass
            self.sensor = MockSensor(is_active_state=False)

        self._running = False
        self._sensor_enabled = True  # Cờ bật/tắt cảm biến
        self.sorter = ServoSorter(config=sorter_config)
        sensor_logic = "active-low" if self.sensor_active_low else "active-high"
        logger.info(f"✅ ConveyorController sẵn sàng (Pins: Fwd={motor_fwd_pin}, Bwd={motor_bwd_pin}, Sensor={sensor_pin}, Logic={sensor_logic}).")

    def _sensor_blocked(self) -> bool:
        """Chuẩn hóa trạng thái sensor về True = có vật cản."""
        raw_active = bool(self.sensor.is_active)
        return raw_active if self.sensor_active_low else not raw_active

    @property
    def has_object(self) -> bool:
        """True nếu cảm biến phát hiện có vật cản."""
        return self._sensor_blocked()

    async def enable_sensor(self, cooldown: float = 0.5):
        """Bật cảm biến — cho phép phát hiện vật thể.
        
        Args:
            cooldown: Thời gian chờ (giây) sau khi bật để nhiễu điện từ 
                      servo/motor ổn định trước khi bắt đầu đọc sensor.
        """
        # Chờ nhiễu điện từ servo PWM / motor L298N lắng xuống
        if cooldown > 0:
            logger.info(f"⏳ Chờ {cooldown}s để sensor ổn định (tránh nhiễu servo/motor)...")
            await asyncio.sleep(cooldown)
        self._sensor_enabled = True
        logger.info("👁️ Cảm biến hồng ngoại: BẬT")

    def disable_sensor(self):
        """Tắt cảm biến — bỏ qua mọi tín hiệu cho đến khi bật lại."""
        self._sensor_enabled = False
        logger.info("🚫 Cảm biến hồng ngoại: TẮT")

    def start(self):
        """Khởi động băng chuyền (chiều ngược)."""
        self._running = True
        self.motor_fwd.off()
        self.motor_bwd.on()
        logger.info("🔄 Băng chuyền CHẠY (chiều ngược).")

    def stop(self):
        """Dừng băng chuyền."""
        self._running = False
        self.motor_fwd.off()
        self.motor_bwd.off()
        logger.info("⏹️  Băng chuyền DỪNG.")

    def shutdown(self):
        """Giải phóng tài nguyên GPIO."""
        self._running = False
        self.stop()
        self.sensor.close()
        self.motor_fwd.close()
        self.motor_bwd.close()
        self.sorter.close()
        logger.info("🛑 ConveyorController đã giải phóng GPIO.")

    async def wait_for_object(self, timeout: float = 30.0) -> bool:
        """
        Chờ không đồng bộ cho đến khi cảm biến phát hiện vật (có debouncing).
        Chỉ hoạt động khi cảm biến đang được bật (_sensor_enabled = True).
        
        Returns:
            True nếu phát hiện vật ổn định, False nếu timeout hoặc sensor bị tắt.
        """
        if not self._sensor_enabled:
            logger.debug("⏸️ Sensor đang tắt, bỏ qua wait_for_object.")
            return False

        deadline = asyncio.get_event_loop().time() + timeout
        consecutive_hits = 0
        # Yêu cầu 5 lần đọc liên tiếp (250ms) để xác nhận có vật cản thật.
        # Giá trị cũ (2 lần / 100ms) quá thấp → nhiễu điện từ servo/motor 
        # gây false positive ngay sau khi kết thúc chu kỳ.
        required_hits = 5

        while True:
            if asyncio.get_event_loop().time() > deadline:
                return False

            # Kiểm tra cờ mỗi vòng lặp (cho phép tắt giữa chừng)
            if not self._sensor_enabled:
                return False

            if self._sensor_blocked():
                consecutive_hits += 1
                if consecutive_hits >= required_hits:
                    logger.debug(f"✅ Sensor xác nhận vật cản ({required_hits} lần liên tiếp).")
                    return True
            else:
                consecutive_hits = 0
                
            await asyncio.sleep(0.05)

    async def wait_until_clear(self, timeout: float = 5.0) -> bool:
        """
        Chờ không đồng bộ cho đến khi vật thể đi qua hết vùng cảm biến.
        Sử dụng debouncing (3 lần đọc liên tiếp sensor trống) để tránh false positive.

        Returns:
            True nếu vùng cảm biến đã trống ổn định, False nếu timeout.
        """
        deadline = asyncio.get_event_loop().time() + timeout
        consecutive_clear = 0
        required_clear = 3  # 3 lần đọc liên tiếp (~150ms) sensor trống mới xác nhận

        while True:
            if asyncio.get_event_loop().time() > deadline:
                return False

            if not self._sensor_blocked():
                consecutive_clear += 1
                if consecutive_clear >= required_clear:
                    return True
            else:
                consecutive_clear = 0

            await asyncio.sleep(0.05)
