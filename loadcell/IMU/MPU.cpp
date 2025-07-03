#include <Wire.h>
#include <MPU6050.h>

MPU6050 imu;

void setup() {
  Serial.begin(115200);
  Wire.begin();
  imu.initialize();
}

void loop() {
  int16_t ax, ay, az;
  imu.getAcceleration(&ax, &ay, &az);

  // 가속도는 보통 raw값이므로 변환 필요
  float accX = ax / 16384.0;
  float accY = ay / 16384.0;
  float accZ = az / 16384.0;

  Serial.print(accX); Serial.print(",");
  Serial.print(accY); Serial.print(",");
  Serial.println(accZ);

  delay(100);
}
