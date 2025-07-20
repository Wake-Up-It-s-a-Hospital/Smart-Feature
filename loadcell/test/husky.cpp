#include <Wire.h>
//#define HUSKYLENS_SLAVE_I2C
#include "HUSKYLENS.h"  // 허스키렌즈 라이브러리 주석 처리
#include <HardwareSerial.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#define API_GATEWAY_URL "https://tln54ai1oi.execute-api.ap-northeast-2.amazonaws.com/v1/data"

HUSKYLENS huskylens;

// STM32와 연결된 UART2 (GPIO 16 RX, GPIO 17 TX)
HardwareSerial stm32Serial(2);

//허스키 관련 변수
const int centerX = 160;         // 화면 중심 x 좌표
int tx_buf = 0;                 // 왼쪽 -90 <<<<<<<>>>>>>>>  +90 오른쪽 으로 각도 변경을 위한 변환  tx_buf = -(angle_offset);
unsigned long previousMillis = 0; // millis 함수 저장 변수

// 배터리 관련 변수 (추가)
char batteryLevel = '0';  // 기본값 0
char lastBatteryLevel = '0';  // 이전 배터리 값 (추가)
unsigned long lastUploadTime = 0;  // 마지막 업로드 시간

//통신 문자열
char str_int[4]; 
char tx_int[5];

void uploadBatteryToDynamoDB(const char* battery) {
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClientSecure client;
    client.setInsecure(); 
    HTTPClient http;
    http.begin(client, API_GATEWAY_URL);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("x-api-key", "NfM1X8S5xk72BrGbFqr1t9CMtzxMaeKe7PFatzaC");

    int battery_level = atoi(battery);  // 문자열을 int로 변환

    StaticJsonDocument<128> doc;
    doc["pole_id"] = "1";
    doc["battery_level"] = battery_level;

    String requestBody;
    serializeJson(doc, requestBody);

    int httpResponseCode = http.POST(requestBody);

    if (httpResponseCode == 200) {
      Serial.println("✅ 배터리 상태 업로드 성공!");
    } else {
      Serial.printf("❌ 업로드 실패 (HTTP 코드: %d)\n", httpResponseCode);
      Serial.println(http.getString());
    }
    http.end();
  } else {
    Serial.println("⚠️ Wi-Fi 연결 안됨");
  }
}

#define WIFI_SSID "iPhone"
#define WIFI_PASSWORD "aksiaksi"

void connectToWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Wi-Fi 연결 중");
  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < 30) { // 최대 15초 대기
    delay(500);
    Serial.print(".");
    retry++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ Wi-Fi 연결 성공");
    Serial.print("IP 주소: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n❌ Wi-Fi 연결 실패! SSID/PW 확인");
  }
}

void setup() 
{
  Serial.begin(115200);                   // PC용 시리얼
  Wire.begin(21, 22);                     // I2C SDA, SCL
  huskylens.begin(Wire);                 // HuskyLens I2C 초기화

  stm32Serial.begin(9600, SERIAL_8N1, 16, 17); // STM32와 UART2 통신 시작

  // HuskyLens 연결 확인
  bool connected = false;
  for (int i = 0; i < 5; i++) 
  {
    if (huskylens.request()) 
    {
      connected = true;
      break;
    }
    Serial.println("HuskyLens 연결 시도 중...");
    delay(500);
  }

  if (!connected) 
  {
    Serial.println("HuskyLens 연결 실패");
    while (1);
  } 
  else 
  {
    Serial.println("HuskyLens 연결 성공");
  }

  huskylens.writeAlgorithm(ALGORITHM_TAG_RECOGNITION);  // 태그 인식 모드 진입
  
  connectToWiFi();
}

void loop() 
{
  //////////////////////////// //////////////////////////////
  ///////////   허스키렌즈 x 값 받아오는 Logic //////////////
  ///////////////////////////////////////////////////////////
  unsigned long currentMillis = millis();

  if (currentMillis - previousMillis >= 100)
  {
    previousMillis = currentMillis;

    if (huskylens.request()) //허스키렌즈 값 요청
    {
        bool id1Found = false;
        int x = 0;

        while (huskylens.available()) 
        {
            HUSKYLENSResult result = huskylens.read();

            if (result.ID == 1)  // ID 1만 처리
            {
                x = result.xCenter;
                id1Found = true;
                break;  // ID 1 찾았으니 종료
            }
        }

        if (id1Found)
        {
            int rightAngle = ((x * 70) + 160) / 320;
            int txBuf = rightAngle;

            char strInt[4];
            char txInt[5];
            sprintf(strInt, "%03d", txBuf);
            sprintf(txInt, "%s/", strInt);

            stm32Serial.print(txInt);
            Serial.print("ID 1 x: ");
            Serial.println(x);
        }
        else
        {
            stm32Serial.print("999/");
            Serial.println("ID 1 태그 인식되지 않음");
        }
    }
    else 
    {
        Serial.println("요청 실패 — 통신 문제");
    }
  }
  
  //////////////////////////// //////////////////////////////
  ///////////             STM32 UART           //////////////
  ///////////////////////////////////////////////////////////
  int rx_data_flag = 0;
  if (stm32Serial.available()) {     // STM32에서 배터리 데이터 수신 (형식: "3\0")
      rx_data_flag = 1;
      char incomingByte = stm32Serial.read();
      
      // 숫자만 받기 (0,1,2,3) - 널문자(\0)는 무시
      if (incomingByte >= '0' && incomingByte <= '3') {
          batteryLevel = incomingByte;
          Serial.printf("배터리 레벨 수신: %c (%.0f%%)\n", batteryLevel, (batteryLevel - '0') * 25.0); // (디버그)
      }
      // 널문자(\0)는 무시하고 숫자만 처리
      else if (incomingByte == '\0') {
          Serial.println("널문자 수신됨 (무시)");
      }
      else {
          Serial.printf("기타 데이터 수신(오류!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!): %d\n", incomingByte);
      }
  }
  
  // 배터리 값이 변경되거나 10초마다 업로드 (지연 문제 해결)
  if ((batteryLevel != lastBatteryLevel) || (currentMillis - lastUploadTime >= 10000)) {
      if (batteryLevel != lastBatteryLevel) {
          Serial.printf("배터리 값 변경 감지: %c → %c\n", lastBatteryLevel, batteryLevel);
          lastBatteryLevel = batteryLevel;
      }
      lastUploadTime = currentMillis;
      char batteryStr[2] = {batteryLevel, '\0'};
      uploadBatteryToDynamoDB(batteryStr);
  }

  // 다른 비동기 처리 구문
}
