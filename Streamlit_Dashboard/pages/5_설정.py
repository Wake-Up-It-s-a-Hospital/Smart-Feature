import streamlit as st
import json
from utils.alert_utils import render_alert_sidebar

st.title("설정")

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

# === 알림 임계값 설정 ===
st.subheader("알림 임계값 설정")
if 'alert_almost_weight' not in st.session_state:
    st.session_state['alert_almost_weight'] = 300
if 'alert_done_weight' not in st.session_state:
    st.session_state['alert_done_weight'] = 150
st.session_state['alert_almost_weight'] = st.slider("거의 다 됨 알림 기준 (g)", 100, 500, st.session_state['alert_almost_weight'], 10)
st.session_state['alert_done_weight'] = st.slider("투여 완료 알림 기준 (g)", 100, 500, st.session_state['alert_done_weight'], 10)

# === 알림 방식 설정 ===
st.subheader("알림 방식 설정")
col1, col2 = st.columns([1, 1])
with col1:
    email_enabled = st.checkbox("이메일 알림", value=True)
    st.session_state['email_enabled'] = email_enabled
    if email_enabled:
        st.text_input("알림 수신 이메일 주소", "user@example.com")
with col2:
    sms_enabled = st.checkbox("SMS 알림", value=False)
    st.session_state['sms_enabled'] = sms_enabled
    if sms_enabled:
        st.text_input("알림 수신 휴대폰 번호", "010-0000-0000")

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

# loadcell_history 사용 시 예시 (필요한 곳에 아래와 같이 사용)
# history = loadcell_history.get(loadcel_id, [])
# tuple_history = [h for h in history if isinstance(h, tuple) and len(h) == 2]
# if tuple_history:
#     timestamps = [h[0] for h in tuple_history]
#     weights = [h[1] for h in tuple_history]
#     ...
