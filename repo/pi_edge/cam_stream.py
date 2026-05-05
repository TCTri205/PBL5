import asyncio
import json
import base64
import cv2
import time
import threading
import websockets
import os
import sys
import logging
import argparse
from concurrent.futures import ThreadPoolExecutor

# Tắt log cảnh báo GPU/Discovery của ONNX Runtime (PHẢI đặt trước khi import onnxruntime)
os.environ["ORT_LOGGING_LEVEL"] = "3"

# Ensure fruit_classifier can be imported from the current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fruit_classifier import FruitClassifier
from conveyor_controller import ConveyorController

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class FatalPipelineError(Exception):
    """Lỗi nghiêm trọng yêu cầu dừng toàn bộ hệ thống (không tự động restart)."""
    pass

class CameraStreamer:
    def __init__(
        self,
        model_path,
        server_url,
        device_id="pi-edge-01",
        confidence_thresh=0.5,
        resolution=(640, 480),
        capture_delay=0.2,
        resume_delay=1.0,
        wait_clear_timeout=5.0,
    ):
        """
        Inference + Streaming pipeline for Raspberry Pi.
        """
        logger.info(f"🧠 Loading model from: {model_path}")
        self.classifier = FruitClassifier(model_path)
        self.server_url = server_url
        self.device_id = device_id
        self.confidence_thresh = confidence_thresh
        self.resolution = resolution
        self.cap = None
        self.websocket = None
        self._acks = {}  # frame_id -> asyncio.Future
        self.executor = ThreadPoolExecutor(
            max_workers=1
        )  # Chạy inference trên thread riêng
        self.capture_delay = capture_delay
        self.resume_delay = resume_delay
        self.wait_clear_timeout = wait_clear_timeout

        # QUAN TRỌNG: Hoãn khởi tạo ConveyorController (servo software PWM
        # gây nhiễu USB isochronous transfer, làm camera DV20 không stream được).
        # ConveyorController sẽ được tạo trong run_pipeline() SAU KHI camera đã sẵn sàng.
        self.conveyor = None
        
        # Cơ chế dừng pipeline chủ động (hữu ích cho testing)
        self._stop_event = asyncio.Event()

    def _encode_frame(self, frame, quality=50):
        """Encode OpenCV frame → base64 JPEG string để gửi qua WebSocket."""
        if frame is None:
            return None
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return base64.b64encode(buffer).decode('utf-8')

    async def connect(self):
        """Duy trì kết nối WebSocket tới server."""
        try:
            logger.info(f"🔄 Connecting to {self.server_url}...")
            self.websocket = await websockets.connect(
                self.server_url, ping_interval=20, ping_timeout=10
            )
            logger.info("✅ Connection established!")
            # Khởi tạo consumer task để giải phóng buffer (đọc ACK từ server)
            self._consumer_task = asyncio.create_task(self._consume_messages())
            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False

    async def _consume_messages(self):
        """Đọc ACKs từ server."""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    if data.get("status") == "success" and "ack_frame" in data:
                        ack_id = data["ack_frame"]
                        if ack_id in self._acks:
                            self._acks[ack_id].set_result(True)
                except Exception as e:
                    logger.warning(f"⚠️ Error parsing server message: {e}")
        except Exception:
            pass

    @property
    def is_ws_closed(self):
        """Kiểm tra xem kết nối WebSocket có bị đóng hay không (tương thích mọi phiên bản)."""
        if not self.websocket:
            return True
        # Tương thích cho websockets < 14.0
        if hasattr(self.websocket, 'closed'):
            return self.websocket.closed
        # Tương thích cho websockets >= 14.0
        return self.websocket.state.name == "CLOSED"

    async def send_result(self, label, confidence, frame_id, frame=None):
        """Gửi kết quả nhận diện sang laptop. Trả về True nếu thành công."""
        if self.is_ws_closed:
            logger.warning("⚠️ Cannot send: Websocket is closed.")
            return False

        payload = {
            "device_id": self.device_id,
            "frame_id": frame_id,
            "timestamp": time.time(),
            "label": label,
            "confidence": float(confidence),
            "conveyor_status": "stopped",
            "image": self._encode_frame(frame) if frame is not None else None,
        }

        try:
            # 1. Đăng ký future TRƯỚC khi gửi để tránh race condition
            # (Nếu server phản hồi quá nhanh, message có thể đến trước khi kịp đăng ký)
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            self._acks[frame_id] = future

            try:
                # 2. Gửi dữ liệu
                await self.websocket.send(json.dumps(payload))
                logger.info(f"📤 Sent: {label.upper()} ({confidence:.1%})")

                # 3. Đợi ACK từ server
                await asyncio.wait_for(future, timeout=3.0)
                logger.info(f"✅ ACK received for frame {frame_id}")
                return True
            except asyncio.TimeoutError:
                logger.error(f"❌ Timeout waiting for ACK for frame {frame_id}")
                return False
            finally:
                # 4. Luôn dọn dẹp để tránh memory leak
                self._acks.pop(frame_id, None)

        except Exception as e:
            logger.error(f"❌ Error sending result: {e}")
            return False

    # ─── Camera Initialization ────────────────────────────────────────

    def _read_with_timeout(self, cap, timeout=5.0):
        """
        Đọc 1 frame từ camera với timeout sử dụng thread riêng.
        CHỈ DÙNG cho pipeline reads (khi camera đã warm).
        KHÔNG dùng cho init (vì camera cần 6-9s cho frame đầu).
        
        Returns:
            (ret, frame) - giống cv2.VideoCapture.read()
        """
        result = {'ret': False, 'frame': None, 'done': False}

        def do_read():
            result['ret'], result['frame'] = cap.read()
            result['done'] = True

        t = threading.Thread(target=do_read, daemon=True)
        t.start()
        t.join(timeout=timeout)

        if not result['done']:
            return False, None

        return result['ret'], result['frame']

    def init_camera(self, manual_idx=None):
        """
        Mở camera DV20 USB với MJPEG format.
        
        Sử dụng blocking cap.read() (KHÔNG dùng threading) để đợi frame đầu tiên,
        vì camera Jieli Technology DV20 cần 6-9 giây để warm up và bắt đầu stream.
        Đây là cùng phương pháp đã hoạt động trong manual test.
        """
        indices = [manual_idx] if manual_idx is not None else [0, 1, 2]

        for idx in indices:
            logger.info(f"🔍 Opening camera at index {idx}...")
            
            # Thử V4L2 backend trước (ổn định hơn trên Linux)
            cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
            if not cap.isOpened():
                cap.release()
                # Fallback: thử AUTO backend
                cap = cv2.VideoCapture(idx)
                if not cap.isOpened():
                    cap.release()
                    continue

            # Ép MJPEG format — bắt buộc cho DV20 trên Pi USB
            # (YUYV quá nặng bandwidth, gây select() timeout)
            fourcc = cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')
            cap.set(cv2.CAP_PROP_FOURCC, fourcc)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])

            # BLOCKING read — đợi frame đầu tiên (V4L2 timeout mặc định ~10s).
            # Camera DV20 cần 6-9s warm up — KHÔNG dùng thread timeout ở đây.
            logger.info(f"  ↳ Waiting for first frame (blocking, up to ~10s)...")
            ret, frame = cap.read()  # ← Giống hệt manual test đã thành công

            if ret and frame is not None:
                actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                logger.info(f"  ✅ Camera OK: index={idx}, MJPEG, {actual_w}x{actual_h}")
                return cap

            logger.warning(f"  ❌ No frames from index={idx} (V4L2 timeout)")
            cap.release()

        # Fallback to auto-discovery if manual index failed
        if manual_idx is not None:
            logger.warning(f"⚠️  Manual index {manual_idx} failed. Falling back to auto-discovery...")
            return self.init_camera(manual_idx=None)

        return None

    def _pause_servos(self):
        """Tạm dừng servo PWM để tránh nhiễu USB khi init camera."""
        if self.conveyor and hasattr(self.conveyor, 'sorter'):
            for label, servo in self.conveyor.sorter.servos.items():
                try:
                    servo.value = None  # Detach PWM signal
                except Exception:
                    pass
            logger.info("⏸️  Servo PWM tạm dừng (tránh nhiễu USB).")

    def _resume_servos(self):
        """Kích hoạt lại servo PWM sau khi camera đã sẵn sàng."""
        if self.conveyor and hasattr(self.conveyor, 'sorter'):
            for label, servo in self.conveyor.sorter.servos.items():
                try:
                    servo.angle = 0  # Re-attach và đặt về vị trí nghỉ
                except Exception:
                    pass
            logger.info("▶️  Servo PWM đã kích hoạt lại.")

    async def run_pipeline(self, cam_idx=None):
        """Vòng lặp: Chụp ảnh -> Phân loại (Async) -> Gửi kết quả."""
        # QUAN TRỌNG: Init camera TRƯỚC conveyor.
        # Servo software PWM gây nhiễu USB isochronous transfer → camera DV20 không stream.
        self.cap = self.init_camera(manual_idx=cam_idx)

        if not self.cap:
            logger.error("❌ Error: Could not open any camera index.")
            logger.error("💡 Hãy kiểm tra:")
            logger.error("   1. Camera có được cắm chắc không? (rút ra cắm lại)")
            logger.error("   2. Thử: v4l2-ctl --list-devices")
            logger.error("   3. Thử: libcamera-hello (nếu dùng Pi Camera)")
            logger.error("   4. Kiểm tra nguồn: vcgencmd get_throttled")
            raise FatalPipelineError("Không thể mở camera sau khi thử tất cả chiến lược.")

        # Khởi tạo ConveyorController SAU KHI camera đã hoạt động
        if self.conveyor is None:
            self.conveyor = ConveyorController()

        frame_id = 0
        loop = asyncio.get_running_loop()
        cam_fail_count = 0

        self.conveyor.start()
        logger.info("⏳ Waiting for hardware stabilization (2s)...")
        await asyncio.sleep(2.0)

        try:
            while not self._stop_event.is_set():
                # 1. Chờ cảm biến phát hiện trái cây
                logger.info("🔍 Waiting for object...")
                if not await self.conveyor.wait_for_object(timeout=30.0):
                    logger.info("⏳ No object detected in 30s, continuing...")
                    continue

                # 2. DỪNG băng chuyền để chụp ảnh ổn định
                self.conveyor.stop()
                await asyncio.sleep(self.capture_delay)

                # 3. Chụp ảnh (sử dụng timeout thread để tránh block 10s)
                ret, frame = self._read_with_timeout(self.cap, timeout=5.0)
                if not ret:
                    cam_fail_count += 1
                    logger.warning(f"⚠️ Failed to grab frame ({cam_fail_count}/3). Attempting camera RE-INIT...")
                    # Tạm dừng servo PWM để tránh nhiễu USB khi re-init camera
                    self._pause_servos()
                    self.cap.release()
                    await asyncio.sleep(1.0)
                    self.cap = self.init_camera(manual_idx=cam_idx)
                    
                    if self.cap:
                        ret, frame = self._read_with_timeout(self.cap, timeout=5.0)
                    # Kích hoạt lại servo sau khi camera đã sẵn sàng
                    self._resume_servos()
                    
                if not ret:
                    if cam_fail_count >= 3:
                        logger.error("🛑 Camera failed 3 times consecutively. Possible hardware issue.")
                        self.conveyor.stop()
                        raise FatalPipelineError("Camera lỗi liên tục 3 lần. Kiểm tra kết nối phần cứng.")
                    
                    logger.warning("⚠️ Still failed to grab frame after re-init. Resuming cycle...")
                    # Vẫn cần chạy lại băng chuyền và đợi vật qua để tránh kẹt logic
                    self.conveyor.start()
                    await asyncio.sleep(self.resume_delay)
                    if not await self._wait_for_clear_safe():
                        logger.error("🛑 Emergency Stop: Sensor blocked after camera fail.")
                        self.conveyor.stop()
                        raise FatalPipelineError("Camera lỗi liên tục và cảm biến kẹt.")
                    continue
                
                # Camera hoạt động tốt → reset bộ đếm lỗi
                cam_fail_count = 0

                # 4. Chạy inference trong ThreadPool
                label, confidence = await loop.run_in_executor(
                    self.executor,
                    self.classifier.predict,
                    frame,
                    self.confidence_thresh,
                )

                # 5. Gửi kết quả (Bao gồm cả unknown để ghi nhận đủ mọi quả)
                if label:
                    sent_success = False
                    for retry in range(3):
                        if await self.send_result(label, confidence, frame_id, frame=frame):
                            sent_success = True
                            break
                        logger.warning(f"🔄 Retry sending/ACK ({retry+1}/3)...")
                        await asyncio.sleep(1)
                    
                    if not sent_success:
                        logger.error("🔥 Data loss prevention: FATAL network/ACK failure.")
                        self.conveyor.stop()
                        raise FatalPipelineError("Không thể gửi dữ liệu sau nhiều lần thử.")
                    
                    frame_id += 1

                # 6. Kích hoạt servo gạt (nếu không phải unknown)
                servo_task = None
                if label and label != "unknown":
                    servo_task = await self.conveyor.sorter.activate(label)

                # 7. Bật lại băng chuyền (chạy song song trong khi servo đang giữ)
                self.conveyor.start()

                # 8. Đợi servo reset xong TRƯỚC KHI kiểm tra sensor
                #    Nếu không đợi → quả/cánh tay servo vẫn nằm trong vùng sensor → Emergency Stop
                if servo_task:
                    try:
                        await servo_task
                    except asyncio.CancelledError:
                        pass
                    # Sau khi servo thu về, cho thêm thời gian để quả rời khỏi vùng sensor
                    await asyncio.sleep(self.resume_delay)
                else:
                    await asyncio.sleep(self.resume_delay)

                # 9. Đảm bảo cảm biến đã trống (quan trọng để không chụp lặp)
                if not await self._wait_for_clear_safe():
                    logger.error("🛑 Emergency Stop: Sensor still blocked. Possible jam or sensor fault.")
                    self.conveyor.stop()
                    self.conveyor.sorter.reset_all() # Reset servo trước khi dừng hẳn
                    raise FatalPipelineError("Cảm biến bị kẹt hoặc lỗi vật lý.")
                
                # Kiểm tra nếu connection bị đóng giữa chừng
                if self.is_ws_closed:
                    logger.warning("⚠️  Websocket connection lost. Breaking pipeline...")
                    break

        except FatalPipelineError:
            raise
        except Exception as e:
            logger.error(f"🔥 Pipeline error: {e}")
        finally:
            # Lưu ý: Không shutdown conveyor ở đây vì nó được quản lý ở main()
            # để tránh bị khởi tạo lại khi reconnect
            await self.cleanup()

    async def cleanup(self):
        """Giải phóng tài nguyên (Camera, Websocket, Tasks)."""
        if hasattr(self, '_consumer_task'):
            self._consumer_task.cancel()
            
        if self.cap:
            self.cap.release()
            self.cap = None
            
        if not self.is_ws_closed:
            await self.websocket.close()
            logger.info("🔌 Websocket connection closed.")
            
        logger.info("🛑 Pipeline stopped.")

    async def _wait_for_clear_safe(self, max_retries=3):
        """Đợi sensor trống một cách an toàn, tránh chạy motor vô hạn."""
        retries = 0
        while not await self.conveyor.wait_until_clear(timeout=self.wait_clear_timeout):
            retries += 1
            if retries >= max_retries:
                return False
            logger.warning(f"⚠️ Sensor still blocked ({retries}/{max_retries}). Still moving...")
            if self._stop_event.is_set():
                break
            await asyncio.sleep(1.0)
        return True


async def main():
    parser = argparse.ArgumentParser(
        description="Raspberry Pi Fruit Classification Streamer"
    )
    parser.add_argument(
        "--server", type=str, default="192.168.1.10", help="Laptop Server IP"
    )
    parser.add_argument("--port", type=int, default=8765, help="WebSocket Port")
    parser.add_argument("--model", type=str, default=None, help="Path to ONNX model")
    parser.add_argument(
        "--device-id", type=str, default="pi-edge-01", help="Unique ID for this Pi"
    )
    parser.add_argument(
        "--resolution",
        type=str,
        default="640x480",
        help="Camera resolution (width x height)",
    )
    parser.add_argument(
        "--cam-idx", type=int, default=None, help="Force specific camera index"
    )
    parser.add_argument(
        "--capture-delay", type=float, default=0.2, help="Delay after stopping motor (s)"
    )
    parser.add_argument(
        "--resume-delay", type=float, default=1.0, help="Min time to move object out (s)"
    )
    parser.add_argument(
        "--clear-timeout", type=float, default=5.0, help="Max time to wait for sensor clear (s)"
    )

    args = parser.parse_args()

    # Parse resolution
    try:
        res_w, res_h = map(int, args.resolution.split("x"))
    except ValueError:
        logger.error("Invalid resolution format. Use WxH (e.g., 640x480)")
        return

    # Mặc định tìm model trong thư mục model/
    if args.model is None:
        MODEL = os.path.join(os.path.dirname(__file__), "model", "best.onnx")
    else:
        MODEL = args.model

    SERVER = f"ws://{args.server}:{args.port}/ws/pi"

    if os.environ.get("TESTING"):
        SERVER = "ws://127.0.0.1:8765/ws/pi"

    if not os.path.exists(MODEL):
        logger.error(f"❌ Model file not found at {MODEL}")
        logger.info("💡 Please ensure the model exists or provide path with --model")
        return

    streamer = CameraStreamer(
        model_path=MODEL,
        server_url=SERVER,
        device_id=args.device_id,
        resolution=(res_w, res_h),
        capture_delay=args.capture_delay,
        resume_delay=args.resume_delay,
        wait_clear_timeout=args.clear_timeout,
    )

    try:
        while True:
            try:
                if await streamer.connect():
                    try:
                        await streamer.run_pipeline(cam_idx=args.cam_idx)
                    except FatalPipelineError as e:
                        logger.critical(f"🚨 FATAL: System halted for safety: {e}")
                        # Exit with non-zero to signal systemd not to auto-restart if configured so
                        sys.exit(1)
                    except Exception as e:
                        logger.error(f"⚠️ Pipeline error (retrying): {e}")
                        await asyncio.sleep(5)
                    finally:
                        await streamer.cleanup()
                else:
                    logger.info(f"Reconnecting to {SERVER} in 5 seconds...")
                    await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                await asyncio.sleep(5)
    finally:
        # Đảm bảo giải phóng phần cứng khi tắt chương trình
        if streamer.conveyor:
            streamer.conveyor.shutdown()


if __name__ == "__main__":
    import signal
    
    def handle_exit():
        logger.info("\n🛑 Received shutdown signal. Exiting...")
        sys.exit(0)
        
    # Catch both Ctrl+C and Systemd SIGTERM
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, lambda *_: handle_exit())
        except (ValueError, RuntimeError):
            pass # Ignore if not on main thread

    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Fatal error: {e}")
