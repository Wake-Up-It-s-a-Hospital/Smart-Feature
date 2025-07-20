import asyncio
import websockets
import boto3
import json
import os
import time

clients = set()

# DynamoDB 설정
TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "loadcell")
POLE_STAT_TABLE = os.environ.get("POLE_STAT_TABLE", "pole_stat")  # 배터리 데이터 테이블
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-2")
POLL_INTERVAL_SECONDS = 1  # 데이터 읽기: 1초마다
UPLOAD_INTERVAL_SECONDS = 60  # 히스토리 업로드: 60초마다

dynamodb_client = boto3.client('dynamodb', region_name=AWS_REGION)
# loadcell_history 테이블 리소스
history_table = boto3.resource('dynamodb', region_name=AWS_REGION).Table('loadcell_history')

def upload_history(loadcel, current_weight, remaining_sec, timestamp):
    # 1주일(7일) 후 만료 시각 계산
    expire_at = int(time.time()) + 7 * 24 * 60 * 60  # 현재 시각 + 7일(초)
    item = {
        'loadcel': str(loadcel),
        'current_weight_history': str(current_weight),
        'remaining_sec_history': str(remaining_sec),
        'timestamp': timestamp,
        'expire_at': expire_at  # TTL 필드 추가
    }
    history_table.put_item(Item=item)
    print(f"[히스토리 업로드] {item}")

async def broadcast_data():
    last_upload_time = 0  # 마지막 업로드 시간 추적
    
    while True:
        try:
            current_time = time.time()
            
            # 1. loadcell 테이블에서 수액 데이터 가져오기
            response = dynamodb_client.scan(TableName=TABLE_NAME)
            items = response.get('Items', [])
            
            for item in items:
                loadcel_id = item.get('loadcel', {}).get('S')
                current_weight = item.get('current_weight', {}).get('S')
                nurse_call = item.get('nurse_call', {}).get('BOOL')
                remaining_sec = item.get('remaining_sec', {}).get('S')
                timestamp = item.get('timestamp', {}).get('S')
                
                # 2. pole_stat 테이블에서 배터리 데이터 가져오기
                battery_level = None
                try:
                    pole_response = dynamodb_client.query(
                        TableName=POLE_STAT_TABLE,
                        KeyConditionExpression='pole_id = :pole_id',
                        ExpressionAttributeValues={':pole_id': {'S': str(loadcel_id)}},  # 문자열(S) 타입으로 변경
                        ScanIndexForward=False,  # 최신순 정렬
                        Limit=1
                    )
                    pole_items = pole_response.get('Items', [])
                    if pole_items:
                        battery_level = pole_items[0].get('battery_level', {}).get('N')
                except Exception as e:
                    print(f"배터리 데이터 조회 실패 (폴대 {loadcel_id}): {e}")
                
                # 디버그용 출력
                print(f"[DynamoDB 폴링] id: {loadcel_id}, 무게: {current_weight}, 배터리 레벨: {battery_level}, 너스콜: {nurse_call}, 남은시간: {remaining_sec}")
                
                if loadcel_id and current_weight is not None and remaining_sec is not None and timestamp is not None:
                    data_to_send = {
                        "loadcel": loadcel_id,
                        "current_weight": current_weight,
                        "battery_level": battery_level,  # 배터리 레벨 추가
                        "nurse_call": nurse_call,
                        "remaining_sec": remaining_sec,
                        "timestamp": timestamp
                    }
                    
                    # 연결된 모든 클라이언트에게 전송 (1초마다)
                    if clients:
                        await asyncio.gather(*[client.send(json.dumps(data_to_send)) for client in clients])
                    
                    # loadcell_history 테이블에 업로드 (60초마다)
                    if current_time - last_upload_time >= UPLOAD_INTERVAL_SECONDS:
                        upload_history(loadcel_id, current_weight, remaining_sec, timestamp)
                        print(f"[히스토리 업로드] {item}")
                        last_upload_time = current_time
                        
        except Exception as e:
            print(f"DynamoDB 폴링/브로드캐스트 오류: {e}")
        
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

async def handler(websocket, path=None):
    clients.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        clients.remove(websocket)

async def main():
    print("WebSocket + DynamoDB 브로드캐스트 서버 실행!")
    async with websockets.serve(handler, "0.0.0.0", 6789):
        await broadcast_data()  # 폴링 및 브로드캐스트 루프 실행

if __name__ == "__main__":
    asyncio.run(main())