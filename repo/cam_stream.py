import asyncio
import json
import cv2
import time
import websockets
import os
import sys

# Ensure pi_inference can be imported from the current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from pi_inference import FruitClassifier

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

    async def connect(self):
        """Duy trì kết nối WebSocket tới server."""
        try:
            print(f"🔄 Connecting to {self.server_url}...")
            self.websocket = await websockets.connect(
                self.server_url, 
                ping_interval=20, 
                ping_timeout=10
            )
            print("✅ Connection established!")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
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
            print(f"📤 Sent: {label.upper()} ({confidence:.1%})")
        except Exception as e:
            print(f"⚠️  Error sending: {e}")

    async def run_pipeline(self):
        """Vòng lặp: Chụp ảnh -> Phân loại -> Gửi kết quả."""
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
        
        if not self.cap.isOpened():
            print("❌ Error: Could not open camera.")
            return

        print(f"📹 Camera started at {self.resolution[0]}x{self.resolution[1]}")
        frame_id = 0
        temp_img_path = "/tmp/stream_frame.jpg"
        os.makedirs("/tmp", exist_ok=True)

        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    break

                # Thực hiện inference
                cv2.imwrite(temp_img_path, frame)
                label, confidence = self.classifier.predict(
                    temp_img_path, 
                    confidence_threshold=self.confidence_thresh
                )

                # Gửi nếu đạt ngưỡng
                if label != "unknown":
                    await self.send_result(label, confidence, frame_id)

                frame_id += 1
                
                # Điều chỉnh tốc độ (~5 FPS để tránh overload CPU)
                await asyncio.sleep(0.2)

        finally:
            self.cleanup()

    def cleanup(self):
        if self.cap:
            self.cap.release()
        print("🛑 Pipeline stopped.")

async def main():
    # Configuration - Adjust server IP to your laptop IP
    MODEL = "model/best.onnx"
    SERVER = "ws://127.0.0.1:8765" if os.environ.get('TESTING') else "ws://TCTRaspberryPi4.local:8765"
    
    streamer = CameraStreamer(model_path=MODEL, server_url=SERVER)
    
    while True:
        if await streamer.connect():
            await streamer.run_pipeline()
        else:
            print("Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExit by user.")
