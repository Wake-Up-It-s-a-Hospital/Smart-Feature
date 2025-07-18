import boto3
import websocket
import json
import time
import os

# --- 설정 (사용자 환경에 맞게 변경 필요) ---
# 환경 변수 또는 기본값을 사용합니다.
# 1. DynamoDB 테이블 이름
TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "loadcell")
# 2. AWS 리전
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-2") # 서울 리전
# 3. 폴링 간격 (초)
POLL_INTERVAL_SECONDS = 1
# --- 설정 끝 ---

print(f"DynamoDB 테이블 '{TABLE_NAME}' (리전: {AWS_REGION})에 연결을 시도합니다.")

# Boto3 클라이언트 초기화.
# AWS 자격증명은 환경변수, ~/.aws/credentials, IAM 역할 등을 통해 자동으로 탐지됩니다.
try:
    dynamodb_client = boto3.client('dynamodb', region_name=AWS_REGION)
    print("DynamoDB 클라이언트 초기화 성공")
except Exception as e:
    print(f"Boto3 클라이언트 초기화 실패: {e}")
    print("AWS 자격증명이 올바르게 설정되었는지 확인하세요.")
    exit(1)

def send_to_websocket(data):
    """웹소켓 서버로 데이터를 전송하는 함수"""
    try:
        ws = websocket.create_connection("ws://localhost:6789")
        ws.send(json.dumps(data))
        ws.close()
        print(f"웹소켓 전송 성공: {data}")
    except Exception as e:
        print(f"웹소켓 전송 실패: {e}")

def scan_table():
    """테이블의 모든 항목을 스캔하여 최신 데이터를 가져옵니다."""
    try:
        response = dynamodb_client.scan(TableName=TABLE_NAME)
        items = response.get('Items', [])
        print(f"[DEBUG] 스캔된 항목 수: {len(items)}")
        
        # 각 항목을 처리합니다
        for item in items:
            # DynamoDB 응답 형식에서 데이터 추출
            loadcel_id = item.get('loadcel', {}).get('S')
            current_weight = item.get('current_weight', {}).get('N')
            remaining_sec = item.get('remaining_sec', {}).get('N')
            
            # 모든 필수 데이터가 존재할 경우 웹소켓으로 전송합니다
            if loadcel_id and current_weight is not None and remaining_sec is not None:
                data_to_send = {
                    "loadcel": loadcel_id,
                    "current_weight": current_weight,
                    "remaining_sec": remaining_sec
                }
                send_to_websocket(data_to_send)
                print(f"[DEBUG] 데이터 전송: {data_to_send}")
        
        return len(items)
    except Exception as e:
        print(f"테이블 스캔 중 오류 발생: {e}")
        return 0

def main():
    """메인 실행 함수"""
    print("DynamoDB 테이블 폴링을 시작합니다...")
    print(f"폴링 간격: {POLL_INTERVAL_SECONDS}초")
    
    while True:
        try:
            item_count = scan_table()
            print(f"폴링 완료 - 처리된 항목: {item_count}개")
        except Exception as e:
            print(f"폴링 중 오류 발생: {e}")
        
        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    main() 