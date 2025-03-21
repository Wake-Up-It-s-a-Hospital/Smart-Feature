#include <HX711.h>
#include <math.h>

#define DOUT  4  // ESP32에서 데이터 핀 설정 (예: GPIO 4)
#define CLK   5  // ESP32에서 클럭 핀 설정 (예: GPIO 5)

HX711 scale(DOUT, CLK);

float calibration_factor = -1500; // ESP32에서도 동일한 보정 계수 사용

float slope = -6.80;  // 보정된 변환 계수
float intercept = 0; // 변환 보정값

void setup() {
  Serial.begin(115200);  // ESP32는 115200bps가 더 적절함
  Serial.println("ESP32 HX711 Calibration");

  scale.set_scale();
  scale.tare(); // 0점 조정 (초기화)

  long zero_factor = scale.read_average();
  Serial.print("Zero factor: ");
  Serial.println(zero_factor);
}

void loop() {
  scale.set_scale(calibration_factor); // 보정 계수 적용

  float raw_value = scale.get_units(); // 원래 측정된 값
  float corrected_weight = (raw_value * slope) + intercept; // 변환된 무게(g)

  Serial.print("Raw Reading: ");
  Serial.print(raw_value, 1);
  Serial.print(" | Corrected Weight: ");
  Serial.print(corrected_weight, 1);
  Serial.print(" g | Calibration Factor: ");
  Serial.println(calibration_factor);

  if (Serial.available()) {
    char temp = Serial.read();
    if (temp == '+' || temp == 'a') {
      calibration_factor += 10;  // 보정 계수 미세 조정
    } else if (temp == '-' || temp == 'z') {
      calibration_factor -= 10;
    }
  }

  delay(500); // 데이터 출력 속도 조절
}