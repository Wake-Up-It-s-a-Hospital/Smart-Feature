#include <HX711.h>

#define DOUT  4
#define CLK   5

HX711 scale(DOUT, CLK);

float calibration_factor = -1500;

float slope = -6.80;
float intercept = 0;

float previous_weight = 0;
unsigned long previous_time = 0;
float infusion_rate = 0;

const float target_weight = 20.0;

unsigned long last_update_time = 0;
const unsigned long update_interval = 500;

float weight_sum = 0;
int weight_count = 0;

float first_weight_in_window = 0;

// 최근 flow speed 값 저장 (평균 계산용)
#define SMOOTHING_WINDOW 5
float infusion_rate_buffer[SMOOTHING_WINDOW] = {0};
int buffer_index = 0;

void setup() {
  Serial.begin(115200);
  scale.set_scale();
  scale.tare();

  long zero_factor = scale.read_average();
  Serial.print("Zero factor: ");
  Serial.println(zero_factor);

  previous_weight = 0;
  previous_time = millis();
  last_update_time = millis();
}

void loop() {
  scale.set_scale(calibration_factor);

  float raw_value = scale.get_units();
  float corrected_weight = (raw_value * slope) + intercept;
  unsigned long current_time = millis();

  if (weight_count == 0) {
    first_weight_in_window = corrected_weight;
  }

  weight_sum += corrected_weight;
  weight_count++;

  if (current_time - last_update_time >= update_interval) {
    float avg_weight = weight_sum / weight_count;

    float weight_diff = avg_weight - first_weight_in_window;
    float current_infusion_rate = weight_diff / (update_interval / 1000.0);

    // 최근 flow speed 값 저장 (이동 평균 적용)
    infusion_rate_buffer[buffer_index] = current_infusion_rate;
    buffer_index = (buffer_index + 1) % SMOOTHING_WINDOW;

    // 최근 N개의 flow speed 평균 계산
    float smoothed_infusion_rate = 0;
    for (int i = 0; i < SMOOTHING_WINDOW; i++) {
      smoothed_infusion_rate += infusion_rate_buffer[i];
    }
    smoothed_infusion_rate /= SMOOTHING_WINDOW;

    infusion_rate = smoothed_infusion_rate;

    float remaining_time = 0;
    if (infusion_rate < -0.1) { // flow speed가 충분히 작을 때만 계산
      float weight_to_target = avg_weight - target_weight;
      if (weight_to_target > 0) {
        remaining_time = weight_to_target / -infusion_rate;
      } else {
        remaining_time = 0;
      }
    } else {
      remaining_time = -1; // 계산 불가
    }

    Serial.print("Raw Reading: ");
    Serial.print(raw_value, 1);
    Serial.print(" | Corrected Weight: ");
    Serial.print(corrected_weight, 1);
    Serial.print(" g | Calibration Factor: ");
    Serial.print(calibration_factor);
    Serial.print(" | Flow Speed: ");
    Serial.print(infusion_rate, 2);
    Serial.print(" g/s | Estimated Time Remaining (20g): ");

    if (remaining_time > 0) {
        int hours = remaining_time / 3600;
        int minutes = ((int)remaining_time % 3600) / 60;
        int seconds = (int)remaining_time % 60;
        Serial.printf("%02d:%02d:%02d\n", hours, minutes, seconds);
    } else {
        Serial.println("Calculating...");
    }

    weight_sum = 0;
    weight_count = 0;
    last_update_time = current_time;
  }

  delay(10);
}
