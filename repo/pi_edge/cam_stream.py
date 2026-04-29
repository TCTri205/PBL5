import asyncio
import json
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

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class CameraStreamer:
    def __init__(
        self,
        model_path,
        server_url,
        device_id="pi-edge-01",
        confidence_thresh=0.5,
        resolution=(640, 480),
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
        self.executor = ThreadPoolExecutor(
            max_workers=1
        )  # Chạy inference trên thread riêng

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
        """Đọc và bỏ qua các message từ server để tránh đầy buffer."""
        try:
            async for _ in self.websocket:
                pass
        except Exception:
            pass

    async def send_result(self, label, confidence, frame_id):
        """Gửi kết quả nhận diện sang laptop."""
        if not self.websocket or self.websocket.closed:
            return

        payload = {
            "device_id": self.device_id,
            "frame_id": frame_id,
            "timestamp": time.time(),
            "label": label,
            "confidence": float(confidence),
        }

        try:
            await self.websocket.send(json.dumps(payload))
            logger.info(f"📤 Sent: {label.upper()} ({confidence:.1%})")
        except Exception as e:
            logger.warning(f"⚠️  Error sending: {e}")

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

        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning("⚠️  Failed to grab frame.")
                    break

                # Chạy inference trong ThreadPool
                label, confidence = await loop.run_in_executor(
                    self.executor,
                    self.classifier.predict,
                    frame,
                    self.confidence_thresh,
                )

                # Gửi nếu đạt ngưỡng
                if label and label != "unknown":
                    await self.send_result(label, confidence, frame_id)
                    
                    # Kiểm tra nếu connection bị đóng giữa chừng
                    if self.websocket and self.websocket.closed:
                        logger.warning("⚠️  Websocket connection lost. Breaking pipeline...")
                        break

                frame_id += 1
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"🔥 Pipeline error: {e}")
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Giải phóng tài nguyên (Camera, Websocket, Tasks)."""
        if hasattr(self, '_consumer_task'):
            self._consumer_task.cancel()
            
        if self.cap:
            self.cap.release()
            self.cap = None
            
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()
            logger.info("🔌 Websocket connection closed.")
            
        logger.info("🛑 Pipeline stopped.")


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

    SERVER = f"ws://{args.server}:{args.port}"

    if os.environ.get("TESTING"):
        SERVER = "ws://127.0.0.1:8765"

    if not os.path.exists(MODEL):
        logger.error(f"❌ Model file not found at {MODEL}")
        logger.info("💡 Please ensure the model exists or provide path with --model")
        return

    streamer = CameraStreamer(
        model_path=MODEL,
        server_url=SERVER,
        device_id=args.device_id,
        resolution=(res_w, res_h),
    )

    while True:
        try:
            if await streamer.connect():
                await streamer.run_pipeline(cam_idx=args.cam_idx)
            else:
                logger.info(f"Reconnecting to {SERVER} in 5 seconds...")
                await asyncio.sleep(5)
            
            # Tránh lặp quá nhanh nếu run_pipeline thoát sớm (vd: lỗi camera)
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            await asyncio.sleep(5)


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
