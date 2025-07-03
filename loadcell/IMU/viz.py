import serial
import re
import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtWidgets, QtCore

# 시리얼 포트 설정 (포트명/속도 맞게 수정)
ser = serial.Serial('COM4', 115200, timeout=1)

app = QtWidgets.QApplication([])
window = gl.GLViewWidget()
window.setWindowTitle('IMU 3D Position & Acceleration Vector')
window.setCameraPosition(distance=4)
window.show()

# 축 그리드
axis = gl.GLAxisItem()
axis.setSize(2, 2, 2)
window.addItem(axis)

# 점(좌표) 누적용
positions = []
scatter = gl.GLScatterPlotItem(pos=np.zeros((1, 3)), color=(1, 0, 0, 1), size=5)
window.addItem(scatter)

# 가속도 벡터(화살표)
line = gl.GLLinePlotItem()
window.addItem(line)

def draw_vector(origin, vec, scale=0.5):
    # vec: 가속도 벡터, scale: 시각화용 크기 조정
    points = np.array([origin, origin + vec * scale])
    line.setData(pos=points, color=(0, 0, 1, 1), width=3, mode='lines')

def update():
    try:
        # 시리얼에서 3줄 읽기 (Pos, Accel, Gyro)
        pos_line = ser.readline().decode(errors='ignore').strip()
        acc_line = ser.readline().decode(errors='ignore').strip()
        gyro_line = ser.readline().decode(errors='ignore').strip()

        # 좌표 파싱
        pos_match = re.search(r'Pos: \[X:([-\d\.]+), Y:([-\d\.]+), Z:([-\d\.]+)\]', pos_line)
        acc_match = re.search(r'Accel: \[([-\d\.]+), ([-\d\.]+), ([-\d\.]+)\]', acc_line)
        if pos_match and acc_match:
            x, y, z = map(float, pos_match.groups())
            ax, ay, az = map(float, acc_match.groups())
            positions.append([x, y, z])
            scatter.setData(pos=np.array(positions), color=(1, 0, 0, 1), size=5)
            draw_vector(np.array([x, y, z]), np.array([ax, ay, az]), scale=0.5)
        print(ser.readline().decode(errors='ignore').strip())
    except Exception as e:
        print('에러:', e)

timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(500)  # 20Hz

if __name__ == '__main__':
    QtWidgets.QApplication.instance().exec_()
