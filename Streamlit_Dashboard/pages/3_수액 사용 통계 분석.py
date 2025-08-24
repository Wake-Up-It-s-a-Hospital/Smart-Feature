import streamlit as st
import json
import pandas as pd
import plotly.express as px
import numpy as np
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.arima.model import ARIMA
import statsmodels.api as sm
from statsmodels.tsa.stattools import acf as sm_acf, pacf as sm_pacf
import boto3
import pytz
from utils.alert_utils import render_alert_sidebar, check_all_alerts
from utils.logo_utils import show_logo
from utils.auth_utils import require_auth, render_userbox, get_current_user

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
                # === 남은 시간 계산: 현재 무게 기반 ===
                if current_weight > 0:
                    remaining_sec = (current_weight / 250) * 3600
                else:
                    remaining_sec = -1
                # 배터리 레벨 처리
                try:
                    battery_level = int(data.get("battery_level", -1)) if data.get("battery_level") is not None else None
                except:
                    battery_level = None
                st.session_state.loadcell_data[loadcel] = {
                    "current_weight": current_weight,
                    "remaining_sec": remaining_sec,
                    "battery_level": battery_level  # 배터리 레벨 추가
                }
                if loadcel not in st.session_state.loadcell_history:
                    st.session_state.loadcell_history[loadcel] = []
                st.session_state.loadcell_history[loadcel].append((timestamp, current_weight))
                if len(st.session_state.loadcell_history[loadcel]) > 30:
                    st.session_state.loadcell_history[loadcel] = st.session_state.loadcell_history[loadcel][-30:]
        except Exception as e:
            print(f"메시지 파싱 오류: {msg} | 오류: {e}")

user = get_current_user()
if not user:
    try:
        st.switch_page("환자_추종_스마트_링거폴대_소개.py")
    except Exception:
        st.stop()
render_userbox()
show_logo()
# 사이드바 내용 추가
st.sidebar.header("수액 사용 통계 분석")
st.sidebar.write("각 링거 폴대 별로")
st.sidebar.write("데이터를 분석합니다.")
st.sidebar.markdown("---")

# ====== 알림 리스트 초기화 ======
if "alert_list" not in st.session_state:
    st.session_state.alert_list = []
if "alert_flags" not in st.session_state:
    st.session_state.alert_flags = set()

# ====== 통합 알림 체크 ======
check_all_alerts()

# ====== 사이드바에 알림 리스트 출력 ======
render_alert_sidebar()

st.title("수액 사용 통계 분석")

# 데이터 불러오기
@st.cache_data
def get_history_df():
    # 추가 데이터와 실제 DB 데이터를 병합하여 반환
    try:
        from utils.dummy_data_utils import get_additional_data_for_analysis_exclude_last, is_additional_data_available
        
        if is_additional_data_available():
            # 추가 데이터 사용 (마지막 데이터 제외)
            df = get_additional_data_for_analysis_exclude_last()
            # 성공 메시지는 표시하지 않음 (사용자에게는 투명하게)
            return df
        else:
            # 실제 DB 데이터 사용
            dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')
            table = dynamodb.Table('loadcell_history')
            response = table.scan()
            items = response['Items']
            df = pd.DataFrame(items)
            if not df.empty:
                df['current_weight_history'] = pd.to_numeric(df['current_weight_history'], errors='coerce')
                # === 남은 시간 컬럼을 무게 기반으로 새로 계산 ===
                df['remaining_sec_history'] = df['current_weight_history'].apply(lambda w: (w/250)*3600 if w > 0 else -1)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
            
    except ImportError:
        # 추가 데이터 유틸리티가 없는 경우 실제 DB만 사용
        dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')
        table = dynamodb.Table('loadcell_history')
        response = table.scan()
        items = response['Items']
        df = pd.DataFrame(items)
        if not df.empty:
            df['current_weight_history'] = pd.to_numeric(df['current_weight_history'], errors='coerce')
            df['remaining_sec_history'] = df['current_weight_history'].apply(lambda w: (w/250)*3600 if w > 0 else -1)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except Exception as e:
        st.error(f"❌ 데이터 로드 실패: {e}")
        return pd.DataFrame()

df = get_history_df()

# === 상단 카드 요약 ===
if not df.empty:
    tz = df['timestamp'].dt.tz
    today = pd.Timestamp.now(tz=tz).normalize()
    week_start = today - pd.Timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    today_sum = df[df['timestamp'].dt.date == today.date()]['current_weight_history'].sum() / 1000
    week_sum = df[(df['timestamp'] >= week_start)]['current_weight_history'].sum() / 1000
    month_sum = df[(df['timestamp'] >= month_start)]['current_weight_history'].sum() / 1000
    col1, col2, col3 = st.columns(3)
    col1.metric("오늘 총 사용량", f"{today_sum:.1f}kg")
    col2.metric("이번주 총 사용량", f"{week_sum:.1f}kg")
    col3.metric("이번달 총 사용량", f"{month_sum:.1f}kg")

if df.empty:
    st.warning("아직 기록된 데이터가 없습니다.")
else:
    # 1. 기간/장비별 필터
    st.sidebar.header("수액 사용 통계 분석 조정")
    
    # 더미데이터에서 사용 가능한 모든 폴대 ID 가져오기
    try:
        from utils.dummy_data_utils import get_additional_pole_ids, is_additional_data_available
        
        if is_additional_data_available():
            # 더미데이터에서 사용 가능한 모든 폴대 ID
            additional_pole_ids = get_additional_pole_ids()
            # 실제 데이터에서 가져온 폴대 ID와 병합
            data_pole_ids = df['loadcel'].unique().tolist()
            all_pole_ids = list(set(data_pole_ids + additional_pole_ids))
            # 숫자 순서로 정렬
            all_pole_ids.sort(key=lambda x: int(x) if str(x).isdigit() else 0)
            loadcel_options = all_pole_ids
        else:
            # 더미데이터가 없는 경우 기존 방식 사용
            loadcel_options = df['loadcel'].unique().tolist()
    except ImportError:
        # 유틸리티가 없는 경우 기존 방식 사용
        loadcel_options = df['loadcel'].unique().tolist()
    except Exception:
        # 오류 발생 시 기존 방식 사용
        loadcel_options = df['loadcel'].unique().tolist()
    
    selected_loadcel = st.sidebar.multiselect("장비 선택", loadcel_options, default=loadcel_options)
    start_date = st.sidebar.date_input("시작일", df['timestamp'].min().date())
    end_date = st.sidebar.date_input("종료일", df['timestamp'].max().date())

    # 타임존 정보 추출 및 일치화
    tz = df['timestamp'].dt.tz if df['timestamp'].dt.tz is not None else None
    start_dt = pd.Timestamp(start_date)
    end_dt = pd.Timestamp(end_date) + pd.Timedelta(days=1)
    if tz is not None:
        if start_dt.tzinfo is None:
            start_dt = start_dt.tz_localize(tz)
        else:
            start_dt = start_dt.tz_convert(tz)
        if end_dt.tzinfo is None:
            end_dt = end_dt.tz_localize(tz)
        else:
            end_dt = end_dt.tz_convert(tz)

    filtered = df[
        (df['loadcel'].isin(selected_loadcel)) &
        (df['timestamp'] >= start_dt) &
        (df['timestamp'] <= end_dt)
    ]

    # 2. 기간별 무게 변화(감소량, kg)
    st.subheader("기간별 무게 변화(감소량, kg)")
    st.text("그래프 좌측 장비를 더블클릭하면 해당 장비만 표시할 수 있습니다.")
    if filtered.empty:
        st.info("선택한 조건에 해당하는 데이터가 없습니다.")
    else:
        # 각 폴대별로 마지막 데이터 제외
        filtered_clean = pd.DataFrame()
        for pole_id in filtered['loadcel'].unique():
            pole_data = filtered[filtered['loadcel'] == pole_id].sort_values('timestamp')
            if len(pole_data) > 1:
                # 마지막 1개 데이터 제외
                pole_data_clean = pole_data.iloc[:-1]
                filtered_clean = pd.concat([filtered_clean, pole_data_clean], ignore_index=True)
            else:
                # 데이터가 1개뿐인 경우 그대로 사용
                filtered_clean = pd.concat([filtered_clean, pole_data], ignore_index=True)
        
        # 정렬 및 사용량 계산
        filtered_clean = filtered_clean.sort_values('timestamp')
        filtered_clean['prev_weight'] = filtered_clean.groupby('loadcel')['current_weight_history'].shift(1)
        filtered_clean['usage'] = (filtered_clean['prev_weight'] - filtered_clean['current_weight_history']).clip(lower=0) / 1000
        
        # 감소량(usage, g) 기준으로 라인차트 표시
        # 감소량이 0인 데이터는 제외하고, 단위를 g로 변환
        filtered_clean_nonzero = filtered_clean[filtered_clean['usage'] > 0].copy()
        filtered_clean_nonzero['usage_g'] = filtered_clean_nonzero['usage'] * 1000  # kg을 g로 변환
        
        if not filtered_clean_nonzero.empty:
            fig = px.line(
                filtered_clean_nonzero,
                x='timestamp',
                y='usage_g',
                color='loadcel',
                markers=True,
                labels={'usage_g': '감소량(g)', 'timestamp': '시간', 'loadcel': '장비'}
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("감소량이 있는 데이터가 없습니다.")

# === 3개 통계 가로 배치 ===
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("시간대별 사용량(g)")
    # 마지막 데이터가 제외된 filtered_clean 사용
    filtered_clean['hour'] = filtered_clean['timestamp'].dt.hour
    
    # 0) 형 변환 및 정렬 보장
    filtered_clean['timestamp'] = pd.to_datetime(filtered_clean['timestamp'])
    filtered_clean['current_weight_history'] = pd.to_numeric(
        filtered_clean['current_weight_history'], errors='coerce'
    )
    
    # 1) 폴대별 시간 정렬 보장
    filtered_clean = filtered_clean.sort_values(['loadcel', 'timestamp'])
    
    # 2) 차분으로 사용량 계산 (현재-이전). 감소분만 취함.
    diff = filtered_clean.groupby('loadcel')['current_weight_history'].diff()  # curr - prev
    filtered_clean['usage'] = (-diff).clip(lower=0).fillna(0) / 1000  # kg
    
    # 3) 디버그로 폴대별 표본수/합계 확인
    debug = filtered_clean.groupby('loadcel').agg(
        rows=('timestamp', 'size'),
        pos_hours=('usage', lambda s: (s > 0).sum()),
        usage_sum=('usage', 'sum')
    )
    
    # 시간대별 사용량 테이블 생성 (원본 데이터)
    usage_by_hour = filtered_clean.groupby(['hour', 'loadcel'])['usage'].sum().reset_index()
    
    # kg을 g로 변환 (1000 곱하기)
    usage_by_hour['usage_g'] = usage_by_hour['usage'] * 1000
    
    # 피벗 테이블로 변환 (g 단위)
    usage_pivot = usage_by_hour.pivot(index='hour', columns='loadcel', values='usage_g').fillna(0)
    
    # 원본 사용량 테이블 표시
    st.dataframe(usage_pivot.round(3), use_container_width=True)
    
with col2:
    st.subheader("폴대별 사용량 랭킹(kg)")
    filtered_clean['usage'] = (filtered_clean['prev_weight'] - filtered_clean['current_weight_history']).clip(lower=0) / 1000
    rank_df = filtered_clean.groupby('loadcel')['usage'].sum().reset_index()
    rank_df['usage'] = rank_df['usage'].round(1)
    rank_df = rank_df.sort_values('usage', ascending=False)
    rank_df.index += 1
    st.dataframe(rank_df.rename(columns={'usage': '총 사용량(kg)'}))

with col3:
    st.subheader("이상치(급격한 변화) 탐지")
    st.text("50g 이상의 급격한 무게 변화가 감지되면 이상치로 분류됩니다. \n이는 측정 오류 또는 주행에 의한 무게 변화를 나타낼 수 있습니다.")
    
    filtered_clean['diff'] = filtered_clean.groupby('loadcel')['current_weight_history'].diff().abs()
    outlier = filtered_clean[filtered_clean['diff'] > 50]  # 예: 50g 이상 변화
    if outlier.empty:
        st.info("이상 변화(급격한 무게 변화) 없음")
    else:
        st.dataframe(outlier[['loadcel', 'timestamp', 'current_weight_history', 'diff']])

    # === 데이터 다운로드 ===
    st.text("이상치 데이터 다운로드")
    csv = filtered_clean.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="CSV로 다운로드",
        data=csv,
        file_name="filtered_stats.csv",
        mime='text/csv'
    )

st.subheader("고급 통계 기능")
col1, col2, col3 = st.columns(3)

with st.expander("각 장비 사이의 상관관계", expanded=False):
    # 도움말 섹션 추가 (expander 대신 버튼으로 토글)
    if "show_corr_help" not in st.session_state:
        st.session_state.show_corr_help = False
        
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("여러 장비의 사용량 상관관계를 분석합니다")
    with col2:
        if st.button("❓ 도움말", key="help_corr_btn"):
            st.session_state.show_corr_help = not st.session_state.show_corr_help
    
    # 도움말 내용 표시
    if st.session_state.show_corr_help:
        st.markdown("---")
        col_help1, col_help2 = st.columns(2)
        with col_help1:
            st.markdown("# 📚 상관관계 분석 가이드")
            st.markdown("""
        **📊 상관관계 분석이란?**
        
        간단히 말하면: 여러 링거폴대(수액 거치대)의 사용량이 서로 얼마나 연관되어 있는지 분석하는 기능입니다.
        
        **예시로 설명하면:**
        - A 폴대의 수액 사용량이 많아질 때, B 폴대도 함께 많아지는지?
        - 특정 시간대에 모든 폴대가 동시에 바쁘게 사용되는지?
        - 어떤 폴대들이 서로 비슷한 패턴으로 사용되는지?
        
        **🎯 이 분석으로 무엇을 알 수 있나요?**
        
        1. **병실 배치 최적화**
           - 사용량이 함께 증가하는 폴대들을 같은 구역에 배치
           - 간호사가 한 번에 여러 폴대를 관리할 수 있도록 배치
        
        2. **인력 배치 효율성**
           - 모든 폴대가 동시에 바쁘게 사용되는 시간대 파악
           - 그 시간대에 간호사 추가 배치 고려
        
        3. **자원 계획 수립**
           - 연관된 폴대들의 총 사용량 예측
           - 수액 재고 및 구매 계획 수립에 활용
        
        **📈 결과 해석 방법**
        
        상관계수는 -1에서 +1 사이의 값입니다:
        
        🔴 **+0.7 ~ +1.0**: 매우 강한 양의 상관관계
        - 두 폴대의 사용량이 거의 항상 함께 증가/감소
        
        🟠 **+0.3 ~ +0.7**: 중간 정도의 양의 상관관계  
        - 두 폴대의 사용량이 어느 정도 함께 변화
        
        🟡 **-0.3 ~ +0.3**: 약한 상관관계
        - 두 폴대 간에 특별한 연관성 없음
        
        🟢 **-0.7 ~ -0.3**: 중간 정도의 음의 상관관계
        - 한 폴대가 증가할 때 다른 폴대는 감소하는 경향
        
        🔵 **-1.0 ~ -0.7**: 매우 강한 음의 상관관계
        - 한 폴대가 증가할 때 다른 폴대는 확실히 감소
        
        **💡 실제 활용 팁**
        
        **높은 상관관계가 발견되면:**
        - 해당 폴대들을 같은 간호사가 담당하도록 배치
        - 같은 시간대에 점검 및 관리 업무 수행
        - 비상 상황 시 대체 폴대로 활용 가능성 검토
        
        **낮은 상관관계가 발견되면:**
        - 각 폴대를 독립적으로 관리해도 무방
        - 개별적인 사용량 예측 및 계획 수립
        

        """)
            
        with col_help2:
            st.markdown("# 📊 그래프 해석 가이드")
            st.markdown("""
        ### **🌐 상관관계 네트워크**
        - **노드(원)**: 각 링거폴대
        - **선의 색상**: 상관관계 강도
            - 🔴 빨간색: 강한 상관관계 (>0.7)
            - 🟠 주황색: 중간 상관관계 (0.5~0.7)
            - 🟡 노란색: 약한 상관관계 (0.3~0.5)
            - ⚪ 연한 회색: 매우 약한 상관관계 (<0.3)
        - **선의 두께**: 상관관계가 강할수록 굵음
        - **선의 스타일**: 실선(양의), 점선(음의)
        
        **📊 상관관계 막대그래프**
        - **가로 막대**: 각 장비 쌍의 상관관계
        - **막대 길이**: 상관계수 절댓값 (길수록 강함)
        - **색상**: 빨간색(양의), 파란색(음의)
        - **순서**: 상관관계가 강한 순서대로 정렬

        ### **🔍 산점도 (장비 비교)**
        - **X축**: 첫 번째 장비 사용량
        - **Y축**: 두 번째 장비 사용량
        - **패턴 해석**:
            - ↗️ 오른쪽 위로 향하는 점들: 양의 상관관계
            - ↖️ 왼쪽 위로 향하는 점들: 음의 상관관계
            - 🔀 점들이 흩어져 있음: 무상관
        - **상관계수**: 그래프 우상단에 표시
        
        **🥧 상관관계 분포**
        - **원형 차트**: 전체 상관관계의 강도별 분포
        - **색상**: 강한 양의(빨강) → 약한(노랑) → 음의(파랑)
        - **비율**: 각 강도별 상관관계가 차지하는 비율
        
        ### **💡 실용적 활용 팁**
                
        **높은 양의 상관관계 발견 시:**
        - 해당 폴대들을 같은 구역에 배치
        - 한 명의 간호사가 동시에 관리
        - 수액 재고를 함께 준비
        
        **높은 음의 상관관계 발견 시:**
        - 두 폴대를 다른 구역에 분리
        - 다른 간호사가 각각 담당
        - 대체 치료로 활용 가능성 검토
        
        **낮은 상관관계 발견 시:**
        - 각 폴대를 독립적으로 관리
        - 개별적인 사용량 예측 및 계획 수립
        """)
        
        if st.button("도움말 닫기", key="close_corr_help"):
            st.session_state.show_corr_help = False
            st.rerun()
    
    # 데이터 검증
    if 'filtered_clean' not in locals() or filtered_clean.empty:
        st.info("선택된 기간/장비 조건에 데이터가 없어 상관관계를 계산할 수 없습니다.")
    else:
        
        # 기존 상관관계 분석 코드
        corr_freq_label = st.sidebar.selectbox("상관관계 집계 간격", ["15분", "30분", "1시간"], index=2, key="corr_freq_select")
        freq_map = {"15분": "15T", "30분": "30T", "1시간": "1H"}
        freq = freq_map[corr_freq_label]

        df_corr = filtered_clean.copy()
        df_corr = df_corr.sort_values('timestamp')
        df_corr['prev_weight'] = df_corr.groupby('loadcel')['current_weight_history'].shift(1)
        df_corr['usage'] = (df_corr['prev_weight'] - df_corr['current_weight_history']).clip(lower=0)
        df_corr = df_corr.dropna(subset=['timestamp'])
        
        try:
            df_resampled = (df_corr.set_index('timestamp')
                                        .groupby('loadcel')
                                        .resample(freq)['usage']
                                        .sum()
                                        .reset_index())
            usage_wide = df_resampled.pivot(index='timestamp', columns='loadcel', values='usage').fillna(0)
            if usage_wide.shape[1] < 2:
                st.info("두 개 이상 장비가 있어야 상관관계를 계산할 수 있습니다.")
            else:
                corr_mat = usage_wide.corr()
                
                # 2x2 그리드로 그래프 배치
                col1, col2 = st.columns(2)
                
                with col1:
                    # 1. 네트워크 그래프 (상관관계가 높은 것만 연결)
                    st.subheader("🌐 상관관계 네트워크")
                    try:
                        import networkx as nx
                        import plotly.graph_objects as go
                        
                        # 상관관계가 높은 것만 연결 (임계값 0.3)
                        threshold = 0.3
                        edges = []
                        for i in range(len(corr_mat.columns)):
                            for j in range(i+1, len(corr_mat.columns)):
                                if abs(corr_mat.iloc[i,j]) > threshold:
                                    edges.append((corr_mat.columns[i], corr_mat.columns[j], corr_mat.iloc[i,j]))
                        
                        if edges:
                            G = nx.Graph()
                            for edge in edges:
                                G.add_edge(edge[0], edge[1], weight=edge[2])
                            
                            # 네트워크 레이아웃
                            pos = nx.spring_layout(G, k=1, iterations=50)
                            
                            # 노드 그리기
                            node_x = [pos[node][0] for node in G.nodes()]
                            node_y = [pos[node][1] for node in G.nodes()]
                            
                            # 네트워크 그래프 생성
                            fig_network = go.Figure()
                            
                            # 엣지 추가 (상관관계 강도에 따른 색상)
                            # 상관계수 절댓값에 따라 색상과 두께 결정
                            for edge in G.edges(data=True):
                                x0, y0 = pos[edge[0]]
                                x1, y1 = pos[edge[1]]
                                corr_strength = abs(edge[2]['weight'])
                                
                                # 상관관계 강도에 따른 색상 결정
                                if corr_strength > 0.7:
                                    color = 'red'  # 강한 양의 상관관계
                                    width = 4
                                elif corr_strength > 0.5:
                                    color = 'orange'  # 중간 양의 상관관계
                                    width = 3
                                elif corr_strength > 0.3:
                                    color = 'yellow'  # 약한 양의 상관관계
                                    width = 2
                                else:
                                    color = 'lightgray'  # 매우 약한 상관관계
                                    width = 1
                                
                                # 양의/음의 상관관계에 따른 선 스타일
                                line_style = 'solid' if edge[2]['weight'] > 0 else 'dash'
                                
                                fig_network.add_trace(go.Scatter(
                                    x=[x0, x1], y=[y0, y1],
                                    line=dict(width=width, color=color, dash=line_style),
                                    hoverinfo='text',
                                    hovertext=f"{edge[0]} ↔ {edge[1]}<br>상관계수: {edge[2]['weight']:.3f}",
                                    mode='lines',
                                    showlegend=False
                                ))
                            
                            # 노드 추가
                            fig_network.add_trace(go.Scatter(
                                x=node_x, y=node_y,
                                mode='markers+text',
                                marker=dict(size=20, color='lightblue', line=dict(width=2, color='darkblue')),
                                text=list(G.nodes()),
                                textposition="middle center",
                                hoverinfo='text'
                            ))
                            
                            fig_network.update_layout(
                                title=f"선의 색이 붉을수록 상관관계가 높습니다.",
                                showlegend=False,
                                hovermode='closest',
                                margin=dict(b=20,l=5,r=5,t=40),
                                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                width=400,
                                height=450
                            )
                            
                            st.plotly_chart(fig_network, use_container_width=True)
                        else:
                            st.info("임계값을 만족하는 상관관계가 없습니다.")
                    except Exception as e:
                        st.warning(f"네트워크 그래프 생성 오류: {e}")
                    
                    # 2. 막대그래프 (상관관계 계수)
                    st.subheader("📊 상관관계 막대그래프")
                    try:
                        # 상관관계를 1차원으로 변환
                        corr_pairs = []
                        for i in range(len(corr_mat.columns)):
                            for j in range(i+1, len(corr_mat.columns)):
                                corr_pairs.append({
                                    'pair': f"{corr_mat.columns[i]}-{corr_mat.columns[j]}",
                                    'correlation': corr_mat.iloc[i,j]
                                })
                        
                        corr_df = pd.DataFrame(corr_pairs)
                        corr_df = corr_df.sort_values('correlation', ascending=False)
                        
                        fig_bar = px.bar(
                            corr_df, 
                            x='correlation', 
                            y='pair',
                            orientation='h',
                            color='correlation',
                            color_continuous_scale='RdBu',
                            title="장비 간 상관관계 계수"
                        )
                        fig_bar.update_layout(
                            width=400,
                            height=450,
                            xaxis_title="상관계수",
                            yaxis_title="장비 쌍"
                        )
                        st.plotly_chart(fig_bar, use_container_width=True)
                    except Exception as e:
                        st.warning(f"막대그래프 생성 오류: {e}")
                
                with col2:
                    # 3. 산점도 (첫 번째 vs 두 번째 장비)
                    st.subheader("🔍 산점도 (장비 비교)")
                    try:
                        if len(corr_mat.columns) >= 2:
                            # 첫 번째와 두 번째 장비 선택
                            device1 = corr_mat.columns[0]
                            device2 = corr_mat.columns[1]
                            
                            # 해당 장비들의 사용량 데이터 추출
                            device1_data = usage_wide[device1]
                            device2_data = usage_wide[device2]
                            
                            # 산점도 생성
                            fig_scatter = px.scatter(
                                x=device1_data,
                                y=device2_data,
                                title=f"{device1} vs {device2} 사용량 산점도",
                                labels={'x': f'{device1} 사용량', 'y': f'{device2} 사용량'}
                            )
                            
                            # 상관계수 표시
                            corr_value = corr_mat.loc[device1, device2]
                            fig_scatter.add_annotation(
                                x=0.05, y=0.95, xref='paper', yref='paper',
                                text=f'상관계수: {corr_value:.3f}',
                                showarrow=False,
                                bgcolor='rgba(255,255,255,0.8)',
                                bordercolor='black',
                                borderwidth=1
                            )
                            
                            fig_scatter.update_layout(
                                width=400,
                                height=450
                            )
                            st.plotly_chart(fig_scatter, use_container_width=True)
                        else:
                            st.info("산점도를 그리려면 최소 2개 장비가 필요합니다.")
                    except Exception as e:
                        st.warning(f"산점도 생성 오류: {e}")
                    
                    # 4. 원형 차트 (상관관계 분포)
                    st.subheader("🥧 상관관계 분포")
                    try:
                        # 상관관계 강도별 분류
                        strong_pos = (corr_mat > 0.7).sum().sum() - len(corr_mat)  # 대각선 제외
                        moderate_pos = ((corr_mat > 0.3) & (corr_mat <= 0.7)).sum().sum()
                        weak = ((corr_mat > -0.3) & (corr_mat <= 0.3)).sum().sum()
                        moderate_neg = ((corr_mat < -0.3) & (corr_mat >= -0.7)).sum().sum()
                        strong_neg = (corr_mat < -0.7).sum().sum()
                        
                        categories = ['강한 양의 상관관계', '중간 양의 상관관계', '약한 상관관계', '중간 음의 상관관계', '강한 음의 상관관계']
                        values = [strong_pos, moderate_pos, weak, moderate_neg, strong_neg]
                        colors = ['red', 'orange', 'yellow', 'lightblue', 'blue']
                        
                        fig_pie = px.pie(
                            values=values,
                            names=categories,
                            title="상관관계 강도 분포",
                            color_discrete_sequence=colors
                        )
                        
                        fig_pie.update_layout(
                            width=400,
                            height=450
                        )
                        st.plotly_chart(fig_pie, use_container_width=True)
                    except Exception as e:
                        st.warning(f"원형 차트 생성 오류: {e}")
                
        except Exception as e:
            st.warning(f"상관관계 분석 중 오류가 발생했습니다: {e}")

with st.expander("무게 변화 추세 분석", expanded=False):
    # 도움말 섹션 추가 (expander 대신 버튼으로 토글)
    if "show_trend_help" not in st.session_state:
        st.session_state.show_trend_help = False
        
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("각 장비의 무게 변화 추세를 분석합니다")
    with col2:
        if st.button("❓ 도움말", key="help_trend_btn"):
            st.session_state.show_trend_help = not st.session_state.show_trend_help
    
    # 도움말 내용 표시
    if st.session_state.show_trend_help:
        st.markdown("---")
        col_help1, col_help2 = st.columns(2)
        with col_help1:
            st.markdown("# 📈 무게 변화 추세 분석 가이드")
            st.markdown("""
        **📊 무게 변화 추세 분석이란?**
        
        간단히 말하면: 링거폴대(수액 거치대)의 무게가 시간에 따라 어떻게 변화하는지 분석하는 기능입니다.
        
        **예시로 설명하면:**
        - 특정 폴대의 수액이 얼마나 빠르게 줄어들고 있는지?
        - 어떤 폴대가 가장 빠르게 수액을 소모하는지?
        - 수액 소모 속도가 일정한지, 아니면 변동이 있는지?
        
        **🎯 이 분석으로 무엇을 알 수 있나요?**
        
        1. **수액 소모 속도 예측**
           - 각 폴대별 수액이 얼마나 빨리 줄어드는지 파악
           - 수액 교체 시점을 미리 예측하여 계획 수립
        
        2. **장비별 효율성 비교**
           - 어떤 폴대가 가장 빠르게 수액을 소모하는지 비교
           - 환자별 치료 강도나 수액 종류에 따른 차이 분석
        
        3. **비정상 상황 감지**
           - 갑작스러운 수액 소모 속도 변화 감지
           - 누출이나 이상 상황 조기 발견
        
        **📈 기울기 해석 방법**
        
        기울기는 시간당 무게 변화량(g/시간)을 나타냅니다:
        
        🔴 **양의 기울기 (예: +50 g/시간)**
        - 무게가 시간이 지날수록 증가
        - 수액이 추가로 투입되고 있음을 의미
        - 정상적인 치료 과정에서 발생 가능
        
        🟢 **음의 기울기 (예: -100 g/시간)**
        - 무게가 시간이 지날수록 감소
        - 수액이 소모되고 있음을 의미
        - 일반적인 치료 상황
        
        🔵 **0에 가까운 기울기 (예: ±5 g/시간)**
        - 무게 변화가 거의 없음
        - 수액 투입과 소모가 균형을 이루고 있음
        - 안정적인 치료 상태
        
        **💡 실제 활용 팁**
        
        **높은 음의 기울기 발견 시:**
        - 수액 교체 시점을 앞당겨야 할 수 있음
        - 환자 상태 변화 여부 확인 필요
        - 치료 강도 조정 고려
        
        **갑작스러운 기울기 변화 시:**
        - 누출이나 이상 상황 점검
        - 환자 상태 급변 여부 확인
        - 의료진 즉시 호출 고려
        """)
            
        with col_help2:
            st.markdown("# 📊 그래프 해석 가이드")
            st.markdown("""
        ### **📋 기울기 요약 테이블**
        - **장비**: 각 링거폴대 번호
        - **기울기(g/시간)**: 시간당 무게 변화량
        - **정렬**: 기울기 값에 따라 오름차순 정렬
        
        ### **📈 무게 변화 추세 상세 그래프**
        - **파란색 점과 선**: 실제 측정된 무게 데이터
        - **빨간색 선**: 수학적으로 계산된 추세선
        - **X축**: 시간 (가로축)
        - **Y축**: 무게(g) (세로축)
        
        **🔍 그래프 패턴 해석**
        
        **직선에 가까운 추세선:**
        - 수액 소모가 일정한 속도로 진행
        - 예측 가능한 수액 교체 시점
        
        **곡선 형태의 추세선:**
        - 수액 소모 속도가 시간에 따라 변화
        - 치료 강도나 환자 상태 변화 가능성
        
        **점들이 추세선에서 많이 벗어남:**
        - 불규칙한 수액 소모 패턴
        - 측정 오류나 외부 요인 영향 가능성
        
        ### **💡 실용적 활용 팁**
                
        **기울기 값 활용:**
        - **-200 g/시간**: 매우 빠른 수액 소모, 주의 필요
        - **-100 g/시간**: 일반적인 수액 소모 속도
        - **-50 g/시간**: 느린 수액 소모, 안정적
        - **+100 g/시간**: 수액 추가 투입 중
        
        **무게 변화 추세 변화 감지:**
        - 기울기가 급격히 변하면 즉시 확인
        - 예상과 다른 패턴 발견 시 의료진 문의
        """)
        
        if st.button("도움말 닫기", key="close_trend_help"):
            st.session_state.show_trend_help = False
            st.rerun()
    
    # 기존 트렌드 분석 코드
    if filtered_clean.empty:
        st.info("데이터가 없어 트렌드를 계산할 수 없습니다.")
    else:
        trend_rows = []
        for loadcel_id, grp in filtered_clean.sort_values('timestamp').groupby('loadcel'):
            if len(grp) < 2:
                continue
            t_hours = (grp['timestamp'] - grp['timestamp'].min()).dt.total_seconds() / 3600.0
            y = grp['current_weight_history']
            try:
                slope, intercept = np.polyfit(t_hours, y, 1)
            except Exception:
                continue
            trend_rows.append({
                'loadcel': loadcel_id,
                'slope_g_per_hour': float(slope)
            })
        trend_df = pd.DataFrame(trend_rows)
        if trend_df.empty:
            st.info("기울기를 계산할 수 있는 충분한 데이터가 없습니다.")
        else:
            trend_df = trend_df.sort_values('slope_g_per_hour')
            st.dataframe(trend_df.rename(columns={'loadcel': '장비', 'slope_g_per_hour': '기울기(g/시간)'}), use_container_width=True)

            loadcel_options = filtered_clean['loadcel'].unique().tolist()
            sel = st.selectbox("무게 변화 추세 상세 보기 - 장비 선택", loadcel_options)
            grp = filtered_clean[filtered_clean['loadcel'] == sel].sort_values('timestamp')
            if len(grp) >= 2:
                t_hours = (grp['timestamp'] - grp['timestamp'].min()).dt.total_seconds() / 3600.0
                y = grp['current_weight_history']
                slope, intercept = np.polyfit(t_hours, y, 1)
                yhat = slope * t_hours + intercept
                try:
                    import plotly.graph_objs as go
                    fig2 = go.Figure()
                    fig2.add_trace(go.Scatter(x=grp['timestamp'], y=y, mode='markers+lines', name='무게'))
                    fig2.add_trace(go.Scatter(x=grp['timestamp'], y=yhat, mode='lines', name='추세선', line=dict(color='red')))
                    fig2.update_layout(title=f"장비 {sel} - 무게 추이 및 추세선 (기울기 {slope:.2f} g/시간)", xaxis_title="시간", yaxis_title="무게(g)")
                    st.plotly_chart(fig2, use_container_width=True)
                except Exception:
                    st.line_chart(pd.DataFrame({'시간': grp['timestamp'], '무게(g)': y}).set_index('시간'))

with st.expander("이상치 심화 분석", expanded=False):
    # 도움말 섹션 추가 (expander 대신 버튼으로 토글)
    if "show_outlier_help" not in st.session_state:
        st.session_state.show_outlier_help = False
        
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("비정상적인 무게 변화를 자동으로 감지합니다")
    with col2:
        if st.button("❓ 도움말", key="help_outlier_btn"):
            st.session_state.show_outlier_help = not st.session_state.show_outlier_help
    
    # 도움말 내용 표시
    if st.session_state.show_outlier_help:
        st.markdown("---")
        col_help1, col_help2 = st.columns(2)
        with col_help1:
            st.markdown("# 🚨 이상치 자동 감지 가이드")
            st.markdown("""
        **📊 이상치 심화 분석이란?**
        
        간단히 말하면: 링거폴대(수액 거치대)의 무게 변화에서 정상 범위를 벗어나는 비정상적인 변화를 자동으로 찾아내는 기능입니다.
        
        **예시로 설명하면:**
        - 갑작스러운 무게 급증이나 급감이 발생했는지?
        - 측정 오류나 외부 요인에 의한 비정상 변화가 있는지?
        - 환자 상태 급변으로 인한 수액 소모 패턴 변화가 있는지?
        
        **🎯 이 분석으로 무엇을 알 수 있나요?**
        
        1. **비정상 상황 조기 발견**
           - 수액 누출이나 이상 상황을 빠르게 감지
           - 환자 상태 급변 시 즉시 대응 가능
           - 장비 오작동이나 측정 오류 조기 발견
        
        2. **데이터 품질 향상**
           - 측정 오류나 외부 요인에 의한 데이터 제거
           - 정확한 통계 분석을 위한 깨끗한 데이터 확보
           - 신뢰할 수 있는 분석 결과 도출
        
        3. **예방적 관리**
           - 이상 패턴의 조기 경고로 사전 대응
           - 장비 유지보수 시점 예측
           - 안전한 치료 환경 조성
        
        **📈 감지 방법별 특징**
        
        **🔍 이동표준편차 방법:**
        - 일정 기간(윈도우) 내의 평균과 표준편차를 기준으로 이상치 판단
        - 지역적 변화에 민감하게 반응
        - 급격한 단기 변화를 잘 감지
        
        **📊 ARIMA 잔차 방법:**
        - 시계열 모델의 예측값과 실제값의 차이(잔차)를 분석
        - 전체적인 패턴을 고려한 이상치 판단
        - 장기적이고 복잡한 패턴 변화를 잘 감지
        
        **💡 임계값(시그마) 설정 가이드**
        
        **🔴 2.0 시그마**: 매우 민감하게 감지
        - 작은 변화도 이상치로 분류
        - 많은 이상치가 감지될 수 있음
        
        **🟠 3.0 시그마**: 일반적인 설정 (권장)
        - 적절한 수준의 이상치 감지
        - 균형잡힌 결과 제공
        
        **🟢 4.0~5.0 시그마**: 보수적으로 감지
        - 확실한 이상치만 감지
        - 중요한 변화를 놓칠 수 있음
        """)
            
        with col_help2:
            st.markdown("# 📊 그래프 해석 가이드")
            st.markdown("""
        ### **📋 이상치 감지 결과**
        - **감지된 이상치 개수**: 비정상으로 판단된 데이터 포인트 수
        - **이상치 비율**: 전체 데이터 대비 이상치의 비율
        
        ### **📈 이상치 시각화 그래프**
        - **파란색 선**: 정상적인 무게 변화 추이
        - **빨간색/주황색 점**: 감지된 이상치 데이터
        - **X축**: 시간 (가로축)
        - **Y축**: 무게(g) (세로축)
        
        **🔍 그래프 패턴 해석**
        
        **이상치가 적게 분포:**
        - 정상적인 치료 과정
        - 안정적인 환자 상태
        - 장비 정상 작동
        
        **이상치가 많이 분포:**
        - 불안정한 치료 상황
        - 환자 상태 급변 가능성
        - 장비 오작동 의심
        
        **이상치가 특정 구간에 집중:**
        - 해당 시간대에 특별한 상황 발생
        - 치료 강도 변화나 외부 요인 영향
        - 의료진 개입이나 치료 변경 시점
        
        ### **💡 실용적 활용 팁**
                
        **이상치 감지 시 대응:**
        - 즉시 해당 장비 상태 점검
        - 환자 상태 변화 여부 확인
        - 의료진에게 상황 보고
        
        **윈도우 크기 조정:**
        - **작은 윈도우(5-15분)**: 급격한 변화에 민감
        - **중간 윈도우(15-30분)**: 일반적인 상황에 적합
        - **큰 윈도우(30-60분)**: 장기적 변화에 집중
        
        **정기적 모니터링:**
        - 이상치 패턴의 변화 추이 관찰
        - 계절성이나 주기성 있는 이상치 패턴 파악
        - 예방적 관리 계획 수립에 활용
        """)
        
        if st.button("도움말 닫기", key="close_outlier_help"):
            st.session_state.show_outlier_help = False
            st.rerun()
    
    # 기존 이상치 자동 감지 코드
    if filtered_clean.empty:
        st.info("데이터가 없어 이상치 탐지를 수행할 수 없습니다.")
    else:
        od_method = st.sidebar.selectbox("이상치 방법", ["이동표준편차", "ARIMA 잔차"], index=0, key="od_method")
        threshold_sigma = st.sidebar.slider("임계 기준(시그마)", 2.0, 5.0, 3.0, 0.5, key="od_sigma")
        single = st.selectbox("장비 선택(단일 감지)", filtered_clean['loadcel'].unique().tolist())
        series = filtered_clean[filtered_clean['loadcel'] == single].sort_values('timestamp')
        if len(series) < 10:
            st.info("이상치 분석을 위한 데이터가 충분하지 않습니다.")
        else:
            s = series[['timestamp', 'current_weight_history']].dropna()
            s = s.set_index('timestamp').asfreq('T')  # 1분 간격 보간
            s['current_weight_history'] = s['current_weight_history'].interpolate(limit_direction='both')
            if od_method == "이동표준편차":
                win = st.sidebar.slider("윈도우 크기(분)", 5, 60, 15, 5, key="od_win")
                roll_mean = s['current_weight_history'].rolling(f'{win}T').mean()
                roll_std = s['current_weight_history'].rolling(f'{win}T').std().fillna(0)
                z = (s['current_weight_history'] - roll_mean).abs() / (roll_std.replace(0, np.nan))
                outlier_mask = z > threshold_sigma
                outliers = s[outlier_mask]
                st.write(f"감지된 이상치: {len(outliers)}개")
                try:
                    import plotly.graph_objs as go
                    fig3 = go.Figure()
                    fig3.add_trace(go.Scatter(x=s.index, y=s['current_weight_history'], mode='lines', name='무게'))
                    fig3.add_trace(go.Scatter(x=outliers.index, y=outliers['current_weight_history'], mode='markers', name='이상치', marker=dict(color='red', size=8)))
                    st.plotly_chart(fig3, use_container_width=True)
                except Exception:
                    st.line_chart(s['current_weight_history'])
            else:
                order_p = st.sidebar.slider("ARIMA p", 0, 3, 1, key="od_arima_p")
                order_d = st.sidebar.slider("ARIMA d", 0, 2, 0, key="od_arima_d")
                order_q = st.sidebar.slider("ARIMA q", 0, 3, 1, key="od_arima_q")
                try:
                    model = ARIMA(s['current_weight_history'], order=(order_p, order_d, order_q))
                    res = model.fit()
                    resid = res.resid
                    resid_z = (resid - resid.mean()) / (resid.std() + 1e-9)
                    outlier_mask = resid_z.abs() > threshold_sigma
                    outliers = s[outlier_mask]
                    st.write(f"감지된 이상치: {int(outlier_mask.sum())}개")
                    import plotly.graph_objs as go
                    fig4 = go.Figure()
                    fig4.add_trace(go.Scatter(x=s.index, y=s['current_weight_history'], mode='lines', name='무게'))
                    fig4.add_trace(go.Scatter(x=outliers.index, y=outliers['current_weight_history'], mode='markers', name='이상치', marker=dict(color='orange', size=8)))
                    st.plotly_chart(fig4, use_container_width=True)
                except Exception as e:
                    st.warning(f"ARIMA 모델 적합 중 오류: {e}")

with st.expander("계절성/주기성 분석", expanded=False):
    # 도움말 섹션 추가 (expander 대신 버튼으로 토글)
    if "show_seasonal_help" not in st.session_state:
        st.session_state.show_seasonal_help = False
        
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("수액 사용량의 주기적 패턴을 분석합니다")
    with col2:
        if st.button("❓ 도움말", key="help_seasonal_btn"):
            st.session_state.show_seasonal_help = not st.session_state.show_seasonal_help
    
    # 도움말 내용 표시
    if st.session_state.show_seasonal_help:
        st.markdown("---")
        col_help1, col_help2 = st.columns(2)
        with col_help1:
            st.markdown("# 🌊 계절성/주기성 분석 가이드")
            st.markdown("""
        **📊 계절성/주기성 분석이란?**
        
        간단히 말하면: 링거폴대(수액 거치대)의 사용량이 일정한 주기로 반복되는 패턴을 찾아내는 기능입니다.
        
        **🤔 왜 '계절성/주기성'이라는 이름을 사용할까요?**
        
        **계절성(Seasonality)**: 
        - 계절(겨울, 봄, 여름, 가을)처럼 일정한 주기로 반복되는 패턴
        - 의료 환경에서는 '계절'이 아니라 '시간의 주기'를 의미
        - 예: 하루(24시간), 일주일(7일), 한 달(30일) 등
        
        **주기성(Periodicity)**:
        - 일정한 간격으로 반복되는 규칙적인 패턴
        - 수액 사용량이 특정 시간마다 늘어나거나 줄어드는 현상
        - 의료진의 업무 스케줄이나 환자 치료 패턴과 연관
        
        **계절성**: 시간의 흐름에 따른 반복 패턴
        - 하루 중 시간대별 패턴 (아침, 점심, 저녁, 밤)
        - 일주일 중 요일별 패턴 (월요일, 화요일...)
        - 한 달 중 주차별 패턴 (첫째 주, 둘째 주...)
        
        **주기성**: 일정한 간격으로 반복되는 패턴
        - 간호사 교대 시간 (8시간, 12시간 주기)
        - 의료진 회의 시간 (1시간, 2시간 주기)
        - 환자 치료 일정 (4시간, 6시간 주기)
        
        **예시로 설명하면:**
        - 하루 중 특정 시간대에 수액 사용량이 늘어나는지?
        - 일주일 중 특정 요일에 사용량이 많아지는지?
        - 한 달 중 특정 시기에 사용량이 변동되는지?
        
        **🎯 이 분석으로 무엇을 알 수 있나요?**
        
        1. **업무 패턴 파악**
           - 간호사 교대 시간대별 수액 관리 패턴 이해
           - 의료진의 일과 중 바쁜 시간대 파악
           - 환자 치료 일정의 주기성 파악
        
        2. **자원 계획 최적화**
           - 수액 재고 준비 시점 예측
           - 인력 배치 최적화를 위한 시간대별 필요 인원 파악
           - 장비 점검 및 유지보수 시점 계획
        
        3. **비정상 패턴 감지**
           - 예상과 다른 주기성 패턴 발견 시 이상 상황 의심
           - 계절성 변화가 없는 경우 정상적이지 않을 수 있음
           - 갑작스러운 패턴 변화 시 즉시 대응 가능
        
        **📈 주기 설정 가이드**
        
        **🔴 60분 (1시간)**: 시간대별 패턴
        - 하루 중 시간대별 사용량 변화 분석
        - 간호사 교대 시간대 영향 파악
        
        **🟠 120-360분 (2-6시간)**: 반일/일일 패턴
        - 오전/오후 사용량 차이 분석
        - 식사 시간대나 치료 시간대 영향 파악
        
        **🟡 720분 (12시간)**: 반일 패턴
        - 주/야간 교대별 사용량 차이 분석
        - 12시간 주기로 반복되는 패턴 파악
        
        **🟢 1440분 (24시간)**: 일일 패턴
        - 하루 단위로 반복되는 패턴 분석
        - 요일별 사용량 차이 파악
        
        **💡 실제 활용 팁**
        
        **높은 계절성이 발견되면:**
        - 해당 주기에 맞춰 수액 재고 준비
        - 인력 배치를 주기성에 맞춰 조정
        - 예측 가능한 업무 계획 수립
        
        **낮은 계절성이 발견되면:**
        - 일정한 수액 소모로 안정적인 관리 가능
        - 예측이 어려워 유연한 대응 체계 필요
        - 비정상 상황일 가능성 검토
        """)
            
        with col_help2:
            st.markdown("# 📊 그래프 해석 가이드")
            st.markdown("""
        ### **📋 STL 분해 결과**
        - **추세(Trend)**: 장기적인 변화 방향
        - **계절성(Seasonal)**: 주기적으로 반복되는 패턴
        - **잔차(Residual)**: 설명되지 않는 나머지 변화
        
        ### **📈 STL 분해 그래프**
        - **파란색 선(추세)**: 전체적인 증가/감소 방향
        - **주황색 선(계절성)**: 주기적으로 반복되는 패턴
        - **초록색 선(잔차)**: 예측할 수 없는 랜덤한 변화
        
        **🔍 그래프 패턴 해석**
        
        **추세선이 일정하게 감소:**
        - 수액 소모가 지속적으로 진행
        - 치료 과정이 정상적으로 진행 중
        
        **계절성 선이 뚜렷한 파형:**
        - 명확한 주기적 패턴 존재
        - 예측 가능한 사용량 변화
        
        **잔차가 작고 안정적:**
        - 모델이 데이터를 잘 설명
        - 신뢰할 수 있는 분석 결과
        
        **잔차가 크고 불규칙:**
        - 예측하기 어려운 변화 많음
        - 외부 요인이나 비정상 상황 영향
        
        ### **💡 실용적 활용 팁**
                
        **주기별 활용:**
        - **1시간 주기**: 시간대별 인력 배치 계획
        - **12시간 주기**: 주/야간 교대별 업무량 예측
        - **24시간 주기**: 일일 수액 소모량 예측
        
        **패턴 변화 감지:**
        - 계절성 패턴이 사라지면 즉시 확인
        - 새로운 주기성 패턴 발견 시 원인 분석
        - 예상과 다른 패턴 시 의료진 문의
        """)
        
        if st.button("도움말 닫기", key="close_seasonal_help"):
            st.session_state.show_seasonal_help = False
            st.rerun()
    
    # 기존 계절성/주기성 분석 코드
    if df.empty:
        st.info("데이터가 없어 계절성 분석을 수행할 수 없습니다.")
    else:
        sel2 = st.selectbox("장비 선택(계절성)", df['loadcel'].unique().tolist(), key="season_sel")
        series2 = df[df['loadcel'] == sel2].sort_values('timestamp')
        if len(series2) < 24:
            st.info("분해를 위해 더 긴 시계열이 필요합니다.")
        else:
            # 맨 뒤의 데이터 1개 제외
            series2_clean = series2.iloc[:-1] if len(series2) > 1 else series2
            
            ts = series2_clean[['timestamp', 'current_weight_history']].dropna()
            ts = ts.set_index('timestamp').asfreq('T')
            ts['current_weight_history'] = ts['current_weight_history'].interpolate(limit_direction='both')
            period_minutes = st.sidebar.selectbox("주기(분)", [60, 120, 180, 240, 360, 720, 1440], index=6, key="stl_period")
            try:
                stl = STL(ts['current_weight_history'], period=period_minutes)
                res = stl.fit()
                comp = pd.DataFrame({
                    'trend': res.trend,
                    'seasonal': res.seasonal,
                    'resid': res.resid
                }, index=ts.index)
                import plotly.graph_objs as go
                fig5 = go.Figure()
                fig5.add_trace(go.Scatter(x=comp.index, y=comp['trend'], name='추세'))
                fig5.add_trace(go.Scatter(x=comp.index, y=comp['seasonal'], name='계절성'))
                fig5.add_trace(go.Scatter(x=comp.index, y=comp['resid'], name='잔차'))
                fig5.update_layout(title=f"장비 {sel2} - STL 분해(주기 {period_minutes}분)")
                st.plotly_chart(fig5, use_container_width=True)
            except Exception as e:
                st.warning(f"STL 분해 중 오류: {e}")

with st.expander("장비 군집화", expanded=False):
    # 도움말 섹션 추가 (expander 대신 버튼으로 토글)
    if "show_clustering_help" not in st.session_state:
        st.session_state.show_clustering_help = False
        
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("사용 패턴이 비슷한 장비들을 그룹으로 분류합니다")
    with col2:
        if st.button("❓ 도움말", key="help_clustering_btn"):
            st.session_state.show_clustering_help = not st.session_state.show_clustering_help
    
    # 도움말 내용 표시
    if st.session_state.show_clustering_help:
        st.markdown("---")
        col_help1, col_help2 = st.columns(2)
        with col_help1:
            st.markdown("# 🎯 장비 군집화 가이드")
            st.markdown("""
        **📊 장비 군집화(Clustering)란?**
        
        간단히 말하면: 여러 링거폴대(수액 거치대)를 사용 패턴이 비슷한 그룹으로 자동으로 분류하는 기능입니다.
        
        해당 기능은 군집화 알고리즘 중 가장 대중적인 KMeans 알고리즘을 사용합니다.
        
        **🤔 왜 '클러스터링'이라는 이름을 사용할까요?**
        
        **클러스터(Cluster)**: 
        - 비슷한 특성을 가진 것들을 하나의 그룹으로 묶는 것
        - 의료 환경에서는 '사용 패턴이 비슷한 장비들의 집합'을 의미
        - 예: 고사용량 장비들, 저사용량 장비들, 불규칙 사용 장비들
        
        **KMeans**: 
        - 가장 널리 사용되는 클러스터링 알고리즘
        - K개의 그룹으로 나누어 각 그룹의 중심점을 찾아 분류
        - 수학적으로 최적화된 그룹 분류 방법
        
        
        
        **클러스터링의 목적**:
        - 비슷한 사용 패턴을 가진 장비들을 그룹화
        - 각 그룹별로 차별화된 관리 전략 수립
        - 효율적인 자원 배분 및 인력 배치 계획
        
        **예시로 설명하면:**
        - 어떤 장비들이 모두 높은 사용량을 보이는지?
        - 어떤 장비들이 불규칙한 사용 패턴을 보이는지?
        - 어떤 장비들이 안정적으로 일정한 사용량을 유지하는지?
        
        **🎯 이 분석으로 무엇을 알 수 있나요?**
        
        1. **장비 그룹별 특성 파악**
           - 고사용량 그룹: 집중 관리가 필요한 장비들
           - 저사용량 그룹: 효율성 개선이 필요한 장비들
           - 불규칙 그룹: 예측이 어려운 장비들
        
        2. **관리 전략 최적화**
           - 각 그룹별로 차별화된 점검 주기 설정
           - 그룹별 특성에 맞는 인력 배치 계획
           - 예방적 유지보수 일정 수립
        
        3. **자원 계획 효율화**
           - 그룹별 수액 재고 준비량 차별화
           - 그룹별 장비 교체 우선순위 결정
           - 예산 배분의 최적화
        
        **📈 클러스터 개수(k) 설정 가이드**
        
        **🔴 2개 클러스터**: 기본적인 분류
        - 고사용량 vs 저사용량
        - 안정적 vs 불안정적
        
        **🟠 3-4개 클러스터**: 세밀한 분류
        - 고/중/저 사용량
        - 안정적/보통/불안정적
        
        **🟢 5개 이상**: 매우 세밀한 분류
        - 세부적인 패턴 차이 분석
        - 많은 장비가 있을 때 유용
        """)
            
        with col_help2:
            st.markdown("# 📊 그래프 해석 가이드")
            st.markdown("""
        ### **📋 클러스터링 결과 테이블**
        - **장비**: 각 링거폴대 번호
        - **평균 사용량**: 시간당 평균 수액 소모량(kg)
        - **표준편차**: 사용량의 변동성(높을수록 불규칙)
        - **일별 평균 사용량**: 하루 평균 총 사용량(kg)
        - **클러스터**: 자동으로 분류된 그룹 번호
        
        ### **📈 클러스터링 산점도**
        - **X축**: 평균 사용량 (가로축)
        - **Y축**: 표준편차 (세로축)
        - **색상**: 각 클러스터 그룹 (다른 색 = 다른 그룹)
        - **점**: 각 링거폴대
        
        **🔍 그래프 패턴 해석**
        
        **오른쪽 위 영역 (높은 평균 + 높은 표준편차)**:
        - 고사용량이면서 불규칙한 패턴
        - 집중 관리가 필요한 장비들
        - 예측이 어려워 주의 필요
        
        **오른쪽 아래 영역 (높은 평균 + 낮은 표준편차)**:
        - 고사용량이면서 안정적인 패턴
        - 예측 가능한 고사용량 장비
        - 계획적 관리 가능
        
        **왼쪽 위 영역 (낮은 평균 + 높은 표준편차)**:
        - 저사용량이면서 불규칙한 패턴
        - 비정상 상황 의심
        - 점검 및 원인 분석 필요
        
        **왼쪽 아래 영역 (낮은 평균 + 낮은 표준편차)**:
        - 저사용량이면서 안정적인 패턴
        - 효율적이지만 개선 여지 있음
        - 안정적인 관리 가능
        
        ### **💡 실용적 활용 팁**
                
        **클러스터별 관리 전략**:
        - **클러스터 0**: 기본 관리 (일반적인 점검 주기)
        - **클러스터 1**: 중간 관리 (정기적 모니터링)
        - **클러스터 2**: 집중 관리 (빈번한 점검)
        - **클러스터 3+**: 특별 관리 (개별 맞춤형 전략)
        
        **클러스터 변화 모니터링**:
        - 장비가 다른 클러스터로 이동하면 패턴 변화 의심
        - 새로운 클러스터가 생기면 새로운 패턴 발견
        - 클러스터가 사라지면 패턴 통합 또는 변화
        """)
        
        if st.button("도움말 닫기", key="close_clustering_help"):
            st.session_state.show_clustering_help = False
            st.rerun()
    
    # 기존 장비 클러스터링 코드
    if df.empty:
        st.info("데이터가 없어 클러스터링을 수행할 수 없습니다.")
    else:
        # 장비별 특성 벡터: 평균 사용량(kg), 변동성(표준편차, kg), 일별 평균 사용량(kg)의 평균
        feat = filtered_clean.copy()
        if feat.empty:
            st.info("선택한 기간/장비에 데이터가 없습니다.")
        else:
            feat = feat.sort_values('timestamp')
            feat['prev_weight'] = feat.groupby('loadcel')['current_weight_history'].shift(1)
            feat['usage'] = (feat['prev_weight'] - feat['current_weight_history']).clip(lower=0) / 1000
            agg = feat.groupby('loadcel').agg(
                mean_usage=('usage', 'mean'),
                std_usage=('usage', 'std')
            ).fillna(0)
            daily = feat.copy()
            daily['date'] = daily['timestamp'].dt.date
            daily_agg = daily.groupby(['loadcel', 'date'])['usage'].sum().groupby('loadcel').mean()
            agg['daily_mean_usage'] = daily_agg
            agg = agg.fillna(0)
            # 스케일링 후 KMeans
            max_k = min(10, max(2, len(agg)))
            default_k = min(4, max(2, len(agg)))
            if max_k == 2:
                chosen_k = 2
            else:
                chosen_k = st.sidebar.slider("클러스터 개수(k)", 2, max_k, default_k, 1, key="kmeans_k")
            try:
                scaler = StandardScaler()
                X = scaler.fit_transform(agg.values)
                km = KMeans(n_clusters=chosen_k, n_init='auto', random_state=42)
                labels = km.fit_predict(X)
                agg['cluster'] = labels
                st.dataframe(agg.reset_index().rename(columns={'loadcel': '장비'}), use_container_width=True)
                # 2D 시각화: PCA 대신 2개 특성 산점(평균 vs 표준편차)
                fig6 = px.scatter(agg.reset_index(), x='mean_usage', y='std_usage', color=agg['cluster'].astype(str), hover_data=['loadcel'])
                fig6.update_layout(title="장비 클러스터링")
                
                # 점 크기를 더 크게 설정
                fig6.update_traces(
                    marker=dict(size=15),  # 기본 크기 8에서 15로 증가
                    selector=dict(mode='markers')
                )
                
                st.plotly_chart(fig6, use_container_width=True)
            except Exception as e:
                st.warning(f"클러스터링 중 오류: {e}")

with st.expander("요일-시간대 히트맵 (평균 사용량)", expanded=False):
    # 도움말 섹션 추가 (expander 대신 버튼으로 토글)
    if "show_heatmap_help" not in st.session_state:
        st.session_state.show_heatmap_help = False
        
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("요일과 시간대별 수액 사용량 패턴을 색상으로 표시합니다")
    with col2:
        if st.button("❓ 도움말", key="help_heatmap_btn"):
            st.session_state.show_heatmap_help = not st.session_state.show_heatmap_help
    
    # 도움말 내용 표시
    if st.session_state.show_heatmap_help:
        st.markdown("---")
        col_help1, col_help2 = st.columns(2)
        with col_help1:
            st.markdown("# 📅 요일-시간대 히트맵 가이드")
            st.markdown("""
        **📊 요일-시간대 히트맵이란?**
        
        간단히 말하면: 일주일 중 각 요일과 하루 중 각 시간대별로 수액 사용량이 얼마나 많은지를 색상의 진하기로 표시하는 기능입니다.
        
        **🤔 왜 '히트맵(Heatmap)'이라는 이름을 사용할까요?**
        
        **히트맵(Heatmap)**: 
        - 데이터의 값에 따라 색상의 진하기나 밝기를 다르게 표시하는 시각화 방법
        - '열(Heat)'이 많은 부분은 진한 색, 적은 부분은 연한 색으로 표현
        - 의료 환경에서는 '사용량이 많은 시간대'를 한눈에 파악 가능
        
        
        
        **요일별 패턴**:
        - 월요일~금요일: 평일 업무 패턴 (의료진 정기 근무)
        - 토요일~일요일: 주말 업무 패턴 (응급 상황 위주)
        - 공휴일: 특별한 패턴 (계절성 영향)
        
        **시간대별 패턴**:
        - 새벽(0-6시): 야간 응급 상황
        - 오전(6-12시): 아침 진료 및 수액 투여
        - 오후(12-18시): 오후 진료 및 수액 교체
        - 저녁(18-24시): 야간 교대 및 정리
        
        **예시로 설명하면:**
        - 월요일 오전 9시에 수액 사용량이 가장 많은 이유는?
        - 주말 밤에 사용량이 적은 이유는?
        - 평일 오후 2시에 사용량이 증가하는 패턴은?
        
        **🎯 이 분석으로 무엇을 알 수 있나요?**
        
        1. **업무 패턴 최적화**
           - 가장 바쁜 시간대와 한가한 시간대 파악
           - 간호사 교대 시간대별 필요 인원 계획
           - 수액 재고 준비 시점 최적화
        
        2. **자원 배분 효율화**
           - 시간대별 수액 소모량 예측
           - 장비 점검 및 유지보수 일정 계획
           - 응급 상황 대비 체계 구축
        
        3. **비정상 패턴 감지**
           - 예상과 다른 시간대별 사용량 변화
           - 특정 요일에만 발생하는 이상 패턴
           - 계절성이나 이벤트성 변화 영향
        
        **📈 색상 해석 가이드**
        
        **🔵 파란색 계열 (Blues 색상 스케일)**:
        - **연한 파란색**: 사용량 적음 (0에 가까움)
        - **중간 파란색**: 사용량 보통 (평균 수준)
        - **진한 파란색**: 사용량 많음 (높은 수준)
        - **가장 진한 파란색**: 사용량 매우 많음 (최고 수준)
        """)
            
        with col_help2:
            st.markdown("# 📊 그래프 해석 가이드")
            st.markdown("""
        ### **📋 히트맵 구조**
        - **X축 (가로)**: 시간대 (0시~23시)
        - **Y축 (세로)**: 요일 (월요일=0 ~ 일요일=6)
        - **색상**: 각 셀의 수액 사용량 (kg 단위)
        - **숫자**: 실제 사용량 값 (자동 표시)
        
        ### **🔍 패턴 해석 방법**
        
        **가로 방향 패턴 (시간대별)**:
        - **새벽 시간대 (0-6시)**: 일반적으로 사용량 적음
        - **오전 시간대 (6-12시)**: 진료 시작으로 사용량 증가
        - **오후 시간대 (12-18시)**: 진료 피크로 사용량 최대
        - **저녁 시간대 (18-24시)**: 진료 종료로 사용량 감소
        
        **세로 방향 패턴 (요일별)**:
        - **월요일 (0)**: 주말 축적된 수요로 사용량 많음
        - **화-목요일 (1-3)**: 안정적인 평일 패턴
        - **금요일 (4)**: 주말 대비로 사용량 증가
        - **토-일요일 (5-6)**: 응급 위주로 사용량 적음
        
        **🔍 특별한 패턴 해석**
        
        **높은 사용량 패턴 (진한 파란색)**:
        - 해당 시간대에 집중적인 치료 진행
        - 간호사 교대 시간과 일치하는지 확인
        - 예상 가능한 패턴인지 검토
        
        **낮은 사용량 패턴 (연한 파란색)**:
        - 해당 시간대에 치료 활동 적음
        - 정상적인 업무 패턴인지 확인
        - 비정상 상황일 가능성 검토
        
        ### **💡 실용적 활용 팁**
                
        **업무 계획 수립**:
        - **고사용량 시간대**: 추가 인력 배치 고려
        - **저사용량 시간대**: 장비 점검 및 유지보수 수행
        - **주말 패턴**: 응급 대응 체계 점검
        
        **자원 관리**:
        - **수액 재고**: 고사용량 시간대 대비 재고 확보
        - **장비 배치**: 사용량 패턴에 따른 최적 위치 선정
        - **인력 배치**: 업무량에 따른 교대 시간 조정
        """)
        
        if st.button("도움말 닫기", key="close_heatmap_help"):
            st.session_state.show_heatmap_help = False
            st.rerun()
    
    # 기존 요일-시간대 히트맵 코드
    if filtered_clean.empty:
        st.info("데이터가 없어 히트맵을 만들 수 없습니다.")
    else:
        tmp2 = filtered_clean.copy().sort_values('timestamp')
        tmp2['prev_weight'] = tmp2.groupby('loadcel')['current_weight_history'].shift(1)
        tmp2['usage'] = (tmp2['prev_weight'] - tmp2['current_weight_history']).clip(lower=0)  # kg 단위 유지
        tmp2['hour'] = tmp2['timestamp'].dt.hour
        tmp2['weekday'] = tmp2['timestamp'].dt.weekday
        heat = tmp2.groupby(['weekday', 'hour'])['usage'].mean().reset_index()
        heat_pivot = heat.pivot(index='weekday', columns='hour', values='usage').fillna(0)
        
        # kg을 g으로 변환 (1000 곱하기)
        heat_pivot_g = heat_pivot * 1000
        
        figh = px.imshow(heat_pivot_g, text_auto=True, color_continuous_scale='Blues')
        figh.update_layout(title="요일-시간대 평균 사용량(g)")
        
        # 히트맵 글자 크기 증가
        figh.update_traces(
            textfont=dict(size=30),  # 기본 크기에서 증가
            selector=dict(type='heatmap')
        )
        
        st.plotly_chart(figh, use_container_width=True)

with st.expander("장비 간 상호 상관관계 분석", expanded=False):
    # 도움말 섹션 추가 (expander 대신 버튼으로 토글)
    if "show_crosscorr_help" not in st.session_state:
        st.session_state.show_crosscorr_help = False
        
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("두 장비 간의 시간 지연을 고려한 상관관계를 분석합니다")
    with col2:
        if st.button("❓ 도움말", key="help_crosscorr_btn"):
            st.session_state.show_crosscorr_help = not st.session_state.show_crosscorr_help
    
    # 도움말 내용 표시
    if st.session_state.show_crosscorr_help:
        st.markdown("---")
        col_help1, col_help2 = st.columns(2)
        with col_help1:
            st.markdown("# 🔗 장비 간 상호 상관관계 분석 가이드")
            st.markdown("""
        **📊 장비 간 상호 상관관계 분석이란?**
        
        간단히 말하면: 두 링거폴대(수액 거치대)의 사용량이 시간적으로 얼마나 지연되어 연관되어 있는지 분석하는 기능입니다.
        
        **🤔 왜 'Cross-Correlation'이라는 이름을 사용할까요?**
        
        **Cross-Correlation (교차 상관)**: 
        - 두 개의 서로 다른 시계열 데이터 간의 상관관계를 분석
        - 'Cross'는 '교차'를 의미하며, 서로 다른 장비 간의 관계를 나타냄
        - 'Correlation'은 상관관계를 의미하며, 얼마나 연관되어 있는지를 측정
        
        
        
        **지연(Lag)의 의미**:
        - **양의 지연**: A 장비가 먼저 사용되고, B 장비가 나중에 사용
        - **음의 지연**: B 장비가 먼저 사용되고, A 장비가 나중에 사용
        - **0 지연**: 두 장비가 동시에 사용됨
        
        **실제 활용 예시**:
        - 간호사가 A 폴대에서 수액을 교체한 후 B 폴대로 이동하는 시간
        - 특정 치료 순서에 따른 장비 사용 순서
        - 병실 배치에 따른 업무 흐름의 영향
        
        **예시로 설명하면:**
        - A 폴대 사용량이 증가한 후 15분 뒤에 B 폴대 사용량이 증가한다면?
        - 두 폴대가 동시에 사용되는 패턴이 있는지?
        - 어떤 폴대가 항상 먼저 사용되는지?
        
        **🎯 이 분석으로 무엇을 알 수 있나요?**
        
        1. **업무 흐름 최적화**
           - 간호사의 업무 순서와 이동 경로 파악
           - 장비 사용의 시간적 순서 이해
           - 효율적인 업무 프로세스 설계
        
        2. **병실 배치 계획**
           - 함께 사용되는 장비들의 최적 배치
           - 간호사 이동 거리 최소화
           - 업무 효율성 향상을 위한 공간 설계
        
        3. **예측 및 계획 수립**
           - 한 장비 사용 후 다른 장비 사용 시점 예측
           - 수액 교체 일정의 최적화
           - 인력 배치의 시간적 계획
        
        **📈 지연 설정 가이드**
        
        **🔴 5-15분**: 단기 지연
        - 같은 간호사가 연속으로 관리하는 장비들
        - 빠른 업무 전환 상황
        
        **🟠 15-30분**: 중기 지연
        - 일반적인 업무 순환 패턴
        - 병실 간 이동 시간 고려
        
        **🟢 30-120분**: 장기 지연
        - 교대 시간대별 패턴
        - 치료 일정에 따른 지연
        """)
            
        with col_help2:
            st.markdown("# 📊 그래프 해석 가이드")
            st.markdown("""
        ### **📋 지연 상관분석 결과**
        - **X축**: 지연 시간 (분 단위, 음수는 B가 먼저, 양수는 A가 먼저)
        - **Y축**: 상관계수 (-1 ~ +1, 절댓값이 클수록 강한 상관관계)
        - **막대 높이**: 각 지연 시간에서의 상관관계 강도
        
        ### **📈 막대 그래프 해석**
        
        **가로축 (지연 시간)**:
        - **0**: 두 장비가 동시에 사용됨
        - **+15**: A 장비 사용 후 15분 뒤 B 장비 사용
        - **-20**: B 장비 사용 후 20분 뒤 A 장비 사용
        
        **세로축 (상관계수)**:
        - **+0.8**: 매우 강한 양의 상관관계
        - **+0.5**: 중간 정도의 양의 상관관계
        - **0.0**: 상관관계 없음
        - **-0.5**: 중간 정도의 음의 상관관계
        
        **🔍 그래프 패턴 해석**
        
        **높은 막대가 양의 지연에 위치**:
        - A 장비가 먼저 사용되고 B 장비가 나중에 사용
        - A → B 순서의 업무 흐름 존재
        - 간호사가 A에서 B로 이동하는 패턴
        
        **높은 막대가 음의 지연에 위치**:
        - B 장비가 먼저 사용되고 A 장비가 나중에 사용
        - B → A 순서의 업무 흐름 존재
        - 다른 업무 순서나 우선순위
        
        **높은 막대가 0 지연에 위치**:
        - 두 장비가 동시에 사용됨
        - 같은 간호사가 동시에 관리
        - 긴급 상황이나 특별한 치료
        
        ### **💡 실용적 활용 팁**
                
        **업무 최적화**:
        - **높은 상관관계 지연**: 해당 시간만큼 여유를 두고 업무 계획
        - **동시 사용 패턴**: 두 장비를 같은 간호사가 담당하도록 배치
        - **순차적 사용 패턴**: 업무 순서를 지연 시간에 맞춰 조정
        
        **병실 배치**:
        - **짧은 지연**: 가까운 위치에 배치
        - **긴 지연**: 업무 흐름을 고려한 배치
        - **동시 사용**: 같은 구역에 배치
        """)
        
        if st.button("도움말 닫기", key="close_crosscorr_help"):
            st.session_state.show_crosscorr_help = False
            st.rerun()
    
    # 기존 장비 간 지연 상관분석 코드
    if filtered_clean.empty or len(filtered_clean['loadcel'].unique()) < 2:
        st.info("두 개 이상의 장비 데이터가 필요합니다.")
    else:
        devs = filtered_clean['loadcel'].unique().tolist()
        a = st.selectbox("장비 A", devs, index=0, help="지연 상관을 계산할 첫 번째 장비입니다.")
        b = st.selectbox("장비 B", devs, index=1 if len(devs) > 1 else 0, help="지연 상관을 계산할 두 번째 장비입니다.")
        max_lag_req = st.sidebar.slider("최대 지연(분)", 5, 120, 30, 5, key="ccf_lag")
        freq = '1T'
        def usage_series(d):
            ddf = filtered_clean[filtered_clean['loadcel'] == d].sort_values('timestamp')
            ddf['prev_weight'] = ddf['current_weight_history'].shift(1)
            u = (ddf['prev_weight'] - ddf['current_weight_history']).clip(lower=0)
            s = pd.Series(u.values, index=ddf['timestamp']).asfreq(freq).interpolate(limit_direction='both').fillna(0)
            return s
        sa, sb = usage_series(a), usage_series(b)
        # 두 시계열 길이 정렬
        N = min(len(sa), len(sb))
        if N < 3:
            st.info("지연 상관을 계산할 충분한 데이터가 없습니다.")
        else:
            sa = sa.iloc[:N]
            sb = sb.iloc[:N]
            # 정규화
            sa = (sa - sa.mean()) / (sa.std() + 1e-9)
            sb = (sb - sb.mean()) / (sb.std() + 1e-9)
            max_lag = min(max_lag_req, N - 2)
            lags = range(-max_lag, max_lag + 1)
            def corr_at_lag(k: int):
                if k < 0:
                    k = -k
                    x = sa.values[k:]
                    y = sb.values[:N - k]
                elif k > 0:
                    x = sa.values[:N - k]
                    y = sb.values[k:]
                else:
                    x = sa.values
                    y = sb.values
                if len(x) == 0 or len(y) == 0 or len(x) != len(y):
                    return np.nan
                return float(np.corrcoef(x, y)[0, 1])
            vals = [corr_at_lag(k) for k in lags]
            figcc = px.bar(x=list(lags), y=vals, labels={'x': '지연(분)', 'y': '상관'})
            figcc.update_layout(title=f"장비 {a}, 장비 {b}의 지연 상관")
            st.plotly_chart(figcc, use_container_width=True)
            # 최대 상관 지연 표시 (NaN 제외)
            valid = [(lag, v) for lag, v in zip(lags, vals) if v == v]
            if valid:
                best_k = max(valid, key=lambda t: abs(t[1]))[0]
                st.caption(f"최대 상관 지연: {best_k}분")

with st.expander("PCA 시각화", expanded=False):
    # 도움말 섹션 추가 (expander 대신 버튼으로 토글)
    if "show_pca_help" not in st.session_state:
        st.session_state.show_pca_help = False
        
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("여러 장비의 특성을 2차원으로 압축하여 시각화합니다")
    with col2:
        if st.button("❓ 도움말", key="help_pca_btn"):
            st.session_state.show_pca_help = not st.session_state.show_pca_help
    
    # 도움말 내용 표시
    if st.session_state.show_pca_help:
        st.markdown("---")
        col_help1, col_help2 = st.columns(2)
        with col_help1:
            st.markdown("# 🔍 PCA 시각화 가이드")
            st.markdown("""
        **📊 PCA(Principal Component Analysis)란?**
        
        간단히 말하면: 여러 링거폴대(수액 거치대)의 복잡한 특성들을 2차원 평면에 압축하여 한눈에 비교할 수 있게 하는 기능입니다.
        
        **🤔 왜 'PCA'라는 이름을 사용할까요?**
        
        **PCA (Principal Component Analysis)**: 
        - 주성분 분석이라고 불리는 차원 축소 기법
        - 'Principal'은 '주요한', 'Component'는 '구성요소'를 의미
        - 의료 환경에서는 '장비의 주요 특성들을 간단하게 표현'하는 방법
        
        **차원 축소의 필요성**:
        - 각 장비마다 평균 사용량, 변동성, 일일 사용량 등 여러 특성 존재
        - 이 모든 특성을 동시에 비교하기 어려움
        - PCA로 가장 중요한 특성들을 2차원으로 압축하여 시각화
        
        **주성분(Principal Components)의 의미**:
        - **PC1**: 가장 중요한 특성 조합 (가장 큰 변화를 설명)
        - **PC2**: 두 번째로 중요한 특성 조합 (PC1과 독립적인 변화)
        
        **예시로 설명하면:**
        - 어떤 장비들이 비슷한 사용 패턴을 보이는지?
        - 어떤 장비가 가장 특별한 특성을 가지고 있는지?
        - 장비들을 몇 개의 그룹으로 나눌 수 있는지?
        
        **🎯 이 분석으로 무엇을 알 수 있나요?**
        
        1. **장비 그룹화 및 패턴 파악**
           - 비슷한 특성을 가진 장비들을 그룹으로 분류
           - 각 그룹별 공통 특성 파악
           - 특이한 패턴을 보이는 장비 식별
        
        2. **장비 간 상관관계 이해**
           - 특성이 비슷한 장비들은 가까이 위치
           - 특성이 다른 장비들은 멀리 위치
           - 장비 간의 유사성과 차이점 시각적 파악
        
        3. **이상치 및 특이 패턴 감지**
           - 다른 장비들과 멀리 떨어진 장비 발견
           - 예상과 다른 특성을 가진 장비 식별
           - 추가 분석이 필요한 장비 선별
        
        **📈 설명분산 해석 가이드**
        
        **🔴 PC1 설명분산 > 80%**: 매우 높은 집중도
        - 첫 번째 주성분이 대부분의 정보를 담고 있음
        - 장비들을 한 방향으로만 비교해도 충분
        
        **🟠 PC1 설명분산 60-80%**: 높은 집중도
        - 첫 번째 주성분이 중요한 정보를 담고 있음
        - PC2도 함께 고려하면 더 정확한 분석 가능
        
        **🟡 PC1 설명분산 < 60%**: 낮은 집중도
        - 여러 주성분이 고르게 정보를 담고 있음
        - 더 복잡한 패턴이 존재할 수 있음
        """)
            
        with col_help2:
            st.markdown("# 📊 그래프 해석 가이드")
            st.markdown("""
        ### **📋 PCA 산점도 구조**
        - **X축 (PC1)**: 첫 번째 주성분 (가장 중요한 특성 조합)
        - **Y축 (PC2)**: 두 번째 주성분 (두 번째로 중요한 특성 조합)
        - **점**: 각 링거폴대 (번호로 표시)
        - **설명분산**: 각 주성분이 전체 정보의 몇 %를 설명하는지
        
        ### **🔍 그래프 패턴 해석**
        
        **점들의 분포 패턴**:
        - **가까이 모여있는 점들**: 비슷한 특성을 가진 장비들
        - **멀리 떨어진 점들**: 특성이 다른 장비들
        - **가장자리에 위치한 점들**: 특이한 특성을 가진 장비들
        
        **축별 의미 해석**:
        - **PC1 방향**: 가장 중요한 특성의 변화 방향
        - **PC2 방향**: PC1과 독립적인 두 번째 특성의 변화 방향
        
        **🔍 특별한 패턴 해석**
        
        **클러스터 형태**:
        - **명확한 그룹**: 장비들이 몇 개의 뚜렷한 그룹으로 나뉨
        - **연속적 분포**: 장비들이 특성에 따라 연속적으로 분포
        - **무작위 분포**: 특별한 패턴이 없는 경우
        
        **이상치 패턴**:
        - **고립된 점**: 다른 장비들과 완전히 다른 특성
        - **가장자리 점**: 특정 특성에서 극단적인 값을 가짐
        - **중앙 점**: 모든 특성이 평균적인 장비
        
        ### **💡 실용적 활용 팁**
                
        **장비 그룹별 관리**:
        - **가까이 위치한 장비들**: 비슷한 관리 전략 적용
        - **멀리 떨어진 장비들**: 개별적인 관리 전략 필요
        - **고립된 장비들**: 특별한 주의와 관리 필요
        
        **설명분산 활용**:
        - **높은 설명분산**: PC1만으로도 충분한 분석 가능
        - **낮은 설명분산**: 더 많은 주성분 고려 필요
        - **균형잡힌 설명분산**: 여러 관점에서 분석 권장
        
        **정기적 모니터링**:
        - 장비들의 위치 변화 추이 관찰
        - 새로운 패턴이나 그룹의 출현 감지
        - 관리 전략의 효과성 평가
        """)
        
        if st.button("도움말 닫기", key="close_pca_help"):
            st.session_state.show_pca_help = False
            st.rerun()
    
    # 기존 PCA 코드
    if df.empty:
        st.info("데이터가 없어 PCA를 수행할 수 없습니다.")
    else:
        # 앞서 만든 agg가 있을 수 있으나 안정적으로 재계산
        feat = filtered_clean.copy().sort_values('timestamp')
        if feat.empty:
            st.info("선택한 기간/장비에 데이터가 없습니다.")
        else:
            feat['prev_weight'] = feat.groupby('loadcel')['current_weight_history'].shift(1)
            feat['usage'] = (feat['prev_weight'] - feat['current_weight_history']).clip(lower=0) / 1000
            agg = feat.groupby('loadcel').agg(
                mean_usage=('usage', 'mean'),
                std_usage=('usage', 'std')
            ).fillna(0)
            daily = feat.copy()
            daily['date'] = daily['timestamp'].dt.date
            daily_agg = daily.groupby(['loadcel', 'date'])['usage'].sum().groupby('loadcel').mean()
            agg['daily_mean_usage'] = daily_agg
            agg = agg.fillna(0)
            try:
                scaler = StandardScaler()
                X = scaler.fit_transform(agg.values)
                pca = PCA(n_components=2, random_state=42)
                comps = pca.fit_transform(X)
                pca_df = pd.DataFrame({'loadcel': agg.index, 'PC1': comps[:, 0], 'PC2': comps[:, 1]})
                figp = px.scatter(pca_df, x='PC1', y='PC2', text='loadcel')
                figp.update_traces(textposition='top center')
                figp.update_layout(title=f"PCA (설명분산: PC1 {pca.explained_variance_ratio_[0]*100:.1f}%, PC2 {pca.explained_variance_ratio_[1]*100:.1f}%)")
                st.plotly_chart(figp, use_container_width=True)
            except Exception as e:
                st.warning(f"PCA 중 오류: {e}")

with st.expander("롤링 추세 기울기", expanded=False):
    # 도움말 섹션 추가 (expander 대신 버튼으로 토글)
    if "show_rolling_help" not in st.session_state:
        st.session_state.show_rolling_help = False
        
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("시간에 따라 변화하는 수액 소모 속도를 실시간으로 추적합니다")
    with col2:
        if st.button("❓ 도움말", key="help_rolling_btn"):
            st.session_state.show_rolling_help = not st.session_state.show_rolling_help
    
    # 도움말 내용 표시
    if st.session_state.show_rolling_help:
        st.markdown("---")
        col_help1, col_help2 = st.columns(2)
        with col_help1:
            st.markdown("# 📈 롤링 추세 기울기 가이드")
            st.markdown("""
        **📊 롤링 추세 기울기란?**
        
        간단히 말하면: 링거폴대(수액 거치대)의 수액 소모 속도가 시간에 따라 어떻게 변화하는지를 실시간으로 추적하는 기능입니다.
        
        **🤔 왜 '롤링(Rolling)'이라는 이름을 사용할까요?**
        
        **롤링(Rolling)**: 
        - '구르다', '굴러가다'라는 의미로, 시간의 흐름에 따라 계속해서 움직이는 것을 의미
        - 의료 환경에서는 '시간의 창(window)을 계속해서 이동시키며 분석'하는 방법
        - 마치 창문을 계속해서 밀어가며 바깥 풍경을 보는 것과 같음
        
        
        
        **롤링 윈도우의 개념**:
        - 고정된 시간 구간(예: 60분)을 설정
        - 이 구간을 1분씩 이동시키며 기울기 계산
        - 각 시점에서의 수액 소모 속도를 연속적으로 추적
        
        **기울기의 의미**:
        - **양의 기울기**: 수액 소모 속도가 증가 (더 빨리 줄어듦)
        - **음의 기울기**: 수액 소모 속도가 감소 (더 천천히 줄어듦)
        - **0에 가까운 기울기**: 수액 소모 속도가 일정
        
        **예시로 설명하면:**
        - 오전 9시에 수액 소모가 갑자기 빨라졌다면?
        - 오후 2시에 소모 속도가 느려졌다면?
        - 하루 종일 소모 속도가 일정한지, 아니면 변동이 있는지?
        
        **🎯 이 분석으로 무엇을 알 수 있나요?**
        
        1. **수액 소모 속도의 실시간 변화 추적**
           - 특정 시점에 소모 속도가 급격히 변하는지 감지
           - 수액 소모 패턴의 변화 시점 파악
           - 예상과 다른 소모 속도 변화 조기 발견
        
        2. **치료 효과 및 환자 상태 변화 모니터링**
           - 수액 소모 속도 변화로 치료 강도 변화 파악
           - 환자 상태 급변 시 소모 속도 변화 감지
           - 치료 효과의 시간적 변화 추적
        
        3. **예측 및 계획 수립**
           - 현재 소모 속도 기반으로 수액 교체 시점 예측
           - 소모 속도 변화 패턴을 통한 향후 계획 수립
           - 비정상 상황에 대한 사전 대응 계획
        
        **📈 윈도우 크기 설정 가이드**
        
        **🔴 10-30분**: 매우 민감한 변화 감지
        - 급격한 단기 변화에 민감하게 반응
        - 노이즈(측정 오류)에 민감할 수 있음
        
        **🟠 30-60분**: 일반적인 변화 감지 (권장)
        - 적절한 수준의 변화 감지
        - 노이즈와 실제 변화의 균형
        
        **🟢 60-240분**: 장기적 변화에 집중
        - 큰 변화만 감지
        - 안정적이지만 세밀한 변화 놓칠 수 있음
        """)
            
        with col_help2:
            st.markdown("# 📊 그래프 해석 가이드")
            st.markdown("""
        ### **📋 롤링 기울기 그래프 구조**
        - **X축**: 시간 (가로축)
        - **Y축**: 기울기 값 (g/시간, 세로축)
        - **파란색 선**: 각 시점에서의 수액 소모 속도 변화
        
        ### **🔍 그래프 패턴 해석**
        
        **기울기 값의 의미**:
        - **+100 g/시간**: 수액이 시간당 100g씩 더 빨리 줄어듦
        - **-50 g/시간**: 수액 소모 속도가 시간당 50g씩 느려짐
        - **0 g/시간**: 수액 소모 속도 변화 없음
        
        **선의 패턴 해석**:
        - **상승하는 선**: 수액 소모 속도가 점점 빨라짐
        - **하강하는 선**: 수액 소모 속도가 점점 느려짐
        - **수평선**: 수액 소모 속도가 일정함
        - **불규칙한 선**: 소모 속도가 불규칙하게 변화
        
        **🔍 특별한 패턴 해석**
        
        **급격한 변화**:
        - **뾰족한 피크**: 갑작스러운 소모 속도 변화
        - **급격한 하강**: 소모 속도가 갑자기 느려짐
        - **급격한 상승**: 소모 속도가 갑자기 빨라짐
        
        **주기적 패턴**:
        - **정기적인 파형**: 일정한 주기로 소모 속도 변화
        - **불규칙한 파형**: 예측할 수 없는 소모 속도 변화
        - **안정적 패턴**: 소모 속도가 거의 일정
        
        ### **💡 실용적 활용 팁**
                
        **윈도우 크기 조정**:
        - **작은 윈도우**: 세밀한 변화 감지, 노이즈 민감
        - **큰 윈도우**: 안정적 변화 감지, 노이즈 덜 민감
        - **중간 윈도우**: 균형잡힌 분석 (일반적으로 권장)
        
        **변화 감지 시 대응**:
        - **급격한 변화**: 즉시 해당 장비 상태 점검
        - **점진적 변화**: 치료 과정의 정상성 여부 확인
        - **주기적 변화**: 예측 가능한 패턴으로 활용
        
        **정기적 모니터링**:
        - 기울기 변화 패턴의 추이 관찰
        - 새로운 변화 패턴의 출현 감지
        - 관리 전략의 효과성 평가
        """)
        
        if st.button("도움말 닫기", key="close_rolling_help"):
            st.session_state.show_rolling_help = False
            st.rerun()
    
    # 기존 롤링 추세 기울기 코드
    if filtered_clean.empty:
        st.info("데이터가 없어 롤링 기울기를 계산할 수 없습니다.")
    else:
        sel_roll = st.selectbox("장비 선택(롤링)", filtered_clean['loadcel'].unique().tolist(), key="roll_sel")
        win_min = st.sidebar.slider("윈도우(분)", 10, 240, 60, 10, key="roll_win")
        grp = filtered_clean[filtered_clean['loadcel'] == sel_roll].sort_values('timestamp')
        if len(grp) < 5:
            st.info("롤링 계산에 충분한 데이터가 필요합니다.")
        else:
            s = grp[['timestamp', 'current_weight_history']].set_index('timestamp').asfreq('T')
            s['current_weight_history'] = s['current_weight_history'].interpolate(limit_direction='both')
            ts = s.index
            vals = s['current_weight_history'].values
            import numpy as np
            k = win_min
            slopes = []
            idxs = []
            for i in range(0, len(vals) - k + 1):
                yw = vals[i:i+k]
                xw = (np.arange(k) / 60.0)
                try:
                    m, b = np.polyfit(xw, yw, 1)
                except Exception:
                    m = np.nan
                slopes.append(m)
                idxs.append(ts[i + k - 1])
            roll_df = pd.DataFrame({'timestamp': idxs, 'slope_g_per_hour': slopes}).set_index('timestamp')
            try:
                import plotly.graph_objs as go
                figr = go.Figure()
                figr.add_trace(go.Scatter(x=roll_df.index, y=roll_df['slope_g_per_hour'], mode='lines', name='기울기'))
                figr.update_layout(title=f"장비 {sel_roll} - 롤링 기울기(g/시간)")
                st.plotly_chart(figr, use_container_width=True)
            except Exception:
                st.line_chart(roll_df['slope_g_per_hour'])

with st.expander("자기상관(ACF) / 부분자기상관(PACF)", expanded=False):
    if filtered_clean.empty:
        st.info("데이터가 없어 ACF/PACF를 계산할 수 없습니다.")
    else:
        sel_acf = st.selectbox("장비 선택(ACF)", filtered_clean['loadcel'].unique().tolist(), key="acf_sel", help="자기상관(ACF)과 부분자기상관(PACF)은 시계열 데이터의 자기상관성을 분석하는 통계적 방법입니다. ACF는 시계열 데이터와 그 지연된 버전 간의 상관관계를 측정하며, PACF는 다른 지연된 버전의 영향을 제거한 후의 상관관계를 측정합니다. 이 도구는 시계열 데이터의 자기상관성을 분석하여 시계열 데이터의 특성을 이해하고 예측 모델을 개발하는 데 도움을 줍니다.")
        lags = st.sidebar.slider("최대 랙", 10, 60, 40, 5, key="acf_lags")
        series4 = filtered_clean[filtered_clean['loadcel'] == sel_acf].sort_values('timestamp')
        if len(series4) < 10:
            st.info("ACF/PACF 계산에 충분한 데이터가 필요합니다.")
        else:
            s4 = series4[['timestamp', 'current_weight_history']].set_index('timestamp').asfreq('T')
            s4['current_weight_history'] = s4['current_weight_history'].interpolate(limit_direction='both')
            vals = s4['current_weight_history'].values
            try:
                acfs = sm_acf(vals, nlags=lags, fft=True)
                pacfs = sm_pacf(vals, nlags=lags)
                import plotly.graph_objs as go
                figa = go.Figure([go.Bar(x=list(range(len(acfs))), y=acfs)])
                figa.update_layout(title="ACF")
                figp = go.Figure([go.Bar(x=list(range(len(pacfs))), y=pacfs)])
                figp.update_layout(title="PACF")
                st.plotly_chart(figa, use_container_width=True)
                st.plotly_chart(figp, use_container_width=True)
            except Exception as e:
                st.warning(f"ACF/PACF 계산 중 오류: {e}")
                
with st.expander("예측: ARIMA 단기 예측", expanded=False):
    if filtered_clean.empty:
        st.info("데이터가 없어 예측을 수행할 수 없습니다.")
    else:
        sel_fc = st.selectbox(
            "장비 선택(예측)",
            filtered_clean['loadcel'].unique().tolist(),
            key="fc_sel",
            help="ARIMA 단기 예측을 수행할 장비입니다."
        )
        horizon = st.sidebar.slider("예측 구간(분)", 10, 240, 60, 10, key="fc_h")
        series3 = filtered_clean[filtered_clean['loadcel'] == sel_fc].sort_values('timestamp')
        s3 = series3[['timestamp', 'current_weight_history']].dropna()
        if len(s3) < 20:
            st.info("예측을 위한 데이터가 충분하지 않습니다.")
        else:
            s3 = s3.set_index('timestamp').asfreq('T')
            s3['current_weight_history'] = s3['current_weight_history'].interpolate(limit_direction='both')
            order_p = st.sidebar.slider("ARIMA p(예측)", 0, 3, 1, key="fc_p")
            order_d = st.sidebar.slider("ARIMA d(예측)", 0, 2, 1, key="fc_d")
            order_q = st.sidebar.slider("ARIMA q(예측)", 0, 3, 1, key="fc_q")
            try:
                model = ARIMA(s3['current_weight_history'], order=(order_p, order_d, order_q))
                res = model.fit()
                f = res.get_forecast(steps=horizon)
                mean_fc = f.predicted_mean
                ci = f.conf_int()
                import plotly.graph_objs as go
                figf = go.Figure()
                figf.add_trace(go.Scatter(x=s3.index, y=s3['current_weight_history'], mode='lines', name='실제'))
                figf.add_trace(go.Scatter(x=mean_fc.index, y=mean_fc.values, mode='lines', name='예측'))
                figf.add_trace(go.Scatter(x=mean_fc.index, y=ci.iloc[:, 0], mode='lines', line=dict(width=0), showlegend=False))
                figf.add_trace(go.Scatter(x=mean_fc.index, y=ci.iloc[:, 1], mode='lines', fill='tonexty', line=dict(width=0), name='예측 구간'))
                figf.update_layout(title=f"장비 {sel_fc} - 단기 예측")
                st.plotly_chart(figf, use_container_width=True)
            except Exception as e:
                st.warning(f"ARIMA 예측 중 오류: {e}")
