import asyncio
import websockets

clients = set()

async def handler(websocket, path):
    clients.add(websocket)
    try:
        async for message in websocket:
            # 메시지 브로드캐스트 (필요시)
            for client in clients:
                if client != websocket:
                    await client.send(message)
    finally:
        clients.remove(websocket)

async def main():
    async with websockets.serve(handler, "0.0.0.0", 6789):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())