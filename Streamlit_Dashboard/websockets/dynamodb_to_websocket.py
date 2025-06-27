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
    streams_client = boto3.client('dynamodbstreams', region_name=AWS_REGION)
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

def get_stream_arn():
    """테이블의 최신 스트림 ARN을 가져옵니다."""
    try:
        response = dynamodb_client.describe_table(TableName=TABLE_NAME)
        return response['Table']['LatestStreamArn']
    except Exception as e:
        print(f"스트림 ARN을 가져오는 데 실패했습니다: {e}")
        print(f"'{TABLE_NAME}' 테이블이 존재하고 스트림이 활성화(New Image)되었는지 확인하세요.")
        return None

def get_shard_iterator(stream_arn):
    """스트림의 첫 번째 샤드에 대한 이터레이터를 가져옵니다."""
    try:
        response = streams_client.describe_stream(StreamArn=stream_arn)
        shards = response['StreamDescription']['Shards']
        if not shards:
            print("Stream에 활성화된 샤드가 없습니다. 테이블에 최근 변경이 있었는지 확인하세요.")
            return None
        shard_id = shards[0]['ShardId']
        
        iterator_response = streams_client.get_shard_iterator(
            StreamArn=stream_arn,
            ShardId=shard_id,
            ShardIteratorType='LATEST'  # 가장 최신 레코드부터 시작
        )
        return iterator_response.get('ShardIterator')
    except Exception as e:
        print(f"샤드 이터레이터를 가져오는 데 실패했습니다: {e}")
        return None

def process_records(shard_iterator):
    """샤드 이터레이터를 사용하여 레코드를 처리하고 다음 이터레이터를 반환합니다."""
    if not shard_iterator:
        return None

    try:
        response = streams_client.get_records(ShardIterator=shard_iterator, Limit=10)
        
        for record in response.get('Records', []):
            if record.get('eventName') in ['INSERT', 'MODIFY']:
                new_image = record.get('dynamodb', {}).get('NewImage', {})
                
                # 변경된 DynamoDB 테이블 구조에 맞게 데이터를 추출합니다.
                # 예: { "loadcel": {"S": "1"}, "current_weight": {"N": "123.4"}, "remaining_sec": {"N": "500"} }
                loadcel_id = new_image.get('loadcel', {}).get('S')
                current_weight = new_image.get('current_weight', {}).get('N')
                remaining_sec = new_image.get('remaining_sec', {}).get('N')

                # 모든 필수 데이터가 존재할 경우 웹소켓으로 전송합니다.
                if loadcel_id and current_weight is not None and remaining_sec is not None:
                    data_to_send = {
                        "loadcel": loadcel_id,
                        "current_weight": current_weight,
                        "remaining_sec": remaining_sec
                    }
                    send_to_websocket(data_to_send)
        
        return response.get('NextShardIterator')
    except streams_client.exceptions.ExpiredIteratorException:
        print("샤드 이터레이터가 만료되었습니다. 새 이터레이터를 가져옵니다.")
        return "EXPIRED"
    except Exception as e:
        print(f"레코드 처리 중 오류 발생: {e}")
        return None

def main():
    """메인 실행 함수"""
    stream_arn = get_stream_arn()
    if not stream_arn:
        return

    print("DynamoDB 스트림 폴링을 시작합니다...")
    shard_iterator = get_shard_iterator(stream_arn)

    while True:
        if shard_iterator == "EXPIRED":
            shard_iterator = get_shard_iterator(stream_arn)
        
        shard_iterator = process_records(shard_iterator)

        if not shard_iterator:
            print("샤드 이터레이터가 없습니다. 5초 후 재시도합니다.")
            time.sleep(5)
            # 스트림 상태가 변경되었을 수 있으므로 스트림 ARN부터 다시 가져옵니다.
            stream_arn = get_stream_arn()
            if stream_arn:
                shard_iterator = get_shard_iterator(stream_arn)
        
        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    main() 