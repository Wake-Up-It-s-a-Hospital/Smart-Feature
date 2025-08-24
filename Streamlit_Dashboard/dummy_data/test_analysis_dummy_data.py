#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
분석 페이지 더미데이터 테스트 스크립트

이 스크립트는 분석 페이지에서 더미데이터가 제대로 작동하는지 테스트합니다.
"""

import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import numpy as np

# matplotlib 한글 폰트 설정
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# 상위 디렉토리(Streamlit_Dashboard)를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_analysis_dummy_data():
    """분석용 더미데이터 함수들을 테스트합니다."""
    print("🧪 분석용 더미데이터 테스트 시작...")
    
    try:
        from utils.dummy_data_utils import (
            get_additional_data_for_analysis,
            get_combined_analysis_data,
            is_additional_data_available
        )
        print("✅ 분석용 더미데이터 함수 임포트 성공")
        
        # 더미데이터 사용 가능 여부 확인
        if is_additional_data_available():
            print("✅ 더미데이터 사용 가능")
            
            # 분석용 데이터 가져오기
            analysis_df = get_additional_data_for_analysis()
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
        from utils.dummy_data_utils import get_additional_data_for_analysis
        
        df = get_additional_data_for_analysis()
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
        from utils.dummy_data_utils import get_additional_data_for_analysis
        
        df = get_additional_data_for_analysis()
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

def plot_weight_changes():
    """각 폴대별로 시간에 따른 무게 변화를 그래프로 표시합니다."""
    print("\n📊 무게 변화 그래프 생성 중...")
    
    try:
        from utils.dummy_data_utils import get_additional_data_for_analysis
        
        df = get_additional_data_for_analysis()
        if df.empty:
            print("⚠️ 테스트할 데이터가 없습니다")
            return False
        
        # 타임스탬프를 datetime으로 변환
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # 디버깅: 시간 범위 확인
        print(f"📅 전체 시간 범위: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
        
        # 폴대별로 데이터 정렬 (시간순)
        df_sorted = df.sort_values(['loadcel', 'timestamp'])
        
        # 그래프 생성
        fig, axes = plt.subplots(3, 3, figsize=(15, 12))
        fig.suptitle('Each pole\'s weight changes over time', fontsize=16, fontweight='bold')
        
        # 폴대별로 서브플롯에 그리기
        for i, pole_id in enumerate(sorted(df['loadcel'].unique())):
            row = i // 3
            col = i % 3
            
            # 해당 폴대의 데이터만 필터링하고 시간순 정렬
            pole_data = df_sorted[df_sorted['loadcel'] == pole_id].copy()
            pole_data = pole_data.sort_values('timestamp')  # 시간순 정렬
            
            if not pole_data.empty:
                # 마지막 1개 데이터 제외 (수액 완료 상태 제거)
                if len(pole_data) > 1:
                    pole_data = pole_data.iloc[:-1]  # 마지막 행 제외
                    print(f"🔍 폴대 {pole_id}: 마지막 1개 데이터 제외, {len(pole_data)}개 데이터 사용")
                
                # 무게 데이터를 숫자로 변환
                weights = pd.to_numeric(pole_data['current_weight_history'])
                timestamps = pole_data['timestamp']
                
                # 디버깅: 폴대별 데이터 정보
                print(f"🔍 폴대 {pole_id}: {len(pole_data)}개 데이터, 시간: {timestamps.min()} ~ {timestamps.max()}")
                print(f"   무게 범위: {weights.min():.1f}g ~ {weights.max():.1f}g")
                
                # 서브플롯에 그래프 그리기
                axes[row, col].plot(timestamps, weights, 'b-', linewidth=2, marker='o', markersize=3)
                axes[row, col].set_title(f'Pole {pole_id}', fontweight='bold')
                axes[row, col].set_xlabel('Time')
                axes[row, col].set_ylabel('Weight (g)')
                axes[row, col].grid(True, alpha=0.3)
                
                # x축 시간 포맷 설정
                axes[row, col].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                axes[row, col].tick_params(axis='x', rotation=45)
                
                # y축 범위 설정 (실제 데이터 범위에 맞춤)
                min_weight = weights.min()
                max_weight = weights.max()
                weight_range = max_weight - min_weight
                axes[row, col].set_ylim(max(0, min_weight - weight_range * 0.1), 
                                       max_weight + weight_range * 0.1)
                
                # 통계 정보 표시
                avg_weight = weights.mean()
                final_weight = weights.iloc[-1]
                initial_weight = weights.iloc[0]
                axes[row, col].text(0.02, 0.98, f'avg: {avg_weight:.1f}g\nfinal: {final_weight:.1f}g\ninitial: {initial_weight:.1f}g', 
                                   transform=axes[row, col].transAxes, 
                                   verticalalignment='top',
                                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        # 빈 서브플롯 숨기기
        for i in range(len(df['loadcel'].unique()), 9):
            row = i // 3
            col = i % 3
            axes[row, col].set_visible(False)
        
        plt.tight_layout()
        plt.show()
        
        print("✅ 무게 변화 그래프 생성 완료 (마지막 1개 데이터 제외)")
        return True
        
    except Exception as e:
        print(f"❌ 그래프 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def plot_weight_distribution():
    """각 폴대별 무게 분포를 박스플롯으로 표시합니다."""
    print("\n📊 무게 분포 박스플롯 생성 중...")
    
    try:
        from utils.dummy_data_utils import get_additional_data_for_analysis
        
        df = get_additional_data_for_analysis()
        if df.empty:
            print("⚠️ 테스트할 데이터가 없습니다")
            return False
        
        # 타임스탬프를 datetime으로 변환
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # 폴대별로 마지막 1개 데이터 제외
        filtered_data = []
        for pole_id in sorted(df['loadcel'].unique()):
            pole_data = df[df['loadcel'] == pole_id].sort_values('timestamp')
            if len(pole_data) > 1:
                # 마지막 1개 데이터 제외
                filtered_pole_data = pole_data.iloc[:-1]
                filtered_data.append(filtered_pole_data)
                print(f"🔍 폴대 {pole_id}: 마지막 1개 데이터 제외, {len(filtered_pole_data)}개 데이터 사용")
            else:
                filtered_data.append(pole_data)
                print(f"🔍 폴대 {pole_id}: 데이터가 1개뿐이므로 그대로 사용")
        
        # 필터링된 데이터를 하나의 DataFrame으로 합치기
        df_filtered = pd.concat(filtered_data, ignore_index=True)
        
        # 무게 데이터를 숫자로 변환
        df_filtered['current_weight_history'] = pd.to_numeric(df_filtered['current_weight_history'])
        
        # 박스플롯 생성
        plt.figure(figsize=(12, 8))
        
        # 폴대별로 데이터 그룹화
        pole_data = [df_filtered[df_filtered['loadcel'] == pole_id]['current_weight_history'].values 
                     for pole_id in sorted(df_filtered['loadcel'].unique())]
        pole_labels = [f'pole {pole_id}' for pole_id in sorted(df_filtered['loadcel'].unique())]
        
        # 박스플롯 그리기
        bp = plt.boxplot(pole_data, labels=pole_labels, patch_artist=True)
        
        # 박스 색상 설정
        colors = plt.cm.Set3(np.linspace(0, 1, len(pole_data)))
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        
        plt.title('Each pole\'s weight distribution (last data excluded)', fontsize=16, fontweight='bold')
        plt.xlabel('Pole ID')
        plt.ylabel('Weight (g)')
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        
        # 통계 정보 추가
        for i, pole_id in enumerate(sorted(df_filtered['loadcel'].unique())):
            pole_weights = df_filtered[df_filtered['loadcel'] == pole_id]['current_weight_history']
            mean_weight = pole_weights.mean()
            plt.text(i+1, mean_weight, f'{mean_weight:.1f}g', 
                    ha='center', va='bottom', fontweight='bold')
        
        plt.tight_layout()
        plt.show()
        
        print("✅ 무게 분포 박스플롯 생성 완료 (마지막 1개 데이터 제외)")
        return True
        
    except Exception as e:
        print(f"❌ 박스플롯 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 테스트 함수"""
    print("🚀 분석 페이지 더미데이터 통합 테스트 시작!")
    print("=" * 60)
    
    tests = [
        ("분석용 더미데이터 함수", test_analysis_dummy_data),
        ("Pandas 연산", test_pandas_operations),
        ("데이터 품질", test_data_quality),
        ("무게 변화 그래프", plot_weight_changes),
        ("무게 분포 박스플롯", plot_weight_distribution)
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
