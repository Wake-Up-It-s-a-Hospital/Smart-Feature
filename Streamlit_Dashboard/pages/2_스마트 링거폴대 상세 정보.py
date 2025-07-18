import streamlit as st
import pandas as pd
import json
# === 추가: DynamoDB 및 Key 임포트 ===
import boto3
from boto3.dynamodb.conditions import Key

st.set_page_config(layout="wide")
st.title("스마트 링거폴대 상세 정보")

# 사이드바 내용 추가
st.sidebar.header("스마트 링거폴대 상세 정보")
st.sidebar.write("각 링거 폴대의 다양한")
st.sidebar.write("데이터를 확인합니다.")
st.sidebar.markdown("---")

# ====== 사이드바에 알림 리스트 출력 ======
st.sidebar.markdown("### 📋 알림")
if st.session_state.get('alert_list'):
    for alert in st.session_state['alert_list']:
        if alert["id"] == 1:
            st.sidebar.success(alert["msg"])
        elif alert["id"] == 2:
            st.sidebar.warning(alert["msg"])
        elif alert["id"] == 3:
            st.sidebar.error(alert["msg"])
        elif alert["id"] == 4:
            st.sidebar.error(alert["msg"])
        else:
            st.sidebar.info(alert["msg"])
else:
    st.sidebar.info("새로운 알림이 없습니다.")

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

loadcell_data = st.session_state.get('loadcell_data', {})

if not loadcell_data:
    st.warning("데이터가 없습니다. 메인 페이지에서 데이터 수신을 확인하세요.")
else:
    # ====== 로컬 Tare(영점) 기능을 위한 offset 관리 ======
    # 1. 드롭다운으로 장비 선택
    device_ids = sorted(loadcell_data.keys())
    selected_device = st.selectbox("확인할 장비 ID를 선택하세요:", device_ids)

    # === 추가: DynamoDB 연결 ===
    dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')
    POLESTAT_TABLE = 'pole_stat'
    table_polestat = dynamodb.Table(POLESTAT_TABLE)

    if selected_device:
        st.write("---")
        st.header(f"{selected_device}번 폴대의 상세 정보")
        device_data = loadcell_data[selected_device]
        # === 배터리 정보 조회 ===
        # 최신 battery_level을 가져오기 (pole_id == selected_device)
        try:
            response = table_polestat.query(
                KeyConditionExpression=Key('pole_id').eq(int(selected_device)),
                ScanIndexForward=False,  # 최신순 정렬
                Limit=1
            )
            battery_level = None
            if response.get('Items'):
                battery_level = response['Items'][0].get('battery_level', None)
        except Exception as e:
            battery_level = None
        # === 표시용 무게 계산 ===
        display_weight = device_data.get('current_weight', 0)
        display_weight = max(0, round(display_weight, 1))
        # === 4열 레이아웃 ===
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("현재 무게 (g)", f"{display_weight}g")
        try:
            remaining_sec = float(device_data.get('remaining_sec', 0)) * 60
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
        except (ValueError, TypeError):
            remaining_str = '정보 없음'
        col2.metric("남은 시간", remaining_str)
        # 인디케이터
        full_weight = 1000
        percent = max(0, min(display_weight / full_weight, 1))
        filled = int(percent * 4 + 0.9999)
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
        col3.metric(label="수액 잔량", value="")
        col3.markdown(indicator_html, unsafe_allow_html=True)
        # === 배터리 metric ===
        if battery_level is not None:
            col4.metric("배터리 (%)", f"{battery_level}%")
        else:
            col4.metric("배터리 (%)", "정보 없음")
        # 무게 변화 plotly 그래프 (Overview와 동일)
        st.subheader("무게 변화 추이 (최근 30개)")
        loadcell_history = st.session_state.get('loadcell_history', {})
        history = loadcell_history.get(selected_device, [])
        tuple_history = [h for h in history if isinstance(h, tuple) and len(h) == 2]
        if tuple_history:
            import plotly.graph_objs as go
            timestamps = [h[0] for h in tuple_history]
            weights = [round(max(0, h[1]), 1) for h in tuple_history]
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=timestamps, y=weights, mode='lines+markers', name='무게'))
            fig.update_layout(title="무게 변화 추이 (최근 30개)", xaxis_title="시간", yaxis_title="무게")
            st.plotly_chart(fig, use_container_width=True)
        # 3. (향후 기능) 과거 데이터 차트
        st.subheader("시간별 무게 변화")
        if tuple_history:
            st.line_chart(pd.DataFrame({'시간': timestamps, '무게': weights}).set_index('시간'))
        else:
            st.info("ℹ️ 데이터가 없습니다.")
