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
        "cam":   (5, 5.0, 40),    # Servo 1: 5s, gạt 40 độ
        "chanh": (6, 8.0, 40),    # Servo 2: 8s, gạt 40 độ
        "quyt":  (26, 11.0, 40),  # Servo 3: 11s, gạt 40 độ
    }

    def __init__(self, config=None):
        self.servos = {}
        self.delays = {}
        self.active_angles = {}
        self._tasks = {} # Mapping label -> task
        conf = config or self.DEFAULT_CONFIG
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

    async def activate(self, label: str):
        """
        Kích hoạt servo gạt 40 độ và tự động thu về sau một khoảng thời gian.
        
        Returns:
            asyncio.Task hoặc None — caller có thể await task để đợi servo reset xong.
        """
        if label in self.servos:
            delay = self.delays.get(label, 5.0)
            active_angle = self.active_angles.get(label, 40)
            logger.info(f"🔧 Gạt Servo {label.upper()} ({active_angle}°). Chờ {delay}s để thu về...")
            
            # Nếu đang có task reset cho label này, cancel nó để tránh xung đột
            if label in self._tasks:
                self._tasks[label].cancel()

            # Gạt theo góc đã cấu hình (40 hoặc -40)
            self.servos[label].angle = active_angle
            
            # Chạy task thu về trong background
            task = asyncio.create_task(self._delayed_reset(label, delay))
            self._tasks[label] = task
            task.add_done_callback(lambda t: self._tasks.pop(label, None) if self._tasks.get(label) == t else None)
            return task
        else:
            if label != "unknown":
                logger.warning(f"⚠️ Không tìm thấy servo cho label: {label}")
            return None

    async def _delayed_reset(self, label: str, delay: float):
        """Chờ một thời gian rồi đưa servo về 0 độ."""
        await asyncio.sleep(delay)
        if label in self.servos:
            logger.info(f"🔄 Thu Servo {label.upper()} về vị trí ban đầu (0°).")
            self.servos[label].angle = 0

    def reset_all(self):
        """Thu tất cả servo về vị trí nghỉ ngay lập tức."""
        for s in self.servos.values():
            s.angle = 0

    def close(self):
        """Giải phóng tài nguyên."""
        # Cancel các task đang đợi reset nếu có
        for task in self._tasks.values():
            task.cancel()
        for s in self.servos.values():
            s.close()


class ConveyorController:
    """
    Điều khiển băng chuyền (L298N) và cảm biến tiệm cận (E18-D80NK).
    Thiết kế để chạy song song với pipeline camera (asyncio-compatible).
    """

    def __init__(self, motor_fwd_pin=22, motor_bwd_pin=23, sensor_pin=17):
        logger.info("⚙️ Khởi tạo ConveyorController...")
        # Sử dụng DigitalOutputDevice thay cho Motor để tránh lỗi PWM trên driver Native/LGPIO
        self.motor_fwd = DigitalOutputDevice(motor_fwd_pin)
        self.motor_bwd = DigitalOutputDevice(motor_bwd_pin)

        # pull_up=True: active-low (GPIO LOW = cảm biến kích hoạt = có vật cản)
        try:
            from gpiozero import DigitalInputDevice
            self.sensor = DigitalInputDevice(sensor_pin, pull_up=True)
        except ImportError:
            # Mock cho cảm biến nếu cần
            class MockSensor:
                def __init__(self): self.is_active = False
                def close(self): pass
            self.sensor = MockSensor()

        self._running = False
        self.sorter = ServoSorter()
        logger.info(f"✅ ConveyorController sẵn sàng (Pins: Fwd={motor_fwd_pin}, Bwd={motor_bwd_pin}, Sensor={sensor_pin}).")

    @property
    def has_object(self) -> bool:
        """True nếu cảm biến phát hiện có vật cản."""
        return self.sensor.is_active

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
        
        Returns:
            True nếu phát hiện vật ổn định, False nếu timeout.
        """
        deadline = asyncio.get_event_loop().time() + timeout
        consecutive_hits = 0
        required_hits = 2 # Yêu cầu 2 lần đọc liên tiếp (khoảng 100ms) để xác nhận

        while True:
            if self.sensor.is_active:
                consecutive_hits += 1
                if consecutive_hits >= required_hits:
                    return True
            else:
                consecutive_hits = 0
            
            if asyncio.get_event_loop().time() > deadline:
                return False
                
            await asyncio.sleep(0.05)
        return False

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
            if not self.sensor.is_active:
                consecutive_clear += 1
                if consecutive_clear >= required_clear:
                    return True
            else:
                consecutive_clear = 0

            if asyncio.get_event_loop().time() > deadline:
                return False
            await asyncio.sleep(0.05)
        return True
