import streamlit as st
from utils.auth_utils import require_auth, render_userbox, get_current_user
from utils.assign_utils import render_assignment_manager


st.set_page_config(page_title="담당 환자 배정", page_icon="🧑⚕️", layout="wide")
st.title("담당 환자(장비) 배정")


user = get_current_user()
if not user:
    try:
        st.switch_page("환자_추종_스마트_링거폴대_소개.py")
    except Exception:
        st.stop()
require_auth(allowed_roles=["admin"])  # 관리자만 관리 가능
render_userbox()


loadcell_data = st.session_state.get('loadcell_data', {})
all_devices = sorted(loadcell_data.keys())


render_assignment_manager(all_devices=all_devices)


