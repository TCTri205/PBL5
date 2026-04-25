import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import json
import os
import sys
import numpy as np

# Add pi_edge and laptop_server to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'pi_edge'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'laptop_server'))

from cam_stream import CameraStreamer

class TestCameraStreamer(unittest.IsolatedAsyncioTestCase):
    @patch('cam_stream.FruitClassifier')
    def setUp(self, mock_classifier):
        self.mock_classifier_instance = mock_classifier.return_value
        self.server_url = "ws://localhost:8765"
        self.streamer = CameraStreamer(
            model_path="dummy.onnx", 
            server_url=self.server_url
        )

    @patch('websockets.connect', new_callable=AsyncMock)
    async def test_connect_success(self, mock_connect):
        mock_ws = AsyncMock()
        mock_connect.return_value = mock_ws
        
        success = await self.streamer.connect()
        
        self.assertTrue(success)
        mock_connect.assert_called_once_with(
            self.server_url, 
            ping_interval=20, 
            ping_timeout=10
        )

    @patch('websockets.connect', side_effect=Exception("Connection refused"))
    async def test_connect_failure(self, mock_connect):
        success = await self.streamer.connect()
        self.assertFalse(success)

    async def test_send_result(self):
        mock_ws = AsyncMock()
        mock_ws.closed = False
        self.streamer.websocket = mock_ws
        
        await self.streamer.send_result("cam", 0.95, 123)
        
        mock_ws.send.assert_called_once()
        sent_data = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(sent_data['label'], "cam")
        self.assertEqual(sent_data['confidence'], 0.95)
        self.assertEqual(sent_data['frame_id'], 123)

    @patch('cv2.VideoCapture')
    @patch('websockets.connect', new_callable=AsyncMock)
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
        mock_cap.read.side_effect = [
            (True, np.zeros((480, 640, 3), dtype=np.uint8)),
            (True, np.zeros((480, 640, 3), dtype=np.uint8)),
            (False, None)
        ]
        
        self.mock_classifier_instance.predict.return_value = ("chanh", 0.8)
        
        # We need to limit the loop because it's usually while True
        # I'll modify run_pipeline to return or use a custom control if I can, 
        # but here it stops on (False, None)
        
        # Patch asyncio.sleep to speed up test
        with patch('asyncio.sleep', AsyncMock()):
            await self.streamer.run_pipeline()
        
        self.assertEqual(mock_ws.send.call_count, 2)
        mock_cap.release.assert_called_once()

if __name__ == '__main__':
    unittest.main()
