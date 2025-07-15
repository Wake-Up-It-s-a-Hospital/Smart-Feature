import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objs as go
import time
import streamlit.components.v1 as components
import json
import boto3
import os
from datetime import datetime, timezone, timedelta
import threading

KST = timezone(timedelta(hours=9))

st.set_page_config(layout="wide")

# 1초마다 자동 새로고침
st_autorefresh(interval=1000, key="datarefresh")

# 사이드바 내용 추가
st.sidebar.header("Overview")
st.sidebar.write("수액의 현재 무게와")
st.sidebar.write("남은 시간을 확인합니다.")
st.sidebar.markdown("---")

# --- UI 표시 ---
st.title("📊 전체 현황 대시보드")

# 메인 페이지에서 이미 초기화된 session_state 데이터 사용
loadcell_data = st.session_state.get('loadcell_data', {})
loadcell_history = st.session_state.get('loadcell_history', {})

# DynamoDB 연결 (환경변수나 credentials 필요)
dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')  # 리전은 실제 환경에 맞게 수정
POLESTAT_TABLE = 'pole_stat'
table_polestat = dynamodb.Table(POLESTAT_TABLE)

# WebSocket에서 받은 메시지 처리 (main.py와 동일하게)
q = st.session_state.get("queue", None)
if q is not None:
    while not q.empty():
        msg = q.get()
        try:
            data = json.loads(msg)
            loadcel = data.get("loadcel")
            timestamp = data.get("timestamp")
            if loadcel:
                try:
                    current_weight = float(data.get("current_weight", 0))
                except:
                    current_weight = 0
                try:
                    remaining_sec = float(data.get("remaining_sec", -1))
                except:
                    remaining_sec = -1
                st.session_state.loadcell_data[loadcel] = {
                    "current_weight": current_weight,
                    "remaining_sec": remaining_sec
                }
                if loadcel not in st.session_state.loadcell_history:
                    st.session_state.loadcell_history[loadcel] = []
                st.session_state.loadcell_history[loadcel].append((timestamp, current_weight))
                if len(st.session_state.loadcell_history[loadcel]) > 30:
                    st.session_state.loadcell_history[loadcel] = st.session_state.loadcell_history[loadcel][-30:]
        except Exception as e:
            print(f"메시지 파싱 오류: {msg} | 오류: {e}")

# 로드셀 ID 순서대로 정렬하여 항상 같은 순서로 표시
for loadcel_id in sorted(loadcell_data.keys()):
    values = loadcell_data[loadcel_id]
    
    st.write("---")
    st.subheader(f"로드셀 #{loadcel_id}")

    # 원점 설정 버튼 및 피드백
    def send_tare_false(battery_level, is_lost):
        import time
        time.sleep(10)
        timestamp = datetime.now(KST).isoformat()
        table_polestat.put_item(
            Item={
                'pole_id': 1,
                'timestamp': timestamp,
                'battery_level': battery_level,
                'is_lost': is_lost,
                'tare_requested': False
            }
        )

    tare_btn = st.button(f"원점 설정 (Tare)", key=f"tare_{loadcel_id}")
    if tare_btn:
        try:
            # 1. 최신 row 조회
            response = table_polestat.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key('pole_id').eq(1),
                ScanIndexForward=False,  # 내림차순
                Limit=1
            )
            items = response.get('Items', [])
            if items:
                latest = items[0]
                battery_level = latest.get('battery_level', -1)
                is_lost = latest.get('is_lost', False)
            else:
                battery_level = -1
                is_lost = False

            # 2. 새로운 row 추가 (tare_requested=True)
            timestamp = datetime.now(KST).isoformat()
            table_polestat.put_item(
                Item={
                    'pole_id': 1,
                    'timestamp': timestamp,
                    'battery_level': battery_level,
                    'is_lost': is_lost,
                    'tare_requested': True
                }
            )
            st.session_state[f"tare_feedback_{loadcel_id}"] = True

            # 3. 10초 후 tare_requested=False로 자동 전송
            threading.Thread(target=send_tare_false, args=(battery_level, is_lost), daemon=True).start()
        except Exception as e:
            st.error(f"DynamoDB 업데이트 실패: {e}")
    if st.session_state.get(f"tare_feedback_{loadcel_id}", False):
        st.success("원점 설정 요청됨 (DB 업데이트 완료)")

    # 데이터가 있는 로드셀만 그래프와 metric 표시
    if values['current_weight'] == 0 and values['remaining_sec'] == -1:
        st.warning("수액이 연결되지 않았습니다.")
    else:
        col1, col2 = st.columns(2)
        # 무게 인디케이터 (배터리 스타일)
        full_weight = 1000  # 예시: 1000g을 full로 가정
        current = values['current_weight']
        percent = max(0, min(current / full_weight, 1))
        filled = int(percent * 4 + 0.9999)  # 4칸, 올림
        indicator = "".join(["■" if i < filled else "□" for i in range(4)])
        col1.metric(label="현재 무게", value=f"{current}g  {indicator}")
        # 남은 시간 인디케이터
        # DB에서 가져오는 값이 분 단위이므로 초 단위로 변환
        if values['remaining_sec'] < 0:
            remaining_str = "정보 없음"
        else:
            remaining_sec = values['remaining_sec'] * 60  # 분 → 초 변환
            minutes = int((remaining_sec + 299) // 300) * 5
            remaining_str = f"{minutes}분 이하"
        col2.metric(label="남은 시간", value=remaining_str)
        # plotly 그래프 추가 (history가 1개 이상일 때만)
        history = loadcell_history.get(loadcel_id, [])
        # 튜플만 필터링
        tuple_history = [h for h in history if isinstance(h, tuple) and len(h) == 2]
        if tuple_history and not (values['current_weight'] == 0 and values['remaining_sec'] == -1):
            timestamps = [h[0] for h in tuple_history]
            weights = [h[1] for h in tuple_history]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=timestamps, y=weights, mode='lines+markers', name='무게'))
            fig.update_layout(title="무게 변화 추이 (최근 30초)", xaxis_title="시간", yaxis_title="무게")
            st.plotly_chart(fig, use_container_width=True)
