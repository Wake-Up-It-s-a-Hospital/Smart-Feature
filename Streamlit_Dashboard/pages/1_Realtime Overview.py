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
LOADCELL_TABLE = 'loadcell'
table_loadcell = dynamodb.Table(LOADCELL_TABLE)
TARE_TABLE = 'tare'
table_tare = dynamodb.Table(TARE_TABLE)

def set_tare_required(loadcel_id, value=True):
    timestamp = datetime.now(KST).isoformat()
    table_tare.put_item(
        Item={
            'loadcel': str(loadcel_id),
            'tare_required': value,
            'updated_at': timestamp
        }
    )

def reset_tare_required(loadcel_id, delay=10):
    import time
    time.sleep(delay)
    set_tare_required(loadcel_id, False)
    st.session_state[f"tare_in_progress_{loadcel_id}"] = False

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

# ====== 로컬 Tare(영점) 기능을 위한 offset 관리 ======
if 'tare_offsets' not in st.session_state:
    st.session_state['tare_offsets'] = {}

# 로드셀 ID 순서대로 정렬하여 항상 같은 순서로 표시
for loadcel_id in sorted(loadcell_data.keys()):
    if str(loadcel_id) != '1':
        continue
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

    # === 대시보드에서만 동작하는 Tare 버튼 ===
    tare_btn = st.button(f"영점 설정", key=f"tare_{loadcel_id}")
    if tare_btn:
        # 현재 값을 offset으로 저장
        st.session_state['tare_offsets'][loadcel_id] = values['current_weight']
        # 그래프 히스토리도 리셋
        st.session_state.loadcell_history[loadcel_id] = []
        st.success("영점 설정 완료!")
    tare_offset = st.session_state['tare_offsets'].get(loadcel_id, 0)

    # === 표시용 무게 계산 ===
    display_weight = values['current_weight'] - tare_offset
    if display_weight < 0:
        display_weight = 0
    display_weight = round(display_weight, 1)

    # 데이터가 있는 로드셀만 그래프와 metric 표시
    if values['current_weight'] == 0 and values['remaining_sec'] == -1:
        st.warning("수액이 연결되지 않았습니다.")
    else:
        col1, col2, col3 = st.columns(3)
        # 무게 인디케이터 (배터리 스타일)
        full_weight = 1000  # 예시: 1000g을 full로 가정
        percent = max(0, min(display_weight / full_weight, 1))
        filled = int(percent * 4 + 0.9999)  # 4칸, 올림
        indicator_html = """
        <style>
        .indicator-bar {
            display: flex;
            justify-content: center;
            gap: 14px;
            margin-top: 0.7em;
        }
        .indicator-box {
            width: 32px;
            height: 32px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(30,40,80,0.10);
            display: inline-block;
            transition: background 0.3s, box-shadow 0.3s;
            border: 2px solid #b0b0b0;
        }
        .indicator-box.filled {
            background: linear-gradient(135deg, #1976d2 60%, #42a5f5 100%);
            border-color: #1976d2;
            box-shadow: 0 4px 16px rgba(25,118,210,0.18);
        }
        .indicator-box.empty {
            background: #f3f6fa;
            border-color: #e0e0e0;
        }
        </style>
        <div class='indicator-bar'>
        """
        for i in range(4):
            if i < filled:
                indicator_html += "<div class='indicator-box filled'></div>"
            else:
                indicator_html += "<div class='indicator-box empty'></div>"
        indicator_html += "</div>"
        col1.metric(label="현재 무게", value=f"{display_weight}g")
        # 남은 시간 인디케이터
        if values['remaining_sec'] < 0:
            remaining_str = "정보 없음"
        else:
            remaining_sec = values['remaining_sec'] * 60  # 분 → 초 변환
            minutes = int((remaining_sec + 299) // 300) * 5
            if minutes < 60:
                remaining_str = f"{minutes}분 이하"
            else:
                hours = minutes // 60
                mins = minutes % 60
                if mins == 0:
                    remaining_str = f"{hours}시간 이하"
                else:
                    remaining_str = f"{hours}시간 {mins}분 이하"
        col2.metric(label="남은 시간", value=remaining_str)
        col3.metric(label="수액 잔량", value="")
        col3.markdown(indicator_html, unsafe_allow_html=True)
        # plotly 그래프 추가 (history가 1개 이상일 때만)
        history = loadcell_history.get(loadcel_id, [])
        tuple_history = [h for h in history if isinstance(h, tuple) and len(h) == 2]
        if tuple_history and not (values['current_weight'] == 0 and values['remaining_sec'] == -1):
            timestamps = [h[0] for h in tuple_history]
            weights = [round(max(0, h[1] - tare_offset), 1) for h in tuple_history]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=timestamps, y=weights, mode='lines+markers', name='무게'))
            fig.update_layout(title="무게 변화 추이 (최근 30초, 대시보드 기준)", xaxis_title="시간", yaxis_title="무게")
            st.plotly_chart(fig, use_container_width=True)
