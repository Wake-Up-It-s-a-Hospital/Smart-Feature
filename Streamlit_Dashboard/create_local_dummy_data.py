#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
로컬 JSON 파일로 스마트 링거폴대 더미데이터를 생성하고 관리하는 스크립트

이 스크립트는 다음 JSON 파일을 생성합니다:
- dummy_loadcell.json: 수액 무게, 남은 시간, 너스콜 상태
- dummy_pole_stat.json: 배터리 레벨, 분실 상태, tare 요청 상태
- dummy_loadcell_history.json: 히스토리 데이터

사용법:
    python create_local_dummy_data.py
"""

import json
import random
import time
import os
from datetime import datetime, timezone, timedelta

# 더미데이터 저장 디렉토리
DUMMY_DATA_DIR = "dummy_data"
DUMMY_FILES = {
    'loadcell': 'dummy_loadcell.json',
    'pole_stat': 'dummy_pole_stat.json',
    'loadcell_history': 'dummy_loadcell_history.json'
}

def ensure_dummy_data_dir():
    """더미데이터 디렉토리 생성"""
    if not os.path.exists(DUMMY_DATA_DIR):
        os.makedirs(DUMMY_DATA_DIR)
        print(f"📁 디렉토리 생성: {DUMMY_DATA_DIR}")

def create_loadcell_dummy_data():
    """loadcell 더미데이터 생성"""
    print("🔄 loadcell 더미데이터 생성 중...")
    
    data = {}
    
    # 폴대 ID 2, 3, 4, 5번에 대한 더미데이터 생성
    for pole_id in [2, 3, 4, 5]:
        # 랜덤 수액 무게 (100g ~ 1000g)
        current_weight = random.uniform(100, 1000)
        
        # 남은 시간 (무게 기반으로 계산, 30분 ~ 8시간)
        remaining_hours = (current_weight / 1000) * 8
        remaining_sec = int(remaining_hours * 3600)
        
        # 너스콜 상태 (10% 확률로 활성화)
        nurse_call = random.random() < 0.1
        
        # 현재 시간
        timestamp = datetime.now(timezone(timedelta(hours=9))).isoformat()
        
        data[str(pole_id)] = {
            'loadcel': str(pole_id),
            'current_weight': str(round(current_weight, 1)),
            'remaining_sec': str(remaining_sec),
            'nurse_call': nurse_call,
            'timestamp': timestamp
        }
        
        print(f"✅ 폴대 {pole_id}번 데이터 생성 완료: 무게={current_weight:.1f}g, 남은시간={remaining_hours:.1f}시간, 너스콜={nurse_call}")
    
    return data

def create_pole_stat_dummy_data():
    """pole_stat 더미데이터 생성"""
    print("\n🔄 pole_stat 더미데이터 생성 중...")
    
    data = {}
    
    # 폴대 ID 2, 3, 4, 5번에 대한 더미데이터 생성
    for pole_id in [2, 3, 4, 5]:
        # 배터리 레벨 (0~3, 대부분 2~3)
        battery_level = random.choices([0, 1, 2, 3], weights=[0.05, 0.15, 0.4, 0.4])[0]
        
        # 분실 상태 (5% 확률로 분실)
        is_lost = random.random() < 0.05
        
        # tare 요청 상태 (15% 확률로 요청)
        tare_requested = random.random() < 0.15
        
        # 현재 시간
        timestamp = datetime.now(timezone(timedelta(hours=9))).isoformat()
        
        data[str(pole_id)] = {
            'pole_id': str(pole_id),
            'battery_level': battery_level,
            'is_lost': is_lost,
            'tare_requested': tare_requested,
            'timestamp': timestamp
        }
        
        print(f"✅ 폴대 {pole_id}번 pole_stat 생성 완료: 배터리={battery_level}, 분실={is_lost}, tare요청={tare_requested}")
    
    return data

def create_loadcell_history_dummy_data():
    """loadcell_history 더미데이터 생성"""
    print("\n🔄 loadcell_history 더미데이터 생성 중...")
    
    data = []
    
    # 폴대 ID 2, 3, 4, 5번에 대한 히스토리 데이터 생성
    for pole_id in [2, 3, 4, 5]:
        # 과거 24시간 동안의 데이터 생성 (1시간마다)
        for hours_ago in range(24, 0, -1):
            # 과거 시간
            past_time = datetime.now(timezone(timedelta(hours=9))) - timedelta(hours=hours_ago)
            timestamp = past_time.isoformat()
            
            # 과거 수액 무게 (현재보다 많았을 것)
            base_weight = random.uniform(800, 1200)  # 기본 무게
            weight_decrease = (24 - hours_ago) * random.uniform(20, 40)  # 시간에 따른 감소
            current_weight_history = max(100, base_weight - weight_decrease)
            
            # 과거 남은 시간
            remaining_hours = (current_weight_history / 1000) * 8
            remaining_sec_history = int(remaining_hours * 3600)
            
            # TTL (1주일 후 만료)
            expire_at = int(time.time()) + 7 * 24 * 60 * 60
            
            history_item = {
                'loadcel': str(pole_id),
                'current_weight_history': str(round(current_weight_history, 1)),
                'remaining_sec_history': str(remaining_sec_history),
                'timestamp': timestamp,
                'expire_at': expire_at
            }
            
            data.append(history_item)
            print(f"✅ 폴대 {pole_id}번 히스토리 {hours_ago}시간 전 데이터 생성 완료")
    
    return data

def save_dummy_data_to_json():
    """더미데이터를 JSON 파일로 저장"""
    print("\n💾 더미데이터를 JSON 파일로 저장 중...")
    
    # 1. loadcell 데이터 저장
    loadcell_data = create_loadcell_dummy_data()
    loadcell_file = os.path.join(DUMMY_DATA_DIR, DUMMY_FILES['loadcell'])
    with open(loadcell_file, 'w', encoding='utf-8') as f:
        json.dump(loadcell_data, f, ensure_ascii=False, indent=2)
    print(f"💾 {loadcell_file} 저장 완료")
    
    # 2. pole_stat 데이터 저장
    pole_stat_data = create_pole_stat_dummy_data()
    pole_stat_file = os.path.join(DUMMY_DATA_DIR, DUMMY_FILES['pole_stat'])
    with open(pole_stat_file, 'w', encoding='utf-8') as f:
        json.dump(pole_stat_data, f, ensure_ascii=False, indent=2)
    print(f"💾 {pole_stat_file} 저장 완료")
    
    # 3. loadcell_history 데이터 저장
    history_data = create_loadcell_history_dummy_data()
    history_file = os.path.join(DUMMY_DATA_DIR, DUMMY_FILES['loadcell_history'])
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)
    print(f"💾 {history_file} 저장 완료")

def load_dummy_data_from_json():
    """JSON 파일에서 더미데이터 로드"""
    print("\n📂 JSON 파일에서 더미데이터 로드 중...")
    
    loaded_data = {}
    
    for data_type, filename in DUMMY_FILES.items():
        file_path = os.path.join(DUMMY_DATA_DIR, filename)
        
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    loaded_data[data_type] = json.load(f)
                print(f"✅ {filename} 로드 완료")
            except Exception as e:
                print(f"❌ {filename} 로드 실패: {e}")
                loaded_data[data_type] = {}
        else:
            print(f"⚠️ {filename} 파일이 존재하지 않습니다.")
            loaded_data[data_type] = {}
    
    return loaded_data

def display_dummy_data_summary():
    """더미데이터 요약 정보 표시"""
    print("\n📊 더미데이터 요약 정보:")
    print("=" * 50)
    
    try:
        data = load_dummy_data_from_json()
        
        # loadcell 데이터 요약
        if 'loadcell' in data and data['loadcell']:
            print(f"📊 loadcell 테이블: {len(data['loadcell'])}개 폴대")
            for pole_id, pole_data in data['loadcell'].items():
                print(f"   - 폴대 {pole_id}: 무게={pole_data['current_weight']}g, 너스콜={pole_data['nurse_call']}")
        
        # pole_stat 데이터 요약
        if 'pole_stat' in data and data['pole_stat']:
            print(f"📊 pole_stat 테이블: {len(data['pole_stat'])}개 폴대")
            for pole_id, pole_data in data['pole_stat'].items():
                print(f"   - 폴대 {pole_id}: 배터리={pole_data['battery_level']}, 분실={pole_data['is_lost']}")
        
        # loadcell_history 데이터 요약
        if 'loadcell_history' in data and data['loadcell_history']:
            print(f"📊 loadcell_history 테이블: {len(data['loadcell_history'])}개 히스토리 항목")
            
            # 폴대별 히스토리 개수 계산
            history_by_pole = {}
            for item in data['loadcell_history']:
                pole_id = item['loadcel']
                if pole_id not in history_by_pole:
                    history_by_pole[pole_id] = 0
                history_by_pole[pole_id] += 1
            
            for pole_id, count in history_by_pole.items():
                print(f"   - 폴대 {pole_id}: {count}개 히스토리")
                
    except Exception as e:
        print(f"❌ 데이터 요약 표시 실패: {e}")

def main():
    """메인 함수"""
    print("🚀 스마트 링거폴대 로컬 더미데이터 생성 시작!")
    print("=" * 50)
    
    try:
        # 1. 더미데이터 디렉토리 생성
        ensure_dummy_data_dir()
        
        # 2. 더미데이터 생성 및 JSON 파일로 저장
        save_dummy_data_to_json()
        
        # 3. 생성된 데이터 요약 표시
        display_dummy_data_summary()
        
        print("\n🎉 로컬 더미데이터 생성 완료!")
        print("=" * 50)
        print("📝 생성된 파일:")
        for data_type, filename in DUMMY_FILES.items():
            file_path = os.path.join(DUMMY_DATA_DIR, filename)
            print(f"   - {file_path}")
        
        print("\n💡 이제 이 JSON 파일들을 사용하여 더미데이터를 관리할 수 있습니다!")
        print("   - 더미데이터 수정: JSON 파일 직접 편집")
        print("   - 더미데이터 로드: load_dummy_data_from_json() 함수 사용")
        
    except Exception as e:
        print(f"\n❌ 더미데이터 생성 중 오류 발생: {e}")

if __name__ == "__main__":
    main()
