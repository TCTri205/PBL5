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
import asyncio

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
        logger.info(f"✅ ConveyorController sẵn sàng (Pins: Fwd={motor_fwd_pin}, Bwd={motor_bwd_pin}, Sensor={sensor_pin}).")

    @property
    def has_object(self) -> bool:
        """True nếu cảm biến phát hiện có vật cản."""
        return self.sensor.is_active

    def start(self):
        """Khởi động băng chuyền theo chiều thuận."""
        self._running = True
        self.motor_fwd.on()
        self.motor_bwd.off()
        logger.info("🔄 Băng chuyền CHẠY.")

    def stop(self):
        """Dừng băng chuyền."""
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
        logger.info("🛑 ConveyorController đã giải phóng GPIO.")

    async def wait_for_object(self, timeout: float = 30.0) -> bool:
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

    async def wait_until_clear(self, timeout: float = 5.0) -> bool:
        """
        Chờ không đồng bộ cho đến khi vật thể đi qua hết vùng cảm biến.
        Giúp tránh việc chụp lặp cùng một quả khi băng chuyền bắt đầu chạy lại.

        Returns:
            True nếu vùng cảm biến đã trống, False nếu timeout.
        """
        deadline = asyncio.get_event_loop().time() + timeout
        while self.sensor.is_active:
            if asyncio.get_event_loop().time() > deadline:
                return False
            await asyncio.sleep(0.05)
        return True
