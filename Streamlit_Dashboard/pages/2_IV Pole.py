import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")
st.title("🩺 IV Pole 상세 정보")

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
        col1, col2 = st.columns(2)
        col1.metric("현재 무게 (g)", device_data.get('current_weight', 'N/A'))
        
        try:
            remaining_min = round(float(device_data.get('remaining_sec', 0)) / 60)
        except (ValueError, TypeError):
            remaining_min = 'N/A'
        col2.metric("남은 시간 (분)", remaining_min)

        # 3. (향후 기능) 과거 데이터 차트
        st.subheader("시간별 무게 변화")
        st.info("ℹ️ 향후 이 영역에 시간대별 수액 무게 변화 그래프가 표시될 예정입니다. (과거 데이터 저장 기능 필요)")
        st.line_chart(pd.DataFrame(
            {'시간': range(10), '무게': [100, 95, 90, 80, 60, 40, 20, 10, 5, 0]}
        ).set_index('시간')) # 예시 데이터
