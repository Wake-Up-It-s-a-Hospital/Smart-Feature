#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
분석 페이지 더미데이터 테스트 스크립트

이 스크립트는 분석 페이지에서 더미데이터가 제대로 작동하는지 테스트합니다.
"""

import sys
import os
import pandas as pd

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_analysis_dummy_data():
    """분석용 더미데이터 함수들을 테스트합니다."""
    print("🧪 분석용 더미데이터 테스트 시작...")
    
    try:
        from utils.dummy_data_utils import (
            get_dummy_data_for_analysis,
            get_combined_analysis_data,
            is_dummy_data_available
        )
        print("✅ 분석용 더미데이터 함수 임포트 성공")
        
        # 더미데이터 사용 가능 여부 확인
        if is_dummy_data_available():
            print("✅ 더미데이터 사용 가능")
            
            # 분석용 데이터 가져오기
            analysis_df = get_dummy_data_for_analysis()
            print(f"📊 분석용 데이터프레임: {len(analysis_df)}개 행")
            
            if not analysis_df.empty:
                print(f"📋 컬럼: {list(analysis_df.columns)}")
                print(f"🏗️ 폴대 ID: {analysis_df['loadcel'].unique()}")
                print(f"📅 시간 범위: {analysis_df['timestamp'].min()} ~ {analysis_df['timestamp'].max()}")
                print(f"⚖️ 무게 범위: {analysis_df['current_weight_history'].min():.1f}g ~ {analysis_df['current_weight_history'].max():.1f}g")
                
                # 데이터 타입 확인
                print(f"🔍 데이터 타입:")
                print(f"  - current_weight_history: {analysis_df['current_weight_history'].dtype}")
                print(f"  - remaining_sec_history: {analysis_df['remaining_sec_history'].dtype}")
                print(f"  - timestamp: {analysis_df['timestamp'].dtype}")
                
                # 결측값 확인
                print(f"❓ 결측값:")
                print(f"  - current_weight_history: {analysis_df['current_weight_history'].isna().sum()}")
                print(f"  - remaining_sec_history: {analysis_df['remaining_sec_history'].isna().sum()}")
                print(f"  - timestamp: {analysis_df['timestamp'].isna().sum()}")
                
                # 폴대별 데이터 개수
                print(f"📊 폴대별 데이터 개수:")
                pole_counts = analysis_df['loadcel'].value_counts()
                for pole_id, count in pole_counts.items():
                    print(f"  - 폴대 {pole_id}: {count}개")
                
                return True
            else:
                print("⚠️ 분석용 데이터프레임이 비어있습니다")
                return False
                
        else:
            print("⚠️ 더미데이터가 없습니다")
            print("💡 `python create_local_dummy_data.py`를 실행하여 더미데이터를 생성하세요.")
            return False
            
    except ImportError as e:
        print(f"❌ 분석용 더미데이터 함수 임포트 실패: {e}")
        return False
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        return False

def test_pandas_operations():
    """더미데이터로 pandas 연산을 테스트합니다."""
    print("\n🔍 Pandas 연산 테스트...")
    
    try:
        from utils.dummy_data_utils import get_dummy_data_for_analysis
        
        df = get_dummy_data_for_analysis()
        if df.empty:
            print("⚠️ 테스트할 데이터가 없습니다")
            return False
        
        # 기본 통계
        print("📊 기본 통계:")
        print(f"  - 총 데이터 수: {len(df)}")
        print(f"  - 폴대 수: {df['loadcel'].nunique()}")
        print(f"  - 평균 무게: {df['current_weight_history'].mean():.1f}g")
        print(f"  - 무게 표준편차: {df['current_weight_history'].std():.1f}g")
        
        # 시간별 분석
        print("\n⏰ 시간별 분석:")
        df['hour'] = df['timestamp'].dt.hour
        hourly_stats = df.groupby('hour')['current_weight_history'].agg(['mean', 'count'])
        print("  시간별 평균 무게 및 데이터 개수:")
        for hour, stats in hourly_stats.iterrows():
            print(f"    {hour:02d}시: {stats['mean']:.1f}g ({stats['count']}개)")
        
        # 폴대별 분석
        print("\n🏗️ 폴대별 분석:")
        pole_stats = df.groupby('loadcel')['current_weight_history'].agg(['mean', 'std', 'count'])
        for pole_id, stats in pole_stats.iterrows():
            print(f"  폴대 {pole_id}: 평균 {stats['mean']:.1f}g, 표준편차 {stats['std']:.1f}g, {stats['count']}개")
        
        return True
        
    except Exception as e:
        print(f"❌ Pandas 연산 테스트 실패: {e}")
        return False

def test_data_quality():
    """더미데이터의 품질을 테스트합니다."""
    print("\n🔍 데이터 품질 테스트...")
    
    try:
        from utils.dummy_data_utils import get_dummy_data_for_analysis
        
        df = get_dummy_data_for_analysis()
        if df.empty:
            print("⚠️ 테스트할 데이터가 없습니다")
            return False
        
        issues = []
        
        # 무게 범위 검증 (0g ~ 2000g)
        invalid_weights = df[(df['current_weight_history'] < 0) | (df['current_weight_history'] > 2000)]
        if len(invalid_weights) > 0:
            issues.append(f"무게 범위 오류: {len(invalid_weights)}개")
        
        # 남은 시간 검증 (0초 ~ 86400초 = 24시간)
        invalid_times = df[(df['remaining_sec_history'] < 0) | (df['remaining_sec_history'] > 86400)]
        if len(invalid_times) > 0:
            issues.append(f"남은 시간 범위 오류: {len(invalid_times)}개")
        
        # 타임스탬프 검증
        invalid_timestamps = df[df['timestamp'].isna()]
        if len(invalid_timestamps) > 0:
            issues.append(f"타임스탬프 누락: {len(invalid_timestamps)}개")
        
        # 폴대 ID 검증
        invalid_poles = df[df['loadcel'].isna()]
        if len(invalid_poles) > 0:
            issues.append(f"폴대 ID 누락: {len(invalid_poles)}개")
        
        if issues:
            print("⚠️ 데이터 품질 문제 발견:")
            for issue in issues:
                print(f"  - {issue}")
            return False
        else:
            print("✅ 데이터 품질 검증 통과")
            return True
            
    except Exception as e:
        print(f"❌ 데이터 품질 테스트 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 분석 페이지 더미데이터 통합 테스트 시작!")
    print("=" * 60)
    
    tests = [
        ("분석용 더미데이터 함수", test_analysis_dummy_data),
        ("Pandas 연산", test_pandas_operations),
        ("데이터 품질", test_data_quality)
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
    print("\n" + "=" * 60)
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
        print("💡 이제 분석 페이지에서 더미데이터를 사용할 수 있습니다.")
        print("📊 수액 사용 통계 분석, 보고서 생성 등 모든 기능이 더미데이터로 작동합니다.")
    else:
        print("⚠️ 일부 테스트가 실패했습니다.")
        print("🔧 문제를 해결한 후 다시 테스트해보세요.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
