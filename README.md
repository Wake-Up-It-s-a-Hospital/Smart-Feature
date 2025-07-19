# 환자 추종 스마트 링거 폴대: Smart Feature

![banner](https://img.shields.io/badge/Project-Smart%20IV%20Pole-blue.svg)
![license](https://img.shields.io/badge/License-MIT-green.svg)
![status](https://img.shields.io/badge/Status-In%20Development-yellow.svg)

환자 추종 스마트 링거 폴대의 스마트 기능을 담당하는 레포입니다. 
로드셀 센서를 통해 링거 팩의 무게를 실시간으로 측정하고, 이를 서버로 전송하여 웹 대시보드에서 모니터링할 수 있는 시스템을 구축하고 있습니다.

본 레포지토리는 2025년 한국공학대학교 종합설계 (캡스톤디자인) 프로젝트의 일부로서 개발되고 있습니다.

---

## 🛠️ 현재까지 구현된 기능

- ✅ **로드셀 센서 기반 무게 측정**  
  HX711 모듈을 사용해 링거 팩의 무게를 정밀하게 측정합니다.

- ✅ **서버 전송 기능**  
  무게 데이터를 서버(DynamoDB)로 업로드하여 보관합니다.

- ✅ **실시간 웹 대시보드**  
  Streamlit을 기반으로 한 실시간 모니터링 대시보드를 제공합니다.
  - 실시간 수액 잔량 모니터링
  - 수액 투여 시간 예측
  - 통계 분석 및 보고서 생성
  - 웹소켓을 통한 실시간 데이터 업데이트

---

## 📁 프로젝트 파일 구조

```
Smart-Feature/
├── loadcell/                   # ESP32 로드셀 측정 펌웨어
│   ├── lib/HX711/              # HX711 라이브러리
│   ├── src/main.cpp            # 메인 펌웨어 코드
│   └── test/                   # 테스트 코드
│
├── Streamlit_Dashboard/        # 메인 웹 대시보드 (현재 사용 중)
│   ├── pages/                  # 대시보드 페이지들
│   │   ├── 1_실시간 대시보드.py
│   │   ├── 2_스마트 링거폴대 상세 정보.py
│   │   ├── 3_수액 사용 통계 분석.py
│   │   ├── 4_보고서 생성.py
│   │   └── 5_설정.py
│   ├── websockets/             # 실시간 통신 모듈
│   │   ├── dynamodb_to_websocket.py
│   │   └── streamlit_websocket.py
│   ├── utils/                  # 유틸리티 함수
│   └── 환자_추종_스마트_링거폴대_소개.py
│
├── Dashboard/                   # ⚠️ Deprecated (React 기반)
│   └── firebase-iv-dashboard/   # 더 이상 사용되지 않음
│
└── user_testcode/               # 사용자 테스트 코드
```

---

## 🚀 설치 및 실행 방법

### 1. 로드셀 펌웨어 (ESP32)

1. PlatformIO IDE 설치
2. `loadcell/` 폴더를 PlatformIO 프로젝트로 열기
3. ESP32와 HX711 모듈 연결
4. 펌웨어 업로드 및 시리얼 모니터로 데이터 확인

### 2. 웹 대시보드 (Streamlit)

```bash
# 1. 저장소 클론
git clone https://github.com/Wake-Up-It-s-a-Hospital/Smart-Feature.git
cd Smart-Feature/Streamlit_Dashboard

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 웹소켓 서버 실행 (백그라운드)
python websockets/dynamodb_to_websocket.py

# 4. Streamlit 대시보드 실행
streamlit run 환자_추종_스마트_링거폴대_소개.py
```

### 3. 개발 환경 설정

```bash
# Python 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 개발 의존성 설치
pip install -r requirements.txt
```

---

## 📊 주요 기능

### 실시간 모니터링
- 로드셀 센서를 통한 실시간 무게 측정
- 웹소켓을 통한 실시간 데이터 전송
- 수액 잔량 및 투여 시간 예측

### 데이터 분석
- 수액 사용 패턴 분석
- 통계 보고서 자동 생성
- 히스토리 데이터 시각화

### 알림 시스템
- 수액 부족 시 자동 알림
- 의료진 호출 시 즉시 알림

---

## 🛠️ 기술 스택

- **하드웨어**: ESP32, HX711 로드셀 모듈
- **펌웨어**: C++ (PlatformIO)
- **백엔드**: Python, DynamoDB(AWS)
- **프론트엔드**: Streamlit
- **실시간 통신**: WebSocket
- **데이터 시각화**: Plotly, Matplotlib, fpdf

---

## 📌 TODO (예정 기능)

- [x] 무게 데이터 주기적 측정 및 서버 업로드
- [x] 수액 투여 시간 예측
- [x] 실시간 웹 대시보드 구현
- [x] 웹소켓 기반 실시간 통신
- [x] 전력 효율 및 통신 안정성 향상
- [x] 다중 환자 관리 시스템

---

## 🤝 기여하기

1. 이 저장소를 포크합니다
2. 새로운 기능 브랜치를 생성합니다 (`git checkout -b feature/AmazingFeature`)
3. 변경사항을 커밋합니다 (`git commit -m 'Add some AmazingFeature'`)
4. 브랜치에 푸시합니다 (`git push origin feature/AmazingFeature`)
5. Pull Request를 생성합니다

---

## 📝 라이선스

이 프로젝트는 [MIT License](LICENSE)를 따릅니다. 자유롭게 사용, 수정, 배포하셔도 좋습니다.

---

## 📬 연락처

- ✉️ 2020144005@tukorea.ac.kr  (학교)
- ✉️ chrisabc94@gmail.com      (개인)

---

## 🙏 감사의 말

이 프로젝트는 한국공학대학교 종합설계(졸업작품)의 일환으로 개발되었습니다.
지도교수님과 팀원들의 도움에 깊이 감사드립니다.