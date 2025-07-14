import streamlit as st
import threading
import queue
import websocket
import time
import json
from streamlit_autorefresh import st_autorefresh
import streamlit_js_eval

# 페이지 설정
st.set_page_config(
    page_title="Smart IV Pole Dashboard",
    page_icon="🩺",
    layout="wide"
)

# 1초마다 자동 새로고침
st_autorefresh(interval=1000, key="main_refresh")

# --- WebSocket 초기화 (백그라운드에서 실행) ---
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

# WebSocket 초기화 (세션 상태에 저장)
if "queue" not in st.session_state:
    st.session_state.queue = queue.Queue()

if "loadcell_data" not in st.session_state:
    st.session_state.loadcell_data = {}

if "loadcell_history" not in st.session_state:
    st.session_state.loadcell_history = {}

# 스레드는 단 한 번만 시작되어야 합니다.
if "ws_thread_started" not in st.session_state:
    st.session_state.ws_thread_started = True
    # 백그라운드에서 WebSocket 리스너 시작
    threading.Thread(target=ws_listener, args=(st.session_state.queue,), daemon=True).start()
    print("[Main] WebSocket 리스너 스레드 시작됨")

# 백그라운드에서 메시지 처리 (데이터는 표시하지 않음)
q = st.session_state.queue
while not q.empty():
    msg = q.get()
    try:
        data = json.loads(msg)
        loadcel = data.get("loadcel")
        if loadcel:
            # float 캐스팅 시도
            try:
                current_weight = float(data.get("current_weight", 0))
            except:
                current_weight = 0
            try:
                remaining_sec = float(data.get("remaining_sec", -1))
            except:
                remaining_sec = -1
            # 데이터를 세션 상태에 저장 (다른 페이지에서 사용)
            st.session_state.loadcell_data[loadcel] = {
                "current_weight": current_weight,
                "remaining_sec": remaining_sec
            }
            # 디버그용 출력
            print(f"[로드셀 데이터] id: {loadcel}, 무게: {current_weight}, 남은 시간: {remaining_sec}")
            # 무게 히스토리 저장 (최대 30개)
            if loadcel not in st.session_state.loadcell_history:
                st.session_state.loadcell_history[loadcel] = []
            st.session_state.loadcell_history[loadcel].append(current_weight)
            if len(st.session_state.loadcell_history[loadcel]) > 30:
                st.session_state.loadcell_history[loadcel] = st.session_state.loadcell_history[loadcel][-30:]
    except Exception as e:
        print(f"메시지 파싱 오류: {msg} | 오류: {e}")

# 사이드바 내용 추가
st.sidebar.header("Wake Up, It's a Hospital")
st.sidebar.write("팀장: 김대연")
st.sidebar.write("조원: 김윤성, 최황은, 최훈석")
st.sidebar.markdown("---")

# ====== 전역 알림 함수 및 알림 아이콘 함수 추가 ======
def global_alert(message, bg_color="#ffcc00", text_color="#000"):
    st.markdown(
        f"""
        <div style='position:fixed; top:0; left:0; right:0; z-index:9999; background-color:{bg_color}; color:{text_color}; padding:10px 20px; font-weight:bold; text-align:center;'>
            {message}
        </div>
        <div style='margin-top:50px'></div>
        """,
        unsafe_allow_html=True
    )

# ====== 알림창 열림 상태 관리 (클릭 토글) ======
if "noti_open" not in st.session_state:
    st.session_state.noti_open = False

def toggle_noti():
    st.session_state.noti_open = not st.session_state.noti_open

# ====== 알림 리스트 및 중복 방지 플래그 관리 (autorefresh에도 유지) ======
if "alert_list" not in st.session_state:
    st.session_state.alert_list = []
if "alert_flags" not in st.session_state:
    st.session_state.alert_flags = set()

def add_alert(pole, bottle, type_, extra=None):
    key = f"{pole}-{bottle}-{type_}"
    if key in st.session_state.alert_flags:
        return
    st.session_state.alert_flags.add(key)
    msg = f"{pole}번 폴대 {bottle}번 링거 {type_}"
    if extra:
        msg += f" ({extra})"
    st.session_state.alert_list.append({
        "pole": pole,
        "bottle": bottle,
        "type": type_,
        "msg": msg
    })

# ====== 알림 조건 체크 및 이벤트 트리거 ======
# 예시 임계값 (실제 값에 맞게 조정)
ALMOST_DONE_SEC = 300  # 5분 이하
ALMOST_DONE_WEIGHT = 50  # 50g 이하
DONE_SEC = 30  # 30초 이하
DONE_WEIGHT = 5  # 5g 이하

# loadcell_data 예시 구조: {loadcel: {"current_weight": ..., "remaining_sec": ..., "nurse_call": ...}}
for loadcel, data in st.session_state.loadcell_data.items():
    pole = loadcel  # 폴대 번호 (loadcel이 곧 폴대 번호라고 가정)
    bottle = 1      # 링거 번호 (예시, 실제 데이터에 맞게 수정)
    # 투여 거의 완료
    if (0 < data.get("remaining_sec", 99999) <= ALMOST_DONE_SEC) or (0 < data.get("current_weight", 99999) <= ALMOST_DONE_WEIGHT):
        add_alert(pole, bottle, "투여 거의 완료", f"남은 시간: {data.get('remaining_sec', '-'):.0f}s, 무게: {data.get('current_weight', '-'):.1f}g")
    # 투여 완료
    if (0 < data.get("remaining_sec", 99999) <= DONE_SEC) or (0 < data.get("current_weight", 99999) <= DONE_WEIGHT):
        add_alert(pole, bottle, "투여 완료", f"남은 시간: {data.get('remaining_sec', '-'):.0f}s, 무게: {data.get('current_weight', '-'):.1f}g")
    # 너스콜
    if data.get("nurse_call", False):
        add_alert(pole, bottle, "너스콜 발생")

# # ====== 알림 리스트 출력 ======
# st.markdown("### 📋 알림 리스트")
# for alert in st.session_state.alert_list:
#     st.info(alert["msg"])

# ====== notification_icon 함수 수정 (Streamlit 버튼으로 토글) ======
def notification_icon():
    alert_count = len(st.session_state.get('alert_list', []))
    badge_html = f'<span style="position:absolute;bottom:2px;right:2px;background:#ff4444;color:white;border-radius:50%;width:14px;height:14px;display:flex;align-items:center;justify-content:center;font-size:0.25em;font-weight:bold;border:1.5px solid white;box-shadow:0 1px 4px rgba(0,0,0,0.12);line-height:1;">{"9+" if alert_count >= 9 else alert_count}</span>' if alert_count > 0 else ''
    st.markdown(
        f"""
        <div style='position:fixed;top:60px;right:30px;z-index:10000;'>
            <button style='position:relative;width:36px;height:36px;border:none;background:none;cursor:pointer;padding:0;' id='noti-bell-btn'>
                <span style='font-size:2.1em;color:#ffb300;'><i class="fa fa-bell"></i></span>
                {badge_html}
            </button>
        </div>
        <script>
        const btn = window.parent.document.getElementById('noti-bell-btn') || document.getElementById('noti-bell-btn');
        if(btn){{btn.onclick = function(){{window.parent.postMessage({{type:'noti_bell_click'}},'*');}}}}
        </script>
        """,
        unsafe_allow_html=True
    )
    # 버튼 클릭 시 session_state.noti_open 토글
    noti_clicked = st.button(" ", key="noti_bell_btn_fake", help="알림 보기", args=())
    if noti_clicked:
        st.session_state.noti_open = not st.session_state.noti_open
    # 알림 드롭다운 표시
    if st.session_state.noti_open:
        alert_html = ""
        if st.session_state.get('alert_list'):
            alert_html += "<ul style='padding-left: 18px; margin: 0;'>"
            for alert in st.session_state['alert_list']:
                alert_html += f"<li style='margin-bottom: 6px; font-size: 0.98em;'>{alert['msg']}</li>"
            alert_html += "</ul>"
        else:
            alert_html = "새로운 알림이 없습니다."
        st.markdown(
            f"""
            <div style='position:fixed; top:98px; right:30px; z-index:10001; background:white; color:#222; border-radius:8px; box-shadow:0 2px 16px rgba(0,0,0,0.18); min-width:220px; padding:12px 16px; max-width:350px; word-break:break-all; max-height:180px; overflow-y:auto;'>
                <b>알림</b><br>
                {alert_html}
            </div>
            """,
            unsafe_allow_html=True
        )
if "global_alert_message" not in st.session_state:
    st.session_state.global_alert_message = ""
# ====== 실제 알림 표시 ======
global_alert(st.session_state.global_alert_message, bg_color="#ff6666", text_color="#fff")
notification_icon()

# --- 1. 히어로 섹션 ---
with st.container():
    st.markdown("""
    <style>
    @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css");
    @import url("https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css");

    * {
        font-family: Pretendard;
        padding: 0;
        margin: 0;
    }

    .section {
        width: 100%;
        height: 100vh;
        position: relative;
        display: flex;
        justify-content: center;
        align-items: center;
        text-align: center;
    }

    .section1 {
        background: linear-gradient(rgba(0, 0, 0, 0.8), rgba(0, 0, 0, 0.8)),
                    url('https://i.imgur.com/wVwCjnr.jpeg') no-repeat;
        background-attachment: fixed;
        background-size: cover;
        background-position: center;
    }

    .section2 {
        background: linear-gradient(rgba(0, 0, 0, 0.8), rgba(0, 0, 0, 0.8)),
                    url('https://i.imgur.com/cW4y4s3.jpeg') no-repeat;
        background-attachment: fixed;
        background-size: cover;
        background-position: center;
    }

    .section3 {
        background: linear-gradient(rgba(0, 0, 0, 0.8), rgba(0, 0, 0, 0.8)),
                    url('https://i.imgur.com/iUenTpM.jpeg') no-repeat;
        background-attachment: fixed;
        background-size: cover;
        background-position: center;
    }

    .section4 {
        background: linear-gradient(rgba(0, 0, 0, 0.8), rgba(0, 0, 0, 0.8)),
                    url('https://i.imgur.com/c5tnILg.jpeg') no-repeat;
        background-attachment: fixed;
        background-size: cover;
        background-position: center;
    }

    .section5 {
        background: linear-gradient(rgba(0, 0, 0, 0.8), rgba(0, 0, 0, 0.8)),
                    url('https://i.imgur.com/OHGBO4C.jpeg') no-repeat;
        background-attachment: fixed;
        background-size: cover;
        background-position: center;
    }

    .section6 {
        background: linear-gradient(rgba(0, 0, 0, 0.8), rgba(0, 0, 0, 0.8)),
                    url('https://i.imgur.com/bcps4wK.jpeg') no-repeat;
        background-attachment: fixed;
        background-size: cover;
        background-position: center;
    }

    .section-content {
        color: white;
        padding: 3rem 4rem;
        background: rgba(30, 57, 30, 0.75);
        border-radius: 15px;
        max-width: 1000px;
        position: relative;
        z-index: 1;
        border: 1px solid rgba(255, 255, 255, 0.2);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        backdrop-filter: blur(4px);
        -webkit-backdrop-filter: blur(4px);
        transition: transform 0.3s ease-in-out, box-shadow 0.3s ease-in-out;
    }

    .section-content:hover {
        transform: translateY(-5px);
        box-shadow: 0 12px 48px 0 rgba(0, 0, 0, 0.45);
    }

    .hero-title {
        font-size: 5em;
        font-weight: 700;
        text-align: center;
        margin-bottom: 0.5em;
        line-height: 1.1;
        color: white;
        text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
    }

    .hero-subtitle {
        font-size: 1.8em;
        text-align: center;
        color: white;
        margin-bottom: 1em;
        text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.3);
    }

    .section-header {
        font-size: 2.8em;
        font-weight: 600;
        text-align: center;
        margin-bottom: 1em;
        color: white;
        text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.3);
    }

    .section-text {
        font-size: 1.2em;
        line-height: 1.6;
        text-align: center;
        margin-bottom: 2em;
        color: white;
    }

    .feature-point {
        font-size: 1.1em;
        line-height: 1.5;
        padding: 0.8em 0;
        color: white;
    }

    .contact-info {
        display: flex;
        justify-content: center;
        align-items: center;
        margin-top: 2em;
    }

    .contact-item {
        display: flex;
        align-items: center;
        margin: 0 1em;
    }

    .contact-item i {
        margin-right: 0.5em;
    }

    .contact-item a {
        color: white;
        text-decoration: none;
    }
    </style>
    """, unsafe_allow_html=True)

    # 첫 번째 섹션
    st.markdown("""
    <div class='section section1'>
        <div class='section-content'>
            <h1 class='hero-title'>Smart IV Pole Dashboard</h1>
            <p class='hero-subtitle'>IV Pole에 설치된 로드셀을 통해 실시간으로 수액 잔량을 모니터링하고 <br>의료진에게 즉시 알림을 제공하여 환자 안전을 보장합니다.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 두 번째 섹션
    st.markdown("""
    <div class='section section2'>
        <div class='section-content'>
            <h2 class='section-header'>의료 현장의 숨겨진 위험</h2>
            <p class='section-text'>
            수액 주입 중 갑작스러운 수액 고갈은 환자의 생명에 직접적인 위협이 될 수 있습니다. <br>
            전통적인 방식으로는 수액 잔량을 수시로 확인해야 하며, <br>
            간호사가 다른 업무에 집중하는 동안 수액이 고갈될 위험이 항상 존재합니다.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 세 번째 섹션
    st.markdown("""
    <div class='section section3'>
        <div class='section-content'>
            <h2 class='section-header'>우리의 솔루션: 실시간 수액 모니터링</h2>
            <p class='section-text'>
            Smart IV Pole Dashboard는 IV Pole에 설치된 로드셀을 통해 수액 무게를 실시간으로 측정하고, <br>
            남은 시간을 정확히 계산하여 의료진에게 사전 알림을 제공합니다.
            </p>
            <ul class='section-text'>
                <li class='feature-point'><b>🔍 실시간 무게 측정:</b> 로드셀 센서가 수액 무게를 지속적으로 측정하여 정확한 잔량 파악.</li>
                <li class='feature-point'><b>⏰ 예측 알림 시스템:</b> 수액 고갈 전 미리 알림을 통해 의료진의 대응 시간 확보.</li>
                <li class='feature-point'><b>📊 직관적인 대시보드:</b> 모든 IV Pole의 상태를 한눈에 파악할 수 있는 실시간 대시보드.</li>
                <li class='feature-point'><b>⚡ 웹소켓 기반 실시간 통신:</b> 지연 없는 실시간 데이터 전송으로 즉각적인 상태 업데이트.</li>
                <li class='feature-point'><b>📈 실시간 그래프:</b> 수액 무게 변화를 시각적으로 확인할 수 있는 인터랙티브 차트.</li>
                <li class='feature-point'><b>🚨 긴급 알림:</b> 수액 잔량이 임계값 이하로 떨어질 때 즉시 경고 알림.</li>
            </ul>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 네 번째 섹션
    st.markdown("""
    <div class='section section4'>
        <div class='section-content'>
            <h2 class='section-header'>최신 기술로 구축된 안정적인 시스템</h2>
            <p class='section-text'>
            현대적인 웹 기술과 클라우드 서비스를 결합하여 <br>
            안정적이고 확장 가능한 모니터링 시스템을 구축했습니다.
            </p>
            <ul class='section-text'>
                <li class='feature-point'><b>🖥️ 하드웨어:</b> 로드셀 센서, 마이크로컨트롤러, 모터 제어 시스템</li>
                <li class='feature-point'><b>☁️ AWS DynamoDB:</b> 안정적인 클라우드 데이터베이스로 센서 데이터 저장 및 관리</li>
                <li class='feature-point'><b>🌐 Streamlit 프레임워크:</b> 빠르고 효율적인 웹 대시보드 구축 및 데이터 시각화</li>
                <li class='feature-point'><b>🔌 WebSocket 통신:</b> 실시간 양방향 통신으로 지연 없는 데이터 전송</li>
                <li class='feature-point'><b>📊 Plotly 라이브러리:</b> 인터랙티브하고 미려한 실시간 그래프 및 차트 제공</li>
                <li class='feature-point'><b>🤖 환자 인식:</b> 허스키렌즈를 활용한 환자 인식 및 거리 측정 시스템</li>
                <li class='feature-point'><b>📏 UWB 기술:</b> 초정밀 거리 측정으로 환자와 IV Pole 간 거리 모니터링</li>
            </ul>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 다섯 번째 섹션
    st.markdown("""
    <div class='section section5'>
        <div class='section-content'>
            <h2 class='section-header'>환자 안전을 한 단계 끌어올리다</h2>
            <p class='section-text'>
            우리의 시스템은 단순한 모니터링을 넘어, 실제 의료 현장의 안전성을 향상시킵니다.
            </p>
            <ul class='section-text'>
                <li class='feature-point'><b>🛡️ 환자 안전 향상:</b> 수액 고갈로 인한 의료 사고 방지 및 환자 안전 보장</li>
                <li class='feature-point'><b>⚡ 의료진 업무 효율성:</b> 수동 확인 작업 감소로 더 중요한 의료 업무에 집중 가능</li>
                <li class='feature-point'><b>🌙 24시간 모니터링:</b> 야간 근무 시에도 안정적인 수액 상태 감시</li>
                <li class='feature-point'><b>📊 데이터 기반 의사결정:</b> 수액 사용 패턴 분석을 통한 효율적인 자원 관리</li>
                <li class='feature-point'><b>🎯 정확한 예측:</b> AI 기반 알고리즘으로 수액 소진 시간을 정확히 예측</li>
                <li class='feature-point'><b>🔔 스마트 알림:</b> 상황별 맞춤형 알림으로 의료진의 신속한 대응 지원</li>
            </ul>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 여섯 번째 섹션
    st.markdown("""
    <div class='section section6'>
        <div class='section-content'>
            <h2 class='section-header'>스마트 의료의 미래, 지금 경험하세요</h2>
            <p class='section-text'>
            본 시스템에 대한 더 자세한 정보나 문의 사항이 있으시면 언제든지 연락 주십시오.
            </p>
            <div class="contact-info">
                <div class="contact-item">
                    <i class="fas fa-envelope"></i>
                    <a href="mailto:2020144005@tukorea.ac.kr">2020144005@tukorea.ac.kr</a>
                </div>
                <div class="contact-item">
                    <i class="fas fa-phone-alt"></i>
                    <span>+82 10-2204-4587</span>
                </div>
                <div class="contact-item">
                    <i class="fab fa-github"></i>
                    <a href="https://github.com/Wake-Up-It-s-a-Hospital" target="_blank">GitHub Repository</a>
                </div>
                <div class="contact-item">
                    <i class="fas fa-map-marker-alt"></i>
                    <span>한국공학대학교 전자공학과</span>
                </div>
            </div>
            <p class='section-text' style='margin-top: 2em;'>
            지금 바로 시작하여 더 안전하고 효율적인 의료 환경을 구축하세요.
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    pass # Streamlit이 자동으로 실행합니다.