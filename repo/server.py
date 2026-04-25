import asyncio
import websockets
import json
import time

async def fruit_classification_handler(websocket):
    """
    Handle incoming fruit classification results from Raspberry Pi clients.
    """
    client_addr = websocket.remote_address
    print(f"[+] Client connected from: {client_addr}")
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                label = data.get('label', 'unknown')
                confidence = data.get('confidence', 0.0)
                frame_id = data.get('frame_id', 'N/A')
                
                print(f"[>] [{frame_id}] Received: {label.upper()} ({confidence:.2%})")
                
                # Business logic: optionally log to file or trigger notification
                response = {
                    "status": "success",
                    "timestamp": time.time(),
                    "ack_frame": frame_id
                }
                await websocket.send(json.dumps(response))
                
            except json.JSONDecodeError:
                print(f"[!] Error: Received invalid JSON from {client_addr}")
                
    except websockets.exceptions.ConnectionClosed:
        print(f"[-] Client {client_addr} disconnected.")

async def main():
    # Listen on all interfaces at port 8765
    async with websockets.serve(fruit_classification_handler, "0.0.0.0", 8765):
        print("🚀 [WEBSOCKET] Multi-class Fruit Classification Server is running...")
        print("📍 Listening at ws://0.0.0.0:8765")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user.")
