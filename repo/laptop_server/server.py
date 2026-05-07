import asyncio
import json
import time
import logging
import argparse
import os
from aiohttp import web

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Quản lý các kết nối
dashboard_clients = set()
pi_clients = set()
last_processed_frames = {}  # device_id -> frame_id

VALID_MANUAL_LABELS = {"cam", "chanh", "quyt", "unknown"}
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


def validate_manual_command(data):
    return (
        isinstance(data, dict)
        and data.get("type") == "manual_command"
        and isinstance(data.get("command_id"), str)
        and data.get("label") in VALID_MANUAL_LABELS
        and data.get("source_key") in VALID_MANUAL_KEYS
    )

async def index_handler(request):
    """Phục vụ trang dashboard chính."""
    return web.FileResponse(os.path.join(os.path.dirname(__file__), 'static', 'index.html'))

async def pi_ws_handler(request):
    """
    Xử lý kết nối WebSocket từ Raspberry Pi.
    """
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    peername = request.transport.get_extra_info('peername')
    client_addr = f"{peername[0]}:{peername[1]}" if peername else "unknown"
    logger.info(f"[+] Pi connected from: {client_addr}")
    pi_clients.add(ws)

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    # Validate schema and types
                    required_fields = {
                        "device_id": str,
                        "frame_id": (int, str),
                        "timestamp": (int, float),
                        "label": str,
                        "confidence": (int, float)
                    }
                    
                    is_valid = True
                    for field, expected_type in required_fields.items():
                        val = data.get(field)
                        if val is None or not isinstance(val, expected_type):
                            logger.warning(f"[!] Payload from {client_addr} invalid field '{field}': expected {expected_type}, got {type(val)}")
                            is_valid = False
                            break
                    
                    if not is_valid:
                        continue

                    device_id = data["device_id"]
                    frame_id = data["frame_id"]
                    
                    # Hàm helper gửi ACK
                    async def send_ack(fid):
                        resp = {"status": "success", "timestamp": time.time(), "ack_frame": fid}
                        await ws.send_str(json.dumps(resp))

                    # Kiểm tra trùng lặp (Idempotency)
                    if last_processed_frames.get(device_id) == frame_id:
                        await send_ack(frame_id)
                        continue
                    
                    # Log thông tin cơ bản ra terminal
                    label = data.get("label", "unknown")
                    confidence = data.get("confidence", 0.0)
                    pi_time = data.get("timestamp", time.time())
                    latency = (time.time() - pi_time) * 1000

                    logger.info(
                        f"[{client_addr}] Frame {frame_id}: "
                        f"{label.upper()} ({confidence:.2%}) | Latency: {latency:.1f}ms"
                    )

                    # Lưu trạng thái xử lý
                    last_processed_frames[device_id] = frame_id
                    
                    # Broadcast tới tất cả dashboard clients
                    if dashboard_clients:
                        broadcast_data = json.dumps(data)
                        # Tạo danh sách các task gửi tin nhắn để chạy song song
                        await asyncio.gather(
                            *[client.send_str(broadcast_data) for client in dashboard_clients],
                            return_exceptions=True
                        )

                    # Gửi ACK về Pi
                    await send_ack(frame_id)

                except json.JSONDecodeError:
                    logger.error(f"[!] Invalid JSON from {client_addr}")
                except Exception as e:
                    logger.error(f"⚠️ Error processing Pi message: {e}")
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"WS connection closed with exception {ws.exception()}")

    finally:
        pi_clients.discard(ws)
        logger.info(f"[-] Pi {client_addr} disconnected.")
    
    return ws

async def dashboard_ws_handler(request):
    """
    Xử lý kết nối WebSocket từ Browser Dashboard.
    """
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    logger.info("[+] Dashboard client connected.")
    dashboard_clients.add(ws)

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                # Hiện tại dashboard không cần gửi gì lên server
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    logger.warning("[!] Invalid JSON from dashboard client")
                    continue

                if not validate_manual_command(data):
                    logger.warning(f"[!] Invalid manual command from dashboard: {data}")
                    continue

                relay_payload = {
                    "type": "manual_command",
                    "command_id": data["command_id"],
                    "label": data["label"],
                    "source_key": data["source_key"],
                    "timestamp": time.time(),
                }

                if pi_clients:
                    relay_data = json.dumps(relay_payload)
                    await asyncio.gather(
                        *[
                            client.send_str(relay_data)
                            for client in pi_clients
                            if not client.closed
                        ],
                        return_exceptions=True
                    )
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(f"Dashboard WS connection closed with exception {ws.exception()}")
    finally:
        dashboard_clients.discard(ws)
        logger.info("[-] Dashboard client disconnected.")
    
    return ws

async def init_app():
    app = web.Application()
    
    # Routes
    app.router.add_get('/', index_handler)
    app.router.add_get('/ws/pi', pi_ws_handler)
    app.router.add_get('/ws/dashboard', dashboard_ws_handler)
    
    # Static files
    static_path = os.path.join(os.path.dirname(__file__), 'static')
    app.router.add_static('/static/', static_path, name='static')
    
    return app

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PBL5 Fruit Classification Web Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen (default: 8765)")
    args = parser.parse_args()

    app = asyncio.run(init_app())
    logger.info(f"🚀 [SERVER] Dashboard is available at http://localhost:{args.port}")
    logger.info(f"📍 WS Pi: ws://localhost:{args.port}/ws/pi")
    logger.info(f"📍 WS Dashboard: ws://localhost:{args.port}/ws/dashboard")
    
    web.run_app(app, host=args.host, port=args.port, access_log=None)
