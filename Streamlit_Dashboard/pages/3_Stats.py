import streamlit as st
import json
import pandas as pd
import plotly.express as px
import boto3
import pytz

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

st.title("📈 수액 사용 통계 분석")

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
        df['remaining_sec_history'] = pd.to_numeric(df['remaining_sec_history'], errors='coerce')
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

df = get_history_df()

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

    # 2. 기간별 무게 변화
    st.subheader("기간별 무게 변화")
    if filtered.empty:
        st.info("선택한 조건에 해당하는 데이터가 없습니다.")
    else:
        fig = px.line(filtered, x='timestamp', y='current_weight_history', color='loadcel', markers=True,
                      labels={'current_weight_history': '무게', 'timestamp': '시간', 'loadcel': '장비'})
        st.plotly_chart(fig, use_container_width=True)

    # 3. 장비별 평균 사용량/최대/최소
    st.subheader("장비별 통계 요약")
    st.dataframe(
        filtered.groupby('loadcel')['current_weight_history'].agg(['count', 'mean', 'min', 'max']).rename(
            columns={'count': '측정수', 'mean': '평균무게', 'min': '최소', 'max': '최대'}
        )
    )

    # 4. 이상치(급격한 변화) 탐지 예시
    st.subheader("이상치(급격한 변화) 탐지")
    filtered['diff'] = filtered.groupby('loadcel')['current_weight_history'].diff().abs()
    outlier = filtered[filtered['diff'] > 50]  # 예: 50g 이상 변화
    if outlier.empty:
        st.info("이상 변화(급격한 무게 변화) 없음")
    else:
        st.dataframe(outlier[['loadcel', 'timestamp', 'current_weight_history', 'diff']])

# loadcell_history 사용 시 예시 (필요한 곳에 아래와 같이 사용)
# history = loadcell_history.get(loadcel_id, [])
# tuple_history = [h for h in history if isinstance(h, tuple) and len(h) == 2]
# if tuple_history:
#     timestamps = [h[0] for h in tuple_history]
#     weights = [h[1] for h in tuple_history]
#     ...
