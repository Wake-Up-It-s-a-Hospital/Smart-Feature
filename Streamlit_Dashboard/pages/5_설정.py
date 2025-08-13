import streamlit as st
import json
from utils.alert_utils import render_alert_sidebar, check_all_alerts
from utils.logo_utils import show_logo
from utils.auth_utils import require_auth, render_userbox, admin_create_or_update_user, get_current_user
from utils.assign_utils import render_assignment_manager

st.title("설정")
user = get_current_user()
if not user:
    try:
        st.switch_page("환자_추종_스마트_링거폴대_소개.py")
    except Exception:
        st.stop()
require_auth(allowed_roles=["admin"])  # 설정 페이지는 관리자 전용으로 가정
render_userbox()

show_logo()
# 사이드바 내용 추가
st.sidebar.header("설정")
st.sidebar.write("다양한 설정값들을")
st.sidebar.write("원하는대로 바꿀 수 있습니다.")
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

# === 알림 카테고리별 표시 여부 설정 ===
st.subheader("알림 카테고리별 표시 설정")
if 'alert_enabled_almost' not in st.session_state:
    st.session_state['alert_enabled_almost'] = True
if 'alert_enabled_done' not in st.session_state:
    st.session_state['alert_enabled_done'] = True
if 'alert_enabled_nursecall' not in st.session_state:
    st.session_state['alert_enabled_nursecall'] = True
if 'alert_enabled_battery' not in st.session_state:
    st.session_state['alert_enabled_battery'] = True
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.session_state['alert_enabled_almost'] = st.checkbox("거의 다 됨 알림", value=st.session_state['alert_enabled_almost'])
with col2:
    st.session_state['alert_enabled_done'] = st.checkbox("투여 완료 알림", value=st.session_state['alert_enabled_done'])
with col3:
    st.session_state['alert_enabled_nursecall'] = st.checkbox("너스콜 알림", value=st.session_state['alert_enabled_nursecall'])
with col4:
    st.session_state['alert_enabled_battery'] = st.checkbox("배터리 알림", value=st.session_state['alert_enabled_battery'])

# === 알림 임계값 설정 (비율 기반) ===
st.subheader("알림 임계값 설정")
if st.session_state['alert_enabled_almost']:
    if 'alert_almost_ratio' not in st.session_state:
        st.session_state['alert_almost_ratio'] = 30
    st.session_state['alert_almost_ratio'] = st.slider("거의 다 됨 알림 기준 (%)", 10, 50, st.session_state['alert_almost_ratio'], 5)
    st.info(f"꽉 찬 수액팩 무게의 {st.session_state['alert_almost_ratio']}% 이하일 때 알림이 발생합니다.")
if st.session_state['alert_enabled_done']:
    if 'alert_done_ratio' not in st.session_state:
        st.session_state['alert_done_ratio'] = 10
    st.session_state['alert_done_ratio'] = st.slider("투여 완료 알림 기준 (%)", 5, 20, st.session_state['alert_done_ratio'], 1)
    st.info(f"꽉 찬 수액팩 무게의 {st.session_state['alert_done_ratio']}% 이하일 때 알림이 발생합니다.")

st.markdown("---")
st.subheader("계정 관리")
admin_create_or_update_user()

# === 기타 시스템 정보/버전 ===
st.markdown("---")
st.subheader("담당 환자(장비) 배정")
loadcell_data = st.session_state.get('loadcell_data', {})
all_devices = sorted(loadcell_data.keys())
render_assignment_manager(all_devices=all_devices)

st.markdown("---")
st.subheader("시스템 정보")
st.markdown("- 버전: v1.8.5")
st.markdown("- 최근 업데이트: 2025-08-13")