import streamlit as st

def render_alert_sidebar():
    st.sidebar.markdown("### 📋 알림")
    if st.session_state.get('alert_list'):
        if 'alert_remove_idx' not in st.session_state:
            st.session_state['alert_remove_idx'] = None
        for idx, alert in enumerate(st.session_state['alert_list']):
            col1, col2 = st.sidebar.columns([8, 1])
            with col1:
                if alert["id"] == 1:
                    st.success(alert["msg"])
                elif alert["id"] == 2:
                    st.warning(alert["msg"])
                elif alert["id"] == 3:
                    st.error(alert["msg"])
                elif alert["id"] == 4:
                    st.error(alert["msg"])
                else:
                    st.info(alert["msg"])
            with col2:
                if st.button("✖", key=f"alert_x_{idx}"):
                    st.session_state['alert_remove_idx'] = idx
        if st.session_state['alert_remove_idx'] is not None:
            del st.session_state['alert_list'][st.session_state['alert_remove_idx']]
            st.session_state['alert_remove_idx'] = None
    else:
        st.sidebar.info("새로운 알림이 없습니다.")