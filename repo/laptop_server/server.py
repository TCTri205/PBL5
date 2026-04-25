import asyncio
import websockets
import json
import time
import logging

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

async def fruit_classification_handler(websocket):
    """
    Xử lý kết quả phân loại trái cây gửi từ các Raspberry Pi client.
    """
    client_addr = websocket.remote_address
    logger.info(f"[+] Client connected from: {client_addr}")
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                label = data.get('label', 'unknown')
                confidence = data.get('confidence', 0.0)
                frame_id = data.get('frame_id', 'N/A')
                pi_time = data.get('timestamp', time.time())
                
                # Tính toán độ trễ (latency) từ Pi đến Laptop
                latency = (time.time() - pi_time) * 1000
                
                logger.info(
                    f"[{client_addr[0]}] Frame {frame_id}: "
                    f"{label.upper()} ({confidence:.2%}) | Latency: {latency:.1f}ms"
                )
                
                # Gửi phản hồi (acknowledgement)
                response = {
                    "status": "success",
                    "timestamp": time.time(),
                    "ack_frame": frame_id
                }
                await websocket.send(json.dumps(response))
                
            except json.JSONDecodeError:
                logger.error(f"[!] Error: Received invalid JSON from {client_addr}")
            except Exception as e:
                logger.error(f"⚠️  Error processing message: {e}")
                
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"[-] Client {client_addr} disconnected.")
    except Exception as e:
        logger.error(f"💥 Server-side exception: {e}")

async def main():
    # Lắng nghe trên tất cả các interface mạng tại port 8765
    port = 8765
    async with websockets.serve(fruit_classification_handler, "0.0.0.0", port):
        logger.info("🚀 [SERVER] Multi-class Fruit Classification Server is running...")
        logger.info(f"📍 Listening at ws://0.0.0.0:{port}")
        await asyncio.Future()  # Chạy mãi mãi

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n🛑 Server stopped by user.")
