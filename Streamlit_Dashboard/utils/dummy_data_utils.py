#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
추가 데이터 관리를 위한 유틸리티 함수들

이 모듈은 로컬 JSON 파일에서 추가 데이터를 로드하고,
실제 DB 데이터와 병합하여 사용할 수 있게 해줍니다.
"""

import json
import os
from typing import Dict, List, Any, Optional
import pandas as pd
from datetime import datetime, timezone, timedelta

# 추가 데이터 파일 경로
ADDITIONAL_DATA_DIR = "dummy_data"
ADDITIONAL_FILES = {
    'loadcell': 'dummy_loadcell.json',
    'pole_stat': 'dummy_pole_stat.json',
    'loadcell_history': 'dummy_loadcell_history.json'
}

def load_additional_data_from_json() -> Dict[str, Any]:
    """
    JSON 파일에서 추가 데이터를 로드합니다.
    
    Returns:
        Dict[str, Any]: 로드된 추가 데이터
    """
    loaded_data = {}
    
    for data_type, filename in ADDITIONAL_FILES.items():
        file_path = os.path.join(ADDITIONAL_DATA_DIR, filename)
        
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    loaded_data[data_type] = json.load(f)
            except Exception as e:
                print(f"⚠️ {filename} 로드 실패: {e}")
                loaded_data[data_type] = {}
        else:
            loaded_data[data_type] = {}
    
    return loaded_data

def merge_db_and_additional_data(db_data: Dict[str, Any], additional_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    실제 DB 데이터와 추가 데이터를 병합합니다.
    
    Args:
        db_data: 실제 DB에서 가져온 데이터
        additional_data: 로컬 JSON에서 로드한 추가 데이터
    
    Returns:
        Dict[str, Any]: 병합된 데이터
    """
    merged_data = {}
    
    # loadcell 데이터 병합
    if 'loadcell' in additional_data:
        merged_data['loadcell'] = {**db_data.get('loadcell', {}), **additional_data['loadcell']}
    else:
        merged_data['loadcell'] = db_data.get('loadcell', {})
    
    # pole_stat 데이터 병합
    if 'pole_stat' in additional_data:
        merged_data['pole_stat'] = {**db_data.get('pole_stat', {}), **additional_data['pole_stat']}
    else:
        merged_data['pole_stat'] = db_data.get('pole_stat', {})
    
    # loadcell_history 데이터 병합
    if 'loadcell_history' in additional_data:
        merged_data['loadcell_history'] = db_data.get('loadcell_history', []) + additional_data['loadcell_history']
    else:
        merged_data['loadcell_history'] = db_data.get('loadcell_history', [])
    
    return merged_data

def get_combined_loadcell_data() -> Dict[str, Any]:
    """
    실제 DB 데이터와 추가 데이터를 병합하여 반환합니다.
    
    Returns:
        Dict[str, Any]: 병합된 loadcell 데이터
    """
    # 추가 데이터 로드
    additional_data = load_additional_data_from_json()
    
    # 실제 DB 데이터는 빈 딕셔너리로 시작 (실제로는 DB에서 가져와야 함)
    db_data = {
        'loadcell': {},
        'pole_stat': {},
        'loadcell_history': []
    }
    
    # 데이터 병합
    merged_data = merge_db_and_additional_data(db_data, additional_data)
    
    return merged_data

def update_additional_data_item(data_type: str, pole_id: str, updates: Dict[str, Any]) -> bool:
    """
    추가 데이터의 특정 항목을 업데이트합니다.
    
    Args:
        data_type: 데이터 타입 ('loadcell', 'pole_stat', 'loadcell_history')
        pole_id: 폴대 ID
        updates: 업데이트할 데이터
    
    Returns:
        bool: 업데이트 성공 여부
    """
    if data_type not in ADDITIONAL_FILES:
        print(f"❌ 지원하지 않는 데이터 타입: {data_type}")
        return False
    
    try:
        # 기존 데이터 로드
        additional_data = load_additional_data_from_json()
        
        if data_type == 'loadcell_history':
            # 히스토리는 리스트 형태이므로 특정 폴대의 최신 항목만 업데이트
            if data_type in additional_data:
                for item in additional_data[data_type]:
                    if item.get('loadcel') == pole_id:
                        item.update(updates)
                        break
        else:
            # loadcell과 pole_stat는 딕셔너리 형태
            if data_type in additional_data and pole_id in additional_data[data_type]:
                additional_data[data_type][pole_id].update(updates)
        
        # 업데이트된 데이터를 파일에 저장
        file_path = os.path.join(ADDITIONAL_DATA_DIR, ADDITIONAL_FILES[data_type])
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(additional_data[data_type], f, ensure_ascii=False, indent=2)
        
        print(f"✅ {data_type} 테이블의 폴대 {pole_id}번 데이터 업데이트 완료")
        return True
        
    except Exception as e:
        print(f"❌ 추가 데이터 업데이트 실패: {e}")
        return False

def get_additional_data_summary() -> Dict[str, Any]:
    """
    추가 데이터의 요약 정보를 반환합니다.
    
    Returns:
        Dict[str, Any]: 추가 데이터 요약 정보
    """
    try:
        additional_data = load_additional_data_from_json()
        summary = {}
        
        # loadcell 데이터 요약
        if 'loadcell' in additional_data and additional_data['loadcell']:
            summary['loadcell'] = {
                'total_poles': len(additional_data['loadcell']),
                'pole_ids': list(additional_data['loadcell'].keys()),
                'nurse_calls': sum(1 for data in additional_data['loadcell'].values() if data.get('nurse_call', False))
            }
        
        # pole_stat 데이터 요약
        if 'pole_stat' in additional_data and additional_data['pole_stat']:
            battery_levels = [data.get('battery_level', 0) for data in additional_data['pole_stat'].values()]
            summary['pole_stat'] = {
                'total_poles': len(additional_data['pole_stat']),
                'pole_ids': list(additional_data['pole_stat'].keys()),
                'avg_battery': sum(battery_levels) / len(battery_levels) if battery_levels else 0,
                'low_battery_count': sum(1 for level in battery_levels if level <= 1)
            }
        
        # loadcell_history 데이터 요약
        if 'loadcell_history' in additional_data and additional_data['loadcell_history']:
            history_by_pole = {}
            for item in additional_data['loadcell_history']:
                pole_id = item['loadcel']
                if pole_id not in history_by_pole:
                    history_by_pole[pole_id] = 0
                history_by_pole[pole_id] += 1
            
            summary['loadcell_history'] = {
                'total_items': len(additional_data['loadcell_history']),
                'poles_with_history': len(history_by_pole),
                'history_by_pole': history_by_pole
            }
        
        return summary
        
    except Exception as e:
        print(f"❌ 추가 데이터 요약 생성 실패: {e}")
        return {}

def is_additional_data_available() -> bool:
    """
    추가 데이터가 사용 가능한지 확인합니다.
    
    Returns:
        bool: 추가 데이터 사용 가능 여부
    """
    try:
        additional_data = load_additional_data_from_json()
        return any(data for data in additional_data.values())
    except:
        return False

def get_additional_pole_ids() -> List[str]:
    """
    추가 데이터에 포함된 폴대 ID 목록을 반환합니다.
    
    Returns:
        List[str]: 폴대 ID 목록
    """
    try:
        additional_data = load_additional_data_from_json()
        pole_ids = set()
        
        # loadcell과 pole_stat에서 폴대 ID 수집
        for data_type in ['loadcell', 'pole_stat']:
            if data_type in additional_data:
                pole_ids.update(additional_data[data_type].keys())
        
        return sorted(list(pole_ids), key=lambda x: int(x))
        
    except Exception as e:
        print(f"❌ 폴대 ID 목록 가져오기 실패: {e}")
        return []

def get_additional_data_for_dashboard() -> Dict[str, Any]:
    """
    대시보드에서 사용할 수 있는 형태로 추가 데이터를 변환합니다.
    
    Returns:
        Dict[str, Any]: 대시보드용 데이터
    """
    try:
        additional_data = load_additional_data_from_json()
        dashboard_data = {}
        
        # loadcell 데이터를 대시보드 형식으로 변환
        if 'loadcell' in additional_data:
            for pole_id, pole_data in additional_data['loadcell'].items():
                dashboard_data[pole_id] = {
                    'current_weight': float(pole_data.get('current_weight', 0)),
                    'remaining_sec': int(pole_data.get('remaining_sec', 0)),
                    'nurse_call': pole_data.get('nurse_call', False),
                    'timestamp': pole_data.get('timestamp', ''),
                    'battery_level': None  # pole_stat에서 가져올 예정
                }
        
        # pole_stat 데이터를 대시보드 형식으로 병합
        if 'pole_stat' in additional_data:
            for pole_id, pole_data in additional_data['pole_stat'].items():
                if pole_id in dashboard_data:
                    dashboard_data[pole_id]['battery_level'] = pole_data.get('battery_level', None)
                    dashboard_data[pole_id]['is_lost'] = pole_data.get('is_lost', False)
                    dashboard_data[pole_id]['tare_requested'] = pole_data.get('tare_requested', False)
        
        return dashboard_data
        
    except Exception as e:
        print(f"❌ 대시보드용 데이터 변환 실패: {e}")
        return {}

def get_additional_data_for_analysis() -> pd.DataFrame:
    """
    분석 페이지에서 사용할 수 있는 형태로 추가 데이터를 변환합니다.
    
    Returns:
        pd.DataFrame: 분석용 데이터프레임
    """
    try:
        additional_data = load_additional_data_from_json()
        analysis_data = []
        
        # loadcell_history 데이터를 분석용 데이터프레임으로 변환
        if 'loadcell_history' in additional_data:
            for item in additional_data['loadcell_history']:
                analysis_data.append({
                    'loadcel': item.get('loadcel'),
                    'current_weight_history': float(item.get('current_weight_history', 0)),
                    'remaining_sec_history': int(item.get('remaining_sec_history', 0)),
                    'timestamp': item.get('timestamp'),
                    'expire_at': item.get('expire_at')
                })
        
        # loadcell 현재 데이터도 추가
        if 'loadcell' in additional_data:
            for pole_id, pole_data in additional_data['loadcell'].items():
                analysis_data.append({
                    'loadcel': pole_id,
                    'current_weight_history': float(pole_data.get('current_weight', 0)),
                    'remaining_sec_history': int(pole_data.get('remaining_sec', 0)),
                    'timestamp': pole_data.get('timestamp'),
                    'expire_at': None
                })
        
        if analysis_data:
            df = pd.DataFrame(analysis_data)
            # 데이터 타입 변환
            df['current_weight_history'] = pd.to_numeric(df['current_weight_history'], errors='coerce')
            df['remaining_sec_history'] = pd.to_numeric(df['remaining_sec_history'], errors='coerce')
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        else:
            return pd.DataFrame()
        
    except Exception as e:
        print(f"❌ 분석용 데이터 변환 실패: {e}")
        return pd.DataFrame()

def get_additional_data_for_analysis_exclude_last() -> pd.DataFrame:
    """
    분석 페이지에서 사용할 수 있는 형태로 추가 데이터를 변환합니다.
    마지막 1개 데이터(수액 완료 상태)는 제외합니다.
    
    Returns:
        pd.DataFrame: 마지막 데이터가 제외된 분석용 데이터프레임
    """
    try:
        additional_data = load_additional_data_from_json()
        analysis_data = []
        
        # loadcell_history 데이터를 분석용 데이터프레임으로 변환
        if 'loadcell_history' in additional_data:
            # 폴대별로 데이터 그룹화
            pole_groups = {}
            for item in additional_data['loadcell_history']:
                pole_id = item.get('loadcel')
                if pole_id not in pole_groups:
                    pole_groups[pole_id] = []
                pole_groups[pole_id].append(item)
            
            # 각 폴대별로 마지막 1개 데이터 제외
            for pole_id, items in pole_groups.items():
                # 시간순 정렬
                sorted_items = sorted(items, key=lambda x: x.get('timestamp', ''))
                # 마지막 1개 제외 (데이터가 2개 이상인 경우)
                if len(sorted_items) > 1:
                    filtered_items = sorted_items[:-1]
                else:
                    filtered_items = sorted_items
                
                # 필터링된 데이터 추가
                for item in filtered_items:
                    analysis_data.append({
                        'loadcel': item.get('loadcel'),
                        'current_weight_history': float(item.get('current_weight_history', 0)),
                        'remaining_sec_history': int(item.get('remaining_sec_history', 0)),
                        'timestamp': item.get('timestamp'),
                        'expire_at': item.get('expire_at')
                    })
        
        # loadcell 현재 데이터도 추가 (마지막 데이터가 아닌 경우)
        if 'loadcell' in additional_data:
            for pole_id, pole_data in additional_data['loadcell'].items():
                # 현재 데이터가 마지막 데이터가 아닌 경우에만 추가
                current_weight = float(pole_data.get('current_weight', 0))
                if current_weight > 100:  # 100g 이상인 경우만 추가
                    analysis_data.append({
                        'loadcel': pole_id,
                        'current_weight_history': current_weight,
                        'remaining_sec_history': int(pole_data.get('remaining_sec', 0)),
                        'timestamp': pole_data.get('timestamp'),
                        'expire_at': None
                    })
        
        if analysis_data:
            df = pd.DataFrame(analysis_data)
            # 데이터 타입 변환
            df['current_weight_history'] = pd.to_numeric(df['current_weight_history'], errors='coerce')
            df['remaining_sec_history'] = pd.to_numeric(df['remaining_sec_history'], errors='coerce')
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        else:
            return pd.DataFrame()
        
    except Exception as e:
        print(f"❌ 분석용 데이터 변환 실패 (마지막 데이터 제외): {e}")
        return pd.DataFrame()

def get_additional_data_for_dashboard_exclude_last() -> Dict[str, Any]:
    """
    대시보드에서 사용할 수 있는 형태로 추가 데이터를 변환합니다.
    마지막 1개 데이터(수액 완료 상태)는 제외합니다.
    
    Returns:
        Dict[str, Any]: 마지막 데이터가 제외된 대시보드용 데이터
    """
    try:
        additional_data = load_additional_data_from_json()
        dashboard_data = {}
        
        # loadcell 데이터를 대시보드 형식으로 변환
        if 'loadcell' in additional_data:
            for pole_id, pole_data in additional_data['loadcell'].items():
                current_weight = float(pole_data.get('current_weight', 0))
                # 현재 무게가 100g 이상인 경우만 추가 (수액 완료 상태 제외)
                if current_weight > 100:
                    dashboard_data[pole_id] = {
                        'current_weight': current_weight,
                        'remaining_sec': int(pole_data.get('remaining_sec', 0)),
                        'nurse_call': pole_data.get('nurse_call', False),
                        'timestamp': pole_data.get('timestamp', ''),
                        'battery_level': None  # pole_stat에서 가져올 예정
                    }
        
        # pole_stat 데이터를 대시보드 형식으로 병합
        if 'pole_stat' in additional_data:
            for pole_id, pole_data in additional_data['pole_stat'].items():
                if pole_id in dashboard_data:
                    dashboard_data[pole_id]['battery_level'] = pole_data.get('battery_level', None)
                    dashboard_data[pole_id]['is_lost'] = pole_data.get('is_lost', False)
                    dashboard_data[pole_id]['tare_requested'] = pole_data.get('tare_requested', False)
        
        return dashboard_data
        
    except Exception as e:
        print(f"❌ 대시보드용 데이터 변환 실패 (마지막 데이터 제외): {e}")
        return {}

def get_additional_history_data_for_dashboard() -> Dict[str, List]:
    """
    대시보드에서 사용할 수 있는 형태로 추가 히스토리 데이터를 변환합니다.
    각 폴대별로 (timestamp, weight) 튜플 리스트를 반환합니다.
    
    Returns:
        Dict[str, List]: 폴대별 히스토리 데이터
    """
    try:
        additional_data = load_additional_data_from_json()
        history_data = {}
        
        # loadcell_history 데이터를 대시보드 형식으로 변환
        if 'loadcell_history' in additional_data:
            for item in additional_data['loadcell_history']:
                pole_id = str(item.get('loadcel'))
                if pole_id not in history_data:
                    history_data[pole_id] = []
                
                # 마지막 데이터가 아닌 경우에만 추가 (100g 이상)
                weight = float(item.get('current_weight_history', 0))
                if weight > 100:
                    timestamp = item.get('timestamp', '')
                    history_data[pole_id].append((timestamp, weight))
        
        # 각 폴대별로 최신 30개만 유지하고 시간순 정렬
        for pole_id in history_data:
            # 시간순 정렬 (최신순)
            history_data[pole_id].sort(key=lambda x: x[0], reverse=True)
            # 최신 30개만 유지
            history_data[pole_id] = history_data[pole_id][:30]
            # 시간순 정렬 (과거순, 그래프 표시용)
            history_data[pole_id].sort(key=lambda x: x[0])
        
        return history_data
        
    except Exception as e:
        print(f"❌ 대시보드용 히스토리 데이터 변환 실패: {e}")
        return {}

def get_combined_analysis_data() -> pd.DataFrame:
    """
    실제 DB 데이터와 추가 데이터를 병합하여 분석용 데이터프레임을 반환합니다.
    
    Returns:
        pd.DataFrame: 병합된 분석용 데이터프레임
    """
    try:
        # 추가 데이터 로드
        additional_df = get_additional_data_for_analysis()
        
        # 실제 DB 데이터는 빈 데이터프레임으로 시작 (실제로는 DB에서 가져와야 함)
        db_df = pd.DataFrame()
        
        # 데이터 병합
        if not additional_df.empty and not db_df.empty:
            combined_df = pd.concat([db_df, additional_df], ignore_index=True)
        elif not additional_df.empty:
            combined_df = additional_df
        elif not db_df.empty:
            combined_df = db_df
        else:
            combined_df = pd.DataFrame()
        
        return combined_df
        
    except Exception as e:
        print(f"❌ 분석 데이터 병합 실패: {e}")
        return pd.DataFrame()
