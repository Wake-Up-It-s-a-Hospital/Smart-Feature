# 테스트용 AWS로 랜덤 데이터 쏴주는 파일

import boto3
import random
import time
import os
from decimal import Decimal

# --- 설정 (dynamodb_to_websocket.py와 동일하게 유지) ---
TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "loadcell")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-2")
# --- 설정 끝 ---

# Boto3 리소스 초기화
try:
    dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    table = dynamodb.Table(TABLE_NAME)
    print(f"DynamoDB 테이블 '{TABLE_NAME}' (리전: {AWS_REGION})에 성공적으로 연결되었습니다.")
except Exception as e:
    print(f"Boto3 초기화 실패: {e}")
    print("AWS 자격증명이 올바르게 설정되었는지 확인하세요. (예: aws configure)")
    exit(1)

def update_loadcell_item(loadcel_id, weight, seconds):
    """DynamoDB 테이블에 로드셀 항목을 추가하거나 업데이트합니다."""
    try:
        response = table.put_item(
            Item={
                'loadcel': loadcel_id,
                'current_weight': weight,
                'remaining_sec': seconds
            }
        )
        print(f"성공적으로 업데이트: loadcel='{loadcel_id}', current_weight={weight}, remaining_sec={seconds}")
        return response
    except Exception as e:
        print(f"항목 업데이트 중 오류 발생: {e}")
        return None

if __name__ == "__main__":
    print("임시 데이터 삽입을 시작합니다. 5초마다 값을 변경합니다.")
    print("Ctrl+C를 눌러 종료하세요.")
    
    # 테스트할 로드셀 ID 목록
    loadcell_ids_to_test = ["1", "2"]

    try:
        while True:
            for loadcel_id in loadcell_ids_to_test:
                # 1. 현재 무게 업데이트 (100.0 ~ 500.0 사이의 랜덤 값)
                current_weight = Decimal(str(round(random.uniform(100.0, 500.0), 2)))

                # 2. 남은 시간 업데이트 (0 ~ 3600 사이의 랜덤 정수)
                remaining_sec = random.randint(0, 3600)
                
                # 3. DynamoDB에 아이템 업데이트
                update_loadcell_item(loadcel_id, current_weight, remaining_sec)

            print("-" * 20)
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n스크립트를 종료합니다.") 