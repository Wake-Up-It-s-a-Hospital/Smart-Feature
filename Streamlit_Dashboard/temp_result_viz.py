import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# CSV 파일 로드
df = pd.read_csv('C:\\YS\\TUK\\Capstone\\Wake up\\Smart-Feature\\results.csv')

# loadcel 값이 1인 데이터만 필터링
df = df[df['loadcel'] == 1].copy()

# timestamp를 datetime 형식으로 변환
df['timestamp'] = pd.to_datetime(df['timestamp'])

# 기준 시간 설정 (첫 번째 시간)
start_time = df['timestamp'].min()
df['elapsed_sec'] = (df['timestamp'] - start_time).dt.total_seconds()

# fig1: timestamp vs current_weight_history
fig1, ax1 = plt.subplots()
ax1.plot(df['timestamp'], df['current_weight_history'], label='Current Weight')
ax1.set_xlabel('Timestamp')
ax1.set_ylabel('Current Weight (g)')
ax1.set_title('Timestamp vs Current Weight')
ax1.grid(True)
ax1.legend()

# fig2: 실제 시간 vs 예측 시간 그래프
fig2, ax2 = plt.subplots()
ax2.plot(df['elapsed_sec'], df['elapsed_sec'], 'r-', label='Actual Time')
ax2.plot(df['elapsed_sec'], df['remaining_sec_history'], 'b-', label='Remaining Sec (Predicted)')
ax2.set_xlabel(f'Elapsed Time (sec, total {df["elapsed_sec"].max():.1f} sec)')
ax2.set_ylabel('Time (sec)')
ax2.set_title('Actual vs Predicted Remaining Time')
ax2.legend()
ax2.grid(True)
ax2.invert_yaxis()
# y축 눈금을 100 단위로 설정
ax2.yaxis.set_major_locator(ticker.MultipleLocator(100))

plt.tight_layout()
plt.show()
