import streamlit as st

st.title("📄 보고서 생성")

st.warning("🚧 기능 개발 중 🚧")
st.info(
    """
    이 페이지에서는 특정 기간의 운영 데이터를 요약하여 보고서로 생성하고,
    PDF 또는 CSV 파일로 다운로드하는 기능을 제공할 예정입니다.
    
    이를 위해서는 **과거 데이터를 DynamoDB에 지속적으로 저장하는 기능**의 추가 개발이 필요합니다.
    """
)

st.write("---")
st.subheader("월간 보고서 생성 (예시)")

selected_month = st.selectbox("보고서 생성 월 선택:", ["2025년 6월", "2025년 5월", "2025년 4월"])

if st.button("보고서 생성 (미구현)"):
    st.success(f"'{selected_month}'의 보고서가 성공적으로 생성되었습니다. (향후 다운로드 링크 제공)")
