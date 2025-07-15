import serial
from ultralytics import YOLO
import cv2
# 클래스 정의
CLASS_NAMES = ['person', 'helmet', 'fire', 'smoke', 'backpack']
# 시리얼 포트 설정 (아두이노연결)
ser = serial.Serial('COM6', 9600)  # 포트 및 속도는 환경에 맞게 설정
def send_command(x1, x2, frame_width):
    center = (x1 + x2) / 2
    if center < frame_width * 0.4:
        ser.write(b'left\n')
    elif center > frame_width * 0.6:
        ser.write(b'right\n')
    else:
        ser.write(b'stop\n')

def detect_and_control(image_path, model_path='yolov8n.pt'):
    model = YOLO(model_path)
    image = cv2.imread(image_path)
    results = model(image)
    boxes = results[0].boxes

    for box in boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        cls_id = int(box.cls[0])
        cls_name = CLASS_NAMES[cls_id]

        if cls_name in ['person', 'fire', 'smoke']:
            send_command(x1, x2, image.shape[1])

    cv2.imshow('Object Detection', image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

# 실행
detect_and_control("disaster_scene.jpg")
