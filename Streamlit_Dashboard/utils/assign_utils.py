import os
import json
import streamlit as st
from .auth_utils import require_auth, get_current_user


ASSIGN_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '../assignments.json'))


def _ensure_dir():
    base = os.path.dirname(ASSIGN_FILE)
    if not os.path.exists(base):
        os.makedirs(base, exist_ok=True)


def _load_assignments() -> dict:
    _ensure_dir()
    if not os.path.exists(ASSIGN_FILE):
        _save_assignments({})
    try:
        with open(ASSIGN_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_assignments(data: dict) -> None:
    _ensure_dir()
    with open(ASSIGN_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user_assignments(username: str) -> list:
    data = _load_assignments()
    return data.get(username, [])


def set_user_assignments(username: str, devices: list) -> None:
    data = _load_assignments()
    data[username] = list(sorted(set(map(str, devices))))
    _save_assignments(data)


def render_assignment_manager(all_devices: list):
    require_auth(allowed_roles=["admin"]) 
    st.subheader("담당 환자(장비) 배정 관리")
    if not all_devices:
        st.info("현재 활성 장비가 없습니다. 실시간 데이터 수신 후 다시 시도하세요.")
        return
    # 사용자 선택
    from .auth_utils import _load_users  # 내부 사용 목적
    users = _load_users()
    usernames = list(users.keys())
    if not usernames:
        st.warning("사용자가 없습니다. 먼저 계정을 생성하세요.")
        return
    target_user = st.selectbox("의료진 선택", usernames)
    current = set(get_user_assignments(target_user))
    selected = st.multiselect("담당 장비 선택", options=list(map(str, all_devices)), default=sorted(current))
    if st.button("저장"):
        set_user_assignments(target_user, selected)
        st.success("배정이 저장되었습니다.")
        st.rerun()


def require_device_access(device_id: str):
    user = get_current_user()
    if not user:
        require_auth()
    role = user.get('role')
    if role == 'admin':
        return True
    assigned = set(get_user_assignments(user.get('username', '')))
    if str(device_id) in assigned:
        return True
    st.error("해당 장비에 대한 접근 권한이 없습니다.")
    st.stop()


