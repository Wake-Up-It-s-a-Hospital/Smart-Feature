import streamlit as st
import json
from utils.alert_utils import render_alert_sidebar
from utils.logo_utils import show_logo

st.title("설정")

show_logo()
# 사이드바 내용 추가
st.sidebar.header("설정")
st.sidebar.write("다양한 설정값들을")
st.sidebar.write("원하는대로 바꿀 수 있습니다.")
st.sidebar.markdown("---")

# ====== 사이드바에 알림 리스트 출력 ======
st.sidebar.markdown("### 📋 알림")
if st.session_state.get('alert_list'):
    if 'alert_remove_idx' not in st.session_state:
        st.session_state['alert_remove_idx'] = None
    for idx, alert in enumerate(st.session_state['alert_list']):
        col1, col2 = st.sidebar.columns([8, 1])
        with col1:
            if alert["id"] == 1:
                st.success(alert["msg"])
            elif alert["id"] == 2:
                st.warning(alert["msg"])
            elif alert["id"] == 3:
                st.error(alert["msg"])
            elif alert["id"] == 4:
                st.error(alert["msg"])
            else:
                st.info(alert["msg"])
        with col2:
            if st.button("✖", key=f"alert_x_{idx}"):
                st.session_state['alert_remove_idx'] = idx
    if st.session_state['alert_remove_idx'] is not None:
        del st.session_state['alert_list'][st.session_state['alert_remove_idx']]
        st.session_state['alert_remove_idx'] = None
else:
    st.sidebar.info("새로운 알림이 없습니다.")

# === 알림 카테고리별 표시 여부 설정 ===
st.subheader("알림 카테고리별 표시 설정")
if 'alert_enabled_almost' not in st.session_state:
    st.session_state['alert_enabled_almost'] = True
if 'alert_enabled_done' not in st.session_state:
    st.session_state['alert_enabled_done'] = True
if 'alert_enabled_nursecall' not in st.session_state:
    st.session_state['alert_enabled_nursecall'] = True
col1, col2, col3 = st.columns(3)
with col1:
    st.session_state['alert_enabled_almost'] = st.checkbox("거의 다 됨 알림", value=st.session_state['alert_enabled_almost'])
with col2:
    st.session_state['alert_enabled_done'] = st.checkbox("투여 완료 알림", value=st.session_state['alert_enabled_done'])
with col3:
    st.session_state['alert_enabled_nursecall'] = st.checkbox("너스콜 알림", value=st.session_state['alert_enabled_nursecall'])

# === 알림 임계값 설정 (비율 기반) ===
st.subheader("알림 임계값 설정")
if st.session_state['alert_enabled_almost']:
    if 'alert_almost_ratio' not in st.session_state:
        st.session_state['alert_almost_ratio'] = 30
    st.session_state['alert_almost_ratio'] = st.slider("거의 다 됨 알림 기준 (%)", 10, 50, st.session_state['alert_almost_ratio'], 5)
    st.info(f"꽉 찬 수액팩 무게의 {st.session_state['alert_almost_ratio']}% 이하일 때 알림이 발생합니다.")
if st.session_state['alert_enabled_done']:
    if 'alert_done_ratio' not in st.session_state:
        st.session_state['alert_done_ratio'] = 10
    st.session_state['alert_done_ratio'] = st.slider("투여 완료 알림 기준 (%)", 5, 20, st.session_state['alert_done_ratio'], 1)
    st.info(f"꽉 찬 수액팩 무게의 {st.session_state['alert_done_ratio']}% 이하일 때 알림이 발생합니다.")

# === 기타 시스템 정보/버전 ===
st.markdown("---")
st.subheader("시스템 정보")
st.markdown("- 버전: v1.5.7")
st.markdown("- 최근 업데이트: 2025-07-19")