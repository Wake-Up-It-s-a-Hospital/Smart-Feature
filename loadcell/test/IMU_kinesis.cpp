/* 
 * IMU 기반 세계좌표 위치 추정을 위한 STM32 코드
 * 
 * 기능:
 * 1. 6축 IMU(가속도계 + 자이로스코프)로 환자의 상대좌표 계산
 * 2. 허스키렌즈와 IMU를 동기화하여 전방 방향 학습
 * 3. 환자의 각도에 관계없이 항상 등 뒤 80cm 거리 유지
 * 4. 허스키렌즈 로스트 시 IMU만으로 예측 추적
 * 
 * 동작 원리:
 * - 환자에게 부착된 IMU의 가속도 데이터를 이중적분하여 위치 추정
 * - 허스키렌즈가 정상일 때는 각도 기반 추적 + 전방 방향 학습
 * - 허스키렌즈 로스트 시 학습된 전방 방향으로 예측 추적
 */

// STM32 HAL 라이브러리 헤더 파일들
#include "main.h"      // STM32 메인 설정
#include "tim.h"       // 타이머 인터페이스
#include "usart.h"     // UART 통신 인터페이스
#include "gpio.h"      // GPIO 제어 인터페이스

// C 표준 라이브러리 헤더 파일들
#include <math.h>      // 수학 함수 (sin, cos, atan2 등)
#include <string.h>    // 문자열 처리 함수
#include <stdio.h>     // printf, sprintf 함수

// 수학 상수 정의
#define PI 3.1415926535                    // 원주율
#define DEG_TO_RAD (PI / 180.0)           // 도를 라디안으로 변환
#define RAD_TO_DEG (180.0 / PI)           // 라디안을 도로 변환

// 시스템 타이밍 설정
#define DT 0.01                            // 시간 간격 (100Hz = 10ms)
#define G 9.81f                           // 중력 가속도 (m/s²)

// 버퍼 크기 설정
#define RX_BUF_SIZE 128                   // UART 수신 버퍼 크기

// 상태 전환 타이머 설정
#define LOST_TIMEOUT 1000                 // 로스트 상태 타임아웃 (1초)
#define PREDICTION_TIMEOUT 100            // 예측 상태 타임아웃 (0.1초)

// 보완 필터 파라미터 (6축 IMU용)
#define ALPHA 0.98f                       // 자이로스코프 가중치 (높은 주파수 신호)
#define BETA 0.02f                        // 가속도계 가중치 (낮은 주파수 신호)

// 외부 UART 핸들러 선언 (main.c에서 정의됨)
extern UART_HandleTypeDef huart3;         // IMU 데이터 수신용 UART
extern UART_HandleTypeDef huart2;         // 허스키렌즈 각도 수신용 UART

// 추적 시스템 상태 정의
typedef enum {
    STATE_IDLE,                           // 초기 대기 상태 (시스템 시작)
    STATE_NORMAL,                         // 정상 추적 상태 (허스키렌즈 + IMU)
    STATE_PREDICTION,                     // 예측 추적 상태 (IMU만 사용)
    STATE_LOST,                           // 추적 실패 상태 (안전 정지)
    STATE_SYNC                            // 초기 동기화 상태 (IMU 데이터 대기)
} TrackingState;

// 현재 추적 상태 변수
TrackingState tracking_state = STATE_IDLE;

// IMU 데이터 수신을 위한 UART 버퍼
uint8_t rx_byte;                          // 1바이트 수신 버퍼
char rx_buf[RX_BUF_SIZE];                 // 문자열 수신 버퍼
uint8_t rx_index = 0;                     // 버퍼 인덱스
volatile uint8_t rx_flag = 0;             // 수신 완료 플래그

// 허스키렌즈 각도 수신을 위한 UART 버퍼
char husky_buf[16];                       // 허스키렌즈 데이터 버퍼
uint8_t husky_index = 0;                  // 버퍼 인덱스
volatile uint8_t husky_flag = 0;          // 수신 완료 플래그
int husky_angle = 0;                      // 허스키렌즈에서 받은 각도 (도)

// 6축 IMU 데이터 구조체 정의
typedef struct {
    float ax, ay, az;                     // 가속도계 데이터 (X, Y, Z축, m/s²)
    float gx, gy, gz;                     // 자이로스코프 데이터 (X, Y, Z축, deg/s)
    uint32_t timestamp;                   // 타임스탬프 (밀리초)
} IMU_Data;

// IMU 데이터 저장 변수
IMU_Data imu_data;

// IMU 좌표 버퍼 설정 (최근 5개 위치 데이터 저장)
#define IMU_BUFFER_SIZE 5                 // 버퍼 크기

// IMU 좌표 데이터 구조체
typedef struct {
    float x, y;                           // XY 평면 좌표 (미터)
    float direction;                      // 이동 방향 (라디안)
    uint32_t timestamp;                   // 타임스탬프
} IMU_Coordinate;

// IMU 좌표 버퍼 배열
IMU_Coordinate imu_buffer[IMU_BUFFER_SIZE];
uint8_t imu_buffer_index = 0;             // 현재 버퍼 인덱스
uint8_t imu_buffer_count = 0;             // 저장된 데이터 개수

// 전방 방향 학습 관련 변수
float learned_front_direction = 0.0f;     // 학습된 전방 방향 (라디안)
uint8_t front_direction_learned = 0;      // 전방 방향 학습 완료 여부
float front_learning_confidence = 0.0f;   // 학습 신뢰도 (0.0 ~ 1.0)

// 보완 필터를 위한 오일러 각도 변수
float roll = 0, pitch = 0, yaw = 0;       // 현재 오일러 각도 (도)
float roll_acc = 0, pitch_acc = 0;        // 가속도계로 계산한 각도
float roll_gyro = 0, pitch_gyro = 0, yaw_gyro = 0;  // 자이로스코프 적분 각도

// 환자의 속도 및 위치 추정 변수
float vx = 0, vy = 0, vz = 0;             // 환자의 속도 (X, Y, Z축, m/s)
float px = 0, py = 0, pz = 0;             // 환자의 위치 (X, Y, Z축, 미터)

// 환자 추적 관련 변수
float patient_direction = 0;              // 환자의 진행 방향 (라디안)
float patient_speed = 0;                  // 환자의 속도 (m/s)
float pole_to_patient_distance = 1.0f;    // 폴대와 환자 간 목표 거리 (미터)

// 상태 관리 변수
uint32_t lost_timer = 0;                  // 로스트 상태 타이머
uint32_t prediction_timer = 0;            // 예측 상태 타이머
uint8_t sync_complete = 0;                // 동기화 완료 플래그
uint8_t husky_lost = 0;                   // 허스키렌즈 로스트 상태 플래그

// 저역통과 필터를 위한 변수 (노이즈 제거용)
float filtered_ax = 0, filtered_ay = 0, filtered_az = 0;  // 필터링된 가속도
float filtered_gx = 0, filtered_gy = 0, filtered_gz = 0;  // 필터링된 자이로스코프
const float alpha = 0.1f;                 // 저역통과 필터 계수

// 모터 제어 변수 (기존 STM32 코드와 통합)
float K_v = 2.0f;                         // 선속도 제어 게인
float K_w = 2.0f;                         // 각속도 제어 게인
float target_distance = 0.8f;             // 목표 거리 (80cm)
float target_angle = 0.0f;                // 목표 각도

/*
 * 6축 IMU용 보완 필터 함수
 * 
 * 매개변수:
 * - ax, ay, az: 가속도계 데이터 (m/s²)
 * - gx, gy, gz: 자이로스코프 데이터 (deg/s)
 * 
 * 동작 원리:
 * - 자이로스코프: 높은 주파수 신호 (빠른 변화 감지)
 * - 가속도계: 낮은 주파수 신호 (중력 기반 각도)
 * - 두 신호를 가중 평균하여 드리프트 보정
 */
void complementary_filter(float ax, float ay, float az, float gx, float gy, float gz) {
    // 가속도계로부터의 각도 계산 (중력 기반)
    roll_acc = atan2f(ay, sqrtf(ax * ax + az * az)) * RAD_TO_DEG;   // Roll 각도
    pitch_acc = atan2f(-ax, sqrtf(ay * ay + az * az)) * RAD_TO_DEG; // Pitch 각도
    
    // 자이로스코프 적분 (라디안/초를 도/초로 변환)
    roll_gyro += gx * DT;   // Roll 각도 적분
    pitch_gyro += gy * DT;  // Pitch 각도 적분
    yaw_gyro += gz * DT;    // Yaw 각도 적분
    
    // 보완 필터 적용 (가중 평균)
    roll = ALPHA * (roll + gx * DT) + BETA * roll_acc;   // Roll 보완 필터
    pitch = ALPHA * (pitch + gy * DT) + BETA * pitch_acc; // Pitch 보완 필터
    yaw = yaw_gyro;  // Yaw는 자이로스코프만 사용 (드리프트 있음)
    
    // 각도 정규화 (-180° ~ +180°)
    while (yaw > 180.0f) yaw -= 360.0f;
    while (yaw < -180.0f) yaw += 360.0f;
}

/*
 * UART 수신 완료 콜백 함수
 * 
 * 매개변수:
 * - huart: UART 핸들러
 * 
 * 동작:
 * 1. IMU 데이터 수신 (USART3)
 * 2. 허스키렌즈 각도 수신 (USART2)
 * 3. 수신 완료 시 플래그 설정
 */
void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
    // IMU 데이터 수신 처리 (USART3)
    if (huart->Instance == USART3) {
        if (rx_byte == '\n') {  // 줄바꿈 문자로 데이터 끝 확인
            rx_buf[rx_index] = '\0';  // 문자열 종료
            rx_flag = 1;              // 수신 완료 플래그 설정
            rx_index = 0;             // 인덱스 초기화
        } else {
            // 버퍼에 문자 저장
            if (rx_index < RX_BUF_SIZE - 1) {
                rx_buf[rx_index++] = rx_byte;
            } else {
                rx_index = 0;  // 버퍼 오버플로우 방지
            }
        }
        // 다음 바이트 수신 대기
        HAL_UART_Receive_IT(&huart3, &rx_byte, 1);
    }
    
    // 허스키렌즈 각도 수신 처리 (USART2)
    if (huart->Instance == USART2) {
        if (rx_byte == '/') {  // '/' 문자로 데이터 끝 확인
            husky_buf[husky_index] = rx_byte;
            husky_buf[husky_index + 1] = '\0';  // 문자열 종료
            husky_flag = 1;                     // 수신 완료 플래그 설정
            husky_index = 0;                    // 인덱스 초기화
            husky_lost = 0;                     // 로스트 상태 해제
        } else {
            // 버퍼에 문자 저장
            if (husky_index < 15) {
                husky_buf[husky_index++] = rx_byte;
            } else {
                husky_index = 0;  // 버퍼 오버플로우 방지
            }
        }
        // 다음 바이트 수신 대기
        HAL_UART_Receive_IT(&huart2, &rx_byte, 1);
    }
}

/*
 * IMU 데이터 파싱 함수
 * 
 * 매개변수:
 * - buf: 수신된 문자열 버퍼
 * - data: 파싱된 IMU 데이터를 저장할 구조체 포인터
 * 
 * 데이터 형식: "$AX,AY,AZ,GX,GY,GZ,TIMESTAMP"
 * 예시: "$1.23,-0.45,9.81,0.12,-0.34,0.56,1234567"
 */
void parse_imu_data(const char* buf, IMU_Data* data) {
    // 6축 IMU 입력 파싱: $AX,AY,AZ,GX,GY,GZ,TIMESTAMP
    sscanf(buf, "$%f,%f,%f,%f,%f,%f,%lu", 
           &data->ax, &data->ay, &data->az,      // 가속도계 (X, Y, Z)
           &data->gx, &data->gy, &data->gz,      // 자이로스코프 (X, Y, Z)
           &data->timestamp);                     // 타임스탬프
}

/*
 * 허스키렌즈 데이터 파싱 함수
 * 
 * 매개변수:
 * - buf: 수신된 문자열 버퍼
 * - angle: 파싱된 각도를 저장할 변수 포인터
 * 
 * 데이터 형식: "45/"
 * 예시: "45/" (45도)
 */
void parse_husky_data(const char* buf, int* angle) {
    // 허스키렌즈 각도 파싱: "45/"
    sscanf(buf, "%d/", angle);
}

/*
 * 저역통과 필터 적용 함수 (노이즈 제거)
 * 
 * 매개변수:
 * - raw: 원본 IMU 데이터
 * - filtered: 필터링된 IMU 데이터
 * 
 * 필터 공식: filtered = α * raw + (1-α) * previous_filtered
 */
void apply_low_pass_filter(IMU_Data* raw, IMU_Data* filtered) {
    // 가속도계 데이터 필터링
    filtered->ax = alpha * raw->ax + (1 - alpha) * filtered_ax;
    filtered->ay = alpha * raw->ay + (1 - alpha) * filtered_ay;
    filtered->az = alpha * raw->az + (1 - alpha) * filtered_az;
    
    // 자이로스코프 데이터 필터링
    filtered->gx = alpha * raw->gx + (1 - alpha) * filtered_gx;
    filtered->gy = alpha * raw->gy + (1 - alpha) * filtered_gy;
    filtered->gz = alpha * raw->gz + (1 - alpha) * filtered_gz;
    
    // 필터링된 값 저장 (다음 필터링에 사용)
    filtered_ax = filtered->ax;
    filtered_ay = filtered->ay;
    filtered_az = filtered->az;
    filtered_gx = filtered->gx;
    filtered_gy = filtered->gy;
    filtered_gz = filtered->gz;
}

/*
 * IMU 좌표 버퍼에 새로운 위치 데이터를 추가하는 함수
 * 
 * 매개변수:
 * - x, y: 환자의 XY 좌표 (미터)
 * - direction: 환자의 이동 방향 (라디안)
 * 
 * 동작:
 * - FIFO 방식으로 최근 5개 데이터만 유지
 * - 버퍼가 가득 차면 가장 오래된 데이터를 덮어씀
 */
void add_to_imu_buffer(float x, float y, float direction) {
    // 현재 인덱스에 데이터 저장
    imu_buffer[imu_buffer_index].x = x;
    imu_buffer[imu_buffer_index].y = y;
    imu_buffer[imu_buffer_index].direction = direction;
    imu_buffer[imu_buffer_index].timestamp = HAL_GetTick();  // 현재 시간 저장
    
    // 인덱스를 다음 위치로 이동 (순환 버퍼)
    imu_buffer_index = (imu_buffer_index + 1) % IMU_BUFFER_SIZE;
    
    // 버퍼가 가득 차지 않았으면 카운트 증가
    if (imu_buffer_count < IMU_BUFFER_SIZE) {
        imu_buffer_count++;
    }
}

/*
 * 전방 방향 학습 함수 (STATE_NORMAL에서 실행)
 * 
 * 동작 원리:
 * 1. IMU로 계산한 환자의 이동 방향과 허스키렌즈 각도를 비교
 * 2. 두 방향이 30도 이내로 일치하면 전방 방향으로 학습
 * 3. 학습 신뢰도는 각도 차이에 따라 계산
 * 
 * 학습 조건:
 * - 최소 3개의 IMU 데이터 필요
 * - 허스키렌즈와 IMU 방향 차이가 30도 이내
 */
void learn_front_direction() {
    // 최소 3개 데이터가 없으면 학습 불가
    if (imu_buffer_count < 3) return;
    
    // 최근 3개 데이터의 평균 방향 계산
    float sum_direction = 0.0f;
    int valid_count = 0;
    
    // 최근 3개 데이터를 역순으로 접근
    for (int i = 0; i < imu_buffer_count && i < 3; i++) {
        // 순환 버퍼에서 올바른 인덱스 계산
        int idx = (imu_buffer_index - 1 - i + IMU_BUFFER_SIZE) % IMU_BUFFER_SIZE;
        
        // 유효한 방향 데이터만 사용
        if (imu_buffer[idx].direction != 0.0f) {
            sum_direction += imu_buffer[idx].direction;
            valid_count++;
        }
    }
    
    // 최소 2개 이상의 유효한 데이터가 있을 때만 학습
    if (valid_count >= 2) {
        float avg_direction = sum_direction / valid_count;  // 평균 방향 계산
        
        // 허스키렌즈 각도를 라디안으로 변환
        float husky_rad = husky_angle * DEG_TO_RAD;
        
        // IMU 방향과 허스키렌즈 방향의 차이 계산
        float direction_diff = fabsf(avg_direction - husky_rad);
        
        // 각도 차이가 30도 이내일 때만 학습 (신뢰할 수 있는 데이터)
        if (direction_diff < 30.0f * DEG_TO_RAD) {
            learned_front_direction = avg_direction;  // 전방 방향 학습
            front_direction_learned = 1;              // 학습 완료 플래그 설정
            front_learning_confidence = 1.0f - (direction_diff / (30.0f * DEG_TO_RAD));  // 신뢰도 계산
            
            // 디버그 메시지 출력
            char debug_msg[128];
            sprintf(debug_msg, "Front_Learned:%.1f Conf:%.2f\n", 
                    learned_front_direction * RAD_TO_DEG, front_learning_confidence);
            HAL_UART_Transmit(&huart3, (uint8_t*)debug_msg, strlen(debug_msg), 100);
        }
    }
}

/*
 * 예측 모드에서 환자 등 뒤 80cm 위치를 계산하는 함수
 * 
 * 매개변수:
 * - target_x, target_y: 계산된 목표 위치 (포인터)
 * 
 * 동작:
 * 1. 전방 방향이 학습되었으면 학습된 방향 사용
 * 2. 학습되지 않았으면 현재 환자 진행 방향 사용
 * 3. 환자 등 뒤 80cm 위치를 계산
 */
void calculate_prediction_target(float* target_x, float* target_y) {
    // 전방 방향이 학습되지 않았으면 기본 방향 사용
    if (!front_direction_learned) {
        *target_x = px + 0.8f * cosf(patient_direction + PI);  // 환자 진행 방향 반대
        *target_y = py + 0.8f * sinf(patient_direction + PI);
        return;
    }
    
    // 학습된 전방 방향을 기반으로 환자 등 뒤 80cm 위치 계산
    float behind_direction = learned_front_direction + PI;  // 전방 반대 방향 (등 뒤)
    
    // 환자의 현재 위치에서 80cm 뒤로 이동한 위치 계산
    *target_x = px + 0.8f * cosf(behind_direction);
    *target_y = py + 0.8f * sinf(behind_direction);
    
    // 디버그 메시지 출력
    char debug_msg[128];
    sprintf(debug_msg, "Pred_Target:%.3f,%.3f Front:%.1f\n", 
            *target_x, *target_y, learned_front_direction * RAD_TO_DEG);
    HAL_UART_Transmit(&huart3, (uint8_t*)debug_msg, strlen(debug_msg), 100);
}

/*
 * 환자의 움직임을 업데이트하는 핵심 함수
 * 
 * 동작 과정:
 * 1. 6축 IMU 데이터에 보완 필터 적용
 * 2. 완전한 회전행렬 계산
 * 3. 센서 좌표계를 세계좌표계로 변환
 * 4. 중력 보정
 * 5. 이중적분으로 위치 계산
 * 6. 환자의 진행 방향과 속도 계산
 */
void update_motion() {
    // 1단계: 6축 IMU 데이터에 보완 필터 적용 (Roll, Pitch, Yaw 계산)
    complementary_filter(imu_data.ax, imu_data.ay, imu_data.az,
                        imu_data.gx, imu_data.gy, imu_data.gz);
    
    // 2단계: 오일러 각도를 라디안으로 변환
    float roll_rad = roll * DEG_TO_RAD;    // Roll 각도 (라디안)
    float pitch_rad = pitch * DEG_TO_RAD;  // Pitch 각도 (라디안)
    float yaw_rad = yaw * DEG_TO_RAD;      // Yaw 각도 (라디안)
    
    // 3단계: 완전한 회전행렬 계산 (ZYX 순서: Yaw → Pitch → Roll)
    // R = Rz(ψ) * Ry(θ) * Rx(φ)
    
    // 각 축의 삼각함수 값 미리 계산 (성능 최적화)
    float cr = cosf(roll_rad), sr = sinf(roll_rad);    // Roll 삼각함수
    float cp = cosf(pitch_rad), sp = sinf(pitch_rad);  // Pitch 삼각함수
    float cy = cosf(yaw_rad), sy = sinf(yaw_rad);      // Yaw 삼각함수
    
    // 4단계: 회전행렬 R[3][3] 계산 (ZYX 순서)
    float R[3][3] = {
        {cp * cy, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr},  // 첫 번째 행
        {cp * sy, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr},  // 두 번째 행
        {  -sp  ,           cp * sr     ,           cp * cr     }   // 세 번째 행
    };
    
    // 5단계: 센서 좌표계의 가속도를 세계좌표계로 변환
    float ax_sensor = imu_data.ax;  // 센서 X축 가속도
    float ay_sensor = imu_data.ay;  // 센서 Y축 가속도
    float az_sensor = imu_data.az;  // 센서 Z축 가속도
    
    // 회전행렬 적용: a_world = R * a_sensor (행렬 곱셈)
    float ax_world = R[0][0] * ax_sensor + R[0][1] * ay_sensor + R[0][2] * az_sensor;
    float ay_world = R[1][0] * ax_sensor + R[1][1] * ay_sensor + R[1][2] * az_sensor;
    float az_world = R[2][0] * ax_sensor + R[2][1] * ay_sensor + R[2][2] * az_sensor;
    
    // 6단계: 중력 벡터 [0, 0, -9.81] 제거 (중력 보정)
    float ax_gravity_free = ax_world;      // X축은 중력 영향 없음
    float ay_gravity_free = ay_world;      // Y축은 중력 영향 없음
    float az_gravity_free = az_world - G;  // Z축에서 중력 제거
    
    // 7단계: 속도 적분 (이중적분의 첫 번째 단계)
    vx += ax_gravity_free * DT;  // X축 속도 적분
    vy += ay_gravity_free * DT;  // Y축 속도 적분
    vz += az_gravity_free * DT;  // Z축 속도 적분
    
    // 8단계: 위치 적분 (이중적분의 두 번째 단계)
    px += vx * DT;  // X축 위치 적분
    py += vy * DT;  // Y축 위치 적분
    pz += vz * DT;  // Z축 위치 적분
    
    // 9단계: XY 평면 위의 위치만 사용 (Z축 무시)
    // 환자의 진행 방향과 속도 계산 (XY 평면)
    float speed_xy = sqrtf(vx * vx + vy * vy);  // XY 평면 속도 크기
    
    // 최소 속도 임계값 (0.1 m/s) 이상일 때만 방향 계산
    if (speed_xy > 0.1f) {
        patient_direction = atan2f(vy, vx);  // 환자의 진행 방향 (라디안)
        patient_speed = speed_xy;            // 환자의 속도 (m/s)
        
        // IMU 버퍼에 현재 위치와 방향 저장 (전방 학습용)
        add_to_imu_buffer(px, py, patient_direction);
    }
    
    // 10단계: 디버그 출력 (XY 평면 좌표)
    char debug_msg[128];
    sprintf(debug_msg, "XY_Pos:%.3f,%.3f Speed:%.3f Dir:%.1f\n", 
            px, py, speed_xy, patient_direction * RAD_TO_DEG);
    HAL_UART_Transmit(&huart3, (uint8_t*)debug_msg, strlen(debug_msg), 100);
}

/*
 * 폴대의 목표 위치를 계산하는 함수
 * 
 * 매개변수:
 * - target_x, target_y: 계산된 폴대 목표 위치 (포인터)
 * 
 * 동작:
 * 1. STATE_NORMAL: 허스키렌즈 각도 사용 + 전방 방향 학습
 * 2. STATE_PREDICTION: 학습된 전방 방향 기반으로 환자 등 뒤 80cm
 * 3. 기타 상태: 기본 환자 진행 방향 사용
 */
void calculate_pole_target_position(float* target_x, float* target_y) {
    // 상태에 따른 목표 위치 계산
    if (!husky_lost && tracking_state == STATE_NORMAL) {
        // STATE_NORMAL: 허스키렌즈 각도 사용 + 전방 방향 학습
        float husky_rad = husky_angle * DEG_TO_RAD;  // 허스키렌즈 각도를 라디안으로 변환
        
        // 허스키렌즈 각도 방향으로 폴대 위치 계산
        *target_x = px + pole_to_patient_distance * cosf(husky_rad);
        *target_y = py + pole_to_patient_distance * sinf(husky_rad);
        
        // 전방 방향 학습 실행 (IMU와 허스키렌즈 동기화)
        learn_front_direction();
        
    } else if (tracking_state == STATE_PREDICTION) {
        // STATE_PREDICTION: 학습된 전방 방향 기반으로 환자 등 뒤 80cm
        calculate_prediction_target(target_x, target_y);
        
    } else {
        // 기타 상태: 기본 환자 진행 방향 사용
        float behind_angle = patient_direction + PI;  // 환자 반대 방향 (등 뒤)
        
        // 환자 진행 방향 반대로 폴대 위치 계산
        *target_x = px + pole_to_patient_distance * cosf(behind_angle);
        *target_y = py + pole_to_patient_distance * sinf(behind_angle);
    }
}

/*
 * 모터 제어 명령을 전송하는 함수
 * 
 * 매개변수:
 * - target_x, target_y: 폴대의 목표 위치
 * 
 * 동작:
 * 1. 현재 위치와 목표 위치의 거리/각도 오차 계산
 * 2. PID 제어로 선속도(V)와 각속도(W) 계산
 * 3. 모터 제어 명령을 UART로 전송
 */
void send_motor_commands(float target_x, float target_y) {
    // 현재 폴대 위치에서 목표 위치까지의 거리 계산
    float current_distance = sqrtf(target_x * target_x + target_y * target_y);
    
    // 현재 폴대 위치에서 목표 위치까지의 각도 계산
    float current_angle = atan2f(target_y, target_x) * RAD_TO_DEG;
    
    // 거리와 각도 오차 계산
    float distance_error = current_distance - target_distance;  // 거리 오차
    float angle_error = current_angle - target_angle;           // 각도 오차
    
    // PID 제어로 모터 제어 명령 계산 (기존 STM32 코드와 동일한 방식)
    float V = K_v * distance_error;  // 선속도 제어 (거리 오차 기반)
    float W = K_w * angle_error * DEG_TO_RAD;  // 각속도 제어 (각도 오차 기반)
    
    // 모터 제어 명령을 UART로 전송
    char cmd[64];
    sprintf(cmd, "MOVE:%.2f,%.2f\n", V, W);
    HAL_UART_Transmit(&huart3, (uint8_t*)cmd, strlen(cmd), 100);
}

/*
 * 추적 상태 전환을 처리하는 함수
 * 
 * 상태 전환 규칙:
 * - STATE_IDLE → STATE_SYNC: 초기화 완료
 * - STATE_SYNC → STATE_NORMAL: IMU 데이터 수신 완료
 * - STATE_NORMAL → STATE_PREDICTION: 허스키렌즈 로스트
 * - STATE_PREDICTION → STATE_NORMAL: 허스키렌즈 복구
 * - STATE_PREDICTION → STATE_LOST: 예측 시간 초과
 * - STATE_LOST → STATE_NORMAL: 허스키렌즈 복구
 */
void handle_state_transition() {
    switch (tracking_state) {
        case STATE_IDLE:
            // 초기화 완료 후 동기화 상태로 전환
            tracking_state = STATE_SYNC;
            break;
            
        case STATE_SYNC:
            // IMU 데이터 수신 시 정상 상태로 전환
            if (sync_complete) {
                tracking_state = STATE_NORMAL;
                lost_timer = 0;  // 타이머 초기화
            }
            break;
            
        case STATE_NORMAL:
            // 허스키렌즈가 태그를 놓친 경우 예측 상태로 전환
            if (husky_lost) {
                tracking_state = STATE_PREDICTION;
                prediction_timer = 0;  // 예측 타이머 초기화
            }
            break;
            
        case STATE_PREDICTION:
            prediction_timer++;  // 예측 타이머 증가
            
            // 예측 시간 초과 시 로스트 상태로 전환
            if (prediction_timer >= PREDICTION_TIMEOUT) {
                tracking_state = STATE_LOST;
                lost_timer = 0;  // 로스트 타이머 초기화
            } 
            // 허스키렌즈 복구 시 정상 상태로 전환
            else if (!husky_lost) {
                tracking_state = STATE_NORMAL;
                lost_timer = 0;
            }
            break;
            
        case STATE_LOST:
            lost_timer++;  // 로스트 타이머 증가
            
            // 로스트 시간 초과 시 정지 명령
            if (lost_timer >= LOST_TIMEOUT) {
                send_motor_commands(0, 0);  // 모터 정지
            } 
            // 허스키렌즈 복구 시 정상 상태로 전환
            else if (!husky_lost) {
                tracking_state = STATE_NORMAL;
                lost_timer = 0;
            }
            break;
    }
}

/*
 * 타이머 인터럽트 콜백 함수 (100Hz 주기로 실행)
 * 
 * 매개변수:
 * - htim: 타이머 핸들러
 * 
 * 동작:
 * 1. 현재 상태에 따라 IMU 데이터 처리
 * 2. 환자 위치 업데이트
 * 3. 폴대 목표 위치 계산 및 모터 제어
 * 4. 허스키렌즈 데이터 처리
 * 5. 상태 전환 처리
 */
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim) {
    // TIM1 타이머 인터럽트만 처리
    if (htim->Instance == TIM1) {
        switch (tracking_state) {
            case STATE_IDLE:
                // 대기 상태: 아무 동작 없음
                break;
                
            case STATE_SYNC:
                // 동기화 상태: IMU 데이터 수신 대기
                if (rx_flag) {
                    rx_flag = 0;  // 플래그 초기화
                    
                    // IMU 데이터 파싱 및 처리
                    parse_imu_data(rx_buf, &imu_data);
                    apply_low_pass_filter(&imu_data, &imu_data);
                    update_motion();
                    
                    sync_complete = 1;  // 동기화 완료 플래그 설정
                }
                break;
                
            case STATE_NORMAL:
            case STATE_PREDICTION:
                // 정상/예측 상태: IMU 데이터 처리 및 모터 제어
                if (rx_flag) {
                    rx_flag = 0;  // 플래그 초기화
                    
                    // IMU 데이터 파싱 및 처리
                    parse_imu_data(rx_buf, &imu_data);
                    apply_low_pass_filter(&imu_data, &imu_data);
                    update_motion();
                    
                    // 폴대 목표 위치 계산 및 모터 제어
                    float target_x, target_y;
                    calculate_pole_target_position(&target_x, &target_y);
                    send_motor_commands(target_x, target_y);
                }
                
                // 허스키렌즈 데이터 처리
                if (husky_flag) {
                    husky_flag = 0;  // 플래그 초기화
                    parse_husky_data(husky_buf, &husky_angle);
                }
                break;
                
            case STATE_LOST:
                // 로스트 상태: 추적 실패 시 동작 없음 (안전 정지)
                break;
        }
        
        // 상태 전환 처리
        handle_state_transition();
    }
}

/*
 * 디버그 정보를 출력하는 함수
 * 
 * 출력 정보:
 * - 현재 추적 상태
 * - 환자 위치 (X, Y)
 * - 환자 진행 방향
 * - 환자 속도
 * - 허스키렌즈 각도
 * - Roll, Pitch 각도
 */
void print_debug_info() {
    char debug_msg[128];
    sprintf(debug_msg, "State:%d Pos:%.2f,%.2f Dir:%.2f Speed:%.2f Husky:%d Roll:%.1f Pitch:%.1f\n", 
            tracking_state, px, py, patient_direction * RAD_TO_DEG, patient_speed, husky_angle, roll, pitch);
    HAL_UART_Transmit(&huart3, (uint8_t*)debug_msg, strlen(debug_msg), 100);
}

/*
 * 허스키렌즈 로스트를 감지하는 함수
 * 
 * 동작:
 * 1. 마지막 허스키렌즈 데이터 수신 시간 추적
 * 2. 100ms 이상 데이터 수신 없으면 로스트 상태로 설정
 * 3. 데이터 수신 시 로스트 상태 해제
 */
void check_husky_lost() {
    static uint32_t last_husky_time = 0;  // 마지막 수신 시간 (정적 변수)
    uint32_t current_time = HAL_GetTick();  // 현재 시간
    
    // 100ms 이상 각도 수신 없으면 로스트 상태로 설정
    if (current_time - last_husky_time > 100) {
        husky_lost = 1;
    }
    
    // 로스트 상태가 아니면 마지막 수신 시간 업데이트
    if (!husky_lost) {
        last_husky_time = current_time;
    }
}

/*
 * 메인 루프에서 실행할 상태 머신 관리 코드
 * 
 * 주의사항:
 * - 실제 구현 시에는 이 주석을 실제 코드로 변경
 * - TIM1 인터럽트에서 대부분의 처리가 이루어짐
 * - 메인 루프에서는 상태 확인 및 디버그 출력만 수행
 */
/*
switch (tracking_state) {
    case STATE_IDLE:
        // 초기화 대기 상태
        break;
        
    case STATE_SYNC:
        // IMU 동기화 대기 상태
        break;
        
    case STATE_NORMAL:
        // 정상 추적 상태 (TIM1 인터럽트에서 갱신됨)
        check_husky_lost();  // 허스키렌즈 로스트 감지
        print_debug_info();  // 디버그 정보 출력
        break;
        
    case STATE_PREDICTION:
        // 예측 추적 상태 (TIM1 인터럽트에서 갱신됨)
        check_husky_lost();  // 허스키렌즈 로스트 감지
        print_debug_info();  // 디버그 정보 출력
        break;
        
    case STATE_LOST:
        // 정지 상태
        break;
}
*/ 