import streamlit as st
import threading
import queue
import websocket
import time

q = queue.Queue()

def ws_listener(q):
    def on_message(ws, message):
        q.put(message)
    ws = websocket.WebSocketApp("ws://localhost:6789", on_message=on_message)
    ws.run_forever()

if 'ws_thread_started' not in st.session_state:
    st.session_state['ws_thread_started'] = True
    threading.Thread(target=ws_listener, args=(q,), daemon=True).start()

st.title("실시간 RTDB 데이터 수신")
if 'latest_data' not in st.session_state:
    st.session_state['latest_data'] = "아직 데이터 없음"

# 데이터 갱신
if not q.empty():
    st.session_state['latest_data'] = q.get()

st.write("최신 데이터:", st.session_state['latest_data'])
st.button("새로고침")  # 수동 새로고침용