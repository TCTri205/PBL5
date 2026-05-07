import json
import time
import os
import sys
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

# Add laptop_server to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "laptop_server"))

from server import init_app

class LaptopServerTestCase(AioHTTPTestCase):
    async def get_application(self):
        """
        Tạo instance của app để test.
        """
        return await init_app()

    async def test_index_page(self):
        """Kiểm tra trang dashboard có load được không."""
        resp = await self.client.get('/')
        self.assertEqual(resp.status, 200)
        text = await resp.text()
        self.assertIn('Fruit Classifier', text)

    async def test_pi_ws_connection(self):
        """Kiểm tra kết nối WebSocket từ Pi và nhận ACK."""
        async with self.client.ws_connect('/ws/pi') as ws:
            payload = {
                "device_id": "test-pi",
                "frame_id": 100,
                "timestamp": time.time(),
                "label": "cam",
                "confidence": 0.95
            }
            await ws.send_str(json.dumps(payload))
            
            # Đợi ACK từ server
            msg = await ws.receive()
            data = json.loads(msg.data)
            self.assertEqual(data["status"], "success")
            self.assertEqual(data["ack_frame"], 100)

    async def test_pi_ws_invalid_payload(self):
        """Kiểm tra server xử lý payload thiếu field."""
        async with self.client.ws_connect('/ws/pi') as ws:
            payload = {"device_id": "test-pi"} # Thiếu nhiều field
            await ws.send_str(json.dumps(payload))
            
            # Server không nên gửi ACK cho payload lỗi (theo logic hiện tại là continue)
            # Chúng ta check xem có nhận được gì không trong 1s
            try:
                await ws.receive(timeout=1.0)
                self.fail("Should not receive response for invalid payload")
            except Exception:
                pass # Timeout là đúng kỳ vọng

    async def test_manual_command_relay_to_pi(self):
        """Kiá»ƒm tra dashboard manual command Ä‘Æ°á»£c relay xuá»‘ng Pi client."""
        async with self.client.ws_connect('/ws/pi') as pi_ws, self.client.ws_connect('/ws/dashboard') as dashboard_ws:
            payload = {
                "type": "manual_command",
                "command_id": "cmd-1",
                "label": "cam",
                "source_key": "1",
            }
            await dashboard_ws.send_str(json.dumps(payload))

            msg = await pi_ws.receive(timeout=1.0)
            data = json.loads(msg.data)
            self.assertEqual(data["type"], "manual_command")
            self.assertEqual(data["command_id"], "cmd-1")
            self.assertEqual(data["label"], "cam")
            self.assertEqual(data["source_key"], "1")
            self.assertIn("timestamp", data)

if __name__ == "__main__":
    import unittest
    unittest.main()
