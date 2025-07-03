#include <Wire.h>
#include <MPU6050.h>

MPU6050 imu;

class SimpleKalmanFilter {
  float Q;  // 프로세스 노이즈
  float R;  // 측정 노이즈
  float X;  // 상태값 (추정값)
  float P;  // 오차 공분산

public:
  SimpleKalmanFilter(float process_noise, float measurement_noise, float estimated_error) {
    Q = process_noise;
    R = measurement_noise;
    P = estimated_error;
    X = 0;
  }

  float update(float measurement) {
    // 예측 단계
    P = P + Q;

    // 칼만 이득
    float K = P / (P + R);

    // 업데이트 단계
    X = X + K * (measurement - X);
    P = (1 - K) * P;

    return X;
  }
};

// Kalman 필터 객체 (Q, R, P 초기값 조정 가능)
SimpleKalmanFilter kalmanX(0.001, 0.1, 0.1);
SimpleKalmanFilter kalmanY(0.001, 0.1, 0.1);
SimpleKalmanFilter kalmanZ(0.001, 0.1, 0.1);

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22); // SDA=21, SCL=22
  imu.initialize();

  if (!imu.testConnection()) {
    Serial.println("MPU6050 연결 실패");
    while (1);
  }

  Serial.println("MPU6050 연결 성공");
}

void loop() {
  int16_t ax, ay, az;
  imu.getAcceleration(&ax, &ay, &az);

  // 단위 변환 (g 단위)
  float rawX = ax / 16384.0;
  float rawY = ay / 16384.0;
  float rawZ = az / 16384.0;

  // Kalman 필터 적용
  float accX = kalmanX.update(rawX);
  float accY = kalmanY.update(rawY);
  float accZ = kalmanZ.update(rawZ);

  // 필터링된 값 출력
  Serial.print(accX); Serial.print(",");
  Serial.print(accY); Serial.print(",");
  Serial.println(accZ);

  delay(100);
}
