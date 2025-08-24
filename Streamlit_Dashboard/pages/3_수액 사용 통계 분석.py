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

# ====== 데이터 상태 표시 ======
st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 데이터 상태")
try:
    from utils.dummy_data_utils import is_dummy_data_available, get_dummy_data_summary
    
    if is_dummy_data_available():
        summary = get_dummy_data_summary()
        if summary:
            st.sidebar.success("✅ 데이터 로드 완료")
            if 'loadcell_history' in summary:
                st.sidebar.write(f"📊 히스토리: {summary['loadcell_history']['total_items']}개")
                st.sidebar.write(f"🏗️ 폴대: {summary['loadcell_history']['poles_with_history']}개")
        else:
            st.sidebar.info("ℹ️ 데이터 정보 없음")
    else:
        st.sidebar.info("ℹ️ 데이터 로드 중")
except ImportError:
    st.sidebar.info("ℹ️ 데이터 유틸리티 로드 중")
except Exception as e:
    st.sidebar.error(f"❌ 데이터 상태 확인 실패")

st.title("수액 사용 통계 분석")

# 데이터 불러오기
@st.cache_data
def get_history_df():
    # 추가 데이터와 실제 DB 데이터를 병합하여 반환
    try:
        from utils.dummy_data_utils import get_combined_analysis_data, is_dummy_data_available
        
        if is_dummy_data_available():
            # 추가 데이터 사용
            df = get_combined_analysis_data()
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
    try:
        fig_hm = px.imshow(heatmap_pivot, text_auto=True, color_continuous_scale='Blues', aspect='auto')
        fig_hm.update_layout(title="시간대별 평균 사용량(kg)", xaxis_title="장비", yaxis_title="시간(시)")
        st.plotly_chart(fig_hm, use_container_width=True)
    except Exception:
        st.dataframe(heatmap_pivot, height=300)

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

st.subheader("고급 통계 기능")
col1, col2, col3 = st.columns(3)

with st.expander("상관관계 분석 (장비별 사용량)", expanded=False):
    if filtered.empty:
        st.info("선택된 기간/장비 조건에 데이터가 없어 상관관계를 계산할 수 없습니다.")
    else:
        corr_freq_label = st.sidebar.selectbox("상관관계 집계 간격", ["15분", "30분", "1시간"], index=2, key="corr_freq_select")
        freq_map = {"15분": "15T", "30분": "30T", "1시간": "1H"}
        freq = freq_map[corr_freq_label]

        df_corr = filtered.copy()
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
                fig = px.imshow(corr_mat, text_auto=True, zmin=-1, zmax=1, color_continuous_scale='RdBu')
                fig.update_layout(title="장비별 사용량 상관관계")
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.warning(f"상관관계 분석 중 오류가 발생했습니다: {e}")

with st.expander("트렌드 분석 (무게 추이 및 기울기)", expanded=False):
    if filtered.empty:
        st.info("데이터가 없어 트렌드를 계산할 수 없습니다.")
    else:
        trend_rows = []
        for loadcel_id, grp in filtered.sort_values('timestamp').groupby('loadcel'):
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

            loadcel_options = filtered['loadcel'].unique().tolist()
            sel = st.selectbox("트렌드 상세 보기 - 장비 선택", loadcel_options)
            grp = filtered[filtered['loadcel'] == sel].sort_values('timestamp')
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

with st.expander("이상치 자동 감지", expanded=False):
    if filtered.empty:
        st.info("데이터가 없어 이상치 탐지를 수행할 수 없습니다.")
    else:
        od_method = st.sidebar.selectbox("이상치 방법", ["이동표준편차", "ARIMA 잔차"], index=0, key="od_method")
        threshold_sigma = st.sidebar.slider("임계 기준(시그마)", 2.0, 5.0, 3.0, 0.5, key="od_sigma")
        single = st.selectbox("장비 선택(단일 감지)", filtered['loadcel'].unique().tolist())
        series = filtered[filtered['loadcel'] == single].sort_values('timestamp')
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
    if df.empty:
        st.info("데이터가 없어 계절성 분석을 수행할 수 없습니다.")
    else:
        sel2 = st.selectbox("장비 선택(계절성)", df['loadcel'].unique().tolist(), key="season_sel")
        series2 = df[df['loadcel'] == sel2].sort_values('timestamp')
        if len(series2) < 24:
            st.info("분해를 위해 더 긴 시계열이 필요합니다.")
        else:
            ts = series2[['timestamp', 'current_weight_history']].dropna()
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

with st.expander("장비 클러스터링 (KMeans)", expanded=False):
    if df.empty:
        st.info("데이터가 없어 클러스터링을 수행할 수 없습니다.")
    else:
        # 장비별 특성 벡터: 평균 사용량(kg), 변동성(표준편차, kg), 일별 평균 사용량(kg)의 평균
        feat = filtered.copy()
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
                fig6.update_layout(title="장비 클러스터링 (평균 vs 표준편차)")
                st.plotly_chart(fig6, use_container_width=True)
            except Exception as e:
                st.warning(f"클러스터링 중 오류: {e}")

with st.expander("다중회귀: 시간대/요일 영향 분석", expanded=False):
    if filtered.empty:
        st.info("데이터가 없어 회귀 분석을 수행할 수 없습니다.")
    else:
        reg_freq_label = st.sidebar.selectbox(
            "회귀 집계 간격",
            ["15분", "30분", "1시간"],
            index=2,
            key="reg_freq",
            help="회귀에 사용할 집계 간격입니다. 시간/요일 더미와 함께 사용량을 해당 간격으로 합산합니다."
        )
        freq_map = {"15분": "15T", "30분": "30T", "1시간": "1H"}
        rf = freq_map[reg_freq_label]
        use_device_dummies = st.sidebar.checkbox("장비 더미 포함", value=False, key="reg_dev_dummy")
        tmp = filtered.copy().sort_values('timestamp')
        tmp['prev_weight'] = tmp.groupby('loadcel')['current_weight_history'].shift(1)
        tmp['usage'] = (tmp['prev_weight'] - tmp['current_weight_history']).clip(lower=0) / 1000
        # 시간대/요일 특성 생성
        tmp['hour'] = tmp['timestamp'].dt.hour
        tmp['weekday'] = tmp['timestamp'].dt.weekday
        # 리샘플: 장비별 합산 후 전체 합산(장비 효과는 더미로 보완 가능)
        df_res = (tmp.set_index('timestamp')
                    .groupby('loadcel')
                    .resample(rf)['usage']
                    .sum()
                    .reset_index())
        # 특성 병합
        df_res['hour'] = df_res['timestamp'].dt.hour
        df_res['weekday'] = df_res['timestamp'].dt.weekday
        # 설계행렬
        feats = ['hour', 'weekday']
        X = pd.get_dummies(df_res[feats], columns=['hour', 'weekday'], drop_first=True)
        if use_device_dummies:
            X = pd.concat([X, pd.get_dummies(df_res['loadcel'].astype(str), prefix='dev', drop_first=True)], axis=1)
        y = df_res['usage'].fillna(0)
        X = sm.add_constant(X, has_constant='add')
        try:
            model = sm.OLS(y, X)
            res = model.fit()
            coef = res.params.rename('coef').to_frame()
            pvals = res.pvalues.rename('pvalue').to_frame()
            out = coef.join(pvals, how='left')
            out['abs_coef'] = out['coef'].abs()
            out = out.sort_values('abs_coef', ascending=False).drop(columns=['abs_coef'])
            st.dataframe(out, use_container_width=True)
            st.caption("계수는 사용량(kg) 변화량에 대한 기여 추정치입니다. p-value가 낮을수록 통계적으로 유의합니다.")
        except Exception as e:
            st.warning(f"회귀 적합 중 오류: {e}")


with st.expander("예측: ARIMA 단기 예측", expanded=False):
    if filtered.empty:
        st.info("데이터가 없어 예측을 수행할 수 없습니다.")
    else:
        sel_fc = st.selectbox(
            "장비 선택(예측)",
            filtered['loadcel'].unique().tolist(),
            key="fc_sel",
            help="ARIMA 단기 예측을 수행할 장비입니다."
        )
        horizon = st.sidebar.slider("예측 구간(분)", 10, 240, 60, 10, key="fc_h")
        series3 = filtered[filtered['loadcel'] == sel_fc].sort_values('timestamp')
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


with st.expander("요일-시간대 히트맵 (평균 사용량)", expanded=False):
    if filtered.empty:
        st.info("데이터가 없어 히트맵을 만들 수 없습니다.")
    else:
        tmp2 = filtered.copy().sort_values('timestamp')
        tmp2['prev_weight'] = tmp2.groupby('loadcel')['current_weight_history'].shift(1)
        tmp2['usage'] = (tmp2['prev_weight'] - tmp2['current_weight_history']).clip(lower=0) / 1000
        tmp2['hour'] = tmp2['timestamp'].dt.hour
        tmp2['weekday'] = tmp2['timestamp'].dt.weekday
        heat = tmp2.groupby(['weekday', 'hour'])['usage'].mean().reset_index()
        heat_pivot = heat.pivot(index='weekday', columns='hour', values='usage').fillna(0)
        figh = px.imshow(heat_pivot, text_auto=True, color_continuous_scale='Blues')
        figh.update_layout(title="요일-시간대 평균 사용량(kg)")
        st.plotly_chart(figh, use_container_width=True)


with st.expander("장비 간 지연 상관분석 (Cross-Correlation)", expanded=False):
    if filtered.empty or len(filtered['loadcel'].unique()) < 2:
        st.info("두 개 이상의 장비 데이터가 필요합니다.")
    else:
        devs = filtered['loadcel'].unique().tolist()
        a = st.selectbox("장비 A", devs, index=0, help="지연 상관을 계산할 첫 번째 장비입니다.")
        b = st.selectbox("장비 B", devs, index=1 if len(devs) > 1 else 0, help="지연 상관을 계산할 두 번째 장비입니다.")
        max_lag_req = st.sidebar.slider("최대 지연(분)", 5, 120, 30, 5, key="ccf_lag")
        freq = '1T'
        def usage_series(d):
            ddf = filtered[filtered['loadcel'] == d].sort_values('timestamp')
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
            figcc.update_layout(title=f"장비 {a} vs {b} 지연 상관")
            st.plotly_chart(figcc, use_container_width=True)
            # 최대 상관 지연 표시 (NaN 제외)
            valid = [(lag, v) for lag, v in zip(lags, vals) if v == v]
            if valid:
                best_k = max(valid, key=lambda t: abs(t[1]))[0]
                st.caption(f"최대 상관 지연: {best_k}분")


with st.expander("PCA 시각화 (장비 특성)", expanded=False):
    if df.empty:
        st.info("데이터가 없어 PCA를 수행할 수 없습니다.")
    else:
        # 앞서 만든 agg가 있을 수 있으나 안정적으로 재계산
        feat = filtered.copy().sort_values('timestamp')
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
    if filtered.empty:
        st.info("데이터가 없어 롤링 기울기를 계산할 수 없습니다.")
    else:
        sel_roll = st.selectbox("장비 선택(롤링)", filtered['loadcel'].unique().tolist(), key="roll_sel")
        win_min = st.sidebar.slider("윈도우(분)", 10, 240, 60, 10, key="roll_win")
        grp = filtered[filtered['loadcel'] == sel_roll].sort_values('timestamp')
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
    if filtered.empty:
        st.info("데이터가 없어 ACF/PACF를 계산할 수 없습니다.")
    else:
        sel_acf = st.selectbox("장비 선택(ACF)", filtered['loadcel'].unique().tolist(), key="acf_sel", help="자기상관(ACF)과 부분자기상관(PACF)은 시계열 데이터의 자기상관성을 분석하는 통계적 방법입니다. ACF는 시계열 데이터와 그 지연된 버전 간의 상관관계를 측정하며, PACF는 다른 지연된 버전의 영향을 제거한 후의 상관관계를 측정합니다. 이 도구는 시계열 데이터의 자기상관성을 분석하여 시계열 데이터의 특성을 이해하고 예측 모델을 개발하는 데 도움을 줍니다.")
        lags = st.sidebar.slider("최대 랙", 10, 60, 40, 5, key="acf_lags")
        series4 = filtered[filtered['loadcel'] == sel_acf].sort_values('timestamp')
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
