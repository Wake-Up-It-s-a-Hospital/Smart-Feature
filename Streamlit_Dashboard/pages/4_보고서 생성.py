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

# 사이드바 내용 추가
st.sidebar.header("보고서 생성")
st.sidebar.write("수집 및 분석된 데이터로")
st.sidebar.write("보고서를 생성합니다.")
st.sidebar.markdown("---")

# ====== 사이드바에 알림 리스트 출력 ======
render_alert_sidebar()

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

st.title("보고서 생성")

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
            stats = period_df.groupby('loadcel')['current_weight_history'].agg(['count', 'mean', 'min'])
            
            # 상위 1% 중간값 계산
            top_1_percent_values = []
            for loadcel in stats.index:
                loadcel_data = period_df[period_df['loadcel'] == loadcel]['current_weight_history']
                if len(loadcel_data) > 0:
                    top_1_percent = loadcel_data.quantile(0.99)
                    top_1_percent_values.append(top_1_percent)
                else:
                    top_1_percent_values.append(0)
            
            stats['top_1_percent'] = top_1_percent_values
            stats_renamed = stats.rename(columns={'count': '측정수', 'mean': '평균(g)', 'min': '최소(g)', 'top_1_percent': '최대(g)'})
            
            # 인덱스를 컬럼으로 변환하여 로드셀 번호 표시
            stats_renamed = stats_renamed.reset_index()
            stats_renamed['loadcel'] = stats_renamed['loadcel'].apply(lambda x: f"로드셀 {x}번")
            stats_renamed = stats_renamed.rename(columns={'loadcel': '로드셀'})
            
            # 표 너비 조정
            st.dataframe(stats_renamed, use_container_width=True)
        if include_outlier:
            st.write("#### 이상치(급격한 변화) 기록")
            period_df['diff'] = period_df.groupby('loadcel')['current_weight_history'].diff().abs()
            outlier = period_df[period_df['diff'] > 50]
            if outlier.empty:
                st.info("이상 변화 없음")
            else:
                # 컬럼명에 단위 표기 추가
                outlier_display = outlier[['loadcel', 'timestamp', 'current_weight_history', 'diff']].copy()
                outlier_display.columns = ['로드셀', '시간', '무게(g)', '변화량(g)']
                st.dataframe(outlier_display)
        if include_graph:
            st.write("#### 무게 변화 기록")
            # g를 kg으로 변환
            period_df_kg = period_df.copy()
            period_df_kg['current_weight_history_kg'] = period_df_kg['current_weight_history'] / 1000
            
            # timestamp를 datetime으로 변환
            period_df_kg['timestamp'] = pd.to_datetime(period_df_kg['timestamp'])
            
            # 상위/하위 0.1% 제외 (오차/노이즈 최소화)
            for loadcel_id in period_df_kg['loadcel'].unique():
                loadcel_data = period_df_kg[period_df_kg['loadcel'] == loadcel_id]
                if len(loadcel_data) > 0:
                    lower_bound = loadcel_data['current_weight_history_kg'].quantile(0.001)
                    upper_bound = loadcel_data['current_weight_history_kg'].quantile(0.999)
                    mask = (loadcel_data['current_weight_history_kg'] >= lower_bound) & (loadcel_data['current_weight_history_kg'] <= upper_bound)
                    period_df_kg = period_df_kg[~((period_df_kg['loadcel'] == loadcel_id) & ~mask)]
            
            # 표로 표시할 데이터 준비
            display_df = period_df_kg[['loadcel', 'timestamp', 'current_weight_history_kg']].copy()
            display_df.columns = ['로드셀', '시간', '무게(kg)']
            
            # 시간 포맷 정리
            display_df['시간'] = display_df['시간'].dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # 최근 50개 데이터만 표시 (너무 많으면 표가 복잡해짐)
            if len(display_df) > 50:
                display_df = display_df.tail(50)
                st.info("최근 50개 데이터만 표시됩니다.")
            
            st.dataframe(display_df, use_container_width=True)
            
            # 그래프는 주석처리
            # import plotly.express as px
            # fig = px.line(period_df_kg, x='timestamp', y='current_weight_history_kg', color='loadcel', markers=True)
            # fig.update_layout(
            #     yaxis_title="무게 (kg)",
            #     xaxis_title="시간"
            # )
            # fig.update_xaxes(
            #     tickformat='%Y-%m-%d %H:%M:%S',
            #     tickangle=45
            # )
            # st.plotly_chart(fig, use_container_width=True)
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
            "나눔손글씨 강부장님체": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/gangbujang/gangbujang.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/gangbujang/thumbnail.png'))
            ),
            "나눔손글씨 고딕 아니고 고딩체": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/gothing/gothing.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/gothing/thumbnail.png'))
            ),
            "나눔손글씨 금은보화체": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/goldandsilver/goldandsilver.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/goldandsilver/thumbnail.png'))
            ),
            "나눔고딕": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/nanumgothic/nanumgothic.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/nanumgothic/thumbnail.png'))
            ),
            "나눔바른고딕": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/nanumbarun/nanumbarun.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/nanumbarun/thumbnail.png'))
            ),
            "나눔스퀘어라운드": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/nanumsquare/nanumsquare.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/nanumsquare/thumbnail.png'))
            ),
            "나눔손글씨 대광유리": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/daegwang/daegwang.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/daegwang/thumbnail.png'))
            ),
            "마루부리체": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/maru/maru.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/maru/thumbnail.png'))
            ),
            "나눔손글씨 세아체": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/sea/sea.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/sea/thumbnail.png'))
            ),
            "나눔손글씨 예당체": (
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/yedang/yedang.ttf')),
                os.path.abspath(os.path.join(os.path.dirname(__file__), '../font/yedang/thumbnail.png'))
            )
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
            
            # 로고 경로 설정
            logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../images/tuk_med.jpg'))
            
            # 페이지에 로고 추가하는 헬퍼 함수
            def add_logo_to_page():
                if os.path.exists(logo_path):
                    pdf.image(logo_path, x=pdf.w - 70, y=10, w=60)
                    pdf.ln(15)  # 로고 아래 여백
            
            # 전문적인 푸터 추가 함수
            def add_professional_footer():
                
                # 구분선 추가 (더 세련된 디자인)
                pdf.set_font(font_name, '', 10)
                pdf.cell(0, 8, "--------------------------------------------------------------------------------", ln=True, align='C')
                
                # 자동 생성 안내 문구
                pdf.cell(0, 16, "본 보고서는 환자 추종 스마트 링거폴대 시스템에서 자동 생성되었습니다.", ln=True, align='C')
                
                # 생성일시 표시
                current_time = pd.Timestamp.now().strftime('%Y년 %m월 %d일 %H:%M:%S')
                pdf.cell(0, 16, f"생성일시: {current_time}", ln=True, align='C')
                
                # 기관명 표시 (더 강조)
                pdf.set_font(font_name, '', 12)
                pdf.cell(0, 14, "한국공학대학교의료원", ln=True, align='C')
                
                # 추가 정보
                pdf.set_font(font_name, '', 8)
                pdf.cell(0, 12, "환자 추종 스마트 링거폴대 시스템", ln=True, align='C')
                pdf.cell(0, 12, "데이터 분석 및 보고서 생성 시스템", ln=True, align='C')
            
            # 첫 페이지 로고 추가
            add_logo_to_page()
            
            # 제목 추가
            pdf.set_font(font_name, '', 25)  # 16 -> 32 (2배)
            pdf.cell(200, 20, txt=title, ln=True, align='C')  # 높이도 2배
            
            # 부제목 추가
            pdf.set_font(font_name, '', 15)  # 10 -> 20 (2배)
            pdf.cell(200, 16, txt="환자 추종 스마트 링거폴대 시스템", ln=True, align='C')  # 높이도 2배
            pdf.cell(200, 16, txt="한국공학대학교의료원", ln=True, align='C')  # 높이도 2배
            pdf.ln(5)
            # 장비별 통계
            if include_stats and stats_df is not None:
                pdf.set_font(font_name, '', 14)
                pdf.cell(0, 10, '장비별 통계 요약', ln=True)
                pdf.set_font(font_name, '', 10)
                
                # 컬럼 너비 계산 (로드셀 + 4개 통계 컬럼)
                col_width = pdf.w / 5
                
                # 헤더 출력
                headers = ['로드셀', '측정수', '평균', '최소', '최대']
                for header in headers:
                    pdf.cell(col_width, 8, str(header), border=1)
                pdf.ln()
                
                # 데이터 출력
                for i, row in stats_df.iterrows():
                    # 로드셀 번호
                    loadcel_name = f"로드셀 {i}번"
                    pdf.cell(col_width, 8, loadcel_name, border=1)
                    
                    # 측정수
                    pdf.cell(col_width, 8, str(row['측정수']), border=1)
                    
                    # 평균 (kg 변환)
                    if isinstance(row['평균'], (int, float)):
                        kg_value = row['평균'] / 1000
                        pdf.cell(col_width, 8, f"{kg_value:.3f} kg", border=1)
                    else:
                        pdf.cell(col_width, 8, str(row['평균']), border=1)
                    
                    # 최소 (kg 변환)
                    if isinstance(row['최소'], (int, float)):
                        kg_value = row['최소'] / 1000
                        pdf.cell(col_width, 8, f"{kg_value:.3f} kg", border=1)
                    else:
                        pdf.cell(col_width, 8, str(row['최소']), border=1)
                    
                    # 최대 (kg 변환) - 실제로는 상위 1% 중간값
                    if '상위1%중간값' in row:
                        if isinstance(row['상위1%중간값'], (int, float)):
                            kg_value = row['상위1%중간값'] / 1000
                            pdf.cell(col_width, 8, f"{kg_value:.3f} kg", border=1)
                        else:
                            pdf.cell(col_width, 8, str(row['상위1%중간값']), border=1)
                    else:
                        # 기존 최대값 사용 (호환성)
                        if isinstance(row['최대'], (int, float)):
                            kg_value = row['최대'] / 1000
                            pdf.cell(col_width, 8, f"{kg_value:.3f} kg", border=1)
                        else:
                            pdf.cell(col_width, 8, str(row['최대']), border=1)
                    
                    pdf.ln()
                pdf.ln(5)
                import matplotlib.pyplot as plt
                import io
                from matplotlib import font_manager
                font_prop = font_manager.FontProperties(fname=selected_font_path)
                plt.rc('font', family=font_prop.get_name())
                plt.figure(figsize=(8, 4))
                # g를 kg으로 변환 (최대값은 실제로 상위 1% 중간값)
                stats_kg = stats_df[['평균', '최소', '최대']].copy()
                
                for col in ['평균', '최소', '최대']:
                    stats_kg[col] = stats_kg[col] / 1000
                
                ax = stats_kg.plot(kind='bar')
                plt.title('장비별 통계(평균/최소/최대)', fontproperties=font_prop)
                plt.ylabel('무게 (kg)', fontproperties=font_prop)
                plt.tight_layout()
                ax.legend(prop=font_prop)
                # 각 막대 위에 값 표시
                for p in ax.patches:
                    height = p.get_height()
                    ax.annotate(f'{height:.2f}', (p.get_x() + p.get_width() / 2, height),
                                ha='center', va='bottom', fontsize=10)
                img_buf = io.BytesIO()
                plt.savefig(img_buf, format='png')
                plt.close()
                img_buf.seek(0)
                img_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
                with open(img_path, 'wb') as f:
                    f.write(img_buf.read())
                pdf.image(img_path, w=pdf.w - 20)
                pdf.ln(5)
            # 이상치
            if include_outlier and outlier_df is not None and not outlier_df.empty:
                # 새 페이지에 우상단 로고 추가
                pdf.add_page()
                add_logo_to_page()
                
                pdf.set_font(font_name, '', 14)
                pdf.cell(0, 10, '이상치(급격한 변화) 기록', ln=True)
                pdf.set_font(font_name, '', 9)
                outlier_cols = outlier_df.columns
                col_width = pdf.w / (len(outlier_cols) + 1)
                # 헤더 출력 (단위 표기 추가)
                for col in outlier_cols:
                    if col == 'current_weight_history':
                        header_text = f"{col} (g)"
                    elif col == 'diff':
                        header_text = f"{col} (g)"
                    else:
                        header_text = str(col)
                    pdf.cell(col_width, 7, header_text, border=1)
                pdf.ln()
                
                # 데이터 출력
                for i, row in outlier_df.iterrows():
                    for col in outlier_cols:
                        cell_text = str(row[col])
                        # timestamp 컬럼은 날짜만 표시
                        if col == 'timestamp':
                            try:
                                cell_text = pd.to_datetime(cell_text).strftime('%m-%d %H:%M')
                            except:
                                cell_text = cell_text[:10]  # 처음 10자만
                        # 다른 컬럼은 너무 길면 자르기
                        elif len(cell_text) > 8:
                            cell_text = cell_text[:8] + '...'
                        
                        pdf.cell(col_width, 7, cell_text, border=1)
                    pdf.ln()
                pdf.ln(5)
                # 1. 시간-이상치(diff) scatter plot
                import matplotlib.pyplot as plt
                import io
                from matplotlib import font_manager
                # 폰트 설정 (selected_font_path가 없으면 기본 폰트 사용)
                try:
                    font_prop = font_manager.FontProperties(fname=selected_font_path)
                    plt.rc('font', family=font_prop.get_name())
                except:
                    font_prop = font_manager.FontProperties()
                    plt.rc('font', family='DejaVu Sans')
                plt.figure(figsize=(8, 4))
                # g를 kg으로 변환
                diff_kg = outlier_df['diff'] / 1000
                plt.scatter(pd.to_datetime(outlier_df['timestamp']), diff_kg, c='red', s=20)
                plt.title('이상치 변화량(시간-차이)', fontproperties=font_prop)
                plt.xlabel('시간', fontproperties=font_prop)
                plt.ylabel('diff (kg)', fontproperties=font_prop)
                plt.tight_layout()
                plt.grid(True)
                img_buf = io.BytesIO()
                plt.savefig(img_buf, format='png')
                plt.close()
                img_buf.seek(0)
                img_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
                with open(img_path, 'wb') as f:
                    f.write(img_buf.read())
                pdf.image(img_path, w=pdf.w - 20)
                pdf.ln(5)
                # 2. 날짜별 이상치 개수 bar plot
                outlier_df['date'] = pd.to_datetime(outlier_df['timestamp']).dt.date
                date_counts = outlier_df.groupby('date').size()
                plt.figure(figsize=(8, 4))
                bars = plt.bar(date_counts.index, date_counts.values, color='orange')
                plt.title('날짜별 이상치 개수', fontproperties=font_prop)
                plt.xlabel('날짜', fontproperties=font_prop)
                plt.ylabel('이상치 개수', fontproperties=font_prop)
                # x축 라벨 45도 회전
                plt.xticks(rotation=45)
                # 각 막대 위에 값 표시
                for bar in bars:
                    height = bar.get_height()
                    plt.text(bar.get_x() + bar.get_width()/2.0, height, f'{height:.0f}', ha='center', va='bottom', fontsize=10)
                plt.tight_layout()
                img_buf2 = io.BytesIO()
                plt.savefig(img_buf2, format='png')
                plt.close()
                img_buf2.seek(0)
                img_path2 = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
                with open(img_path2, 'wb') as f:
                    f.write(img_buf2.read())
                pdf.image(img_path2, w=pdf.w - 20)
                pdf.ln(5)
            # 무게 변화 기록 (표로 표시)
            if include_graph:
                # 새 페이지에 우상단 로고 추가
                pdf.add_page()
                add_logo_to_page()
                
                pdf.set_font(font_name, '', 14)
                pdf.cell(0, 10, '무게 변화 기록', ln=True)
                pdf.set_font(font_name, '', 8)
                
                # 표 데이터 준비
                display_df = df[['loadcel', 'timestamp', 'current_weight_history']].copy()
                display_df['current_weight_history_kg'] = display_df['current_weight_history'] / 1000
                
                # 상위/하위 0.1% 제외 (오차/노이즈 최소화)
                for loadcel_id in display_df['loadcel'].unique():
                    loadcel_data = display_df[display_df['loadcel'] == loadcel_id]
                    if len(loadcel_data) > 0:
                        lower_bound = loadcel_data['current_weight_history_kg'].quantile(0.001)
                        upper_bound = loadcel_data['current_weight_history_kg'].quantile(0.999)
                        mask = (loadcel_data['current_weight_history_kg'] >= lower_bound) & (loadcel_data['current_weight_history_kg'] <= upper_bound)
                        display_df = display_df[~((display_df['loadcel'] == loadcel_id) & ~mask)]
                
                # 최근 30개 데이터만 표시 (PDF에서는 더 적게)
                if len(display_df) > 30:
                    display_df = display_df.tail(30)
                
                # 컬럼 너비 설정
                col_widths = [30, 60, 40]  # 로드셀, 시간, 무게
                
                # 헤더 출력
                headers = ['로드셀', '시간', '무게(kg)']
                for i, header in enumerate(headers):
                    pdf.cell(col_widths[i], 8, header, border=1)
                pdf.ln()
                
                # 데이터 출력
                for i, row in display_df.iterrows():
                    # 로드셀 번호
                    loadcel_name = f"로드셀 {row['loadcel']}번"
                    pdf.cell(col_widths[0], 6, loadcel_name, border=1)
                    
                    # 시간 (간단하게 표시)
                    try:
                        time_str = pd.to_datetime(row['timestamp']).strftime('%m-%d %H:%M')
                    except:
                        time_str = str(row['timestamp'])[:10]
                    pdf.cell(col_widths[1], 6, time_str, border=1)
                    
                    # 무게 (kg)
                    kg_value = row['current_weight_history_kg']
                    pdf.cell(col_widths[2], 6, f"{kg_value:.3f}", border=1)
                    
                    pdf.ln()
                
                pdf.ln(5)
                
                # 무게 변화 그래프 추가 (날짜별 합산 bar 그래프)
                import matplotlib.dates as mdates
                plt.figure(figsize=(10, 4))
                
                # 데이터 준비
                df_sorted = df.copy()
                df_sorted['timestamp'] = pd.to_datetime(df_sorted['timestamp'])
                df_sorted['current_weight_history_kg'] = df_sorted['current_weight_history'] / 1000
                df_sorted['date'] = df_sorted['timestamp'].dt.date

                # 상위/하위 0.1% 제외 (오차/노이즈 최소화)
                for loadcel_id in df_sorted['loadcel'].unique():
                    loadcel_data = df_sorted[df_sorted['loadcel'] == loadcel_id]
                    if len(loadcel_data) > 0:
                        lower_bound = loadcel_data['current_weight_history_kg'].quantile(0.001)
                        upper_bound = loadcel_data['current_weight_history_kg'].quantile(0.999)
                        mask = (loadcel_data['current_weight_history_kg'] >= lower_bound) & (loadcel_data['current_weight_history_kg'] <= upper_bound)
                        df_sorted = df_sorted[~((df_sorted['loadcel'] == loadcel_id) & ~mask)]

                # 날짜별, 로드셀별 평균 무게 계산
                daily_avg = df_sorted.groupby(['date', 'loadcel'])['current_weight_history_kg'].mean().reset_index()
                
                # 각 로드셀별로 bar 그래프 그리기
                unique_dates = sorted(daily_avg['date'].unique())
                unique_loadcels = sorted(daily_avg['loadcel'].unique())
                
                # x축 위치 설정
                x_positions = range(len(unique_dates))
                bar_width = 0.8 / len(unique_loadcels)
                
                colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']  # 다양한 색상
                
                for i, loadcel_id in enumerate(unique_loadcels):
                    loadcel_data = daily_avg[daily_avg['loadcel'] == loadcel_id]
                    values = []
                    for date in unique_dates:
                        date_data = loadcel_data[loadcel_data['date'] == date]
                        if len(date_data) > 0:
                            values.append(date_data['current_weight_history_kg'].iloc[0])
                        else:
                            values.append(0)
                    
                    x_pos = [pos + i * bar_width for pos in x_positions]
                    bars = plt.bar(x_pos, values, bar_width, label=f"로드셀 {loadcel_id}번", color=colors[i % len(colors)])
                    # 각 막대 위에 값 표시
                    for bar in bars:
                        height = bar.get_height()
                        plt.text(bar.get_x() + bar.get_width()/2.0, height, f'{height:.2f}', ha='center', va='bottom', fontsize=9)

                plt.xlabel("날짜", fontproperties=font_prop)
                plt.ylabel("평균 무게 (kg)", fontproperties=font_prop)
                plt.title("날짜별 평균 무게 변화", fontproperties=font_prop)
                plt.legend(prop=font_prop)
                plt.grid(True, alpha=0.3)

                # x축 라벨 설정
                plt.xticks([pos + bar_width * (len(unique_loadcels) - 1) / 2 for pos in x_positions], 
                          [date.strftime('%m-%d') for date in unique_dates], rotation=45)
                plt.tight_layout()

                # 이미지로 저장 후 PDF에 삽입
                img_buf = io.BytesIO()
                plt.savefig(img_buf, format='png', dpi=300)
                plt.close()
                img_buf.seek(0)

                img_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
                with open(img_path, 'wb') as f:
                    f.write(img_buf.read())
                pdf.image(img_path, w=pdf.w - 20)
                pdf.ln(5)
                
                # 무게 변화 기록 바로 밑에 푸터 추가
                add_professional_footer()
            
            tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            pdf.output(tmpfile.name)
            tmpfile.seek(0)
            return tmpfile
        # 3. PDF 다운로드 버튼 (옵션별 포함)
        if include_stats:
            # stats, outlier, fig 등 준비
            # 상위 1% 중간값 계산
            top_1_percent_values = []
            for loadcel in stats.index:
                loadcel_data = period_df[period_df['loadcel'] == loadcel]['current_weight_history']
                if len(loadcel_data) > 0:
                    top_1_percent = loadcel_data.quantile(0.99)
                    top_1_percent_values.append(top_1_percent)
                else:
                    top_1_percent_values.append(0)
            
            stats_with_top1 = stats.copy()
            stats_with_top1['top_1_percent'] = top_1_percent_values
            stats_df = stats_with_top1.rename(columns={'count': '측정수', 'mean': '평균', 'min': '최소', 'top_1_percent': '최대'}) if include_stats else None
            outlier_df = outlier[['loadcel', 'timestamp', 'current_weight_history', 'diff']] if include_outlier and 'outlier' in locals() and not outlier.empty else None
            
            # 그래프 생성 코드는 주석처리 (표로 대체)
            # graph_fig = None
            # if include_graph:
            #     import plotly.express as px
            #     # g를 kg으로 변환
            #     period_df_kg = period_df.copy()
            #     period_df_kg['current_weight_history_kg'] = period_df_kg['current_weight_history'] / 1000
            #     
            #     # timestamp를 datetime으로 변환
            #     period_df_kg['timestamp'] = pd.to_datetime(period_df_kg['timestamp'])
            #     
            #     graph_fig = px.line(
            #         period_df_kg,
            #         x='timestamp',
            #         y='current_weight_history_kg',
            #         color='loadcel',
            #         markers=True,
            #         color_discrete_sequence=px.colors.qualitative.Set1
            #     )
            #     # 그래프 개선: 단위 표기, x축 포맷, xticks 회전
            #     graph_fig.update_layout(
            #         yaxis_title="무게 (kg)",
            #         xaxis_title="시간"
            #     )
            #     # x축 시간 포맷 개선 (지수 표현 제거)
            #     graph_fig.update_xaxes(
            #         tickformat='%Y-%m-%d %H:%M:%S',
            #         tickangle=45
            #     )
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
                    include_graph=include_graph
                )).read(),
                file_name=f"{selected_period} 환자 추종 스마트 링거폴대 보고서.pdf",
                mime="application/pdf"
            ):
                pass
else:
    st.warning("아직 기록된 데이터가 없습니다.")