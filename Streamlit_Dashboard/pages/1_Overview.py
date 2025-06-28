import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objs as go

st.set_page_config(layout="wide")

# 1초마다 자동 새로고침
st_autorefresh(interval=1000, key="datarefresh")

# --- UI 표시 ---
st.title("📊 전체 현황 대시보드")

# 메인 페이지에서 이미 초기화된 session_state 데이터 사용
loadcell_data = st.session_state.get('loadcell_data', {})
loadcell_history = st.session_state.get('loadcell_history', {})

if not loadcell_data:
    # 데이터가 없으면 안내 문구 표시
    st.info("수신 대기 중... 아직 데이터가 없습니다.")
    st.write("`streamlit run main.py`를 실행한 터미널에서 `[WebSocket] 연결 성공` 메시지가 보이는지 확인하세요.")
else:
    # 로드셀 ID 순서대로 정렬하여 항상 같은 순서로 표시
    for loadcel_id in sorted(loadcell_data.keys()):
        values = loadcell_data[loadcel_id]
        
        st.write(f"---")
        st.subheader(f"로드셀 #{loadcel_id}")
        col1, col2 = st.columns(2)
        col1.metric(label="현재 무게", value=values['current_weight'])
        col2.metric(label="남은 시간(초)", value=values['remaining_sec'])
        # plotly 그래프 추가
        history = loadcell_history.get(loadcel_id, [])
        if history:
            fig = go.Figure()
            fig.add_trace(go.Scatter(y=history, mode='lines+markers', name='무게'))
            fig.update_layout(title="무게 변화 추이 (최근 30개)", xaxis_title="측정 순서", yaxis_title="무게")
            st.plotly_chart(fig, use_container_width=True)
