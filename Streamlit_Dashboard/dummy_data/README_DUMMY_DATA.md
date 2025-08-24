# 스마트 링거폴대 더미데이터 사용 가이드

이 문서는 스마트 링거폴대 시스템에서 더미데이터를 생성하고 관리하는 방법을 설명합니다.

## 📋 개요

더미데이터는 개발 및 테스트 목적으로 사용되며, 다음과 같은 두 가지 방법으로 관리할 수 있습니다:

1. **로컬 JSON 파일 방식**: 파일 시스템에 JSON으로 저장하여 관리
2. **DynamoDB 직접 업로드 방식**: AWS DynamoDB에 직접 데이터 생성

## 🚀 빠른 시작

### 방법 1: 로컬 JSON 파일로 더미데이터 생성 (권장)

```bash
# Streamlit_Dashboard 디렉토리에서
python create_local_dummy_data.py
```

이 명령어를 실행하면 `dummy_data/` 디렉토리에 다음 파일들이 생성됩니다:
- `dummy_loadcell.json`: 수액 무게, 남은 시간, 너스콜 상태
- `dummy_pole_stat.json`: 배터리 레벨, 분실 상태, tare 요청 상태  
- `dummy_loadcell_history.json`: 24시간 히스토리 데이터

### 방법 2: DynamoDB에 직접 더미데이터 생성

```bash
# Streamlit_Dashboard 디렉토리에서
python create_dummy_data.py
```

⚠️ **주의**: 이 방법은 실제 AWS DynamoDB에 데이터를 생성하므로 비용이 발생할 수 있습니다.

## 📁 생성되는 데이터 구조

### 1. loadcell 테이블 (수액 데이터)
```json
{
  "2": {
    "loadcel": "2",
    "current_weight": "750.3",
    "remaining_sec": "21600",
    "nurse_call": false,
    "timestamp": "2024-01-15T10:30:00+09:00"
  }
}
```

### 2. pole_stat 테이블 (폴대 상태)
```json
{
  "2": {
    "pole_id": "2",
    "battery_level": 3,
    "is_lost": false,
    "tare_requested": false,
    "timestamp": "2024-01-15T10:30:00+09:00"
  }
}
```

### 3. loadcell_history 테이블 (히스토리)
```json
[
  {
    "loadcel": "2",
    "current_weight_history": "800.5",
    "remaining_sec_history": "23040",
    "timestamp": "2024-01-14T10:30:00+09:00",
    "expire_at": 1705123200
  }
]
```

## 🔧 더미데이터 관리

### Python 코드에서 더미데이터 사용

```python
from utils.dummy_data_utils import (
    load_dummy_data_from_json,
    get_combined_loadcell_data,
    update_dummy_data_item,
    get_dummy_data_summary
)

# 더미데이터 로드
dummy_data = load_dummy_data_from_json()

# 실제 DB 데이터와 병합
combined_data = get_combined_loadcell_data()

# 특정 폴대 데이터 업데이트
update_dummy_data_item('loadcell', '2', {'nurse_call': True})

# 더미데이터 요약 정보
summary = get_dummy_data_summary()
```

### 더미데이터 수정

JSON 파일을 직접 편집하여 더미데이터를 수정할 수 있습니다:

```bash
# 예: 폴대 2번의 수액 무게를 500g로 변경
vim dummy_data/dummy_loadcell.json
```

## 📊 더미데이터 포함 폴대

- **폴대 1번**: 실제 DB 데이터 (더미데이터에 포함되지 않음)
- **폴대 2번**: 더미데이터 (수액 무게: 100-1000g, 배터리: 0-3)
- **폴대 3번**: 더미데이터 (수액 무게: 100-1000g, 배터리: 0-3)
- **폴대 4번**: 더미데이터 (수액 무게: 100-1000g, 배터리: 0-3)
- **폴대 5번**: 더미데이터 (수액 무게: 100-1000g, 배터리: 0-3)

## 🔄 더미데이터 새로고침

더미데이터를 새로 생성하려면:

```bash
# 기존 더미데이터 삭제
rm -rf dummy_data/

# 새로운 더미데이터 생성
python create_local_dummy_data.py
```

## ⚠️ 주의사항

1. **로컬 JSON 방식**: 
   - 파일 시스템에 저장되므로 Git으로 버전 관리 가능
   - 팀원들과 공유하기 쉬움
   - 실제 DB 연결 없이도 테스트 가능

2. **DynamoDB 직접 업로드 방식**:
   - 실제 AWS 리소스 사용으로 비용 발생 가능
   - 실제 환경과 동일한 조건에서 테스트
   - 팀원들과 데이터 공유 시 AWS 자격증명 필요

## 🛠️ 문제 해결

### 더미데이터가 로드되지 않는 경우

1. `dummy_data/` 디렉토리가 존재하는지 확인
2. JSON 파일들이 올바르게 생성되었는지 확인
3. 파일 권한 문제가 없는지 확인

### JSON 파일 형식 오류

1. JSON 파일의 문법이 올바른지 확인
2. 파일 인코딩이 UTF-8인지 확인
3. 파일이 손상되지 않았는지 확인

## 📞 지원

더미데이터 관련 문제가 발생하면:
1. 로그 메시지 확인
2. JSON 파일 형식 검증
3. Python 스크립트 실행 권한 확인

---

💡 **팁**: 개발 초기에는 로컬 JSON 방식을 사용하고, 실제 배포 전에 DynamoDB 방식으로 테스트하는 것을 권장합니다.
