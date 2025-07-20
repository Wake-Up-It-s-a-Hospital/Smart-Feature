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
from utils.alert_utils import render_alert_sidebar, check_all_alerts
from utils.logo_utils import show_logo

KST = timezone(timedelta(hours=9))

st.set_page_config(layout="wide")

# 1초마다 자동 새로고침
st_autorefresh(interval=1000, key="datarefresh")

show_logo()
# 사이드바 내용 추가
st.sidebar.header("실시간 대시보드")
st.sidebar.write("수액의 현재 무게와")
st.sidebar.write("남은 시간을 확인합니다.")
st.sidebar.markdown("---")

# ====== 사이드바에 알림 리스트 출력 ======
render_alert_sidebar()

# --- UI 표시 ---
st.title("실시간 대시보드")

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
            # === nurse_call 알림 추가 ===
            if data.get("nurse_call", False):
                if 'alert_list' not in st.session_state:
                    st.session_state['alert_list'] = []
                # 중복 방지: 같은 loadcel, nurse_call 알림이 이미 최근에 있으면 추가하지 않음
                recent_nurse_alerts = [a for a in st.session_state['alert_list'][-10:] if a.get('nurse_call') and a.get('loadcel_id') == loadcel]
                if not recent_nurse_alerts:
                    st.session_state['alert_list'].append({
                        "id": 3,
                        "msg": f"🚨 로드셀 {loadcel}에서 간호사 호출이 발생했습니다!",
                        "loadcel_id": loadcel,
                        "nurse_call": True
                    })
            if loadcel:
                try:
                    current_weight = float(data.get("current_weight", 0))
                except:
                    current_weight = 0
                # === 기존 서버에서 remaining_sec 받아오는 부분 주석처리 ===
                # try:
                #     remaining_sec = float(data.get("remaining_sec", -1))
                # except:
                #     remaining_sec = -1
                # === 남은 시간 계산: 현재 무게 기반 ===
                # 1kg = 1000g, 시간당 250ml(=250g) 소모, 남은 시간(초)
                if 'weight_sec_calc' not in st.session_state:
                    st.session_state['weight_sec_calc'] = {}
                prev_sec = st.session_state['weight_sec_calc'].get(loadcel, None)
                est_sec = (current_weight / 250) * 3600 if current_weight > 0 else -1
                if est_sec > 0:
                    est_sec = int((est_sec + 299) // 300) * 300
                if prev_sec is not None and est_sec > prev_sec:
                    est_sec = prev_sec
                st.session_state['weight_sec_calc'][loadcel] = est_sec
                weight_sec = est_sec
                st.session_state.loadcell_data[loadcel] = {
                    "current_weight": current_weight,
                    # "weight_sec": weight_sec  # 서버 기반 남은 시간 저장 주석처리
                }
                if loadcel not in st.session_state.loadcell_history:
                    st.session_state.loadcell_history[loadcel] = []
                st.session_state.loadcell_history[loadcel].append((timestamp, current_weight))
                if len(st.session_state.loadcell_history[loadcel]) > 30:
                    st.session_state.loadcell_history[loadcel] = st.session_state.loadcell_history[loadcel][-30:]
        except Exception as e:
            print(f"메시지 파싱 오류: {msg} | 오류: {e}")

# ====== 알림 리스트 초기화 ======
if "alert_list" not in st.session_state:
    st.session_state.alert_list = []
if "alert_flags" not in st.session_state:
    st.session_state.alert_flags = set()

# ====== 통합 알림 체크 ======
check_all_alerts()

# ====== 로컬 Tare(영점) 기능을 위한 offset 관리 ======
if 'tare_offsets' not in st.session_state:
    st.session_state['tare_offsets'] = {}

# ====== 배터리 칸 표시 함수 ======
def render_battery_bars(battery_level):
    """
    배터리 레벨(0-3)을 받아서 옛날 폴더폰 스타일의 칸으로 표시
    3: 꽉참 (3칸), 2: 2칸, 1: 1칸, 0: 빈 상태 (0칸)
    """
    if battery_level is None:
        return "정보 없음"
    
    # 색상 결정
    if battery_level == 3:
        color = "#4CAF50"  # 초록색 (꽉참)
        status = "양호"
    elif battery_level == 2:
        color = "#8BC34A"  # 연한 초록색
        status = "보통"
    elif battery_level == 1:
        color = "#FF9800"  # 주황색
        status = "부족"
    else:  # battery_level == 0
        color = "#F44336"  # 빨간색
        status = "위험"
    
    # 배터리 칸 생성 (3칸)
    bars_html = ""
    for i in range(3):
        if i < battery_level:
            bars_html += f'<div style="width: 15px; height: 25px; background-color: {color}; border: 1px solid {color}; border-radius: 2px; margin-right: 2px;"></div>'
        else:
            bars_html += '<div style="width: 15px; height: 25px; background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 2px; margin-right: 2px;"></div>'
    
    battery_html = f"""
    <style>
    .battery-container {{
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 0.5em;
    }}
    .battery-bars {{
        display: flex;
        align-items: center;
    }}
    .battery-text {{
        font-size: 14px;
        color: #666;
    }}
    </style>
    <div class="battery-container">
        <div class="battery-bars">
            {bars_html}
        </div>
        <div class="battery-text">Level {battery_level} ({status})</div>
    </div>
    """
    return battery_html

# 로드셀 ID 순서대로 정렬하여 항상 같은 순서로 표시
for loadcel_id in sorted(loadcell_data.keys()):
    if str(loadcel_id) != '1':
        continue
    values = loadcell_data[loadcel_id]
    
    # === 배터리 정보 조회 ===
    try:
        response = table_polestat.query(
            KeyConditionExpression=Key('pole_id').eq(int(loadcel_id)),
            ScanIndexForward=False,  # 최신순 정렬
            Limit=1
        )
        battery_level = None
        if response.get('Items'):
            battery_level = response['Items'][0].get('battery_level', None)
    except Exception as e:
        battery_level = None
    
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
        # === 추가: 영점 시각 기록 및 full_weight 초기화 ===
        st.session_state[f'tare_time_{loadcel_id}'] = time.time()
        st.session_state[f'full_weight_{loadcel_id}'] = None
        st.success("영점 설정 완료! 30초 후 수액팩 무게가 자동으로 기준이 됩니다.")
    tare_offset = st.session_state['tare_offsets'].get(loadcel_id, 0)
    tare_time = st.session_state.get(f'tare_time_{loadcel_id}', None)
    full_weight = st.session_state.get(f'full_weight_{loadcel_id}', None)
    now = time.time()
    if tare_time is not None and full_weight is None:
        if now - tare_time >= 30:
            full_weight_val = values['current_weight'] - tare_offset
            if full_weight_val > 0:
                st.session_state[f'full_weight_{loadcel_id}'] = full_weight_val
                full_weight = full_weight_val
        else:
            st.info(f"수액팩을 걸어주세요! {int(30 - (now - tare_time))}초 후 수액 무게가 기준이 됩니다.")
    # === 표시용 무게 계산 ===
    display_weight = values['current_weight'] - tare_offset
    if display_weight < 0:
        display_weight = 0
    display_weight = round(display_weight, 1)
    # === weight_sec를 매번 계산 ===
    if display_weight > 0:
        weight_sec = (display_weight / 250) * 3600
        weight_sec = int((weight_sec + 299) // 300) * 300
    else:
        weight_sec = -1
    # 데이터가 있는 로드셀만 그래프와 metric 표시
    if values['current_weight'] == 0 and weight_sec == -1:
        st.warning("수액이 연결되지 않았습니다.")
    else:
        col1, col2, col3 = st.columns(3)
        # 무게 인디케이터 (배터리 스타일)
        if full_weight is not None and full_weight > 0:
            percent = max(0, min(display_weight / full_weight, 1))
            filled = int(percent * 4 + 0.9999)  # 4칸, 올림
        else:
            percent = 0
            filled = 0
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
        # 남은 시간 인디케이터 (무게 기반 계산값만 사용)
        if weight_sec < 0:
            remaining_str = "정보 없음"
        else:
            minutes = int((weight_sec + 299) // 300) * 5
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
        
        # === 배터리 표시 추가 ===
        st.write("---")
        col_bat1, col_bat2 = st.columns(2)
        col_bat1.metric("배터리 상태", "")
        col_bat1.markdown(render_battery_bars(battery_level), unsafe_allow_html=True)
        

        
        # plotly 그래프 추가 (history가 1개 이상일 때만)
        history = loadcell_history.get(loadcel_id, [])
        tuple_history = [h for h in history if isinstance(h, tuple) and len(h) == 2]
        if tuple_history and not (values['current_weight'] == 0 and weight_sec == -1):
            timestamps = [h[0] for h in tuple_history]
            weights = [round(max(0, h[1] - tare_offset), 1) for h in tuple_history]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=timestamps, y=weights, mode='lines+markers', name='무게'))
            fig.update_layout(title="무게 변화 추이 (최근 30초, 대시보드 기준)", xaxis_title="시간", yaxis_title="무게")
            st.plotly_chart(fig, use_container_width=True)
