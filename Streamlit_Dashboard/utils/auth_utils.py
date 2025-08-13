import os
import json
import streamlit as st


try:
    import bcrypt
except Exception:
    bcrypt = None


USERS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '../users.json'))


def _ensure_dirs():
    base_dir = os.path.dirname(USERS_FILE)
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok=True)


def _hash_password(plain: str) -> str:
    if bcrypt is None:
        # 안전하지 않지만, 의존성 미설치 시 임시 비교용
        return f"plain::{plain}"
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode('utf-8'), salt).decode('utf-8')


def _verify_password(plain: str, hashed: str) -> bool:
    if bcrypt is None:
        return hashed == f"plain::{plain}"
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def _load_users() -> dict:
    _ensure_dirs()
    if not os.path.exists(USERS_FILE):
        _create_default_users()
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_users(users: dict) -> None:
    _ensure_dirs()
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def _create_default_users() -> None:
    users = {
        "admin": {
            "name": "관리자",
            "role": "admin",
            "password_hash": _hash_password("admin123")
        },
        "nurse1": {
            "name": "간호사1",
            "role": "clinician",
            "password_hash": _hash_password("nurse123")
        }
    }
    _save_users(users)


def ensure_auth(allowed_roles=None):
    if 'user' in st.session_state and st.session_state['user']:
        if allowed_roles is None:
            return True
        return st.session_state['user'].get('role') in set(allowed_roles)

    st.title("로그인")
    st.info("계정으로 로그인해 주세요.")
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("아이디")
        password = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("로그인")
    if submitted:
        users = _load_users()
        user = users.get(username)
        if user and _verify_password(password, user.get('password_hash', '')):
            st.session_state['user'] = {
                'username': username,
                'name': user.get('name', username),
                'role': user.get('role', 'clinician')
            }
            st.success("로그인 성공")
            st.rerun()
        else:
            st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
    st.stop()


def require_auth(allowed_roles=None):
    ok = ensure_auth(allowed_roles=allowed_roles)
    if not ok:
        st.error("해당 페이지에 접근할 권한이 없습니다.")
        st.stop()


def get_current_user():
    return st.session_state.get('user')


def logout_button(sidebar: bool = True):
    container = st.sidebar if sidebar else st
    if container.button("로그아웃"):
        st.session_state.pop('user', None)
        st.success("로그아웃 되었습니다.")
        st.rerun()


def render_userbox(sidebar: bool = True):
    user = get_current_user()
    if not user:
        return
    container = st.sidebar if sidebar else st
    container.markdown(f"**사용자**: {user.get('name')} ({user.get('role')})")
    logout_button(sidebar=sidebar)


def render_login_inline(sidebar: bool = False):
    if get_current_user():
        return
    container = st.sidebar if sidebar else st
    with container.form("inline_login_form", clear_on_submit=False):
        username = st.text_input("아이디")
        password = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("로그인")
    if submitted:
        users = _load_users()
        user = users.get(username)
        if user and _verify_password(password, user.get('password_hash', '')):
            st.session_state['user'] = {
                'username': username,
                'name': user.get('name', username),
                'role': user.get('role', 'clinician')
            }
            st.success("로그인 성공")
            st.rerun()
        else:
            st.error("아이디 또는 비밀번호가 올바르지 않습니다.")


def admin_create_or_update_user():
    require_auth(allowed_roles=["admin"]) 
    st.subheader("사용자 생성/수정")
    users = _load_users()
    mode = st.radio("모드", ["생성", "수정"], horizontal=True)
    if mode == "생성":
        new_username = st.text_input("아이디")
        new_name = st.text_input("이름")
        new_role = st.selectbox("역할", ["clinician", "admin"])
        new_password = st.text_input("비밀번호", type="password")
        if st.button("생성"):
            if not new_username or not new_password:
                st.warning("아이디와 비밀번호를 입력하세요.")
            elif new_username in users:
                st.error("이미 존재하는 아이디입니다.")
            else:
                users[new_username] = {
                    "name": new_name or new_username,
                    "role": new_role,
                    "password_hash": _hash_password(new_password)
                }
                _save_users(users)
                st.success("사용자 생성 완료")
                st.rerun()
    else:
        target = st.selectbox("수정할 아이디", list(users.keys()) or [""])
        if target:
            cur = users[target]
            new_name = st.text_input("이름", value=cur.get('name', target))
            new_role = st.selectbox("역할", ["clinician", "admin"], index=0 if cur.get('role') == 'clinician' else 1)
            new_password = st.text_input("비밀번호 (변경 시 입력)", type="password")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("저장"):
                    cur['name'] = new_name
                    cur['role'] = new_role
                    if new_password:
                        cur['password_hash'] = _hash_password(new_password)
                    users[target] = cur
                    _save_users(users)
                    st.success("저장 완료")
                    st.rerun()
            with col2:
                if st.button("삭제", type="primary"):
                    if target == st.session_state.get('user', {}).get('username'):
                        st.error("본인 계정은 삭제할 수 없습니다.")
                    else:
                        users.pop(target, None)
                        _save_users(users)
                        st.success("삭제 완료")
                        st.rerun()


