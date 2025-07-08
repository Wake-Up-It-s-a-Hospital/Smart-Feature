import streamlit as st
import pandas as pd
import json

st.set_page_config(layout="wide")
st.title("🩺 IV Pole 상세 정보")

# 사이드바 내용 추가
st.sidebar.header("IV Pole Info")
st.sidebar.write("각 링거 폴대의 다양한")
st.sidebar.write("데이터를 확인합니다.")
st.sidebar.markdown("---")

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
    # 1. 드롭다운으로 장비 선택
    device_ids = sorted(loadcell_data.keys())
    selected_device = st.selectbox("확인할 장비 ID를 선택하세요:", device_ids)

    if selected_device:
        st.write("---")
        st.header(f"장비 #{selected_device} 상세 정보")
        
        device_data = loadcell_data[selected_device]
        
        # 2. 선택된 장비의 현재 상태 표시
        col1, col2, col3 = st.columns(3)
        col1.metric("현재 무게 (g)", device_data.get('current_weight', 'N/A'))
        try:
            remaining_min = round(float(device_data.get('remaining_sec', 0)) / 60)
        except (ValueError, TypeError):
            remaining_min = 'N/A'
        col2.metric("남은 시간 (분)", remaining_min)
        # 배터리(더미)
        col3.metric("배터리 (%)", "85% (Dummy)")

        # 위치(더미)
        st.info("시계 배터리: 78% (Dummy)")

        # 무게 변화 plotly 그래프 (Overview와 동일)
        st.subheader("무게 변화 추이 (최근 30개)")
        loadcell_history = st.session_state.get('loadcell_history', {})
        history = loadcell_history.get(selected_device, [])
        # 튜플만 필터링
        tuple_history = [h for h in history if isinstance(h, tuple) and len(h) == 2]
        if tuple_history:
            import plotly.graph_objs as go
            timestamps = [h[0] for h in tuple_history]
            weights = [h[1] for h in tuple_history]
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
