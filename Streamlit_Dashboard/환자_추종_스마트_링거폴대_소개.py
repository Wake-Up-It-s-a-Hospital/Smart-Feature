import streamlit as st
import threading
import queue
import websocket
import time
import json
from streamlit_autorefresh import st_autorefresh
from utils.alert_utils import render_alert_sidebar

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

# ====== 알림 템플릿 딕셔너리 ======
ALERT_TEMPLATES = {
    1: "{pole}번 폴대의 {bottle} 수액이 다 투여되었습니다.",
    2: "{pole}번 폴대의 {bottle} 수액이 거의 다 되었습니다. (남은 시간: {remaining_sec:.0f}분, 무게: {current_weight:.1f}g)",
    3: "{pole}번 폴대의 배터리가 거의 방전되었습니다. (남은 배터리: {battery:.0f}%",
    4: "{pole}번 폴대에서 너스콜이 발생했습니다."
}

# ====== 알림 추가 함수 (ID와 파라미터 기반) ======
def add_alert(alert_id, **params):
    template = ALERT_TEMPLATES.get(alert_id)
    if template is None:
        return
    msg = template.format(**params)
    # 중복 방지: 같은 알림이 이미 있으면 추가하지 않음
    key = (alert_id, tuple(sorted(params.items())))
    if "alert_flags" not in st.session_state:
        st.session_state.alert_flags = set()
    if key in st.session_state.alert_flags:
        return
    st.session_state.alert_flags.add(key)
    st.session_state.alert_list.append({
        "id": alert_id,
        "msg": msg,
        "params": params
    })

# ====== 알림 리스트 및 플래그 초기화 ======
if "alert_list" not in st.session_state:
    st.session_state.alert_list = []
if "alert_flags" not in st.session_state:
    st.session_state.alert_flags = set()

# ====== 알림 조건 체크 및 이벤트 트리거 (ID/파라미터 기반으로 변경) ======
# ALMOST_DONE_WEIGHT =300  # 50g 이하
# DONE_WEIGHT = 150  # 5g 이하

for loadcel, data in st.session_state.loadcell_data.items():
    pole = loadcel  # 폴대 번호 (loadcel이 곧 폴대 번호라고 가정)
    bottle = "오른쪽"     # 링거 번호 (예시, 실제 데이터에 맞게 수정)
    # 각 장비별 임계값 불러오기
    almost_key = f'alert_almost_weight_{loadcel}'
    done_key = f'alert_done_weight_{loadcel}'
    almost_weight = st.session_state.get(almost_key, 300)
    done_weight = st.session_state.get(done_key, 150)
    # 투여 거의 완료 (무게만으로 판단)
    if (0 < data.get("current_weight", 99999) <= almost_weight):
        add_alert(2, pole=pole, bottle=bottle, remaining_sec=data.get("remaining_sec", -1), current_weight=data.get("current_weight", 0))
    # 투여 완료
    if (0 < data.get("current_weight", 99999) <= done_weight):
        add_alert(1, pole=pole, bottle=bottle)
    # 배터리 부족
    if "battery" in data and data["battery"] <= 20:  # 예시: 20% 이하일 때 알림
        add_alert(3, pole=pole, battery=data["battery"])
    # 너스콜
    if data.get("nurse_call", False):
        add_alert(4, pole=pole)

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
                    url('https://i.imgur.com/WDcZVTB.jpeg') no-repeat;
        background-attachment: fixed;
        background-size: cover;
        background-position: center;
    }

    .section2 {
        background: linear-gradient(rgba(0, 0, 0, 0.8), rgba(0, 0, 0, 0.8)),
                    url('https://i.imgur.com/f39Lij3.jpeg') no-repeat;
        background-attachment: fixed;
        background-size: cover;
        background-position: center;
    }

    .section3 {
        background: linear-gradient(rgba(0, 0, 0, 0.8), rgba(0, 0, 0, 0.8)),
                    url('https://i.imgur.com/I1KZGj4.jpeg') no-repeat;
        background-attachment: fixed;
        background-size: cover;
        background-position: center;
    }

    .section4 {
        background: linear-gradient(rgba(0, 0, 0, 0.8), rgba(0, 0, 0, 0.8)),
                    url('https://i.imgur.com/9lU4jYP.jpeg') no-repeat;
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
            Smart IV Pole Dashboard는 IV Pole에 설치된 고정밀 로드셀 센서를 통해 수액 무게를 실시간으로 측정하고,<br>
            AI 기반 알고리즘으로 남은 투여 시간을 예측하여, 의료진에게 사전 경고 및 다양한 자동 알림을 제공합니다.<br>
            이를 통해 환자 안전을 극대화하고, 의료진의 업무 효율성을 혁신적으로 향상시킵니다.
            </p>
            <ul class='section-text'>
                <li class='feature-point'><b>실시간 무게 측정:</b> 고정밀 로드셀 센서가 수액 무게를 초 단위로 지속적으로 측정하여, 잔량 변화를 즉시 파악합니다.</li>
                <li class='feature-point'><b>AI 예측 및 자동 알림:</b> AI 기반 예측 알고리즘이 수액 소진 예상 시간을 계산하고, 고갈 전 미리 의료진에게 자동으로 알림을 전송합니다.</li>
                <li class='feature-point'><b>다중 임계값 경고:</b> 잔량이 임계값 이하로 떨어질 때 단계별(거의 소진/완전 소진)로 맞춤형 경고 알림을 제공합니다.</li>
                <li class='feature-point'><b>직관적인 대시보드:</b> 모든 IV Pole의 상태와 수액 잔량, 남은 시간을 한눈에 확인할 수 있는 실시간 대시보드를 제공합니다.</li>
                <li class='feature-point'><b>웹소켓 기반 실시간 통신:</b> 지연 없는 실시간 데이터 전송으로 즉각적인 상태 업데이트와 빠른 의사결정을 지원합니다.</li>
                <li class='feature-point'><b>실시간 그래프 및 이력 관리:</b> 수액 무게 변화 추이를 시각적으로 확인할 수 있는 인터랙티브 차트와 히스토리 기능을 제공합니다.</li>
                <li class='feature-point'><b>환자 안전 강화:</b> 수액 고갈로 인한 의료 사고를 예방하고, 환자 안전을 최우선으로 보장합니다.</li>
                <li class='feature-point'><b>의료진 업무 효율화:</b> 반복적인 수액 확인 업무를 자동화하여, 의료진이 더 중요한 업무에 집중할 수 있도록 돕습니다.</li>
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
                <li class='feature-point'><b>하드웨어:</b> 로드셀 센서, 마이크로컨트롤러, 모터 제어 시스템</li>
                <li class='feature-point'><b>AWS DynamoDB:</b> 안정적인 클라우드 데이터베이스로 센서 데이터 저장 및 관리</li>
                <li class='feature-point'><b>Streamlit 프레임워크:</b> 빠르고 효율적인 웹 대시보드 구축 및 데이터 시각화</li>
                <li class='feature-point'><b>WebSocket 통신:</b> 실시간 양방향 통신으로 지연 없는 데이터 전송</li>
                <li class='feature-point'><b>Plotly 라이브러리:</b> 인터랙티브하고 미려한 실시간 그래프 및 차트 제공</li>
                <li class='feature-point'><b>환자 인식:</b> 허스키렌즈를 활용한 환자 인식 및 거리 측정 시스템</li>
                <li class='feature-point'><b>UWB 기술:</b> 초정밀 거리 측정으로 환자와 IV Pole 간 거리 모니터링</li>
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
                <li class='feature-point'><b>환자 안전 향상:</b> 수액 고갈로 인한 의료 사고 방지 및 환자 안전 보장</li>
                <li class='feature-point'><b>의료진 업무 효율성:</b> 수동 확인 작업 감소로 더 중요한 의료 업무에 집중 가능</li>
                <li class='feature-point'><b>24시간 모니터링:</b> 야간 근무 시에도 안정적인 수액 상태 감시</li>
                <li class='feature-point'><b>데이터 기반 의사결정:</b> 수액 사용 패턴 분석을 통한 효율적인 자원 관리</li>
                <li class='feature-point'><b>정확한 예측:</b> AI 기반 알고리즘으로 수액 소진 시간을 정확히 예측</li>
                <li class='feature-point'><b>스마트 알림:</b> 상황별 맞춤형 알림으로 의료진의 신속한 대응 지원</li>
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

# ====== 사이드바에 알림 리스트 출력 ======
render_alert_sidebar()


if __name__ == "__main__":
    pass # Streamlit이 자동으로 실행합니다.