import serial
import matplotlib.pyplot as plt

ser = serial.Serial('COM2', 115200)
data = []

plt.ion()
fig, ax = plt.subplots()

while True:
    if ser.in_waiting:
        line = ser.readline().decode().strip()
        try:
            value = float(line)
            data.append(value)
            if len(data) > 100:
                data.pop(0)

            ax.clear()
            ax.plot(data)
            plt.pause(0.01)
        except ValueError:
            pass  # 숫자가 아니면 무시
