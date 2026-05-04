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
    from gpiozero import Motor, DigitalInputDevice
except ImportError:
    # Cho phép mock fallback nếu:
    # 1. Không phải Raspberry Pi thật
    # 2. Hoặc đang trong chế độ TESTING
    if not is_raspberry_pi() or os.environ.get("TESTING") == "1":
        print("WARNING: gpiozero not found or not on RPi. Using Mock hardware classes.")
        class Motor:
            def __init__(self, **kwargs): pass
            def forward(self, speed=1): pass
            def backward(self, speed=1): pass
            def stop(self): pass
            def close(self): pass
        class DigitalInputDevice:
            def __init__(self, *args, **kwargs): self.is_active = False
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
        # Motor A: IN1=GPIO22 (forward), IN2=GPIO23 (backward)
        self.motor = Motor(forward=motor_fwd_pin, backward=motor_bwd_pin)

        # pull_up=True: active-low (GPIO LOW = cảm biến kích hoạt = có vật cản)
        self.sensor = DigitalInputDevice(sensor_pin, pull_up=True)

        self._running = False
        logger.info(f"✅ ConveyorController sẵn sàng (Pins: Fwd={motor_fwd_pin}, Bwd={motor_bwd_pin}, Sensor={sensor_pin}).")

    @property
    def has_object(self) -> bool:
        """True nếu cảm biến phát hiện có vật cản."""
        # pull_up=True: is_active=True khi GPIO bị kéo xuống LOW (có vật cản)
        return self.sensor.is_active

    def start(self):
        """Khởi động băng chuyền theo chiều thuận."""
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
