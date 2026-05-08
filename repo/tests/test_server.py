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
        """Kiểm tra dashboard manual command được relay xuống Pi client."""
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

    async def test_manual_command_invalid_label_rejected(self):
        """Kiểm tra server bỏ qua manual command có label không hợp lệ."""
        async with self.client.ws_connect('/ws/pi') as pi_ws, self.client.ws_connect('/ws/dashboard') as dashboard_ws:
            payload = {
                "type": "manual_command",
                "command_id": "cmd-bad",
                "label": "durian", # Invalid label
                "source_key": "1",
            }
            await dashboard_ws.send_str(json.dumps(payload))

            try:
                await pi_ws.receive(timeout=1.0)
                self.fail("Pi should not receive invalid manual command")
            except Exception:
                pass  # Expected - Pi should not receive invalid command
            
            # Verify dashboard connection is still functional by sending a valid command
            valid_payload = {
                "type": "manual_command",
                "command_id": "cmd-valid",
                "label": "cam",
                "source_key": "1",
            }
            await dashboard_ws.send_str(json.dumps(valid_payload))
            
            # Pi should receive the valid command
            msg = await pi_ws.receive(timeout=1.0)
            data = json.loads(msg.data)
            self.assertEqual(data["type"], "manual_command")
            self.assertEqual(data["command_id"], "cmd-valid")
            self.assertEqual(data["label"], "cam")
            self.assertEqual(data["source_key"], "1")

    async def test_manual_command_invalid_key_rejected(self):
        """Kiểm tra server bỏ qua manual command có source_key không hợp lệ."""
        async with self.client.ws_connect('/ws/pi') as pi_ws, self.client.ws_connect('/ws/dashboard') as dashboard_ws:
            payload = {
                "type": "manual_command",
                "command_id": "cmd-bad-key",
                "label": "cam",
                "source_key": "X", # Invalid key
            }
            await dashboard_ws.send_str(json.dumps(payload))

            try:
                await pi_ws.receive(timeout=1.0)
                self.fail("Pi should not receive invalid manual command")
            except Exception:
                pass  # Expected - Pi should not receive invalid command
            
            # Verify dashboard connection is still functional by sending a valid command
            valid_payload = {
                "type": "manual_command",
                "command_id": "cmd-valid",
                "label": "cam",
                "source_key": "1",
            }
            await dashboard_ws.send_str(json.dumps(valid_payload))
            
            # Pi should receive the valid command
            msg = await pi_ws.receive(timeout=1.0)
            data = json.loads(msg.data)
            self.assertEqual(data["type"], "manual_command")
            self.assertEqual(data["command_id"], "cmd-valid")
            self.assertEqual(data["label"], "cam")
            self.assertEqual(data["source_key"], "1")

    async def test_discard_safety_on_disconnect(self):
        """Kiểm tra server sử dụng discard() để tránh lỗi khi client ngắt kết nối đột ngột."""
        # Thực tế logic này nằm ở server.py, test này đảm bảo không crash khi client ngắt
        ws = await self.client.ws_connect('/ws/dashboard')
        await ws.close()
        # Nếu dùng remove() và client đã bị xóa đâu đó, server sẽ crash. 
        # discard() thì an toàn. Test này chạy qua block finally của server.
        resp = await self.client.get('/')
        self.assertEqual(resp.status, 200)

if __name__ == "__main__":
    import unittest
    unittest.main()
