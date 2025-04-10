// 데이터 플로우
// 100ms 간격으로 데이터 측정 => EMA 필터로 입력값 안정화 => 선형회귀 수행(데이터가 1개일때는 예외처리) => 100ms 간격으로 데이터 측정.....

// max_data: 측정 가능한 최대 데이터 수 → 고정 크기 배열로 관리
// 100ms 간격으로 데이터 측정
// EMA 필터로 입력값 안정화 (α=0.01)
// 최근 회귀 윈도우 길이만큼 데이터를 기준으로 선형 회귀 수행
// 데이터가 2개 미만이거나 기울기 너무 작을 경우 예외 처리
// 100ms 간격으로 루프가 계속 돌아가면서 잔여 시간 출력

#include <HX711.h>
#include <WiFi.h>
#include <FirebaseESP32.h>
#include <math.h>

// Function prototypes
void upload_to_firebase(float weight, float remaining_time);
void predict_remaining_time();
void connectToWiFi();
void setupFirebase();

#define WIFI_SSID "MERCUSYS_FF46"
#define WIFI_PASSWORD "Yoonsung123"
#define FIREBASE_PROJECT_ID "smart-iv-pole-f98ce"
#define API_KEY "AIzaSyA-CdsRfm7pIXDNQClaco2KWnapFZfOaGs"
#define DATABASE_URL "https://smart-iv-pole-f98ce-default-rtdb.asia-southeast1.firebasedatabase.app/"
FirebaseAuth auth;
FirebaseConfig config;
FirebaseData fbdo;

#define DOUT  4
#define CLK   5

HX711 scale(DOUT, CLK);

// 보정값
float calibration_factor = -1500;
float slope = -6.80;
float intercept = 0;

// EMA 필터 설정
const float alpha = 0.01;
float ema_previous = 0;

// 측정 설정
const int delay_interval = 100;         // 100ms 간격
const int max_data = 300;               // 최대 저장 데이터 수
const int regression_window = 30;       // 선형회귀에 사용할 데이터 수

float raw_data[max_data];               // 원본 측정값
float ema_data[max_data];               // EMA 필터 적용값
int data_index = 0;                     // 현재 데이터 수

bool is_running = true;

// ===== 선형 회귀 함수 =====
float compute_slope(float* y_values, int start_idx, int count, float interval_sec) {
  float sum_x = 0, sum_y = 0, sum_xy = 0, sum_x2 = 0;
  for (int i = 0; i < count; i++) {
    float x = i * interval_sec;
    float y = y_values[start_idx + i];
    sum_x += x;
    sum_y += y;
    sum_xy += x * y;
    sum_x2 += x * x;
  }

  float numerator = (count * sum_xy) - (sum_x * sum_y);
  float denominator = (count * sum_x2) - (sum_x * sum_x);
  if (denominator == 0) return NAN;
  return numerator / denominator;
}

void upload_to_firebase(float weight, float remaining_time) {
  if (Firebase.ready()) {
    String path_weight = "/infusion/current_weight";
    String path_time = "/infusion/remaining_sec";

    if (Firebase.RTDB.setFloat(&fbdo, path_weight, weight)) {
      Serial.println("✅ 수액 무게 업로드 성공");
    } else {
      Serial.print("❌ 수액 무게 업로드 실패: ");
      Serial.println(fbdo.errorReason());
    }

    if (Firebase.RTDB.setFloat(&fbdo, path_time, remaining_time)) {
      Serial.println("✅ 남은 시간 업로드 성공");
    } else {
      Serial.print("❌ 남은 시간 업로드 실패: ");
      Serial.println(fbdo.errorReason());
    }
  } else {
    Serial.println("⚠️ Firebase가 준비되지 않음");
  }
}

// ===== 투여 시간 예측 루틴 =====
void predict_remaining_time() {
  if (data_index < 2) {
    Serial.println("⏳ 데이터 부족으로 예측 불가");
    return;
  }

  int use_count = data_index;
  int start_idx = 0;

  float slope_estimate = compute_slope(ema_data, start_idx, use_count, delay_interval / 1000.0);

  if (isnan(slope_estimate)) {
    Serial.println("❌ 기울기 계산 불가 (NaN)");
    return;
  }

  if (abs(slope_estimate) < 0.001) {
    Serial.println("⚠️ 변화량 너무 작아 예측 정확도 낮음");
    return;
  }

  float current_weight = ema_data[data_index - 1];
  float remaining_sec = current_weight / abs(slope_estimate);

  Serial.print("📉 추정 기울기: ");
  Serial.print(slope_estimate, 4);
  Serial.print(" g/s, 남은 무게: ");
  Serial.print(current_weight, 2);
  Serial.print(" g, 예상 시간: ");
  Serial.print(remaining_sec, 1);
  Serial.println(" 초");
  upload_to_firebase(current_weight, remaining_sec);
}

void connectToWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Wi-Fi 연결 중");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ Wi-Fi 연결 성공");
}

void setupFirebase() {
  config.api_key = API_KEY;
  config.database_url = DATABASE_URL;
  auth.user.email = "";
  auth.user.password = "";

  Firebase.begin(&config, &auth);
  Firebase.reconnectWiFi(true);
}

// ===== 초기 설정 =====
void setup() {
  Serial.begin(115200);

  connectToWiFi();
  setupFirebase();
  
  scale.set_scale();
  scale.tare();
  Serial.println("ESP32 실시간 수액 예측 시스템 준비 완료");
  Serial.println("100ms마다 측정 + EMA + 선형 회귀로 잔여 시간 예측 시작");
  Serial.println("📦 's' 키를 누르면 측정 중단\n");

  ema_previous = 0;
}

// ===== 메인 루프 =====
void loop() {
  // 시리얼 키 입력 확인
  if (Serial.available()) {
    char c = Serial.read();
    if (c == 's' || c == 'S') {
      is_running = false;
      Serial.println("🛑 측정 중단됨");
    }
  }

  if (!is_running) return;

  // 측정
  scale.set_scale(calibration_factor);
  float raw = scale.get_units();
  float corrected = (raw * slope) + intercept;

  // EMA 적용
  float ema = (data_index == 0) ? corrected : alpha * corrected + (1 - alpha) * ema_previous;
  ema_previous = ema;

  // 데이터 저장 (FIFO 방식)
  if (data_index < max_data) {
    raw_data[data_index] = corrected;
    ema_data[data_index] = ema;
    data_index++;
  } else {
    // 데이터 이동: 가장 오래된 값 삭제, 한 칸씩 앞으로 밀기
    for (int i = 1; i < max_data; i++) {
      raw_data[i - 1] = raw_data[i];
      ema_data[i - 1] = ema_data[i];
    }
    raw_data[max_data - 1] = corrected;
    ema_data[max_data - 1] = ema;
  }

  // 예측 수행
  predict_remaining_time();

  delay(delay_interval);
}
