import streamlit as st
import json

st.title("⚙️ 설정")

# === 장비별 알림 임계값 설정 ===
st.subheader("장비별 알림 임계값 설정")
loadcell_ids = st.session_state.get('loadcell_data', {}).keys()
if loadcell_ids:
    for loadcel in loadcell_ids:
        key = f'alert_threshold_{loadcel}'
        if key not in st.session_state:
            st.session_state[key] = 15
        st.session_state[key] = st.slider(f"장비 {loadcel} 교체 필요 알림 기준 (분)", 5, 60, st.session_state[key], 5)
else:
    st.info("장비 데이터가 없습니다. (실시간 데이터 수신 필요)")

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

# loadcell_history 사용 시 예시 (필요한 곳에 아래와 같이 사용)
# history = loadcell_history.get(loadcel_id, [])
# tuple_history = [h for h in history if isinstance(h, tuple) and len(h) == 2]
# if tuple_history:
#     timestamps = [h[0] for h in tuple_history]
#     weights = [h[1] for h in tuple_history]
#     ...
