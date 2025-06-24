import asyncio
import websockets

clients = set()

async def handler(websocket, path=None):
    clients.add(websocket)
    try:
        async for message in websocket:
            # 받은 메시지를 모든 클라이언트에게 브로드캐스트
            for client in clients:
                try:
                    await client.send(message)
                except websockets.ConnectionClosed:
                    # 연결이 닫힌 클라이언트에 보내려고 할 때 발생하는 오류를 무시합니다.
                    pass
    finally:
        clients.remove(websocket)

async def main():
    print("Currently Running Websockets.py!")
    async with websockets.serve(handler, "0.0.0.0", 6789):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())