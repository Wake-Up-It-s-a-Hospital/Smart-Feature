import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")

st.title("📊 전체 현황 대시보드")

# main.py에서 생성된 session_state를 가져옴
loadcell_data = st.session_state.get('loadcell_data', {})

if not loadcell_data:
    st.info("현재 활성화된 장비가 없거나 데이터를 수신 대기 중입니다.")
else:
    # 1. 핵심 지표 표시
    total_devices = len(loadcell_data)
    
    # 예시: 남은 시간이 10분(600초) 미만인 장비를 '경고'로 간주
    warning_devices = 0
    for data in loadcell_data.values():
        try:
            if float(data.get('remaining_sec', 9999)) < 600:
                warning_devices += 1
        except (ValueError, TypeError):
            continue

    col1, col2 = st.columns(2)
    col1.metric("총 활성 장비 수", f"{total_devices} 개")
    col2.metric("긴급 교체 필요", f"{warning_devices} 개")

    st.write("---")

    # 2. 데이터 테이블 표시
    st.subheader("실시간 장비 현황")
    
    # Pandas DataFrame으로 변환하여 표시
    df_data = []
    for device_id, data in loadcell_data.items():
        remaining_sec = data.get('remaining_sec', 'N/A')
        status = "정상"
        try:
            if float(remaining_sec) < 600:
                status = "🚨 교체 필요"
            elif float(remaining_sec) < 1800:
                status = "⚠️ 곧 교체"
        except (ValueError, TypeError):
            status = "알 수 없음"
            
        df_data.append({
            "장비 ID": device_id,
            "현재 무게 (g)": data.get('current_weight', 'N/A'),
            "남은 시간 (초)": remaining_sec,
            "상태": status
        })
    
    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True)
