import serial
import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
from pyqtgraph.Qt import QtWidgets, QtCore

# 시리얼 포트 설정 (COM 포트 맞게 수정)
ser = serial.Serial('COM4', 115200)

app = QtWidgets.QApplication([])
window = gl.GLViewWidget()
window.setWindowTitle('IMU 3D Acceleration Vector')
window.setCameraPosition(distance=4)
window.show()

# 축 그리드
axis = gl.GLAxisItem()
axis.setSize(2, 2, 2)
window.addItem(axis)

# 3D 화살표 벡터 (line + cone 조합)
line = gl.GLLinePlotItem()
window.addItem(line)

def draw_vector(x, y, z):
    origin = np.array([0, 0, 0])
    vec = np.array([x, y, z])
    points = np.array([origin, origin + vec])
    line.setData(pos=points, color=(0, 0, 1, 1), width=3, mode='lines')

def update():
    try:
        line_raw = ser.readline().decode().strip()
        parts = line_raw.split(',')
        if len(parts) != 3:
            return
        x, y, z = map(float, parts)
        draw_vector(x, y, z)
    except Exception as e:
        print("에러:", e)

timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(100)  # 10Hz

if __name__ == '__main__':
    QtWidgets.QApplication.instance().exec_()
