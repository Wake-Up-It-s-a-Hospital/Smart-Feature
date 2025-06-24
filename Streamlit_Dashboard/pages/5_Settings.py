import streamlit as st

st.title("⚙️ 설정")

# session_state에 설정값 초기화
if 'alert_threshold_min' not in st.session_state:
    st.session_state['alert_threshold_min'] = 15

if 'enable_notifications' not in st.session_state:
    st.session_state['enable_notifications'] = True


st.header("알림 설정")
st.write("수액 잔량이 설정된 시간 미만으로 남았을 때 알림을 받도록 설정합니다.")

# 슬라이더를 사용하여 임계값 설정
threshold = st.slider(
    "교체 필요 알림 기준 (분)",
    min_value=5,
    max_value=60,
    value=st.session_state.alert_threshold_min,
    step=5
)
st.session_state.alert_threshold_min = threshold
st.info(f"ℹ️ 남은 시간이 **{st.session_state.alert_threshold_min}분** 미만일 때 '교체 필요'로 표시됩니다.")


st.write("---")

st.header("푸시 알림")
st.write("외부 알림 서비스(이메일, SMS 등) 연동을 위한 설정입니다. (미구현)")

# 토글 버튼으로 알림 활성화/비활성화
notifications_enabled = st.toggle(
    "푸시 알림 활성화",
    value=st.session_state.enable_notifications
)
st.session_state.enable_notifications = notifications_enabled

if st.session_state.enable_notifications:
    st.text_input("알림 수신 이메일 주소", "user@example.com")

st.write("---")
if st.button("설정 저장"):
    # 실제로는 이 값들을 파일이나 DB에 저장해야 함
    st.success("설정이 성공적으로 저장되었습니다! (현재는 세션에만 임시 저장됩니다)")
