import streamlit as st
import json
import pandas as pd
import boto3

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

# DynamoDB에서 데이터 불러오기 함수
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

st.title("📄 보고서 생성")

df = get_history_df()

st.write("---")
st.subheader("월간 보고서 생성")

# 월 리스트 생성 (데이터에 따라 동적으로)
if not df.empty:
    df['year_month'] = df['timestamp'].dt.strftime('%Y-%m')
    month_options = sorted(df['year_month'].unique(), reverse=True)
    month_labels = [f"{m[:4]}년 {int(m[5:]):02d}월" for m in month_options]
    month_map = dict(zip(month_labels, month_options))
    selected_label = st.selectbox("보고서 생성 월 선택:", month_labels)
    selected_month = month_map[selected_label]
    # 해당 월 데이터 필터링
    month_df = df[df['year_month'] == selected_month]
    if month_df.empty:
        st.info("해당 월에 데이터가 없습니다.")
    else:
        # 장비별 사용량 요약 (무게/남은시간 각각)
        weight_stats = month_df.groupby('loadcel')['current_weight_history'].agg(['count', 'mean', 'min', 'max', 'sum'])
        weight_stats = weight_stats.rename(columns={
            'count': '무게_측정수', 'mean': '무게_평균', 'min': '무게_최소', 'max': '무게_최대', 'sum': '무게_총합'
        })
        sec_stats = month_df.groupby('loadcel')['remaining_sec_history'].agg(['count', 'mean', 'min', 'max', 'sum'])
        sec_stats = sec_stats.rename(columns={
            'count': '남은시간_측정수', 'mean': '남은시간_평균', 'min': '남은시간_최소', 'max': '남은시간_최대', 'sum': '남은시간_총합'
        })
        summary = pd.concat([weight_stats, sec_stats], axis=1)
        st.dataframe(summary)
        # CSV 다운로드
        csv = summary.reset_index().to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="CSV로 다운로드",
            data=csv,
            file_name=f"{selected_month}_loadcell_report.csv",
            mime='text/csv'
        )
else:
    st.warning("아직 기록된 데이터가 없습니다.")

# loadcell_history 사용 시 예시 (필요한 곳에 아래와 같이 사용)
# history = loadcell_history.get(loadcel_id, [])
# tuple_history = [h for h in history if isinstance(h, tuple) and len(h) == 2]
# if tuple_history:
#     timestamps = [h[0] for h in tuple_history]
#     weights = [h[1] for h in tuple_history]
#     ...
