import streamlit as st
import json

st.title("⚙️ 설정")

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

# === 장비별 알림 임계값 설정 ===
st.subheader("장비별 알림 임계값 설정")
loadcell_ids = st.session_state.get('loadcell_data', {}).keys()
if loadcell_ids:
    for loadcel in loadcell_ids:
        key_almost = f'alert_almost_weight_{loadcel}'
        key_done = f'alert_done_weight_{loadcel}'
        if key_almost not in st.session_state:
            st.session_state[key_almost] = 300
        if key_done not in st.session_state:
            st.session_state[key_done] = 150
        st.session_state[key_almost] = st.slider(f"장비 {loadcel} 거의 다 됨 알림 기준 (g)", 100, 500, st.session_state[key_almost], 10)
        st.session_state[key_done] = st.slider(f"장비 {loadcel} 투여 완료 알림 기준 (g)", 100, 500, st.session_state[key_done], 10)
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
