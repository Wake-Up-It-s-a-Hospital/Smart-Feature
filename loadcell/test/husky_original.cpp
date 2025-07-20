#include <Wire.h>
//#define HUSKYLENS_SLAVE_I2C
#include "HUSKYLENS.h"
#include <HardwareSerial.h>

HUSKYLENS huskylens;

// STM32와 연결된 UART2 (GPIO 16 RX, GPIO 17 TX)
HardwareSerial stm32Serial(2);


//허스키 관련 변수
const int centerX = 160;         // 화면 중심 x 좌표
int tx_buf = 0;                 // 왼쪽 -90 <<<<<<<>>>>>>>>  +90 오른쪽 으로 각도 변경을 위한 변환  tx_buf = -(angle_offset);
unsigned long previousMillis = 0; // millis 함수 저장 변수



//통신 문자열
char str_int[4]; 
char tx_int[5];



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
}

void loop() 
{

  //////////////////////////// //////////////////////////////
  ///////////   허스키렌즈 x 값 받아오는 Logic //////////////
  ///////////////////////////////////////////////////////////
  unsigned long currentMillis = millis();

  if (currentMillis - previousMillis >= 100)  // 100ms 주기
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
            int leftAngle = ((x * 70) + 160) / 320;
            int txBuf = leftAngle;

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
  ///////////////////////////////////////////////////////////


  // 다른 비동기 처리 구문
}
