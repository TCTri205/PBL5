import asyncio
import websockets
import json
import time
import logging

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


async def fruit_classification_handler(websocket):
    """
    Xử lý kết quả phân loại trái cây gửi từ các Raspberry Pi client.
    """
    client_addr = websocket.remote_address
    logger.info(f"[+] Client connected from: {client_addr}")

    # Lưu vết frame_id cuối cùng để tránh log trùng (Idempotency)
    last_processed_frames = {} # device_id -> frame_id

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                device_id = data.get("device_id", "unknown_pi")
                frame_id = data.get("frame_id", "N/A")
                
                # Hàm helper gửi ACK
                async def send_ack(fid):
                    resp = {"status": "success", "timestamp": time.time(), "ack_frame": fid}
                    await websocket.send(json.dumps(resp))

                # Kiểm tra trùng lặp (nếu là retry)
                if last_processed_frames.get(device_id) == frame_id:
                    await send_ack(frame_id) # ACK lại cho client yên tâm
                    continue
                
                # Xử lý log
                label = data.get("label", "unknown")
                confidence = data.get("confidence", 0.0)
                conveyor_status = data.get("conveyor_status", "N/A")
                pi_time = data.get("timestamp", time.time())
                latency = (time.time() - pi_time) * 1000

                logger.info(
                    f"[{client_addr[0]}] Frame {frame_id}: "
                    f"{label.upper()} ({confidence:.2%}) | "
                    f"Conveyor: {conveyor_status} | Latency: {latency:.1f}ms"
                )

                # Gửi ACK SAU khi đã log xong (handshake hoàn tất)
                last_processed_frames[device_id] = frame_id
                await send_ack(frame_id)

            except json.JSONDecodeError:
                logger.error(f"[!] Error: Received invalid JSON from {client_addr}")
            except Exception as e:
                logger.error(f"⚠️  Error processing message: {e}")

    except websockets.exceptions.ConnectionClosed:
        logger.info(f"[-] Client {client_addr} disconnected.")
    except Exception as e:
        logger.error(f"💥 Server-side exception: {e}")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="PBL5 Fruit Classification Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen (default: 8765)")
    args = parser.parse_args()

    async with websockets.serve(fruit_classification_handler, args.host, args.port):
        logger.info("🚀 [SERVER] Multi-class Fruit Classification Server is running...")
        logger.info(f"📍 Listening at ws://{args.host}:{args.port}")
        await asyncio.Future()  # Chạy mãi mãi


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n🛑 Server stopped by user.")
