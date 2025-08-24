#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
더미데이터 테스트 스크립트

이 스크립트는 더미데이터가 제대로 작동하는지 테스트합니다.
"""

import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_dummy_data_utils():
    """더미데이터 유틸리티 함수들을 테스트합니다."""
    print("🧪 더미데이터 유틸리티 테스트 시작...")
    
    try:
        from utils.dummy_data_utils import (
            load_dummy_data_from_json,
            is_dummy_data_available,
            get_dummy_data_summary,
            get_dummy_pole_ids,
            get_dummy_data_for_dashboard
        )
        print("✅ 유틸리티 함수 임포트 성공")
        
        # 더미데이터 사용 가능 여부 확인
        if is_dummy_data_available():
            print("✅ 더미데이터 사용 가능")
            
            # 더미데이터 로드
            dummy_data = load_dummy_data_from_json()
            print(f"📊 로드된 데이터 타입: {list(dummy_data.keys())}")
            
            # 요약 정보 가져오기
            summary = get_dummy_data_summary()
            print(f"📋 요약 정보: {summary}")
            
            # 폴대 ID 목록
            pole_ids = get_dummy_pole_ids()
            print(f"🏗️ 폴대 ID 목록: {pole_ids}")
            
            # 대시보드용 데이터
            dashboard_data = get_dummy_data_for_dashboard()
            print(f"🖥️ 대시보드 데이터: {len(dashboard_data)}개 폴대")
            
            return True
            
        else:
            print("⚠️ 더미데이터가 없습니다")
            print("💡 `python create_local_dummy_data.py`를 실행하여 더미데이터를 생성하세요.")
            return False
            
    except ImportError as e:
        print(f"❌ 유틸리티 함수 임포트 실패: {e}")
        return False
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        return False

def test_dummy_data_files():
    """더미데이터 파일들이 존재하는지 확인합니다."""
    print("\n📁 더미데이터 파일 테스트...")
    
    dummy_data_dir = "dummy_data"
    expected_files = [
        "dummy_loadcell.json",
        "dummy_pole_stat.json", 
        "dummy_loadcell_history.json"
    ]
    
    if not os.path.exists(dummy_data_dir):
        print(f"❌ {dummy_data_dir} 디렉토리가 존재하지 않습니다.")
        return False
    
    print(f"✅ {dummy_data_dir} 디렉토리 존재")
    
    missing_files = []
    for filename in expected_files:
        file_path = os.path.join(dummy_data_dir, filename)
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            print(f"✅ {filename} 존재 (크기: {file_size} bytes)")
        else:
            print(f"❌ {filename} 없음")
            missing_files.append(filename)
    
    if missing_files:
        print(f"⚠️ 누락된 파일: {', '.join(missing_files)}")
        return False
    
    return True

def test_json_format():
    """JSON 파일 형식이 올바른지 확인합니다."""
    print("\n🔍 JSON 형식 테스트...")
    
    try:
        from utils.dummy_data_utils import load_dummy_data_from_json
        
        dummy_data = load_dummy_data_from_json()
        
        # JSON 직렬화 테스트
        import json
        json_str = json.dumps(dummy_data, ensure_ascii=False, indent=2)
        print(f"✅ JSON 직렬화 성공 (크기: {len(json_str)} characters)")
        
        # 데이터 구조 검증
        if 'loadcell' in dummy_data:
            loadcell_count = len(dummy_data['loadcell'])
            print(f"✅ loadcell 데이터: {loadcell_count}개 폴대")
        
        if 'pole_stat' in dummy_data:
            pole_stat_count = len(dummy_data['pole_stat'])
            print(f"✅ pole_stat 데이터: {pole_stat_count}개 폴대")
        
        if 'loadcell_history' in dummy_data:
            history_count = len(dummy_data['loadcell_history'])
            print(f"✅ loadcell_history 데이터: {history_count}개 항목")
        
        return True
        
    except Exception as e:
        print(f"❌ JSON 형식 테스트 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 더미데이터 통합 테스트 시작!")
    print("=" * 50)
    
    tests = [
        ("파일 존재 여부", test_dummy_data_files),
        ("JSON 형식", test_json_format),
        ("유틸리티 함수", test_dummy_data_utils)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🔍 {test_name} 테스트 중...")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 테스트 중 예외 발생: {e}")
            results.append((test_name, False))
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("📊 테스트 결과 요약:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 통과" if result else "❌ 실패"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 전체 결과: {passed}/{total} 테스트 통과")
    
    if passed == total:
        print("🎉 모든 테스트가 통과했습니다!")
        print("💡 이제 대시보드에서 더미데이터를 사용할 수 있습니다.")
    else:
        print("⚠️ 일부 테스트가 실패했습니다.")
        print("🔧 문제를 해결한 후 다시 테스트해보세요.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
