import streamlit as st
import json
import pandas as pd
import boto3
from fpdf import FPDF
import tempfile
import os
import matplotlib.pyplot as plt
import plotly.io as pio
from PIL import Image
import io

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

# ====== 사이드바에 알림 리스트 출력 ======
st.sidebar.markdown("### 📋 알림")
if st.session_state.get('alert_list'):
    for alert in st.session_state['alert_list']:
        if alert["id"] == 1:
            st.sidebar.success(alert["msg"])
        elif alert["id"] == 2:
            st.sidebar.warning(alert["msg"])
        elif alert["id"] == 3:
            st.sidebar.error(alert["msg"])
        elif alert["id"] == 4:
            st.sidebar.error(alert["msg"])
        else:
            st.sidebar.info(alert["msg"])
else:
    st.sidebar.info("새로운 알림이 없습니다.")

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
st.subheader("보고서 생성")

if not df.empty:
    # === 보고서 유형 선택 ===
    report_type = st.radio("보고서 유형 선택", ["월간", "주간", "일간"], horizontal=True)
    if report_type == "월간":
        df['period'] = df['timestamp'].dt.strftime('%Y-%m')
        period_options = sorted(df['period'].unique(), reverse=True)
        period_labels = [f"{m[:4]}년 {int(m[5:]):02d}월" for m in period_options]
    elif report_type == "주간":
        df['period'] = df['timestamp'].dt.strftime('%Y-%U')
        period_options = sorted(df['period'].unique(), reverse=True)
        period_labels = [f"{m[:4]}년 {int(m[5:]):02d}주" for m in period_options]
    else:
        df['period'] = df['timestamp'].dt.strftime('%Y-%m-%d')
        period_options = sorted(df['period'].unique(), reverse=True)
        period_labels = [f"{m[:4]}년 {int(m[5:7])}월 {int(m[8:]):02d}일" for m in period_options]
    period_map = dict(zip(period_labels, period_options))
    selected_label = st.selectbox("보고서 생성 기간 선택:", period_labels)
    selected_period = period_map[selected_label]
    # === 포함 항목 선택 ===
    st.write("포함할 항목을 선택하세요:")
    include_stats = st.checkbox("장비별 통계 요약", value=True)
    include_outlier = st.checkbox("이상치(급격한 변화) 기록", value=True)
    include_graph = st.checkbox("그래프 포함", value=True)
    # === 데이터 필터링 ===
    period_df = df[df['period'] == selected_period]
    if period_df.empty:
        st.info("해당 기간에 데이터가 없습니다.")
    else:
        # === 미리보기 ===
        st.write("---")
        st.subheader("보고서 미리보기")
        if include_stats:
            st.write("#### 장비별 통계 요약")
            stats = period_df.groupby('loadcel')['current_weight_history'].agg(['count', 'mean', 'min', 'max', 'sum'])
            st.dataframe(stats.rename(columns={'count': '측정수', 'mean': '평균', 'min': '최소', 'max': '최대', 'sum': '총합'}))
        if include_outlier:
            st.write("#### 이상치(급격한 변화) 기록")
            period_df['diff'] = period_df.groupby('loadcel')['current_weight_history'].diff().abs()
            outlier = period_df[period_df['diff'] > 50]
            if outlier.empty:
                st.info("이상 변화 없음")
            else:
                st.dataframe(outlier[['loadcel', 'timestamp', 'current_weight_history', 'diff']])
        if include_graph:
            st.write("#### 무게 변화 그래프")
            import plotly.express as px
            fig = px.line(period_df, x='timestamp', y='current_weight_history', color='loadcel', markers=True)
            st.plotly_chart(fig, use_container_width=True)
        # === PDF/CSV 다운로드 ===
        st.write("---")
        st.subheader("보고서 다운로드")
        csv = period_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="CSV로 다운로드",
            data=csv,
            file_name=f"{selected_period}_loadcell_report.csv",
            mime='text/csv'
        )
        # PDF 다운로드(간단 텍스트 기반, 실제 PDF 변환은 별도 구현 필요)
        pdf_text = f"보고서 기간: {selected_label}\n\n"
        if include_stats:
            pdf_text += "[장비별 통계 요약]\n" + stats.to_string() + "\n\n"
        if include_outlier:
            pdf_text += "[이상치 기록]\n" + outlier.to_string() + "\n\n"
        pdf_bytes = io.BytesIO(pdf_text.encode('utf-8'))
        st.download_button(
            label="txt로 다운로드",
            data=pdf_bytes,
            file_name=f"{selected_period}_loadcell_report.txt",
            mime='text/plain'
        )
        # === PDF 다운로드 기능: 폰트 선택 드롭다운(직접 경로 지정) ===
        font_options = {
            "강부장님체": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/강부장님체/나눔손글씨 강부장님체.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/강부장님체/thumbnail.png'))
            ),
            "고딕_아니고_고딩": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/고딕_아니고_고딩/나눔손글씨 고딕 아니고 고딩.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/고딕_아니고_고딩/thumbnail.png'))
            ),
            "금은보화": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/금은보화/나눔손글씨 금은보화.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/금은보화/thumbnail.png'))
            ),
            "나눔고딕": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/나눔고딕/NanumGothic.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/나눔고딕/thumbnail.png'))
            ),
            "나눔바른고딕": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/나눔바른고딕/NanumBarunGothic.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/나눔바른고딕/thumbnail.png'))
            ),
            "나눔스퀘어라운드": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/나눔스퀘어라운드/NanumSquareRoundB.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/나눔스퀘어라운드/thumbnail.png'))
            ),
            "대광유리": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/대광유리/나눔손글씨 대광유리.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/대광유리/thumbnail.png'))
            ),
            "마루": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/마루/MaruBuri-Regular.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/마루/thumbnail.png'))
            ),
            "세아체": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/세아체/나눔손글씨 세아체.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/세아체/thumbnail.png'))
            ),
            "예당체": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/예당체/나눔손글씨 예당체.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../../font/예당체/thumbnail.png'))
            ),
        }
        col1, col2 = st.columns([1, 1])
        with col1:
            selected_font_name = st.selectbox("PDF 폰트 선택", list(font_options.keys()), key="font_selectbox")
        selected_font_path, selected_thumbnail_path = font_options[selected_font_name]
        with col2:
            if os.path.exists(selected_thumbnail_path):
                st.image(selected_thumbnail_path, width=360, caption=f"{selected_font_name} 미리보기")
            else:
                st.info("썸네일 이미지가 없습니다.")
        # 2. PDF 생성 함수에 폰트 경로 전달
        def dataframe_to_pdf(df, title="보고서", font_path=None, font_name="CustomFont",
                            include_stats=True, stats_df=None,
                            include_outlier=True, outlier_df=None,
                            include_graph=True, graph_fig=None):
            pdf = FPDF()
            pdf.add_page()
            if font_path:
                pdf.add_font(font_name, '', font_path, uni=True)
                pdf.set_font(font_name, '', 12)
            else:
                pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt=title, ln=True, align='C')
            pdf.ln(10)
            # 장비별 통계
            if include_stats and stats_df is not None:
                pdf.set_font(font_name, '', 14)
                pdf.cell(0, 10, '장비별 통계 요약', ln=True)
                pdf.set_font(font_name, '', 10)
                col_width = pdf.w / (len(stats_df.columns) + 1)
                for col in stats_df.columns:
                    pdf.cell(col_width, 8, str(col), border=1)
                pdf.ln()
                for i, row in stats_df.iterrows():
                    for item in row:
                        pdf.cell(col_width, 8, str(item), border=1)
                    pdf.ln()
                pdf.ln(5)
                pdf.add_page()
            # 이상치
            if include_outlier and outlier_df is not None and not outlier_df.empty:
                pdf.set_font(font_name, '', 14)
                pdf.cell(0, 10, '이상치(급격한 변화) 기록', ln=True)
                pdf.set_font(font_name, '', 9)
                outlier_cols = outlier_df.columns
                col_width = pdf.w / (len(outlier_cols) + 1)
                for col in outlier_cols:
                    pdf.cell(col_width, 7, str(col), border=1)
                pdf.ln()
                for i, row in outlier_df.iterrows():
                    for item in row:
                        pdf.cell(col_width, 7, str(item), border=1)
                    pdf.ln()
                pdf.ln(5)
                pdf.add_page()
            # 그래프
            if include_graph and graph_fig is not None:
                pdf.set_font(font_name, '', 14)
                pdf.cell(0, 10, '무게 변화 그래프', ln=True)
                # plotly figure를 이미지로 변환
                img_bytes = graph_fig.to_image(format="png")
                img_stream = io.BytesIO(img_bytes)
                img = Image.open(img_stream)
                img_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
                img.save(img_path)
                pdf.image(img_path, w=pdf.w - 20)
                pdf.ln(5)
            tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            pdf.output(tmpfile.name)
            tmpfile.seek(0)
            return tmpfile
        # 3. PDF 다운로드 버튼 (옵션별 포함)
        if include_stats:
            # stats, outlier, fig 등 준비
            stats_df = stats.rename(columns={'count': '측정수', 'mean': '평균', 'min': '최소', 'max': '최대', 'sum': '총합'}) if include_stats else None
            outlier_df = outlier[['loadcel', 'timestamp', 'current_weight_history', 'diff']] if include_outlier and 'outlier' in locals() and not outlier.empty else None
            graph_fig = None
            if include_graph:
                import plotly.express as px
                graph_fig = px.line(
                    period_df,
                    x='timestamp',
                    y='current_weight_history',
                    color='loadcel',
                    markers=True,
                    color_discrete_sequence=px.colors.qualitative.Set1
                )
            pdf_file = None
            if st.download_button(
                label="PDF로 다운로드",
                data=(pdf_file := dataframe_to_pdf(
                    period_df,
                    title=f"{selected_label} 보고서",
                    font_path=selected_font_path,
                    font_name=selected_font_name,
                    include_stats=include_stats,
                    stats_df=stats_df,
                    include_outlier=include_outlier,
                    outlier_df=outlier_df,
                    include_graph=include_graph,
                    graph_fig=graph_fig
                )).read(),
                file_name=f"{selected_period} Smart IV Pole Report.pdf",
                mime="application/pdf"
            ):
                pass
else:
    st.warning("아직 기록된 데이터가 없습니다.")

# loadcell_history 사용 시 예시 (필요한 곳에 아래와 같이 사용)
# history = loadcell_history.get(loadcel_id, [])
# tuple_history = [h for h in history if isinstance(h, tuple) and len(h) == 2]
# if tuple_history:
#     timestamps = [h[0] for h in tuple_history]
#     weights = [h[1] for h in tuple_history]
#     ...
