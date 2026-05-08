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
import random
from concurrent.futures import ThreadPoolExecutor

# Tắt log cảnh báo GPU/Discovery của ONNX Runtime (PHẢI đặt trước khi import onnxruntime)
os.environ["ORT_LOGGING_LEVEL"] = "3"

# Ensure fruit_classifier can be imported from the current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fruit_classifier import FruitClassifier
from conveyor_controller import ConveyorController

# Import constants from server if possible, or define locally for Pi
VALID_MANUAL_KEYS = {
    "1",
    "2",
    "3",
    "4",
    "ArrowLeft",
    "ArrowDown",
    "ArrowRight",
    "ArrowUp",
}

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

VALID_MANUAL_LABELS = {"cam", "chanh", "quyt", "unknown"}


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
        wait_clear_timeout=10.0,
        sensor_bypass_timeout=20.0,
        sensor_active_low=True,
        sensor_bypass_enabled=False,
        manual_control=False,
        manual_run_duration=2.0,
        jpeg_quality=50,
        ack_timeout=1.5,
        max_frame_retries=3,
        sorter_config=None,
    ):
        """
        Inference + Streaming pipeline for Raspberry Pi.
        """
        if model_path is not None:
            logger.info(f"🧠 Loading model from: {model_path}")
            try:
                self.classifier = FruitClassifier(model_path)
            except FileNotFoundError:
                raise FatalPipelineError(f"Model file not found at {model_path}")
            except Exception as e:
                raise FatalPipelineError(f"Failed to load model: {e}")
        else:
            self.classifier = None
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
        self.sensor_bypass_timeout = sensor_bypass_timeout
        self.sensor_active_low = sensor_active_low
        self.sensor_bypass_enabled = sensor_bypass_enabled
        self.manual_control = manual_control
        self.manual_run_duration = manual_run_duration
        self.jpeg_quality = jpeg_quality
        self.ack_timeout = ack_timeout
        self.max_frame_retries = max_frame_retries
        self._manual_command_queue = asyncio.Queue()
        self._manual_stop_task = None
        self._frame_id = 0
        self._sorting_task_running = False

        # Pipeline Queues
        self._inference_queue = asyncio.Queue(maxsize=5) # Giới hạn backlog
        self._sorting_queue = asyncio.Queue(maxsize=10)
        self._network_queue = asyncio.Queue(maxsize=10) # Quan trọng: Giới hạn để không tràn RAM khi mất mạng lâu

        # QUAN TRỌNG: Hoãn khởi tạo ConveyorController (servo software PWM
        # gây nhiễu USB isochronous transfer, làm camera DV20 không stream được).
        # ConveyorController sẽ được tạo trong run_pipeline() SAU KHI camera đã sẵn sàng.
        self.conveyor = None
        self.sorter_config = sorter_config
        
        # Background Camera Reader
        self._bg_frame = None
        self._bg_ret = False
        self._bg_running = False
        self._bg_thread = None
        # Thread safety lock for frame access
        self._lock = threading.Lock()

        # Cơ chế dừng pipeline chủ động (hữu ích cho testing)
        self._stop_event = asyncio.Event()
        self._pipeline_tasks = []
        self._cleaned_up = False

    def _encode_frame(self, frame):
        """Encode OpenCV frame → base64 JPEG string để gửi qua WebSocket."""
        if frame is None:
            return None
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        return base64.b64encode(buffer).decode('utf-8')

    async def connect(self):
        """Duy trì kết nối WebSocket tới server."""
        if not self.is_ws_closed:
            return True
            
        try:
            logger.info(f"🔄 Connecting to {self.server_url}...")
            # Dọn dẹp task cũ nếu có
            if hasattr(self, '_consumer_task') and not self._consumer_task.done():
                self._consumer_task.cancel()
                
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
                    elif data.get("type") == "manual_command":
                        label = data.get("label")
                        if self.manual_control and label in VALID_MANUAL_LABELS:
                            await self._manual_command_queue.put(data)
                        else:
                            logger.warning(f"⚠️ Ignoring invalid manual command: {data}")
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

    async def send_result(self, label, confidence, frame_id, frame=None, conveyor_status="stopped"):
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
            "conveyor_status": conveyor_status,
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
                await asyncio.wait_for(future, timeout=self.ack_timeout)
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

    async def _network_worker(self):
        """Worker gửi kết quả lên server ngầm (Background)."""
        logger.info("📡 Network worker started.")
        while not self._stop_event.is_set():
            try:
                # Đợi dữ liệu cần gửi với timeout để kiểm tra stop_event
                try:
                    payload_data = await asyncio.wait_for(self._network_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                label = payload_data["label"]
                confidence = payload_data["confidence"]
                frame_id = payload_data["frame_id"]
                frame = payload_data.get("frame")
                conveyor_status = payload_data.get("conveyor_status", "stopped")

                sent_success = False
                # Thử gửi tối đa 3 lần (E6)
                for retry in range(3):
                    if await self.send_result(label, confidence, frame_id, frame=frame, conveyor_status=conveyor_status):
                        sent_success = True
                        break
                    await asyncio.sleep(1.0)
                
                if not sent_success:
                    logger.warning(f"📡 Network lag: Frame {frame_id} ({label}) failed to send after 3 retries, but pipeline continues.")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"💥 Network worker error: {e}")
                await asyncio.sleep(1)
            finally:
                try:
                    self._network_queue.task_done()
                except Exception:
                    pass
        logger.info("📡 Network worker stopped.")

    async def _reconnect_worker(self):
        """Worker tự động kết nối lại nếu mất mạng mà không làm dừng pipeline."""
        while not self._stop_event.is_set():
            try:
                if self.is_ws_closed:
                    logger.info("🔄 Websocket closed. Attempting background reconnect...")
                    await self.connect()
                await asyncio.sleep(10) # Thử lại sau mỗi 10 giây
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"💥 Reconnect worker error: {e}")
                await asyncio.sleep(10)

    async def _inference_worker(self):
        """Worker chạy model phân loại."""
        logger.info("🧠 Inference worker started.")
        loop = asyncio.get_running_loop()
        while not self._stop_event.is_set():
            try:
                # Đợi dữ liệu với timeout (W3)
                try:
                    item = await asyncio.wait_for(self._inference_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                frame = item["frame"]
                frame_id = item["frame_id"]

                # Null check for safety (C2)
                if self.classifier is None:
                    logger.error("❌ Classifier not available in inference worker!")
                    break

                # Chạy inference trên thread pool và đo thời gian (E1)
                t0 = time.perf_counter()
                label, confidence = await loop.run_in_executor(
                    self.executor,
                    self.classifier.predict,
                    frame,
                    self.confidence_thresh,
                )
                inference_ms = (time.perf_counter() - t0) * 1000
                logger.info(f"🧠 Inference: {label.upper()} ({confidence:.1%}) in {inference_ms:.1f}ms")

                # Đẩy sang Sorter và Network (C1: pass conveyor_status="running")
                await self._sorting_queue.put({"label": label, "confidence": confidence, "frame_id": frame_id})
                await self._network_queue.put({
                    "label": label, 
                    "confidence": confidence, 
                    "frame_id": frame_id, 
                    "frame": frame,
                    "conveyor_status": "running"
                })
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"💥 Inference worker error: {e}")
            finally:
                try:
                    self._inference_queue.task_done()
                except Exception:
                    pass
            
        logger.info("🧠 Inference worker stopped.")

    async def _sorting_worker(self):
        """Worker điều khiển servo gạt quả (Không phụ thuộc vào mạng)."""
        logger.info("🔧 Sorting worker started.")
        while not self._stop_event.is_set():
            try:
                # Đợi dữ liệu với timeout (W3)
                try:
                    result = await asyncio.wait_for(self._sorting_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                label = result["label"]
                frame_id = result["frame_id"]
                
                if label and label != "unknown":
                    # Kích hoạt servo ngay lập tức khi có kết quả
                    await self.conveyor.sorter.activate(label)
                    logger.info(f"✅ ACTION: Sorted {label.upper()} (Frame {frame_id})")
                else:
                    logger.info(f"⏭️  ACTION: Passed (Unknown/Low confidence) (Frame {frame_id})")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"💥 Sorting worker error: {e}")
            finally:
                try:
                    self._sorting_queue.task_done()
                except Exception:
                    pass
        logger.info("🔧 Sorting worker stopped.")

    # ─── Background Camera Reader ─────────────────────────────────────

    def _camera_worker(self):
        """Thread chạy ngầm đọc camera liên tục để xóa buffer."""
        logger.info("🧵 Background camera worker started.")
        while self._bg_running:
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                with self._lock:
                    self._bg_ret = ret
                    self._bg_frame = frame
                if not ret:
                    # Nếu lỗi, đợi một chút để tránh chiếm dụng CPU
                    time.sleep(0.1)
                else:
                    time.sleep(0.01)
            else:
                time.sleep(0.5)
        logger.info("🧵 Background camera worker stopped.")

    def get_latest_frame(self):
        """Lấy frame mới nhất từ background worker."""
        with self._lock:
            return self._bg_ret, self._bg_frame

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
        """
        # Dừng worker cũ nếu đang chạy
        self._bg_running = False
        if self._bg_thread and self._bg_thread.is_alive():
            self._bg_thread.join(timeout=2.0)

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
                
                # Start background worker after successful open
                if not self._bg_running:
                    self._bg_running = True
                    self._bg_thread = threading.Thread(target=self._camera_worker, daemon=True)
                    self._bg_thread.start()
                
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

    def _fake_confidence(self, label):
        if label == "unknown":
            return random.uniform(0.35, 0.55)
        return random.uniform(0.82, 0.98)

    async def _auto_stop_conveyor(self):
        try:
            await asyncio.sleep(self.manual_run_duration)
            if self.conveyor:
                self.conveyor.stop()
        except asyncio.CancelledError:
            raise

    async def _handle_manual_command(self, command):
        label = command["label"]
        frame_id = self._frame_id
        self._frame_id += 1
        confidence = self._fake_confidence(label)

        self.conveyor.start()

        ret, frame = self._read_with_timeout(self.cap, timeout=5.0)
        if not ret:
            logger.warning("⚠️ Failed to grab manual frame.")
            # Thử nhanh lại 1-2 frame trước khi re-init camera
            for quick_retry in range(2):
                await asyncio.sleep(0.2)
                ret, frame = self._read_with_timeout(self.cap, timeout=2.0)
                if ret:
                    logger.info(f"📸 Quick retry succeeded on attempt {quick_retry + 1}")
                    break
            if not ret:
                logger.warning("🔄 Quick retry failed, attempting camera RE-INIT...")
                self._pause_servos()
                if self.cap:
                    self.cap.release()
                await asyncio.sleep(1.0)
                self.cap = self.init_camera()
                if self.cap:
                    ret, frame = self._read_with_timeout(self.cap, timeout=5.0)
                self._resume_servos()

        if not ret:
            self.conveyor.stop()
            raise FatalPipelineError("Camera lỗi khi chạy manual control.")

        if label != "unknown":
            await self.conveyor.sorter.activate(label)

        sent_success = False
        for retry in range(3):
            if await self.send_result(
                label,
                confidence,
                frame_id,
                frame=frame,
                conveyor_status="stopped",
            ):
                sent_success = True
                break
            logger.warning(f"🔄 Retry sending manual result ({retry+1}/3)...")
            await asyncio.sleep(1)

        if not sent_success:
            logger.error("❌ Manual result was not ACKed after retries.")

        if self._manual_stop_task and not self._manual_stop_task.done():
            self._manual_stop_task.cancel()
        self._manual_stop_task = asyncio.create_task(self._auto_stop_conveyor())

    async def run_manual_control(self, cam_idx=None):
        self.cap = self.init_camera(manual_idx=cam_idx)
        if not self.cap:
            logger.error("❌ Error: Could not open any camera index.")
            raise FatalPipelineError("Không thể mở camera cho manual control.")

        if self.conveyor is None:
            self.conveyor = ConveyorController(sensor_active_low=self.sensor_active_low)

        try:
            while not self._stop_event.is_set():
                if self.is_ws_closed:
                    logger.warning("⚠️ Websocket connection lost. Breaking manual loop...")
                    break

                try:
                    command = await asyncio.wait_for(
                        self._manual_command_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                await self._handle_manual_command(command)
        except FatalPipelineError:
            raise
        except Exception as e:
            logger.error(f"💥 Manual control error: {e}")
        finally:
            if self._manual_stop_task and not self._manual_stop_task.done():
                self._manual_stop_task.cancel()
            if self.conveyor:
                self.conveyor.stop()
            await self.cleanup()

    async def run_pipeline(self, cam_idx=None):
        """Vòng lặp Pipeline: Chụp ảnh -> Queue -> Xử lý song song."""
        self._stop_event.clear()
        self._cleaned_up = False
        
        # Re-initialize queues to clear any stale items from previous runs
        self._inference_queue = asyncio.Queue(maxsize=5)
        self._sorting_queue = asyncio.Queue(maxsize=10)
        self._network_queue = asyncio.Queue(maxsize=10)

        self.cap = self.init_camera(manual_idx=cam_idx)

        if not self.cap:
            logger.error("❌ Error: Could not open any camera index.")
            raise FatalPipelineError("Không thể mở camera.")

        if self.conveyor is None:
            self.conveyor = ConveyorController(
                sensor_active_low=self.sensor_active_low,
                sorter_config=self.sorter_config
            )

        if self.classifier is None:
            raise FatalPipelineError("Auto mode requires a model classifier.")

        # Băng chuyền chạy TRƯỚC khi tạo worker (C3: Fix race condition)
        self.conveyor.start()
        logger.info("🚀 Pipeline started in parallel mode.")

        # Khởi động các worker song song
        self._pipeline_tasks = [
            asyncio.create_task(self._inference_worker()),
            asyncio.create_task(self._sorting_worker()),
            asyncio.create_task(self._network_worker()),
            asyncio.create_task(self._reconnect_worker())
        ]

        cam_fail_count = 0
        reinit_fail_count = 0 # W4: Track consecutive re-init failures

        try:
            while not self._stop_event.is_set():
                # ─── BƯỚC 1: Chờ cảm biến phát hiện trái cây ───
                if not await self.conveyor.wait_for_object(timeout=30.0):
                    continue

                # ─── BƯỚC 2: Tạm dừng để ảnh ổn định (Cấu hình) ───
                if self.capture_delay > 0:
                    self.conveyor.stop()
                    await asyncio.sleep(self.capture_delay)

                # ─── BƯỚC 3: Chụp ảnh ───
                ret, frame = self.get_latest_frame()
                
                # Sau khi chụp xong, cho băng chuyền chạy tiếp ngay để đón quả mới
                self.conveyor.start()

                if not ret or frame is None:
                    cam_fail_count += 1
                    logger.warning(f"⚠️ Failed to grab frame ({cam_fail_count}/{self.max_frame_retries}).")
                    
                    if cam_fail_count >= self.max_frame_retries:
                        logger.warning("🔄 Attempting camera RE-INIT...")
                        self._pause_servos()
                        if self.cap:
                            self.cap.release()
                        await asyncio.sleep(1.0)
                        self.cap = self.init_camera(manual_idx=cam_idx)
                        self._resume_servos()
                        
                        # Thử lại 1 lần sau re-init
                        await asyncio.sleep(2.0)
                        ret, frame = self.get_latest_frame()
                        
                        if not ret:
                            reinit_fail_count += 1
                            logger.error(f"❌ Camera re-init failed ({reinit_fail_count}/3).")
                            if reinit_fail_count >= 3:
                                raise FatalPipelineError("Camera re-init failed 3 times consecutively.")
                            cam_fail_count = 0
                            continue
                    
                    if not ret:
                        continue
                
                cam_fail_count = 0
                reinit_fail_count = 0 # Reset sau khi có frame thành công

                # ─── BƯỚC 4: Đẩy vào Queue để xử lý song song ───
                try:
                    # Dùng put_nowait để không làm nghẽn loop chính nếu queue đầy
                    self._inference_queue.put_nowait({
                        "frame": frame.copy(), 
                        "frame_id": self._frame_id
                    })
                    logger.info(f"📸 Captured Frame {self._frame_id}, sent to inference.")
                    self._frame_id += 1
                except asyncio.QueueFull:
                    logger.warning(f"⚠️ Pipeline OVERLOAD! Queues are full. Skipping frame {self._frame_id}.")
                # ─── BƯỚC 9: Đợi quả rời khỏi vùng sensor ───
                # Quả đang ở vị trí sensor, khi băng chạy quả sẽ di chuyển đi
                await asyncio.sleep(self.resume_delay)

                if not await self._wait_for_clear_safe():
                    logger.error("🛑 Emergency Stop: Sensor did not clear after sorting.")
                    self.conveyor.stop()
                    raise FatalPipelineError("Cảm biến vẫn bị che sau khi phân loại. Kiểm tra sensor GPIO 17 hoặc vật kẹt.")

                # ─── BƯỚC 10: Tiếp tục ngay (Không đợi servo thu về) ───
                # Servo tự động thu về trong background task đã tạo ở BƯỚC 7.
                # Bỏ qua việc await servo_task để tăng tốc độ phân loại quả tiếp theo.
                pass
                
                # Kiểm tra nếu connection bị đóng giữa chừng
                if self.is_ws_closed:
                    logger.warning("⚠️ Websocket disconnected. Sorting continues offline while reconnecting...")
                    # Không break nữa để hệ thống vẫn tự động chạy khi mất mạng

        except FatalPipelineError:
            raise
        except Exception as e:
            logger.error(f"🔥 Pipeline error: {e}")
        finally:
            self._stop_event.set()
            self.conveyor.stop()  # Đảm bảo dừng băng chuyền khi thoát (Hardware Safety)
            
            # Cancel current workers to avoid duplicates on retry
            for task in self._pipeline_tasks:
                if not task.done():
                    task.cancel()
            self._pipeline_tasks = []

    async def cleanup(self):
        """Giải phóng tài nguyên (Camera, Websocket, Tasks, Executor)."""
        if getattr(self, '_cleaned_up', False):
            return
        self._cleaned_up = True
        
        self._stop_event.set()

        # Cancel all background tasks
        for task in self._pipeline_tasks:
            if not task.done():
                task.cancel()
        self._pipeline_tasks = []

        if hasattr(self, '_consumer_task'):
            self._consumer_task.cancel()

        self._bg_running = False
        if self._bg_thread and self._bg_thread.is_alive():
            self._bg_thread.join(timeout=1.0)

        if hasattr(self, 'executor') and self.executor:
            self.executor.shutdown(wait=False)

        if self.cap:
            self.cap.release()
            self.cap = None

        if not self.is_ws_closed:
            await self.websocket.close()
            logger.info("🔌 Websocket connection closed.")

        logger.info("🛑 Pipeline stopped.")

    async def _wait_for_clear_safe(self, max_retries=3):
        """
        Đợi sensor trống một cách an toàn.
        
        - Thử tối đa max_retries lần, mỗi lần chờ wait_clear_timeout giây.
        - Đảm bảo băng chuyền đang CHẠY trong suốt quá trình chờ.
        - Mặc định dừng an toàn nếu sensor vẫn kẹt sau sensor_bypass_timeout giây.
        - Chỉ tiếp tục khi bật sensor_bypass_enabled rõ ràng.
        """
        # Đảm bảo băng chuyền đang chạy để vật thể có thể di chuyển qua
        if not self.conveyor._running:
            logger.warning("⚠️ Conveyor not running during clear-wait — restarting.")
            self.conveyor.start()

        elapsed = 0.0
        retries = 0
        while not await self.conveyor.wait_until_clear(timeout=self.wait_clear_timeout):
            retries += 1
            elapsed += self.wait_clear_timeout

            if self._stop_event.is_set():
                break

            if elapsed >= self.sensor_bypass_timeout:
                if self.sensor_bypass_enabled:
                    logger.warning(
                        f"⚠️ Sensor bypass: sensor vẫn kẹt sau {elapsed:.0f}s. "
                        f"Tiếp tục pipeline theo cấu hình bypass."
                    )
                    return True

                logger.warning(
                    f"⚠️ Sensor vẫn kẹt sau {elapsed:.0f}s. Dừng an toàn; "
                    f"kiểm tra sensor GPIO 17 hoặc vật kẹt trên băng chuyền."
                )
                self.conveyor.stop()
                return False

            if retries >= max_retries:
                return False

            logger.warning(f"⚠️ Sensor still blocked ({retries}/{max_retries}). Still moving...")
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
        "--manual-control",
        action="store_true",
        help="Enable hidden dashboard keyboard manual control mode",
    )
    parser.add_argument(
        "--manual-run-duration",
        type=float,
        default=2.0,
        help="Seconds to keep conveyor running after each manual command",
    )
    parser.add_argument(
        "--capture-delay", type=float, default=0.2, help="Delay after stopping motor (s)"
    )
    parser.add_argument(
        "--resume-delay", type=float, default=1.0, help="Min time to move object out (s)"
    )
    parser.add_argument(
        "--clear-timeout", type=float, default=10.0, help="Max time per retry to wait for sensor clear (s)"
    )
    parser.add_argument(
        "--bypass-timeout", type=float, default=20.0,
        help="Total time before safe stop when sensor is stuck (default 20s)"
    )
    parser.add_argument(
        "--sensor-active-high",
        action="store_true",
        help="Use when the sensor reports blocked at GPIO HIGH instead of the default active-low wiring",
    )
    parser.add_argument(
        "--enable-sensor-bypass",
        action="store_true",
        help="Allow pipeline to continue if the sensor stays blocked after --bypass-timeout",
    )
    parser.add_argument(
        "--disable-sensor-bypass",
        action="store_true",
        help="Keep safe-stop behavior when sensor is stuck (default)",
    )
    parser.add_argument(
        "--jpeg-quality", type=int, default=50,
        help="JPEG encoding quality for images sent to server (1-100, lower = faster but less detail)",
    )
    parser.add_argument(
        "--ack-timeout", type=float, default=1.5,
        help="Timeout in seconds waiting for ACK from server (lower = faster retries)",
    )
    parser.add_argument(
        "--max-frame-retries", type=int, default=3,
        help="Max consecutive frame capture failures before camera re-init",
    )
    # Servo delays config
    parser.add_argument("--delay-cam", type=float, default=5.0, help="Delay for Orange servo (s) [Default: 5.0]")
    parser.add_argument("--delay-chanh", type=float, default=8.0, help="Delay for Lemon servo (s) [Default: 8.0]")
    parser.add_argument("--delay-quyt", type=float, default=11.0, help="Delay for Tangerine servo (s) [Default: 11.0]")

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

    if not args.manual_control and not os.path.exists(MODEL):
        logger.error(f"❌ Model file not found at {MODEL}")
        logger.info("💡 Please ensure the model exists or provide path with --model")
        return

    # Build sorter config from args
    SORTER_CONFIG = {
        "cam":   (5, args.delay_cam, 40),
        "chanh": (6, args.delay_chanh, 40),
        "quyt":  (26, args.delay_quyt, 40),
    }

    streamer = CameraStreamer(
        model_path=None if args.manual_control else MODEL,
        server_url=SERVER,
        device_id=args.device_id,
        resolution=(res_w, res_h),
        capture_delay=args.capture_delay,
        resume_delay=args.resume_delay,
        wait_clear_timeout=args.clear_timeout,
        sensor_bypass_timeout=args.bypass_timeout,
        sensor_active_low=not args.sensor_active_high,
        sensor_bypass_enabled=args.enable_sensor_bypass and not args.disable_sensor_bypass,
        manual_control=args.manual_control,
        manual_run_duration=args.manual_run_duration,
        jpeg_quality=args.jpeg_quality,
        ack_timeout=args.ack_timeout,
        max_frame_retries=args.max_frame_retries,
        sorter_config=SORTER_CONFIG,
    )

    try:
        while True:
            try:
                if await streamer.connect():
                    try:
                        if args.manual_control:
                            await streamer.run_manual_control(cam_idx=args.cam_idx)
                        else:
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
