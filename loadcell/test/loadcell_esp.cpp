#include <HX711.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <math.h>
#include <time.h>

// ===== Nextion 디스플레이 통신 설정 =====
#define RXD2 16  // Nextion TX(파랑) 연결
#define TXD2 17  // Nextion RX(노랑) 연결

void sendCommand(const String& cmd) {
  Serial2.print(cmd);
  Serial2.write(0xFF);
  Serial2.write(0xFF);
  Serial2.write(0xFF);
}
float simple_remaining_sec = 0;

// ===== 하이브리드 필터 클래스 =====
class HybridFilter {
private:
    float buffer[10];
    int index = 0;
    float last_filtered_value = 0;
    bool is_initialized = false;
    
public:
    float filter(float new_value) {
        // 버퍼에 새 값 추가
        buffer[index] = new_value;
        index = (index + 1) % 10;
        
        // 초기화 중일 때는 원본 값 반환
        if (!is_initialized && index < 10) {
            return new_value;
        } 
        
        if (index == 0) {
            is_initialized = true;
        }
        
        // 1단계: 중간값으로 급격한 스파이크 제거
        float temp[10];
        for (int i = 0; i < 10; i++) {
            temp[i] = buffer[i];
        }
        
        // 버블 정렬로 중간값 찾기
        for (int i = 0; i < 9; i++) {
            for (int j = 0; j < 9 - i; j++) {
                if (temp[j] > temp[j + 1]) {
                    float t = temp[j];
                    temp[j] = temp[j + 1];
                    temp[j + 1] = t;
                }
            }
        }
        
        float median = temp[5];  // 중간값
        
        // 2단계: 이전 값과의 적응형 평균
        float difference = abs(median - last_filtered_value);
        float alpha = (difference > 2.0) ? 0.3 : 0.7;  // 변화량에 따라 가중치 조절
        
        last_filtered_value = last_filtered_value * (1 - alpha) + median * alpha;
        
        return last_filtered_value;
    }
    
    void reset() {
        index = 0;
        last_filtered_value = 0;
        is_initialized = false;
    }
};

// Function prototypes
void uploadToDynamoDB(int loadcell_id, float weight, float remaining_time);
void uploadNurseCall();
void process_loadcell_data(int loadcell_id, HX711 &scale, float &ema_previous, float *ema_data, int &data_index);
void connectToWiFi();

// Home
// #define WIFI_SSID "MERCUSYS_FF46"
// #define WIFI_PASSWORD "64196374"

// Hotspot
#define WIFI_SSID "iPhone"
#define WIFI_PASSWORD "aksiaksi"


// --- AWS & API Gateway ---
#define API_GATEWAY_URL "https://tln54ai1oi.execute-api.ap-northeast-2.amazonaws.com/v1/data"

// --- Pin Definitions ---
#define DOUT1 34
#define CLK1  25
#define LED_PIN 19
unsigned long last_blink_time = 0;
bool led_state = false;

// --- HX711 Instances ---
HX711 scale1;

// --- Calibration and Filter settings ---
const float calibration_factor = 1486.0;
const float slope = -6.80;
const float intercept = 0;
const float alpha = 0.01;
const int delay_interval = 100;
const int max_data = 300;

// --- 필터 인스턴스 ---
HybridFilter filter1;

// Per-loadcell data
float ema_previous_1 = 0;
float ema_data_1[max_data];
int data_index_1 = 0;

// ===== Nextion 디스플레이 변수 =====
unsigned long lastMillis = 0;

// ===== nurse_call 관련 변수 =====
bool nurse_call_active = false;
unsigned long nurse_blink_start = 0;
int nurse_blink_count = 0;
bool nurse_blink_state = false;

// ===== nurse_call 상태 유지 변수 =====
bool nurse_call_status = false;
unsigned long nurse_call_start_time = 0;
const unsigned long NURSE_CALL_DURATION = 5 * 60 * 1000;  // 5분 (밀리초)

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
    http.addHeader("x-api-key", "NfM1X8S5xk72BrGbFqr1t9CMtzxMaeKe7PFatzaC"); // 여기에 실제 API 키 입력

    // JSON 페이로드 생성
    JsonDocument doc;
    doc["loadcel"] = String(loadcell_id);
    doc["current_weight"] = weight;
    doc["remaining_sec"] = remaining_time;
    doc["nurse_call"] = nurse_call_status;  // 현재 nurse_call 상태 사용

    String requestBody;
    serializeJson(doc, requestBody);

    int httpResponseCode = http.POST(requestBody);

    if (httpResponseCode == 200) {
      Serial.printf("✅ 로드셀 %d: DynamoDB 업로드 성공!\n", loadcell_id);
    } else {
      String responseBody = http.getString();
      Serial.printf("❌ 로드셀 %d: DynamoDB 업로드 실패 (HTTP 코드: %d)\n", loadcell_id, httpResponseCode);
      Serial.printf("   AWS 응답: %s\n", responseBody.c_str());
    }

    http.end();
  } else {
    Serial.printf("⚠️ 로드셀 %d: Wi-Fi 연결이 끊어져 업로드 불가\n", loadcell_id);
  }
}

// ===== pole_stat 업로드 함수 개선 (tare_requested를 인자로 받음) =====
void uploadPoleStatTest(bool lost_status, int battery, bool tare_requested) {
    if (WiFi.status() == WL_CONNECTED) {
        WiFiClientSecure client;
        client.setInsecure();
        HTTPClient http;
        http.begin(client, "https://tln54ai1oi.execute-api.ap-northeast-2.amazonaws.com/v1/data");
        http.addHeader("Content-Type", "application/json");
        http.addHeader("x-api-key", "NfM1X8S5xk72BrGbFqr1t9CMtzxMaeKe7PFatzaC"); // 여기에 실제 API 키 입력
        JsonDocument doc;
        doc["pole_id"] = "1";
        doc["is_lost"] = lost_status;
        doc["battery_level"] = battery;
        doc["tare_requested"] = tare_requested;
        String requestBody;
        serializeJson(doc, requestBody);
        int httpResponseCode = http.PATCH(requestBody); // PATCH로 수정
        if (httpResponseCode == 200) {
            Serial.println("✅ pole_stat 업로드 성공!");
        } else {
            Serial.printf("❌ 업로드 실패 (HTTP 코드: %d)\n", httpResponseCode);
            Serial.println(http.getString());
        }
        http.end();
    } else {
        Serial.println("⚠️ Wi-Fi 연결 안됨");
    }
}

// ===== nurse_call 업로드 함수 =====
void uploadNurseCall() {
    if (WiFi.status() == WL_CONNECTED) {
        WiFiClientSecure client;
        client.setInsecure();

        HTTPClient http;
        http.begin(client, API_GATEWAY_URL);
        http.addHeader("Content-Type", "application/json");
        http.addHeader("x-api-key", "NfM1X8S5xk72BrGbFqr1t9CMtzxMaeKe7PFatzaC"); // 여기에 실제 API 키 입력

        // 현재 무게 데이터 가져오기
        float current_weight = (data_index_1 > 0) ? ema_data_1[data_index_1 - 1] : 0;
        if (current_weight < 0) current_weight = 0;

        JsonDocument doc;
        doc["loadcel"] = "1";
        doc["current_weight"] = current_weight;
        doc["remaining_sec"] = -1;
        doc["nurse_call"] = true;

        String requestBody;
        serializeJson(doc, requestBody);

        int httpResponseCode = http.POST(requestBody);

        if (httpResponseCode == 200) {
            Serial.println("✅ nurse_call 업로드 성공!");
        } else {
            Serial.printf("❌ nurse_call 업로드 실패 (HTTP 코드: %d)\n", httpResponseCode);
            Serial.println(http.getString());
        }
        http.end();
    } else {
        Serial.println("⚠️ Wi-Fi 연결 안됨");
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
    // 1. HX711 상태 확인
    if (!scale.is_ready()) {
        Serial.printf("❌ 로드셀 %d: HX711 응답 없음\n", loadcell_id);
        return;
    }

    // 2. 측정
    float raw = scale.get_units();
    float corrected = (raw * slope) + intercept;

    // 3. 하이브리드 필터 적용
    HybridFilter& current_filter = (loadcell_id == 1) ? filter1 : filter1;
    float filtered_value = current_filter.filter(corrected);

    // 4. FIFO 버퍼에 데이터 저장
    if (data_index < max_data) {
        ema_data[data_index] = filtered_value;
        data_index++;
    } else {
        for (int i = 1; i < max_data; i++) {
            ema_data[i - 1] = ema_data[i];
        }
        ema_data[max_data - 1] = filtered_value;
    }

    // 5. 예측 및 업로드
    if (data_index < 2) {
        Serial.printf("⏳ 로드셀 %d: 데이터 부족으로 예측 불가\n", loadcell_id);
        return;
    }

    // 최근 30개 포인트만 사용 (3초간 데이터)
    int recent_count = min(30, data_index);
    float slope_estimate = compute_slope(ema_data, data_index - recent_count, recent_count, delay_interval / 1000.0);
    
    // 디버깅: 기울기 계산 확인
    Serial.printf("🔍 디버깅: 최근 %d개 데이터, 기울기: %.4f g/s\n", recent_count, slope_estimate);

    if (isnan(slope_estimate)) {
        Serial.printf("❌ 로드셀 %d: 기울기 계산 불가 (NaN)\n", loadcell_id);
        return;
    }

    float current_weight = ema_data[data_index - 1];
    if (current_weight < 0) current_weight = 0;

    // === LED 제어 ===
    if (current_weight <= 300) {
        // 깜빡임: 0.5초마다 ON/OFF
        unsigned long now = millis();
        if (now - last_blink_time >= 500) {
            led_state = !led_state;
            digitalWrite(LED_PIN, led_state ? HIGH : LOW);
            last_blink_time = now;
        }
    } else if (current_weight <= 500) {
        // 500g 이하~300g 초과: 항상 ON
        digitalWrite(LED_PIN, HIGH);
        led_state = true;
        last_blink_time = millis(); // 깜빡임 타이머 리셋
    } else {
        // 500g 초과: 항상 OFF
        digitalWrite(LED_PIN, LOW);
        led_state = false;
        last_blink_time = millis(); // 깜빡임 타이머 리셋
    }

    // === 오버뷰 방식의 단순 남은 시간 계산 ===
    simple_remaining_sec = (current_weight > 0) ? (current_weight / 250.0f) * 3600.0f : -1;

    // // 기존 회귀 기반 예측 코드 (주석처리)
    // if (abs(slope_estimate) < 0.001) {
    //     Serial.printf("⚠️ 로드셀 %d: 변화량 작아 예측 불가 (무게만 업로드)\n", loadcell_id);
    //     Serial.printf("로드셀 %d의 무게: %.2f g\n", loadcell_id, current_weight);
    //     uploadToDynamoDB(loadcell_id, current_weight, -1);
    //     return;
    // }
    // float remaining_time = -1;
    // if (slope_estimate > 0.001) {  // 양수 기울기일 때 계산 (임시)
    //   remaining_time = current_weight / slope_estimate;
    // }
    // Serial.printf("📦 로드셀 %d | 📉 기울기: %.4f g/s | 무게: %.2f g | 남은 시간: %.1f 초\n",
    //               loadcell_id, slope_estimate, current_weight, remaining_time);
    // uploadToDynamoDB(loadcell_id, current_weight, remaining_time);

    // === 오버뷰 방식으로 서버 업로드 ===
    Serial.printf("📦 로드셀 %d | 무게: %.2f g | (단순계산) 남은 시간: %.1f 초\n", loadcell_id, current_weight, simple_remaining_sec);
    uploadToDynamoDB(loadcell_id, current_weight, simple_remaining_sec);
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
  
  Serial.println("HX711 로드셀 1개 초기화 중...");
  
  // ✅ HX711 우선 초기화 (test 코드와 동일한 순서)
  scale1.begin(DOUT1, CLK1);
  scale1.set_scale(calibration_factor);
  scale1.tare();
  Serial.println("로드셀 1 영점 보정 완료.");

  // Nextion 디스플레이 초기화 (HX711 초기화 후)
  Serial2.begin(9600, SERIAL_8N1, RXD2, TXD2);
  
  // Nextion 디스플레이 초기 정보 설정
  sendCommand("t_esp.txt=\"연결됨\"");
  
  // NTP 서버 설정 (백그라운드에서)
  configTime(9 * 3600, 0, "pool.ntp.org", "time.nist.gov");
  
  // 시간 동기화 대기 (최대 10초)
  Serial.print("시간 동기화 중");
  int timeout = 0;
  while (time(nullptr) < 24 * 3600 && timeout < 20) {
    delay(500);
    Serial.print(".");
    timeout++;
  }
  Serial.println();
  
  // 실제 시간으로 초기 설정
  time_t now;
  struct tm timeinfo;
  time(&now);
  localtime_r(&now, &timeinfo);
  
  if (timeinfo.tm_year >= (2024 - 1900)) {
    // 날짜 설정 (YYYY-MM-DD 형식)
    char dateBuf[11];
    sprintf(dateBuf, "%04d-%02d-%02d", 
            timeinfo.tm_year + 1900, 
            timeinfo.tm_mon + 1, 
            timeinfo.tm_mday);
    sendCommand("t_date.txt=\"" + String(dateBuf) + "\"");
    
    // 요일 설정
    const char* days[] = {"일요일", "월요일", "화요일", "수요일", "목요일", "금요일", "토요일"};
    sendCommand("t_day.txt=\"" + String(days[timeinfo.tm_wday]) + "\"");
    
    Serial.printf("✅ 시간 동기화 완료: %s %s\n", dateBuf, days[timeinfo.tm_wday]);
  } else {
    sendCommand("t_date.txt=\"2025-01-01\"");
    sendCommand("t_day.txt=\"수\"");
    Serial.println("⚠️ 시간 동기화 실패, 기본값 사용");
  }

  // 테스트용 pole_stat 업로드 (예: lost 상황, 배터리 85%)
  uploadPoleStatTest(true, 85, false);

  Serial.println("ESP32 실시간 수액 예측 시스템 준비 완료");
  Serial.println("100ms마다 측정 + 하이브리드 필터 + 선형 회귀로 잔여 시간 예측 시작");
  Serial.println("Nextion 디스플레이와 연동됨");
  Serial.println("📦 's' 키를 누르면 측정 중단\n");

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW); // 처음엔 꺼짐
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

  // Nextion 디스플레이 이벤트 확인
  if (Serial2.available()) {
    // 버퍼에 있는 모든 데이터를 읽어서 이벤트 확인
    while (Serial2.available()) {
      int firstByte = Serial2.read();
      
      // 65 (0x65) 이벤트 시작 확인
      if (firstByte == 0x65) {
        // 충분한 데이터가 있는지 확인
        if (Serial2.available() >= 5) {
          int secondByte = Serial2.read();
          int thirdByte = Serial2.read();
          int end1 = Serial2.read();
          int end2 = Serial2.read();
          int end3 = Serial2.read();
          
          // 65 01 03 FF FF FF 이벤트 확인
          if (secondByte == 0x01 && thirdByte == 0x03 && 
              end1 == 0xFF && end2 == 0xFF && end3 == 0xFF) {
            Serial.println("hello");
          }
        }
      }
      
      // 24 (0x24) nurse_call 이벤트 시작 확인
      if (firstByte == 0x24) {
        // 충분한 데이터가 있는지 확인
        if (Serial2.available() >= 5) {
          int secondByte = Serial2.read();
          int thirdByte = Serial2.read();
          int end1 = Serial2.read();
          int end2 = Serial2.read();
          int end3 = Serial2.read();
          
          // 24 00 00 FF FF FF nurse_call 이벤트 확인
          if (secondByte == 0x00 && thirdByte == 0x00 && 
              end1 == 0xFF && end2 == 0xFF && end3 == 0xFF) {
            Serial.println("🚨 nurse_call 버튼이 눌렸습니다!");
            
            // nurse_call 활성화 및 깜빡임 시작
            nurse_call_active = true;
            nurse_blink_start = millis();
            nurse_blink_count = 0;
            nurse_blink_state = false;
            
            // 처음에 텍스트를 검은색으로 설정하여 보이게 함
            sendCommand("t_nurse.pco=0");
            
            // nurse_call 상태 설정 (5분간 유지)
            nurse_call_status = true;
            nurse_call_start_time = millis();
            
            // DynamoDB에 nurse_call 업로드
            uploadNurseCall();
            Serial.printf("🔔 nurse_call_status = %s, 시작 시간: %lu\n", 
                         nurse_call_status ? "true" : "false", nurse_call_start_time);
          }
        }
      }
    }
  }

  // nurse_call 깜빡임 처리
  if (nurse_call_active) {
    unsigned long currentTime = millis();
    unsigned long elapsed = currentTime - nurse_blink_start;
    
    // 1초마다 상태 변경 (깜빡임)
    if (elapsed >= 1000) {
      nurse_blink_state = !nurse_blink_state;
      nurse_blink_start = currentTime;
      nurse_blink_count++;
      
      // pco 값 설정 (검은색 또는 하얀색)
      int pco_value = nurse_blink_state ? 0 : 65535;  // 검은색 ↔ 하얀색 전환
      sendCommand("t_nurse.pco=" + String(pco_value));
      
      Serial.printf("💡 nurse_call 깜빡임 %d/6 (pco: %d)\n", nurse_blink_count, pco_value);
      
      // 6번 깜빡인 후 종료 (3번 깜빡임 = 6번 상태 변경)
      if (nurse_blink_count >= 6) {
        nurse_call_active = false;
        sendCommand("t_nurse.pco=65535");  // 하얀색으로 만들어서 숨기기
        Serial.println("✅ nurse_call 깜빡임 완료");
      }
    }
  }

  // nurse_call 상태 유지 시간 체크
  if (nurse_call_status) {
    unsigned long currentTime = millis();
    if (currentTime - nurse_call_start_time >= NURSE_CALL_DURATION) {
      nurse_call_status = false;
      Serial.printf("⏰ nurse_call 상태 만료 (5분 경과), 경과 시간: %lu ms\n", 
                   currentTime - nurse_call_start_time);
    }
  }

  if (!is_running) return;

  // test 코드와 동일한 구조로 HX711 측정
  process_loadcell_data(1, scale1, ema_previous_1, ema_data_1, data_index_1);

  // Nextion 디스플레이 업데이트 (1초마다)
  unsigned long currentMillis = millis();
  if (currentMillis - lastMillis >= 500) {
    lastMillis = currentMillis;
    
    float current_weight = (data_index_1 > 0) ? ema_data_1[data_index_1 - 1] : 0;
    float remaining_time = -1;
    
    if (data_index_1 >= 2) {
      // 최근 30개 포인트만 사용 (3초간 데이터)
      int recent_count = min(30, data_index_1);
      float slope_estimate = compute_slope(ema_data_1, data_index_1 - recent_count, recent_count, delay_interval / 1000.0);
      if (!isnan(slope_estimate) && slope_estimate < -0.001) {  // 음수 기울기일 때만
        remaining_time = current_weight / abs(slope_estimate);
      }
    }
    
    // 실제 시간 가져오기
    time_t now;
    struct tm timeinfo;
    time(&now);
    localtime_r(&now, &timeinfo);

    // 시간이 유효한지 확인
    if (timeinfo.tm_year >= (2024 - 1900)) {
      char timeBuf[9];
      sprintf(timeBuf, "%02d:%02d:%02d", timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec);
      sendCommand("t_time.txt=\"" + String(timeBuf) + "\"");
    } else {
      sendCommand("t_time.txt=\"--:--:--\"");
    }

    // 왼쪽은 비어있음 표시 (사용하지 않음)
    // sendCommand("t_wgt_L.txt=\"비어있음\"");
    // sendCommand("t_rem_L.txt=\"--:--\"");
    
    // 오른쪽에만 실제 측정된 무게 표시
    if (current_weight < 0) current_weight = 0;
    int weightR = max(0, (int)current_weight);
    sendCommand("t_wgt_R.txt=\"" + String(weightR) + "g\"");

    // === [추가] 오른쪽 프로그레스바 값 계산 및 전송 ===
    int min_weight = 100;
    int max_weight = 1000;
    int progressR = 0;
    if (weightR <= min_weight) {
        progressR = 0;
    } else if (weightR >= max_weight) {
        progressR = 100;
    } else {
        progressR = (int)(((float)(weightR - min_weight) / (max_weight - min_weight)) * 100);
    }
    sendCommand("pr_wgt_r.val=" + String(progressR));

    // 남은 시간 표시 (0 미만 방지)
    int remSecR = (simple_remaining_sec > 0) ? (int)simple_remaining_sec : 0;
    int remHour = remSecR / 3600;
    int remMin = (remSecR % 3600) / 60;
    char remRBuf[6];
    sprintf(remRBuf, "%02d:%02d", remHour, remMin);
    
    // 디버깅: 남은 시간 계산 확인
    Serial.printf("🔍 디버깅: simple_remaining_sec=%.1f, remSecR=%d, remHour=%d, remMin=%d, remRBuf='%s'\n", 
                  simple_remaining_sec, remSecR, remHour, remMin, remRBuf);
    
    sendCommand("t_rem_R.txt=\"" + String(remRBuf) + "\"");

    // 기타 정보 고정 전송
    int battery = 78;
    String espStatus = (WiFi.status() == WL_CONNECTED) ? "신호 연결 양호" : "신호 연결 불량";
    // String typeL = "비어있음", typeR = "수액";  // 왼쪽은 사용하지 않음

    sendCommand("t_bat.txt=\"" + String(battery) + "%\"");
    sendCommand("t_esp.txt=\"" + espStatus + "\"");
    // sendCommand("t_type_L.txt=\"" + typeL + "\"");  // 왼쪽은 사용하지 않음
    // sendCommand("t_type_R.txt=\"\"");
  }

  delay(delay_interval);
}