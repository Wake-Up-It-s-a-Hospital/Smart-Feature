#include <HX711.h>
#include <math.h>

#define DOUT  4
#define CLK   5

HX711 scale(DOUT, CLK);

// 보정 관련 변수
float calibration_factor = -1500;
float slope = -6.80;
float intercept = 0;

// 실험 세팅
const int total_duration = 30 * 1000;       // 30초 측정
const int delay_interval = 100;             // 100ms 간격
const int sample_count = total_duration / delay_interval;

float weights[sample_count];
bool experiment_ready = true;

// 최적화 결과 저장용 변수
float best_alpha = 0;
float best_score = -1;

// ===== 점수 계산 함수 (단일 수치화용) =====
float compute_score(float* data) {
  float squared_sum = 0, stddev = 0;
  float max_val = data[0], min_val = data[0];

  for (int i = 0; i < sample_count; i++) {
    squared_sum += data[i] * data[i];
    if (data[i] > max_val) max_val = data[i];
    if (data[i] < min_val) min_val = data[i];
  }

  float rms = sqrt(squared_sum / sample_count);
  for (int i = 0; i < sample_count; i++) {
    stddev += pow(data[i] - rms, 2);
  }
  stddev = sqrt(stddev / sample_count);
  float peak = max_val - min_val;

  float score_rms = 60.0 / (1.0 + rms);
  float score_std = 25.0 / (1.0 + stddev);
  float score_peak = 15.0 / (1.0 + peak);
  return score_rms + score_std + score_peak;
}

// ===== 6가지 지표를 개별 출력하는 함수 =====
void print_metrics(float* data, float alpha_value) {
  float squared_sum = 0;
  float max_val = data[0];
  float min_val = data[0];

  for (int i = 0; i < sample_count; i++) {
    squared_sum += data[i] * data[i];
    if (data[i] > max_val) max_val = data[i];
    if (data[i] < min_val) min_val = data[i];
  }

  float rms_mean = sqrt(squared_sum / sample_count);

  float stddev = 0;
  for (int i = 0; i < sample_count; i++) {
    stddev += pow(data[i] - rms_mean, 2);
  }
  stddev = sqrt(stddev / sample_count);

  float peak = max_val - min_val;

  float mad = 0;
  for (int i = 1; i < sample_count; i++) {
    mad += abs(data[i] - data[i - 1]);
  }
  mad /= (sample_count - 1);

  float delta_sum = 0;
  for (int i = 1; i < sample_count; i++) {
    float diff = data[i] - data[i - 1];
    delta_sum += pow(diff - mad, 2);
  }
  float jitter = sqrt(delta_sum / (sample_count - 1));

  const float stability_threshold = 0.05;
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
  float stable_duration_sec = (max_stable_count + 1) * (delay_interval / 1000.0);

  Serial.print("\n<α = ");
  Serial.print(alpha_value, 2);
  Serial.println("의 EMA 필터 성능 지표>");

  Serial.print("RMS 평균: ");
  Serial.println(rms_mean, 3);
  Serial.print("표준편차: ");
  Serial.println(stddev, 3);
  Serial.print("변화폭: ");
  Serial.println(peak, 3);
  Serial.print("MAD (평균 변화량): ");
  Serial.println(mad, 4);
  Serial.print("지터 (샘플 간 변화 표준편차): ");
  Serial.println(jitter, 4);
  Serial.print("최대 안정 구간 길이: ");
  Serial.print(stable_duration_sec, 2);
  Serial.println("초");
}

// ===== EMA 알파 최적화 함수 (지표 출력 포함) =====
void find_best_alpha_dynamic(float* weights) {
  Serial.println("\n[동적 EMA α 최적화 시작]");

  best_alpha = 0;
  best_score = -1;

  float ema[sample_count];

  for (float alpha = 0.05; alpha <= 0.5; alpha += 0.01) {
    ema[0] = weights[0];
    for (int i = 1; i < sample_count; i++) {
      ema[i] = alpha * weights[i] + (1 - alpha) * ema[i - 1];
    }

    float score = compute_score(ema);
    if (score > best_score) {
      best_score = score;
      best_alpha = alpha;
    }

    print_metrics(ema, alpha);
  }

  Serial.print("\n✅ 최적 α = ");
  Serial.print(best_alpha, 2);
  Serial.print(" (예상 윈도우 길이 ≈ ");
  Serial.print((2.0 / best_alpha) - 1, 1);
  Serial.println(" 샘플)");
}

// ===== 실험 실행 함수 =====
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

  find_best_alpha_dynamic(weights);

  // 최적 EMA 적용 시범 출력
  Serial.println("\n최적 EMA 필터 결과 (일부 출력):");
  float filtered[sample_count];
  filtered[0] = weights[0];
  for (int i = 1; i < sample_count; i++) {
    filtered[i] = best_alpha * weights[i] + (1 - best_alpha) * filtered[i - 1];
  }

  for (int i = 0; i < 10; i++) {
    Serial.print("Filtered[");
    Serial.print(i);
    Serial.print("] = ");
    Serial.println(filtered[i], 4);
  }

  Serial.println("\n아무 키나 입력하면 실험을 다시 시작합니다.");
  experiment_ready = true;
}

// ===== 초기 설정 =====
void setup() {
  Serial.begin(115200);
  scale.set_scale();
  scale.tare();
  Serial.println("ESP32 HX711 Stability Test Ready. 아무 키나 누르면 시작합니다.");
}

// ===== 메인 루프 =====
void loop() {
  if (experiment_ready && Serial.available()) {
    Serial.read();
    experiment_ready = false;
    run_experiment();
  }
}
