import asyncio
import json
import cv2
import time
import websockets
import os
import sys
import logging
from concurrent.futures import ThreadPoolExecutor

# Ensure fruit_classifier can be imported from the current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fruit_classifier import FruitClassifier

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class CameraStreamer:
    def __init__(self, model_path, server_url, confidence_thresh=0.5, resolution=(640, 480)):
        """
        Inference + Streaming pipeline for Raspberry Pi.
        """
        self.classifier = FruitClassifier(model_path)
        self.server_url = server_url
        self.confidence_thresh = confidence_thresh
        self.resolution = resolution
        self.cap = None
        self.websocket = None
        self.executor = ThreadPoolExecutor(max_workers=1) # Chạy inference trên thread riêng

    async def connect(self):
        """Duy trì kết nối WebSocket tới server."""
        try:
            logger.info(f"🔄 Connecting to {self.server_url}...")
            self.websocket = await websockets.connect(
                self.server_url, 
                ping_interval=20, 
                ping_timeout=10
            )
            logger.info("✅ Connection established!")
            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False

    async def send_result(self, label, confidence, frame_id):
        """Gửi kết quả nhận diện sang laptop."""
        if not self.websocket or self.websocket.closed:
            return

        payload = {
            "device_id": "pi-edge-01",
            "frame_id": frame_id,
            "timestamp": time.time(),
            "label": label,
            "confidence": float(confidence)
        }
        
        try:
            await self.websocket.send(json.dumps(payload))
            logger.info(f"📤 Sent: {label.upper()} ({confidence:.1%})")
        except Exception as e:
            logger.warning(f"⚠️  Error sending: {e}")

    async def run_pipeline(self):
        """Vòng lặp: Chụp ảnh -> Phân loại (Async) -> Gửi kết quả."""
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
        
        if not self.cap.isOpened():
            logger.error("❌ Error: Could not open camera.")
            return

        logger.info(f"📹 Camera started at {self.resolution[0]}x{self.resolution[1]}")
        frame_id = 0
        loop = asyncio.get_running_loop()

        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning("⚠️  Failed to grab frame.")
                    break

                # Chạy inference trong ThreadPool để không block event loop
                # Điều này rất quan trọng để duy trì kết nối WebSocket (ping/pong)
                label, confidence = await loop.run_in_executor(
                    self.executor, 
                    self.classifier.predict, 
                    frame, 
                    self.confidence_thresh
                )

                # Gửi nếu đạt ngưỡng
                if label and label != "unknown":
                    await self.send_result(label, confidence, frame_id)

                frame_id += 1
                
                # Điều chỉnh tốc độ (~5 FPS để tránh overload CPU Raspberry Pi)
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"🔥 Pipeline error: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        if self.cap:
            self.cap.release()
        self.executor.shutdown(wait=False)
        logger.info("🛑 Pipeline stopped.")

async def main():
    # Cấu hình - Thay đổi IP laptop của bạn tại đây hoặc qua biến môi trường
    MODEL = os.path.join(os.path.dirname(__file__), "model", "best.onnx")
    SERVER_IP = os.environ.get('SERVER_IP', '192.168.1.10')
    SERVER = f"ws://{SERVER_IP}:8765"
    
    if os.environ.get('TESTING'):
        SERVER = "ws://127.0.0.1:8765"
    
    if not os.path.exists(MODEL):
        logger.error(f"❌ Model file not found at {MODEL}. Please check the path.")
        return

    streamer = CameraStreamer(model_path=MODEL, server_url=SERVER)
    
    while True:
        try:
            if await streamer.connect():
                await streamer.run_pipeline()
            else:
                logger.info(f"Reconnecting to {SERVER} in 5 seconds...")
                await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nExit by user.")
