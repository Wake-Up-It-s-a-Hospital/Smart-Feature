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
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <math.h>

// Function prototypes
void uploadToDynamoDB(int loadcell_id, float weight, float remaining_time);
void process_loadcell_data(int loadcell_id, HX711 &scale, float &ema_previous, float *ema_data, int &data_index);
void connectToWiFi();

#define WIFI_SSID "MERCUSYS_FF46"
#define WIFI_PASSWORD "64196374"

// --- AWS & API Gateway ---
// AWS 설정 단계에서 생성한 API Gateway 호출 URL을 여기에 입력하세요.
#define API_GATEWAY_URL "https://tln54ai1oi.execute-api.ap-northeast-2.amazonaws.com/v1"

// --- Pin Definitions ---
#define DOUT1 34
#define CLK1  35
#define DOUT2 25
#define CLK2  26

// --- HX711 Instances ---
HX711 scale1;
HX711 scale2;

// --- Calibration and Filter settings ---
const float calibration_factor = -1500.0;
const float slope = -6.80;
const float intercept = 0;
const float alpha = 0.01;
const int delay_interval = 100;
const int max_data = 300;

// Per-loadcell data
// Loadcell 1
float ema_previous_1 = 0;
float ema_data_1[max_data];
int data_index_1 = 0;

// Loadcell 2
float ema_previous_2 = 0;
float ema_data_2[max_data];
int data_index_2 = 0;

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

// ===== DynamoDB 업로드 함수 =====
void uploadToDynamoDB(int loadcell_id, float weight, float remaining_time) {
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClientSecure client;
    client.setInsecure(); 

    HTTPClient http;
    http.begin(client, API_GATEWAY_URL);
    http.addHeader("Content-Type", "application/json");

    // JSON 페이로드 생성
    StaticJsonDocument<200> doc;
    doc["loadcel"] = String(loadcell_id);
    doc["current_weight"] = weight;
    doc["remaining_sec"] = remaining_time;

    String requestBody;
    serializeJson(doc, requestBody);

    int httpResponseCode = http.POST(requestBody);

    if (httpResponseCode > 0) {
      Serial.printf("✅ 로드셀 %d: DynamoDB 업로드 성공! (코드: %d)\n", loadcell_id, httpResponseCode);
    } else {
      Serial.printf("❌ 로드셀 %d: DynamoDB 업로드 실패, 에러: %s\n", loadcell_id, http.errorToString(httpResponseCode).c_str());
    }

    http.end();
  } else {
    Serial.printf("⚠️ 로드셀 %d: Wi-Fi 연결이 끊어져 업로드 불가\n", loadcell_id);
  }
}

// ===== 데이터 처리, 예측 및 업로드 통합 함수 =====
void process_loadcell_data(
    int loadcell_id,
    HX711 &scale,
    float &ema_previous,
    float *ema_data,
    int &data_index)
{
    // 1. 측정
    scale.set_scale(calibration_factor);
    float raw = scale.get_units();
    float corrected = (raw * slope) + intercept;

    // 2. EMA 필터 적용
    float ema = (data_index == 0) ? corrected : alpha * corrected + (1 - alpha) * ema_previous;
    ema_previous = ema;

    // 3. FIFO 버퍼에 데이터 저장
    if (data_index < max_data) {
        ema_data[data_index] = ema;
        data_index++;
    } else {
        for (int i = 1; i < max_data; i++) {
            ema_data[i - 1] = ema_data[i];
        }
        ema_data[max_data - 1] = ema;
    }

    // 4. 예측 및 업로드
    if (data_index < 2) {
        Serial.printf("⏳ 로드셀 %d: 데이터 부족으로 예측 불가\n", loadcell_id);
        return;
    }

    float slope_estimate = compute_slope(ema_data, 0, data_index, delay_interval / 1000.0);

    if (isnan(slope_estimate)) {
        Serial.printf("❌ 로드셀 %d: 기울기 계산 불가 (NaN)\n", loadcell_id);
        return;
    }

    float current_weight = ema_data[data_index - 1];

    if (abs(slope_estimate) < 0.001) {
        Serial.printf("⚠️ 로드셀 %d: 변화량 작아 예측 불가 (무게만 업로드)\n", loadcell_id);
        uploadToDynamoDB(loadcell_id, current_weight, -1); // 남은 시간 -1로 전송
        return;
    }

    float remaining_sec = current_weight / abs(slope_estimate);

    Serial.printf("📦 로드셀 %d | 📉 기울기: %.4f g/s | 무게: %.2f g | 남은 시간: %.1f 초\n",
                  loadcell_id, slope_estimate, current_weight, remaining_sec);

    uploadToDynamoDB(loadcell_id, current_weight, remaining_sec);
}

// ===== Wi-Fi 연결 =====
void connectToWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Wi-Fi 연결 중");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ Wi-Fi 연결 성공");
}

// ===== 초기 설정 =====
void setup() {
  Serial.begin(115200);

  connectToWiFi();
  
  Serial.println("HX711 로드셀 2개 초기화 중...");
  scale1.begin(DOUT1, CLK1);
  scale2.begin(DOUT2, CLK2);

  scale1.set_scale(calibration_factor);
  scale2.set_scale(calibration_factor);

  Serial.println("영점 보정 시작 (각 로드셀에 3초 소요)...");
  scale1.tare();
  Serial.println("로드셀 1 영점 보정 완료.");
  scale2.tare();
  Serial.println("로드셀 2 영점 보정 완료.");

  Serial.println("ESP32 실시간 수액 예측 시스템 준비 완료");
  Serial.println("100ms마다 측정 + EMA + 선형 회귀로 잔여 시간 예측 시작");
  Serial.println("📦 's' 키를 누르면 측정 중단\n");

  ema_previous_1 = 0;
  ema_previous_2 = 0;
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

  // 각 로드셀에 대한 데이터 처리
  process_loadcell_data(1, scale1, ema_previous_1, ema_data_1, data_index_1);
  process_loadcell_data(2, scale2, ema_previous_2, ema_data_2, data_index_2);

  delay(delay_interval);
}


// #include <HX711.h>

// // 핀 설정: HX711의 DT → GPIO 4, SCK → GPIO 5
// #define DOUT  4
// #define CLK   5

// HX711 scale(DOUT, CLK);

// // 보정 계수: 필요에 따라 실험적으로 조정
// float calibration_factor = -1500.0;  
// float slope = -6.80;
// float intercept = 0;

// void setup() {
//   Serial.begin(115200);
//   Serial.println("HX711 로드셀 무게 측정 초기화 중...");

//   // HX711 초기화
//   scale.set_scale(calibration_factor);  // 보정 계수 설정
//   scale.begin(DOUT, CLK);
//   scale.tare();  // 영점 보정 (로드셀 위에 아무것도 없는 상태에서)

//   Serial.println("초기화 완료. 측정을 시작합니다.");
// }

// void loop() {
//     float raw = scale.get_units();
//     float corrected = (raw * slope) + intercept;
//     Serial.print("측정된 무게: ");
//     Serial.print(corrected, 2);  // 소수점 2자리까지 출력
//     Serial.println(" g");

//   delay(100);  // 0.5초마다 측정
// }
