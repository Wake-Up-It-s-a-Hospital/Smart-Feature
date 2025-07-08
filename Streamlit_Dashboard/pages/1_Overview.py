import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objs as go
import time
import streamlit.components.v1 as components

st.set_page_config(layout="wide")

# 1초마다 자동 새로고침
st_autorefresh(interval=1000, key="datarefresh")

# --- UI 표시 ---
st.title("📊 전체 현황 대시보드")

# 메인 페이지에서 이미 초기화된 session_state 데이터 사용
loadcell_data = st.session_state.get('loadcell_data', {})
loadcell_history = st.session_state.get('loadcell_history', {})

if not loadcell_data:
    # 데이터가 없으면 픽토그램 스타일 애니메이션 로딩 인디케이터 표시
    html_code = '''
    <style>
    @keyframes outer {
        50% { transform: translateY(0); }
        25%, 75% { transform: translateY(4px); }
    }

    @keyframes body {
        50% { transform: rotate(16deg); }
        25%, 75% { transform: rotate(24deg); }
    }

    @keyframes arm-leg {
        50% { transform: rotate(var(--r-to)); }
    }

    @keyframes arm-b {
        30%, 70% { transform: rotate(var(--r-to)); }
    }

    @keyframes moveRight {
        0% { transform: translateX(-100px); }
        100% { transform: translateX(calc(100vw + 100px)); }
    }

    @keyframes moveLeft {
        0% { transform: translateX(calc(100vw + 100px)); }
        100% { transform: translateX(-100px); }
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.8; transform: scale(1.05); }
    }

    .loading-container {
        text-align: center;
        padding: 40px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 20px;
        margin: 20px 0;
        color: white;
        position: relative;
        overflow: hidden;
        min-height: 300px;
    }

    .scene-title {
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 30px;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        animation: pulse 2s infinite;
    }

    .animation-scene {
        position: relative;
        height: 200px;
        margin: 20px 0;
    }

    /* 픽토그램 스타일 달리는 사람 */
    .running {
        --color: #fff;
        --duration: 0.7s;
        position: absolute;
        top: 50%;
        transform: translateY(-50%);
    }

    .running .outer {
        animation: outer var(--duration) linear infinite;
    }

    .running .body {
        background: var(--color);
        height: 15px;
        width: 8px;
        border-radius: 4px;
        transform-origin: 4px 11px;
        position: relative;
        transform: rotate(32deg);
        animation: body var(--duration) linear infinite;
    }

    .running .body:before {
        content: '';
        width: 8px;
        height: 8px;
        border-radius: 4px;
        bottom: 16px;
        left: 0;
        position: absolute;
        background: var(--color);
    }

    .running .arm,
    .running .arm:before,
    .running .leg,
    .running .leg:before {
        content: '';
        width: var(--w, 11px);
        height: 4px;
        top: var(--t, 0);
        left: var(--l, 2px);
        border-radius: 2px;
        transform-origin: 2px 2px;
        position: absolute;
        background: var(--c, var(--color));
        transform: rotate(var(--r, 0deg));
        animation: var(--name, arm-leg) var(--duration) linear infinite;
    }

    .running .arm:before {
        --l: 7px;
        --name: arm-b;
    }

    .running .arm.front {
        --r: 24deg;
        --r-to: 164deg;
    }

    .running .arm.front:before {
        --r: -48deg;
        --r-to: -36deg;
    }

    .running .arm.behind {
        --r: 164deg;
        --r-to: 24deg;
    }

    .running .arm.behind:before {
        --r: -36deg;
        --r-to: -48deg;
    }

    .running .leg {
        --w: 12px;
        --t: 11px;
    }

    .running .leg:before {
        --t: 0;
        --l: 8px;
    }

    .running .leg.front {
        --r: 10deg;
        --r-to: 108deg;
    }

    .running .leg.front:before {
        --r: 18deg;
        --r-to: 76deg;
    }

    .running .leg.behind {
        --r: 108deg;
        --r-to: 10deg;
        --c: none;
    }

    .running .leg.behind:before {
        --c: var(--color);
        --r: 76deg;
        --r-to: 18deg;
    }

    .running .leg.behind:after {
        content: '';
        top: 0;
        right: 0;
        height: 4px;
        width: 6px;
        clip-path: polygon(2px 0, 6px 0, 6px 4px, 0 4px);
        border-radius: 0 2px 2px 0;
        position: absolute;
        background: var(--color);
    }

    /* 의료진 캐릭터들 */
    .emergency-team {
        position: absolute;
        top: 30%;
        left: 0;
        display: flex;
        gap: 20px;
        animation: moveRight 8s linear infinite;
        animation-delay: 0s;
    }

    .doctor-running {
        --color: #4169E1;
        --duration: 0.6s;
    }

    .nurse-running {
        --color: #FF69B4;
        --duration: 0.65s;
    }

    .stretcher-bearer {
        --color: #FFD700;
        --duration: 0.7s;
    }

    /* 들것 */
    .stretcher {
        width: 60px;
        height: 15px;
        background: linear-gradient(180deg, #F5F5F5 0%, #E0E0E0 100%);
        border: 2px solid #A0A0A0;
        border-radius: 8px;
        position: relative;
        margin: 0 10px;
    }

    .stretcher:before {
        content: '';
        position: absolute;
        top: -6px;
        left: 10px;
        width: 40px;
        height: 4px;
        background: #808080;
        border-radius: 2px;
    }

    /* 평상시 환자 */
    .patient-walking {
        position: absolute;
        top: 60%;
        left: 0;
        --color: #32CD32;
        --duration: 1.2s;
        animation: moveLeft 12s linear infinite;
        animation-delay: 3s;
    }

    /* IV 폴대 */
    .iv-pole {
        position: absolute;
        top: 40%;
        left: 50px;
        width: 6px;
        height: 60px;
        background: linear-gradient(180deg, #C0C0C0 0%, #A0A0A0 100%);
        border-radius: 3px;
        animation: moveLeft 15s linear infinite;
        animation-delay: 5s;
    }

    .iv-pole:before {
        content: '';
        position: absolute;
        top: -15px;
        left: -6px;
        width: 18px;
        height: 25px;
        background: linear-gradient(180deg, #E0F7FA 0%, #B2EBF2 100%);
        border: 2px solid #4FC3F7;
        border-radius: 6px;
    }

    .iv-pole:after {
        content: '';
        position: absolute;
        top: 55px;
        left: -1px;
        width: 8px;
        height: 12px;
        background: #4FC3F7;
        border-radius: 4px;
    }

    /* 병원 건물 */
    .hospital-building {
        position: absolute;
        top: 20px;
        right: 20px;
        width: 50px;
        height: 35px;
        background: linear-gradient(180deg, #E8F4F8 0%, #D4EDDA 100%);
        border: 2px solid #4A90E2;
        border-radius: 6px;
        animation: pulse 4s infinite ease-in-out;
    }

    .hospital-building:before {
        content: '🏥';
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        font-size: 16px;
    }

    /* 모니터 */
    .monitor {
        position: absolute;
        top: 80px;
        right: 20px;
        width: 40px;
        height: 30px;
        background: #2C3E50;
        border: 2px solid #34495E;
        border-radius: 4px;
        animation: pulse 3s infinite ease-in-out;
    }

    .monitor:before {
        content: '';
        position: absolute;
        top: 4px;
        left: 4px;
        width: 32px;
        height: 22px;
        background: #00FF00;
        border-radius: 2px;
    }

    .info-box {
        background: rgba(255, 255, 255, 0.9);
        border-radius: 15px;
        padding: 20px;
        margin-top: 20px;
        color: #2c3e50;
        border-left: 5px solid #3498db;
    }
    </style>
    '''
    components.html(html_code, height=800)
    
    
    html_body = '''
    <div class="loading-container">
        <div class="scene-title">🏥 스마트 의료 시스템 로딩 중</div>
        
        <div class="animation-scene">
            <!-- 병원 건물 -->
            <div class="hospital-building"></div>
            <div class="monitor"></div>
            
            <!-- 응급 의료진 -->
            <div class="emergency-team">
                <div class="running doctor-running">
                    <div class="outer">
                        <div class="body">
                            <div class="arm behind"></div>
                            <div class="arm front"></div>
                            <div class="leg behind"></div>
                            <div class="leg front"></div>
                        </div>
                    </div>
                </div>
                <div class="stretcher"></div>
                <div class="running nurse-running">
                    <div class="outer">
                        <div class="body">
                            <div class="arm behind"></div>
                            <div class="arm front"></div>
                            <div class="leg behind"></div>
                            <div class="leg front"></div>
                        </div>
                    </div>
                </div>
                <div class="running stretcher-bearer">
                    <div class="outer">
                        <div class="body">
                            <div class="arm behind"></div>
                            <div class="arm front"></div>
                            <div class="leg behind"></div>
                            <div class="leg front"></div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 평상시 환자 -->
            <div class="running patient-walking">
                <div class="outer">
                    <div class="body">
                        <div class="arm behind"></div>
                        <div class="arm front"></div>
                        <div class="leg behind"></div>
                        <div class="leg front"></div>
                    </div>
                </div>
            </div>
            
            <!-- IV 폴대 -->
            <div class="iv-pole"></div>
        </div>
        
        <p style="font-size: 18px; margin-top: 20px;">의료진이 환자를 돌보고 있습니다...</p>
    </div>
    
    <div class="info-box">
        <h3>💡 연결 확인 필요</h3>
        <p>연결이 제대로 되지 않아 데이터를 불러오지 못하고 있습니다.</p>
        <p>터미널에서 <code>streamlit run main.py</code> 실행 후 <code>[WebSocket] 연결 성공</code> 메시지가 나타나는지 확인하세요.</p>
    </div>
    '''
    components.html(html_body, height=800)
    
else:
    # 로드셀 ID 순서대로 정렬하여 항상 같은 순서로 표시
    for loadcel_id in sorted(loadcell_data.keys()):
        values = loadcell_data[loadcel_id]
        
        st.write("---")
        st.subheader(f"로드셀 #{loadcel_id}")

        # 수액 미연결 상태 체크
        if values['current_weight'] == 0 and values['remaining_sec'] == -1:
            st.warning("�� 수액이 연결되지 않았습니다.")
        else:
            col1, col2 = st.columns(2)
            col1.metric(label="현재 무게", value=values['current_weight'])
            col2.metric(label="남은 시간(초)", value=values['remaining_sec'])
            # plotly 그래프 추가
            history = loadcell_history.get(loadcel_id, [])
            if history:
                fig = go.Figure()
                fig.add_trace(go.Scatter(y=history, mode='lines+markers', name='무게'))
                fig.update_layout(title="무게 변화 추이 (최근 30개)", xaxis_title="측정 순서", yaxis_title="무게")
                st.plotly_chart(fig, use_container_width=True)
