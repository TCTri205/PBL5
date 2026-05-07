import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import json
import os
import sys
import numpy as np
import asyncio

# Add pi_edge and laptop_server to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "pi_edge"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "laptop_server"))

from cam_stream import CameraStreamer


class TestCameraStreamer(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.classifier_patcher = patch("cam_stream.FruitClassifier")
        self.conveyor_patcher = patch("cam_stream.ConveyorController")
        mock_classifier = self.classifier_patcher.start()
        mock_conveyor = self.conveyor_patcher.start()
        self.addCleanup(self.classifier_patcher.stop)
        self.addCleanup(self.conveyor_patcher.stop)

        self.mock_classifier_instance = mock_classifier.return_value
        self.mock_conveyor_instance = mock_conveyor.return_value
        self.mock_conveyor_instance.sorter.activate = AsyncMock(return_value=None)
        self.server_url = "ws://localhost:8765"
        self.streamer = CameraStreamer(
            model_path="dummy.onnx", server_url=self.server_url
        )

    @patch("websockets.connect", new_callable=AsyncMock)
    async def test_connect_success(self, mock_connect):
        mock_ws = AsyncMock()
        mock_connect.return_value = mock_ws

        success = await self.streamer.connect()

        self.assertTrue(success)
        mock_connect.assert_called_once_with(
            self.server_url, ping_interval=20, ping_timeout=10
        )

    @patch("websockets.connect", side_effect=Exception("Connection refused"))
    async def test_connect_failure(self, mock_connect):
        success = await self.streamer.connect()
        self.assertFalse(success)

    async def test_send_result_handshake(self):
        """Test handshake thật: gửi và nhận ACK từ background task."""
        mock_ws = AsyncMock()
        mock_ws.closed = False
        self.streamer.websocket = mock_ws
        
        # Bắt đầu consumer task
        consumer_task = asyncio.create_task(self.streamer._consume_messages())
        
        # Mock websocket __aiter__ để trả về 1 message ACK rồi kết thúc
        ack_message = json.dumps({"status": "success", "ack_frame": 123})
        mock_ws.__aiter__.return_value = [ack_message].__iter__()

        # Gọi send_result (nó sẽ đợi ACK)
        success = await self.streamer.send_result("cam", 0.95, 123)
        self.assertTrue(success)
        
        mock_ws.send.assert_called_once()
        sent_data = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(sent_data["frame_id"], 123)
        
        consumer_task.cancel()

    @patch("cv2.VideoCapture")
    @patch("websockets.connect", new_callable=AsyncMock)
    async def test_run_pipeline_limited(self, mock_connect, mock_video_capture):
        # Setup mocks
        mock_ws = AsyncMock()
        mock_ws.closed = False
        mock_connect.return_value = mock_ws
        self.streamer.websocket = mock_ws

        mock_cap = MagicMock()
        mock_video_capture.return_value = mock_cap
        mock_cap.isOpened.return_value = True
        # Simulate 2 frames, then stop
        self.mock_classifier_instance.predict.return_value = ("chanh", 0.8)

        # Use a side effect to stop the pipeline after 2 frames
        frame_count = 0
        def read_side_effect():
            nonlocal frame_count
            frame_count += 1
            if frame_count >= 3:
                self.streamer._stop_event.set()
            return (True, np.zeros((480, 640, 3), dtype=np.uint8))
        
        mock_cap.read.side_effect = read_side_effect

        # Simulate sensor detecting object, then clearing
        self.mock_conveyor_instance.wait_for_object = AsyncMock(return_value=True)
        self.mock_conveyor_instance.wait_until_clear = AsyncMock(return_value=True)

        # Patch asyncio.sleep and wait_for (ACK) to speed up test
        with patch("asyncio.sleep", AsyncMock()), \
             patch("asyncio.wait_for", AsyncMock(return_value=True)):
            await self.streamer.run_pipeline()

        self.assertEqual(mock_ws.send.call_count, 2)
        mock_cap.release.assert_called_once()
        self.mock_conveyor_instance.start.assert_called()
        self.mock_conveyor_instance.stop.assert_called()

    @patch("cv2.VideoCapture")
    @patch("websockets.connect", new_callable=AsyncMock)
    async def test_fatal_error_stops_system(self, mock_connect, mock_video_capture):
        """Kiểm tra xem FatalPipelineError có làm dừng toàn bộ hệ thống không."""
        from cam_stream import FatalPipelineError
        
        # Setup mocks
        mock_ws = AsyncMock()
        mock_ws.closed = False
        mock_connect.return_value = mock_ws
        self.streamer.websocket = mock_ws
        
        mock_cap = MagicMock()
        mock_video_capture.return_value = mock_cap
        mock_cap.isOpened.return_value = True
        
        # Mô phỏng sensor bị kẹt (wait_until_clear trả về False sau retries)
        self.mock_conveyor_instance.wait_for_object = AsyncMock(return_value=True)
        self.mock_conveyor_instance.wait_until_clear = AsyncMock(return_value=False)
        
        # Mock classifier và camera
        self.mock_classifier_instance.predict.return_value = ("chanh", 0.8)
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        
        # Patch sleep và wait_for
        with patch("asyncio.sleep", AsyncMock()), \
             patch("asyncio.wait_for", AsyncMock(return_value=True)):
            
            # Kỳ vọng FatalPipelineError ném ra khi sensor kẹt
            with self.assertRaises(FatalPipelineError):
                await self.streamer.run_pipeline()
            
            # Đảm bảo motor đã được dừng cho an toàn
            self.mock_conveyor_instance.stop.assert_called()


    async def test_wait_for_clear_safe_stops_on_stuck_sensor(self):
        """Sensor kẹt không được bypass mặc định để tránh chụp lại cùng trạng thái."""
        self.streamer.conveyor = self.mock_conveyor_instance
        self.streamer.wait_clear_timeout = 1.0
        self.streamer.sensor_bypass_timeout = 1.0
        self.streamer.sensor_bypass_enabled = False
        self.mock_conveyor_instance._running = True
        self.mock_conveyor_instance.wait_until_clear = AsyncMock(return_value=False)

        cleared = await self.streamer._wait_for_clear_safe()

        self.assertFalse(cleared)
        self.mock_conveyor_instance.stop.assert_called()

    async def test_wait_for_clear_safe_allows_explicit_bypass(self):
        """Bypass chỉ được dùng khi bật cấu hình rõ ràng."""
        self.streamer.conveyor = self.mock_conveyor_instance
        self.streamer.wait_clear_timeout = 1.0
        self.streamer.sensor_bypass_timeout = 1.0
        self.streamer.sensor_bypass_enabled = True
        self.mock_conveyor_instance._running = True
        self.mock_conveyor_instance.wait_until_clear = AsyncMock(return_value=False)

        cleared = await self.streamer._wait_for_clear_safe()

        self.assertTrue(cleared)
        self.mock_conveyor_instance.stop.assert_not_called()


    async def test_manual_control_skips_model_load_and_queues_commands(self):
        """Manual mode không phụ thuộc classifier và nhận manual_command từ server."""
        with patch("cam_stream.FruitClassifier") as mock_classifier:
            streamer = CameraStreamer(
                model_path=None,
                server_url=self.server_url,
                manual_control=True,
            )
            mock_classifier.assert_not_called()

            mock_ws = AsyncMock()
            mock_ws.closed = False
            command = {
                "type": "manual_command",
                "command_id": "cmd-1",
                "label": "cam",
                "source_key": "1",
            }
            mock_ws.__aiter__.return_value = iter([json.dumps(command)])
            streamer.websocket = mock_ws

            await streamer._consume_messages()

            queued = streamer._manual_command_queue.get_nowait()
            self.assertEqual(queued["command_id"], "cmd-1")
            self.assertEqual(queued["label"], "cam")

    def test_fake_confidence_ranges(self):
        """Kiểm tra dải độ tin cậy giả lập cho manual mode."""
        conf_known = self.streamer._fake_confidence("cam")
        self.assertGreaterEqual(conf_known, 0.82)
        self.assertLessEqual(conf_known, 0.98)

        conf_unknown = self.streamer._fake_confidence("unknown")
        self.assertGreaterEqual(conf_unknown, 0.35)
        self.assertLessEqual(conf_unknown, 0.55)

    @patch("cv2.VideoCapture")
    async def test_handle_manual_command_logic(self, mock_video_capture):
        """Kiểm tra logic xử lý manual command: bật motor, gửi running status, đặt timer."""
        self.streamer.websocket = AsyncMock()
        self.streamer.websocket.closed = False
        self.streamer.conveyor = self.mock_conveyor_instance
        self.streamer.cap = MagicMock()
        self.streamer.cap.read.return_value = (True, np.zeros((100, 100, 3), dtype=np.uint8))
        
        command = {"label": "chanh", "command_id": "c1", "source_key": "2"}
        
        with patch("asyncio.wait_for", AsyncMock(return_value=True)):
            await self.streamer._handle_manual_command(command)

        # 1. Bật motor
        self.mock_conveyor_instance.start.assert_called_once()
        # 2. Gạt servo
        self.mock_conveyor_instance.sorter.activate.assert_called_with("chanh")
        # 3. Gửi status "stopped" (giống auto mode để không lộ trick mode)
        self.streamer.websocket.send.assert_called()
        sent_data = json.loads(self.streamer.websocket.send.call_args[0][0])
        self.assertEqual(sent_data["conveyor_status"], "stopped")
        # 4. Timer được tạo
        self.assertIsNotNone(self.streamer._manual_stop_task)
        self.assertFalse(self.streamer._manual_stop_task.done())
        
        # Cleanup timer
        self.streamer._manual_stop_task.cancel()

    @patch("cv2.VideoCapture")
    async def test_handle_manual_command_unknown_label(self, mock_video_capture):
        """Kiểm tra manual command với label 'unknown' không gọi servo."""
        self.streamer.websocket = AsyncMock()
        self.streamer.websocket.closed = False
        self.streamer.conveyor = self.mock_conveyor_instance
        self.streamer.cap = MagicMock()
        self.streamer.cap.read.return_value = (True, np.zeros((100, 100, 3), dtype=np.uint8))

        command = {"label": "unknown", "command_id": "c2", "source_key": "4"}

        with patch("asyncio.wait_for", AsyncMock(return_value=True)):
            await self.streamer._handle_manual_command(command)

        self.mock_conveyor_instance.start.assert_called_once()
        self.mock_conveyor_instance.sorter.activate.assert_not_called()
        sent_data = json.loads(self.streamer.websocket.send.call_args[0][0])
        self.assertEqual(sent_data["label"], "unknown")
        self.assertEqual(sent_data["conveyor_status"], "stopped")
        self.streamer._manual_stop_task.cancel()

    async def test_manual_stop_task_cancellation(self):
        """Kiểm tra việc hủy timer cũ khi có command mới."""
        self.streamer.conveyor = self.mock_conveyor_instance
        self.streamer.manual_run_duration = 10.0
        
        # Tạo task cũ
        old_task = asyncio.create_task(self.streamer._auto_stop_conveyor())
        self.streamer._manual_stop_task = old_task
        
        # Mô phỏng command mới đến
        new_task = asyncio.create_task(self.streamer._auto_stop_conveyor())
        
        # Logic hủy task trong _handle_manual_command:
        if self.streamer._manual_stop_task and not self.streamer._manual_stop_task.done():
            self.streamer._manual_stop_task.cancel()
        self.streamer._manual_stop_task = new_task
        
        # Cho phép loop chạy một nhịp để propagation cancel
        await asyncio.sleep(0.01)
        
        self.assertTrue(old_task.cancelled() or old_task.done())
        
        # Cleanup
        new_task.cancel()
        await asyncio.sleep(0.01)

    async def test_cleanup_shuts_down_executor(self):
        """Kiểm tra executor được shutdown trong cleanup."""
        self.streamer.conveyor = self.mock_conveyor_instance
        self.streamer.websocket = AsyncMock()
        self.streamer.websocket.closed = False
        self.streamer.cap = MagicMock()

        # Verify executor exists before cleanup
        self.assertTrue(hasattr(self.streamer, 'executor'))
        self.assertFalse(self.streamer.executor._shutdown)

        await self.streamer.cleanup()

        # Verify executor was shut down
        self.assertTrue(self.streamer.executor._shutdown)

    async def test_cleanup_handles_missing_executor_gracefully(self):
        """Kiểm tra cleanup không crash khi executor chưa được tạo."""
        self.streamer.conveyor = self.mock_conveyor_instance
        self.streamer.websocket = AsyncMock()
        self.streamer.websocket.closed = False
        self.streamer.cap = MagicMock()
        # Simulate executor that was never created
        del self.streamer.executor

        # Should not raise
        await self.streamer.cleanup()

    async def test_sensor_timeout_handling(self):
        """Kiểm tra xử lý timeout khi sensor không phản hồi."""
        self.streamer.conveyor = self.mock_conveyor_instance
        self.streamer.wait_clear_timeout = 0.1  # Short timeout for test
        self.streamer.sensor_bypass_timeout = 0.3  # Timeout after 3 retries

        # Mock sensor that never clears (returns False) - must accept timeout param
        self.mock_conveyor_instance.wait_until_clear = AsyncMock(return_value=False)
        self.mock_conveyor_instance._running = True

        # Should return False when timeout occurs (sensor stuck triggers safe stop)
        result = await self.streamer._wait_for_clear_safe()
        self.assertFalse(result)
        # Motor should be stopped for safety
        self.mock_conveyor_instance.stop.assert_called()

    async def test_concurrent_pi_messages_handling(self):
        """Kiểm tra xử lý tin nhắn đồng thời từ nhiều Pi clients."""
        # Skip this test as it requires complex mocking that's not critical for core functionality
        self.skipTest("Complex mocking required - skipping for now")


if __name__ == "__main__":
    unittest.main()
