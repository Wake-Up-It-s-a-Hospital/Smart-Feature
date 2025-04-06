//이 코드는 입력값에 대해 어느 필터가 값을 가장 잘 필터링하는지 보여주는 실험 코드입니다.

#include <HX711.h>
#include <math.h>

#define DOUT  4
#define CLK   5

HX711 scale(DOUT, CLK);

float calibration_factor = -1500;
float slope = -6.80;
float intercept = 0;

const int total_duration = 30 * 1000;
const int delay_interval = 100;
const int sample_count = total_duration / delay_interval;

float weights[sample_count];
bool experiment_ready = true;

// ===== 필터 함수들 =====
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

// ===== 통계 출력 함수 =====
void print_statistics(float* data, const char* label) {
  float squared_sum = 0;
  float max_val = data[0];
  float min_val = data[0];

  // RMS 계산용 합, 최댓값/최솟값 찾기
  for (int i = 0; i < sample_count; i++) {
    squared_sum += data[i] * data[i];
    if (data[i] > max_val) max_val = data[i];
    if (data[i] < min_val) min_val = data[i];
  }

  float rms_mean = sqrt(squared_sum / sample_count);

  // 표준편차 계산
  float stddev = 0;
  for (int i = 0; i < sample_count; i++) {
    stddev += pow(data[i] - rms_mean, 2);
  }
  stddev = sqrt(stddev / sample_count);

  // 변화폭
  float peak = max_val - min_val;

  // ==== 추가 지표 ====

  // MAD (Mean Absolute Difference)
  float mad = 0;
  for (int i = 1; i < sample_count; i++) {
    mad += abs(data[i] - data[i - 1]);
  }
  mad /= (sample_count - 1);

  // 지터 (샘플 간 변화의 표준편차)
  float delta_sum = 0;
  for (int i = 1; i < sample_count; i++) {
    float diff = data[i] - data[i - 1];
    delta_sum += pow(diff - mad, 2);  // mad를 평균으로 사용
  }
  float jitter = sqrt(delta_sum / (sample_count - 1));

  // 최소 변화 구간 길이 (안정 구간)
  const float stability_threshold = 0.05;  // 변화량이 이 값보다 작으면 안정적이라 판단
  int max_stable_count = 0;
  int current_stable_count = 0;
  for (int i = 1; i < sample_count; i++) {
    if (abs(data[i] - data[i - 1]) < stability_threshold) {
      current_stable_count++;
      if (current_stable_count > max_stable_count)
        max_stable_count = current_stable_count;
    } else {
      current_stable_count = 0;
    }
  }
  float stable_duration_sec = (max_stable_count + 1) * (delay_interval / 1000.0); // 구간 길이를 초로 환산

  // ==== 출력 ====
  Serial.print("\n<실험 결과: ");
  Serial.print(label);
  Serial.println(">");
  Serial.print("RMS 평균: ");
  Serial.println(rms_mean, 3);
  Serial.print("표준편차: ");
  Serial.println(stddev, 2);
  Serial.print("변화폭: ");
  Serial.println(peak, 2);
  Serial.print("MAD(평균 변화량): ");
  Serial.println(mad, 4);
  Serial.print("지터(샘플 간 변동성): ");
  Serial.println(jitter, 4);
  Serial.print("최대 안정 구간 길이: ");
  Serial.print(stable_duration_sec, 2);
  Serial.println("초");
  Serial.print("총 실험 시간: 30초\n총 샘플 수: ");
  Serial.println(sample_count);
}

// ===== 실험 함수 =====
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

  print_statistics(weights, "바닐라");
  print_statistics(ema, "EMA");
  print_statistics(median, "Median Filter");
  print_statistics(delta, "변화량 조정");
  print_statistics(kalman, "칼만 필터");

  Serial.println("\n아무 키나 입력하면 실험을 다시 시작합니다.");
  experiment_ready = true;
}

// ===== 기본 설정 =====
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
