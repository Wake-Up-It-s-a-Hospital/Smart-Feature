import streamlit as st
import boto3
from boto3.dynamodb.conditions import Key

def render_alert_sidebar():
    # 알림 헤더와 모두 지우기 버튼
    col1, col2 = st.sidebar.columns([6, 4])
    with col1:
        st.markdown("### 📋 알림")
    with col2:
        if st.session_state.get('alert_list') and len(st.session_state['alert_list']) > 3:
            if st.button("모두 지우기", key="clear_all_alerts"):
                st.session_state['alert_list'] = []
                st.session_state['alert_flags'] = set()
                st.rerun()
    
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

# ====== 알림 템플릿 딕셔너리 ======
ALERT_TEMPLATES = {
    1: "{pole}번 폴대의 {bottle} 수액이 다 투여되었습니다.",
    2: "{pole}번 폴대의 {bottle} 수액이 거의 다 되었습니다. (남은 시간: {remaining_sec:.0f}분, 무게: {current_weight:.1f}g)",
    3: "{pole}번 폴대의 배터리가 부족합니다.",
    4: "{pole}번 폴대에서 너스콜이 발생했습니다."
}

# ====== 알림 추가 함수 ======
def add_alert(alert_id, **params):
    """알림을 추가하는 함수"""
    template = ALERT_TEMPLATES.get(alert_id)
    if template is None:
        return
    
    msg = template.format(**params)
    
    # 중복 방지: 같은 알림이 이미 있으면 추가하지 않음
    key = (alert_id, tuple(sorted(params.items())))
    if "alert_flags" not in st.session_state:
        st.session_state.alert_flags = set()
    if key in st.session_state.alert_flags:
        return
    
    st.session_state.alert_flags.add(key)
    st.session_state.alert_list.append({
        "id": alert_id,
        "msg": msg,
        "params": params
    })

# ====== 배터리 상태 체크 및 알림 함수 ======
def check_battery_alerts():
    """모든 폴대의 배터리 상태를 체크하고 알림을 생성하는 함수"""
    try:
        dynamodb = boto3.resource('dynamodb', region_name='ap-northeast-2')
        table_polestat = dynamodb.Table('pole_stat')
        
        # 현재 활성화된 폴대들 확인 (loadcell_data에서)
        loadcell_data = st.session_state.get('loadcell_data', {})
        
        for loadcel_id in loadcell_data.keys():
            try:
                response = table_polestat.query(
                    KeyConditionExpression=Key('pole_id').eq(int(loadcel_id)),
                    ScanIndexForward=False,
                    Limit=1
                )
                
                if response.get('Items'):
                    battery_level = response['Items'][0].get('battery_level', None)
                    if battery_level is not None and battery_level <= 1:
                        # 배터리 부족 알림 (레벨 1 이하)
                        add_alert(3, pole=loadcel_id, battery=battery_level)
                        
            except Exception as e:
                print(f"폴대 {loadcel_id} 배터리 정보 조회 실패: {e}")
                continue
                
    except Exception as e:
        print(f"배터리 알림 체크 실패: {e}")

# ====== 수액 관련 알림 체크 함수 ======
def check_infusion_alerts():
    """수액 상태를 체크하고 알림을 생성하는 함수"""
    loadcell_data = st.session_state.get('loadcell_data', {})
    
    for loadcel, data in loadcell_data.items():
        pole = loadcel
        bottle = "오른쪽"
        
        # 각 장비별 임계값 불러오기
        almost_key = f'alert_almost_weight_{loadcel}'
        done_key = f'alert_done_weight_{loadcel}'
        almost_weight = st.session_state.get(almost_key, 300)
        done_weight = st.session_state.get(done_key, 150)
        
        # 투여 거의 완료 (무게만으로 판단)
        if (0 < data.get("current_weight", 99999) <= almost_weight):
            add_alert(2, pole=pole, bottle=bottle, 
                     remaining_sec=data.get("remaining_sec", -1), 
                     current_weight=data.get("current_weight", 0))
        
        # 투여 완료
        if (0 < data.get("current_weight", 99999) <= done_weight):
            add_alert(1, pole=pole, bottle=bottle)
        
        # 너스콜
        if data.get("nurse_call", False):
            add_alert(4, pole=pole)

# ====== 통합 알림 체크 함수 ======
def check_all_alerts():
    """모든 알림을 체크하는 통합 함수"""
    check_infusion_alerts()  # 수액 관련 알림
    check_battery_alerts()   # 배터리 관련 알림