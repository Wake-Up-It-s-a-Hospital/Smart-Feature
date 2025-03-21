#include <HX711.h>

#define DOUT  4  // ESP32에서 데이터 핀 설정 (예: GPIO 4)
#define CLK   5  // ESP32에서 클럭 핀 설정 (예: GPIO 5)

HX711 scale(DOUT, CLK);

float calibration_factor = -1500; // ESP32에서도 동일한 보정 계수 사용

float slope = -6.80;  // 보정된 변환 계수
float intercept = 0; // 변환 보정값

float previous_weight = 0; // 이전 무게 저장
unsigned long previous_time = 0; // 이전 시간 저장
float infusion_rate = 0; // 투여 속도 (g/s)

const float target_weight = 20.0; // 목표 무게 설정 (20g 이하로 떨어지는 시점)

unsigned long last_update_time = 0; // 마지막 flow speed & 예측 시간 업데이트
const unsigned long update_interval = 500; // 500ms마다 업데이트

float weight_sum = 0; // 지난 500ms 동안 측정된 무게 합
int weight_count = 0; // 지난 500ms 동안 측정된 무게 개수

float first_weight_in_window = 0; // 500ms 구간의 첫 번째 무게 값 저장

void setup() {
  Serial.begin(115200);  // ESP32는 115200bps가 더 적절함
  Serial.println("ESP32 HX711 Calibration");

  scale.set_scale();
  scale.tare(); // 0점 조정 (초기화)

  long zero_factor = scale.read_average();
  Serial.print("Zero factor: ");
  Serial.println(zero_factor);

  previous_weight = 0;
  previous_time = millis();
  last_update_time = millis();
}

void loop() {
  scale.set_scale(calibration_factor); // 보정 계수 적용

  float raw_value = scale.get_units(); // 원래 측정된 값
  float corrected_weight = (raw_value * slope) + intercept; // 변환된 무게(g)
  unsigned long current_time = millis();

  // 첫 번째 무게 값 저장 (500ms 구간 시작 시점)
  if (weight_count == 0) {
    first_weight_in_window = corrected_weight;
  }

  // 무게 값 누적 (500ms 평균 계산용)
  weight_sum += corrected_weight;
  weight_count++;

  // 500ms마다 flow speed 및 예측 시간 업데이트
  if (current_time - last_update_time >= update_interval) {
    float avg_weight = weight_sum / weight_count; // 평균 무게 계산

    // Flow speed 계산 (500ms 동안의 무게 변화량 기반)
    float weight_diff = avg_weight - first_weight_in_window;
    infusion_rate = weight_diff / (update_interval / 1000.0); // g/s 변환

    // 예측 시간 계산
    float remaining_time = 0;
    if (infusion_rate < 0) { // 음수일 때만 남은 시간 계산
      float weight_to_target = avg_weight - target_weight; // 목표까지 남은 무게
      if (weight_to_target > 0) {
        remaining_time = weight_to_target / -infusion_rate;
      } else {
        remaining_time = 0; // 이미 목표 이하라면 0으로 설정
      }
    }

    // 시리얼 출력
    Serial.print("Raw Reading: ");
    Serial.print(raw_value, 1);
    Serial.print(" | Corrected Weight: ");
    Serial.print(corrected_weight, 1);
    Serial.print(" g | Calibration Factor: ");
    Serial.print(calibration_factor);
    Serial.print(" | Flow Speed: ");
    Serial.print(infusion_rate, 2);
    Serial.print(" g/s | Estimated Time Remaining: ");

    // 남은 예상 투여 시간 출력
    if (remaining_time > 0) {
        int hours = remaining_time / 3600;
        int minutes = ((int)remaining_time % 3600) / 60;
        int seconds = (int)remaining_time % 60;
        Serial.printf("%02d:%02d:%02d\n", hours, minutes, seconds); // 개행 포함
    } else {
        Serial.println("Completed or Calculating..."); // 개행 포함
    }

    // 누적 데이터 초기화
    weight_sum = 0;
    weight_count = 0;
    last_update_time = current_time;
  }

  delay(10); // 10ms마다 업데이트
}