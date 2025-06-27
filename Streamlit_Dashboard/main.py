import streamlit as st
import threading
import queue
import websocket
import time
import json
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objs as go

# 1초마다 자동 새로고침
st_autorefresh(interval=1000, key="datarefresh")

# --- WebSocket 리스너 (디버깅 로그 추가) ---
def ws_listener(q):
    def on_message(ws, message):
        print(f"[WebSocket] 메시지 수신: {message}")
        q.put(message)

    def on_error(ws, error):
        print(f"[WebSocket] 오류 발생: {error}")

    def on_close(ws, close_status_code, close_msg):
        print(f"[WebSocket] 연결 종료됨: {close_status_code} {close_msg}")

    def on_open(ws):
        print("[WebSocket] 연결 성공")

    ws = websocket.WebSocketApp("ws://localhost:6789",
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close,
                              on_open=on_open)
    ws.run_forever()


# --- Streamlit 앱 메인 로직 ---
# st.session_state를 사용하여 큐, 데이터, 스레드 시작 플래그를 관리합니다.
if "queue" not in st.session_state:
    st.session_state.queue = queue.Queue()

if "loadcell_data" not in st.session_state:
    st.session_state.loadcell_data = {}

if "loadcell_history" not in st.session_state:
    st.session_state.loadcell_history = {}

# 스레드는 단 한 번만 시작되어야 합니다.
if "ws_thread_started" not in st.session_state:
    st.session_state.ws_thread_started = True
    # 세션 상태에 저장된 "진짜" 큐를 스레드에 전달합니다.
    threading.Thread(target=ws_listener, args=(st.session_state.queue,), daemon=True).start()
    print("[Streamlit] WebSocket 리스너 스레드 시작됨")

# 세션 상태에 저장된 큐에서 메시지를 가져옵니다.
q = st.session_state.queue
while not q.empty():
    msg = q.get()
    try:
        data = json.loads(msg)
        loadcel = data.get("loadcel")
        if loadcel:
            # get() 메소드를 사용하여 키가 없는 경우에도 오류가 나지 않게 처리
            st.session_state.loadcell_data[loadcel] = {
                "current_weight": data.get("current_weight", "N/A"),
                "remaining_sec": data.get("remaining_sec", "N/A")
            }
            # 무게 히스토리 저장 (최대 30개)
            if loadcel not in st.session_state.loadcell_history:
                st.session_state.loadcell_history[loadcel] = []
            try:
                weight = float(data.get("current_weight", 0))
            except:
                weight = 0
            st.session_state.loadcell_history[loadcel].append(weight)
            if len(st.session_state.loadcell_history[loadcel]) > 30:
                st.session_state.loadcell_history[loadcel] = st.session_state.loadcell_history[loadcel][-30:]
    except Exception as e:
        st.error(f"메시지 파싱 오류: {msg} | 오류: {e}")


# --- UI 표시 ---
st.title("실시간 로드셀 데이터")

if st.session_state.loadcell_data:
    # 로드셀 ID 순서대로 정렬하여 항상 같은 순서로 표시
    for loadcel_id in sorted(st.session_state.loadcell_data.keys()):
        values = st.session_state.loadcell_data[loadcel_id]
        
        st.write(f"---")
        st.subheader(f"로드셀 #{loadcel_id}")
        col1, col2 = st.columns(2)
        col1.metric(label="현재 무게", value=values['current_weight'])
        col2.metric(label="남은 시간(초)", value=values['remaining_sec'])
        # plotly 그래프 추가
        history = st.session_state.loadcell_history.get(loadcel_id, [])
        if history:
            fig = go.Figure()
            fig.add_trace(go.Scatter(y=history, mode='lines+markers', name='무게'))
            fig.update_layout(title="무게 변화 추이 (최근 30개)", xaxis_title="측정 순서", yaxis_title="무게")
            st.plotly_chart(fig, use_container_width=True)
else:
    # 데이터가 없으면 안내 문구 표시
    st.info("수신 대기 중... 아직 데이터가 없습니다.")
    st.write("`streamlit run main.py`를 실행한 터미널에서 `[WebSocket] 연결 성공` 메시지가 보이는지 확인하세요.")