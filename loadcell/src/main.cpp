#include <HX711.h>
#include <math.h>

#define DOUT  4
#define CLK   5

HX711 scale(DOUT, CLK);

float calibration_factor = -1500;
float slope = -6.80;
float intercept = 0;

const int total_duration = 30 * 1000;
const int delay_interval = 500;
const int sample_count = total_duration / delay_interval;

float weights[sample_count];
bool experiment_ready = true;

// ===== 필터링 함수 정의 =====
float ema_filter(int index, float alpha, float* data) {
  static float prev = 0;
  if (index == 0) prev = data[0];
  float result = alpha * data[index] + (1 - alpha) * prev;
  prev = result;
  return result;
}

float median_filter(int index, float* data) {
  int start = max(0, index - 1);
  int end = min(sample_count - 1, index + 1);
  float temp[3];
  int j = 0;
  for (int i = start; i <= end; i++) {
    temp[j++] = data[i];
  }
  // 정렬
  for (int i = 0; i < j - 1; i++) {
    for (int k = i + 1; k < j; k++) {
      if (temp[i] > temp[k]) {
        float t = temp[i]; temp[i] = temp[k]; temp[k] = t;
      }
    }
  }
  return temp[j / 2];
}

float delta_filter(int index, float* data) {
  static float prev = 0;
  if (index == 0) prev = data[0];
  float delta = data[index] - prev;
  if (abs(delta) < 0.05) return prev;
  prev = data[index];
  return data[index];
}

float kalman_filter(int index, float* data) {
  static float x = 0;
  static float P = 1;
  static float last_measurement = 0;
  if (index == 0) {
    x = data[0];
    last_measurement = data[0];
  }

  float measurement = data[index];
  float measurement_diff = abs(measurement - last_measurement);
  last_measurement = measurement;

  float Q_kalman = 0.001 + 0.05 * measurement_diff;
  float R_kalman = 0.01 + 0.1 * measurement_diff;

  P = P + Q_kalman;
  float K = P / (P + R_kalman);
  x = x + K * (measurement - x);
  P = (1 - K) * P;

  return x;
}

// ===== 통계 및 점수 계산 =====
float compute_score(float* data, const char* label) {
  float abs_sum = 0, mean = 0, stddev = 0, max_val = data[0], min_val = data[0];

  for (int i = 0; i < sample_count; i++) {
    abs_sum += abs(data[i]);
    mean += data[i];
    if (data[i] > max_val) max_val = data[i];
    if (data[i] < min_val) min_val = data[i];
  }
  mean /= sample_count;
  float avg_abs = abs_sum / sample_count;

  for (int i = 0; i < sample_count; i++) {
    stddev += pow(data[i] - mean, 2);
  }
  stddev = sqrt(stddev / sample_count);

  float peak = max_val - min_val;
  float score_avg = 60.0 / (1.0 + avg_abs);
  float score_std = 25.0 / (1.0 + stddev);
  float score_peak = 15.0 / (1.0 + peak);
  float total_score = score_avg + score_std + score_peak;

  Serial.print("\n<실험 결과: ");
  Serial.print(label);
  Serial.println(">");
  Serial.print("무게 변화량: "); Serial.println(score_avg, 2);
  Serial.print("표준편차: "); Serial.println(score_std, 2);
  Serial.print("최대 변화폭: "); Serial.println(score_peak, 2);
  Serial.print("총점: "); Serial.println(total_score, 2);

  return total_score;
}

void run_experiment() {
  Serial.println("\n센서 안정화 중...");
  delay(5000);
  Serial.println("측정 시작");

  unsigned long start_time = millis();
  unsigned long last_second_mark = start_time;

  for (int i = 0; i < sample_count; i++) {
    scale.set_scale(calibration_factor);
    float raw = scale.get_units();
    float corrected = (raw * slope) + intercept;
    weights[i] = corrected;

    unsigned long current_time = millis();
    if (current_time - last_second_mark >= 1000) {
      int seconds_elapsed = (current_time - start_time) / 1000;
      Serial.print(seconds_elapsed);
      Serial.println("초 경과");
      last_second_mark += 1000;
    }

    delay(delay_interval);
  }

  float ema[sample_count];
  float median[sample_count];
  float delta[sample_count];
  float kalman[sample_count];

  for (int i = 0; i < sample_count; i++) {
    ema[i] = ema_filter(i, 0.2, weights);
    median[i] = median_filter(i, weights);
    delta[i] = delta_filter(i, weights);
    kalman[i] = kalman_filter(i, weights);
  }

  compute_score(weights, "바닐라");
  compute_score(ema, "EMA");
  compute_score(median, "Median Filter");
  compute_score(delta, "변화량 조정");
  compute_score(kalman, "칼만 필터");

  Serial.println("\n아무 키나 입력하면 실험을 다시 시작합니다.");
  experiment_ready = true;
}

void setup() {
  Serial.begin(115200);
  scale.set_scale();
  scale.tare();
  Serial.println("ESP32 HX711 Stability Test Ready. 아무 키나 누르면 시작합니다.");
}

void loop() {
  if (experiment_ready && Serial.available()) {
    Serial.read(); // 입력 소비
    experiment_ready = false;
    run_experiment();
  }
}
