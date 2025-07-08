import streamlit as st
import json

st.title("⚙️ 설정")

st.warning("🚧 기능 개발 중 🚧")

# session_state에 설정값 초기화
if 'alert_threshold_min' not in st.session_state:
    st.session_state['alert_threshold_min'] = 15

if 'enable_notifications' not in st.session_state:
    st.session_state['enable_notifications'] = True

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

# loadcell_history 사용 시 예시 (필요한 곳에 아래와 같이 사용)
# history = loadcell_history.get(loadcel_id, [])
# tuple_history = [h for h in history if isinstance(h, tuple) and len(h) == 2]
# if tuple_history:
#     timestamps = [h[0] for h in tuple_history]
#     weights = [h[1] for h in tuple_history]
#     ...
