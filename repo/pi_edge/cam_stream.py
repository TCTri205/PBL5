import asyncio
import json
import base64
import cv2
import time
import websockets
import os
import sys
import logging
import argparse
from concurrent.futures import ThreadPoolExecutor

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

        # Khởi tạo phần cứng băng chuyền
        self.conveyor = ConveyorController()
        
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

    def init_camera(self, manual_idx=None):
        """Thử mở camera. Nếu manual_idx được cung cấp, dùng nó trước."""
        indices = [manual_idx] if manual_idx is not None else [0, 1, 2]
        
        for idx in indices:
            logger.info(f"Trying to open camera at index {idx}...")
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
                # Optimize for latency: Set buffer size to 1 if supported
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                logger.info(f"✅ Camera started at index {idx}")
                return cap
            cap.release()
            
        # Fallback to auto-discovery if manual index failed
        if manual_idx is not None:
            logger.warning(f"⚠️  Manual index {manual_idx} failed. Falling back to auto-discovery...")
            return self.init_camera(manual_idx=None)
            
        return None

    async def run_pipeline(self, cam_idx=None):
        """Vòng lặp: Chụp ảnh -> Phân loại (Async) -> Gửi kết quả."""
        self.cap = self.init_camera(manual_idx=cam_idx)

        if not self.cap:
            logger.error("❌ Error: Could not open any camera index.")
            return

        frame_id = 0
        loop = asyncio.get_running_loop()

        self.conveyor.start()
        # Chờ camera và phần cứng ổn định (quan trọng để tránh sụt áp gây lỗi timeout)
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

                # 3. Chụp ảnh
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning("⚠️ Failed to grab frame. Clearing buffer and retrying...")
                    # Thử giải phóng buffer nếu timeout nhẹ
                    for _ in range(5): self.cap.grab() 
                    ret, frame = self.cap.read()
                    
                if not ret:
                    logger.warning("⚠️ Still failed to grab frame. Resuming cycle to clear object...")
                    # Vẫn cần chạy lại băng chuyền và đợi vật qua để tránh kẹt logic
                    self.conveyor.start()
                    await asyncio.sleep(self.resume_delay)
                    if not await self._wait_for_clear_safe():
                        logger.error("🛑 Emergency Stop: Sensor blocked after camera fail.")
                        self.conveyor.stop()
                        raise FatalPipelineError("Camera lỗi và cảm biến kẹt.")
                    continue

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
                if label and label != "unknown":
                    await self.conveyor.sorter.activate(label)

                # 7. Bật lại băng chuyền để đưa quả ra ngoài
                self.conveyor.start()
                await asyncio.sleep(self.resume_delay)

                # 8. Đảm bảo cảm biến đã trống (quan trọng để không chụp lặp)
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
