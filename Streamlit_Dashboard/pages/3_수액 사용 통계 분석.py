import streamlit as st
import json
import pandas as pd
import plotly.express as px
import boto3
import pytz
from utils.alert_utils import render_alert_sidebar

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

# 사이드바 내용 추가
st.sidebar.header("수액 사용 통계 분석")
st.sidebar.write("각 링거 폴대 별로")
st.sidebar.write("데이터를 분석합니다.")
st.sidebar.markdown("---")

# ====== 사이드바에 알림 리스트 출력 ======
render_alert_sidebar()

st.title("수액 사용 통계 분석")

# 데이터 불러오기
@st.cache_data
def get_history_df():
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
    st.sidebar.header("필터")
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
    if filtered.empty:
        st.info("선택한 조건에 해당하는 데이터가 없습니다.")
    else:
        filtered = filtered.sort_values('timestamp')
        filtered['prev_weight'] = filtered.groupby('loadcel')['current_weight_history'].shift(1)
        filtered['usage'] = (filtered['prev_weight'] - filtered['current_weight_history']).clip(lower=0) / 1000
        # 감소량(usage, kg) 기준으로 라인차트 표시
        fig = px.line(
            filtered,
            x='timestamp',
            y='usage',
            color='loadcel',
            markers=True,
            labels={'usage': '감소량(kg)', 'timestamp': '시간', 'loadcel': '장비'}
        )
        st.plotly_chart(fig, use_container_width=True)

# === 3개 통계 가로 배치 ===
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("시간대별 사용량(kg)")
    filtered['hour'] = filtered['timestamp'].dt.hour
    filtered = filtered.sort_values('timestamp')
    filtered['prev_weight'] = filtered.groupby('loadcel')['current_weight_history'].shift(1)
    filtered['usage'] = (filtered['prev_weight'] - filtered['current_weight_history']).clip(lower=0) / 1000
    usage_by_hour = filtered.groupby(['hour', 'loadcel'])['usage'].sum().reset_index()
    usage_by_hour['usage'] = usage_by_hour['usage'].round(1)
    heatmap_pivot = usage_by_hour.pivot(index='hour', columns='loadcel', values='usage').fillna(0)
    styled_heatmap = heatmap_pivot.style.format("{:.1f}").background_gradient(cmap='Blues')
    st.dataframe(styled_heatmap, height=300)

with col2:
    st.subheader("폴대별 사용량 랭킹(kg)")
    filtered['usage'] = (filtered['prev_weight'] - filtered['current_weight_history']).clip(lower=0) / 1000
    rank_df = filtered.groupby('loadcel')['usage'].sum().reset_index()
    rank_df['usage'] = rank_df['usage'].round(1)
    rank_df = rank_df.sort_values('usage', ascending=False)
    rank_df.index += 1
    st.dataframe(rank_df.rename(columns={'usage': '총 사용량(kg)'}))

with col3:
    st.subheader("이상치(급격한 변화) 탐지")
    filtered['diff'] = filtered.groupby('loadcel')['current_weight_history'].diff().abs()
    outlier = filtered[filtered['diff'] > 50]  # 예: 50g 이상 변화
    if outlier.empty:
        st.info("이상 변화(급격한 무게 변화) 없음")
    else:
        st.dataframe(outlier[['loadcel', 'timestamp', 'current_weight_history', 'diff']])

    # === 데이터 다운로드 ===
    st.subheader("데이터 다운로드")
    csv = filtered.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="CSV로 다운로드",
        data=csv,
        file_name="filtered_stats.csv",
        mime='text/csv'
    )

# loadcell_history 사용 시 예시 (필요한 곳에 아래와 같이 사용)
# history = loadcell_history.get(loadcel_id, [])
# tuple_history = [h for h in history if isinstance(h, tuple) and len(h) == 2]
# if tuple_history:
#     timestamps = [h[0] for h in tuple_history]
#     weights = [h[1] for h in tuple_history]
#     ...
