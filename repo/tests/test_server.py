import unittest
from unittest.mock import AsyncMock
import json
import os
import sys
import time

# Add laptop_server to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "laptop_server"))

from server import fruit_classification_handler


class TestLaptopServer(unittest.IsolatedAsyncioTestCase):
    async def test_handler_success(self):
        # Mock WebSocket
        mock_ws = AsyncMock()
        mock_ws.remote_address = ("192.168.1.50", 12345)

        # Simulate receiving one message
        payload = {
            "device_id": "pi-01",
            "frame_id": 1,
            "timestamp": time.time() - 0.05,  # 50ms latency
            "label": "cam",
            "confidence": 0.99,
        }

        # __aiter__ allows "async for message in websocket"
        mock_ws.__aiter__.return_value = [json.dumps(payload)]

        await fruit_classification_handler(mock_ws)

        # Verify a response was sent back
        self.assertEqual(mock_ws.send.call_count, 1)
        response = json.loads(mock_ws.send.call_args[0][0])
        self.assertEqual(response["status"], "success")
        self.assertEqual(response["ack_frame"], 1)

    async def test_handler_invalid_json(self):
        mock_ws = AsyncMock()
        mock_ws.remote_address = ("192.168.1.50", 12345)
        mock_ws.__aiter__.return_value = ["not a json"]

        # Should not crash, just log error
        await fruit_classification_handler(mock_ws)

        # No response should be sent for invalid JSON
        self.assertEqual(mock_ws.send.call_count, 0)


if __name__ == "__main__":
    unittest.main()
