# 환자 추종 스마트 링거 폴대: Smart Feature

![banner](https://img.shields.io/badge/Project-Smart%20IV%20Pole-blue.svg)
![license](https://img.shields.io/badge/License-MIT-green.svg)
![status](https://img.shields.io/badge/Status-In%20Development-yellow.svg)

환자 추종 스마트 링거 폴대의 스마트 기능을 담당하는 레포입니다. 
로드셀 센서를 통해 링거 팩의 무게를 실시간으로 측정하고, 이를 서버로 전송하기 위한 기반을 구축하고 있습니다.

본 레포지토리는 2025년 한국공학대학교 종합설계 (캡스톤디자인) 프로젝트의 일부로서 개발되고 있습니다.

---

## 🛠️ 현재까지 구현된 기능

- ✅ **로드셀 센서 기반 무게 측정**  
  HX711 모듈을 사용해 링거 팩의 무게를 정밀하게 측정합니다.

- ✅ **서버 전송 기능 구현 예정**  
  무게 데이터를 서버(Firebase RTDB)로 업로드하여 보관합니다.

- ✅ **데이터 시각화 및 대시보드 구현 예정**  
  서버로 업로드 된 데이터를 시각화합니다.
  알림 등의 부가기능은 추후 추가될 예정입니다.

---

## 📁 프로젝트 파일 구조

```
loadcell: HX711을 이용하여 ESP32로 로드셀 무게 측정, 입력값 보정과 남은 시간 예측
├── include
├── lib
│   └── HX711
│       ├── HX711.cpp
│       ├── HX711.h
│       └── examples
│           ├── HX711Serial
│           └── HX711SerialBegin
├── src
│   └── main.cpp
└── test
    ├── adaptive_ema.cpp
    └── filtertest.cpp

Dashboard: Firebase RTDB에 업로드 된 센서 값을 불러와서 간단하게 시각화하는 대시보드 (리액트 기반)
└── firebase-iv-dashboard
    ├── eslint.config.js
    ├── index.html
    ├── node_modules
    │   ├── tailwindcss
    │   │   ├── index.css
    │   │   ├── preflight.css
    │   │   ├── theme.css
    │   │   └── utilities.css
    │   └── tslib
    │       ├── tslib.es6.html
    │       ├── tslib.es6.js
    │       ├── tslib.html
    │       └── tslib.js
    ├── src
    │   ├── App.css
    │   ├── App.jsx
    │   ├── components
    │   │   ├── ChartComponent.jsx
    │   │   └── ui
    │   │       └── card.jsx
    │   ├── firebase.js
    │   ├── index.css
    │   └── main.jsx
    ├── tailwind.config.js
    └── vite.config.js
```

---

## 🚀 설치 및 실행 방법

이 레포는 현재 실행 가능한 소프트웨어 프로젝트가 아니며, 마이크로컨트롤러에 직접 업로드되는 펌웨어 코드 중심으로 구성되어 있습니다.

1. 로드셀 모듈(HX711)과 ESP32를 연결합니다.
2. 코드를 PlatformIO를 통해 ESP에 업로드합니다.
3. 시리얼 모니터를 통해 무게 측정 값을 확인할 수 있습니다.

Dashboard는 리액트 기반 프로젝트로, 아래와 같은 과정을 거쳐 실행 가능합니다.

1. Node.js 설치
2. 이 레포지토리 다운 및 Dashboard/firebase-iv-dashboard 폴더에서 cmd 실행
3. npm install (프로젝트에 쓰인 라이브러리 다운로드 및 의존성 파일 다운)
4. npm run dev

1. 이 레포지토리 클론
2. `pip install -r requirements.txt`
3. streamlit_websocket.py 실행
4. dynamodb_to_websocket.py 실행
5. `streamlit run main.py`

---

## 📌 TODO (예정 기능)

- [x] 무게 데이터 주기적 측정 및 서버 업로드
- [x] 수액 투여 시간 예측
- [x] 병원 환경에 맞춘 UI 및 대시보드 연동
- [ ] 전력 효율 및 통신 안정성 향상

---

## 🔓 라이선스

이 프로젝트는 [MIT License](LICENSE)를 따릅니다. 자유롭게 사용, 수정, 배포하셔도 좋습니다.

---

## 📬 연락처

- ✉️ 2020144005@tukorea.ac.kr  (학교)
- ✉️ chrisabc94@gmail.com      (개인)
