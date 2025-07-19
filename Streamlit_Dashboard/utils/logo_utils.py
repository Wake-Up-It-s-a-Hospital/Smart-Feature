import streamlit as st
import os

def show_logo(width=220):
    """
    Streamlit 사이드바 맨 위에 로고 이미지를 띄웁니다.
    기본 경로: images/tuk_med.jpg
    width: 이미지 너비 (기본값 220)
    """
    logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../images/tuk_med.jpg'))
    if os.path.exists(logo_path):
        st.sidebar.image(logo_path, width=width)
    else:
        st.sidebar.warning("로고 이미지를 찾을 수 없습니다.") 