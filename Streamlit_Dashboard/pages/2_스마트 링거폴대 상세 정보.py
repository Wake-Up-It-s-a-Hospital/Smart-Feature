import streamlit as st
import pandas as pd
import json
# === 추가: DynamoDB 및 Key 임포트 ===
import boto3
from boto3.dynamodb.conditions import Key
from utils.alert_utils import render_alert_sidebar, check_all_alerts
from utils.logo_utils import show_logo
from utils.auth_utils import require_auth, render_userbox, get_current_user
from utils.assign_utils import require_device_access, get_user_assignments

st.set_page_config(layout="wide")
st.title("스마트 링거폴대 상세 정보")
user = get_current_user()
if not user:
    try:
        st.switch_page("환자_추종_스마트_링거폴대_소개.py")
    except Exception:
        st.stop()
render_userbox()

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

show_logo()
# 사이드바 내용 추가
st.sidebar.header("스마트 링거폴대 상세 정보")
st.sidebar.write("각 링거 폴대의 다양한")
st.sidebar.write("데이터를 확인합니다.")
st.sidebar.markdown("---")

# ====== 알림 리스트 초기화 ======
if "alert_list" not in st.session_state:
    st.session_state.alert_list = []
if "alert_flags" not in st.session_state:
    st.session_state.alert_flags = set()

# ====== 통합 알림 체크 ======
check_all_alerts()

# ====== 사이드바에 알림 리스트 출력 ======
render_alert_sidebar()

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
                # === 남은 시간 계산: 현재 무게 기반 ===
                if current_weight > 0:
                    remaining_sec = (current_weight / 250) * 3600
                else:
                    remaining_sec = -1
                # 배터리 레벨 처리
                try:
                    battery_level = int(data.get("battery_level", -1)) if data.get("battery_level") is not None else None
                except:
                    battery_level = None
                st.session_state.loadcell_data[loadcel] = {
                    "current_weight": current_weight,
                    "remaining_sec": remaining_sec,
                    "battery_level": battery_level  # 배터리 레벨 추가
                }
                if loadcel not in st.session_state.loadcell_history:
                    st.session_state.loadcell_history[loadcel] = []
                st.session_state.loadcell_history[loadcel].append((timestamp, current_weight))
                if len(st.session_state.loadcell_history[loadcel]) > 30:
                    st.session_state.loadcell_history[loadcel] = st.session_state.loadcell_history[loadcel][-30:]
        except Exception as e:
            print(f"메시지 파싱 오류: {msg} | 오류: {e}")

loadcell_data = st.session_state.get('loadcell_data', {})

# 추가 데이터 로드 및 통합
try:
    from utils.dummy_data_utils import get_dummy_data_for_dashboard, is_dummy_data_available
    
    if is_dummy_data_available():
        additional_data = get_dummy_data_for_dashboard()
        # 추가 데이터를 session_state에 병합
        for pole_id, pole_data in additional_data.items():
            if pole_id not in loadcell_data:
                loadcell_data[pole_id] = pole_data
            else:
                # 기존 데이터와 병합
                loadcell_data[pole_id].update(pole_data)
        
        # 성공 메시지는 표시하지 않음 (사용자에게는 투명하게)
    else:
        pass
except ImportError:
    # 유틸리티가 없는 경우 조용히 처리
    pass
except Exception as e:
    # 오류가 발생해도 사용자에게는 표시하지 않음
    pass

if not loadcell_data:
    st.warning("데이터가 없습니다. 메인 페이지에서 데이터 수신을 확인하세요.")
else:
    # ====== 로컬 Tare(영점) 기능을 위한 offset 관리 ======
    # 1. 드롭다운으로 장비 선택
    device_ids = sorted(loadcell_data.keys())
    user = get_current_user()
    if user and user.get('role') == 'clinician':
        assigned = set(get_user_assignments(user.get('username', '')))
        device_ids = [d for d in device_ids if str(d) in assigned]
    selected_device = st.selectbox("확인할 장비 ID를 선택하세요:", device_ids)
    if selected_device:
        require_device_access(selected_device)

    # === 추가: DynamoDB 연결 ===
    dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')
    POLESTAT_TABLE = 'pole_stat'
    table_polestat = dynamodb.Table(POLESTAT_TABLE)

    if selected_device:
        st.write("---")
        st.header(f"{selected_device}번 폴대의 상세 정보")
        device_data = loadcell_data[selected_device]
        # === 배터리 정보 조회 (웹소켓에서 받은 데이터 우선 사용) ===
        battery_level = device_data.get('battery_level', None)
        if battery_level is None:
            # 웹소켓에서 받지 못한 경우 DynamoDB에서 조회
            try:
                response = table_polestat.query(
                    KeyConditionExpression=Key('pole_id').eq(int(selected_device)),
                    ScanIndexForward=False,  # 최신순 정렬
                    Limit=1
                )
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
        # === 남은 시간: 무게 기반 단순 계산 ===
        if display_weight > 0:
            remaining_sec = (display_weight / 250) * 3600
        else:
            remaining_sec = -1
        if remaining_sec < 0:
            remaining_str = '정보 없음'
        else:
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
        # === 배터리 칸 표시 ===
        col4.metric("배터리 상태", "")
        col4.markdown(render_battery_bars(battery_level), unsafe_allow_html=True)
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
