/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2025 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "tim.h"
#include "usart.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <math.h>
#include <string.h>
#include <stdio.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */
/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */
#define SOFT_START_TIME_MS   500     // 부팅 후 0.5 s 동안 소프트-스타트
#define PWM_SOFT_CAP_RATIO   0.60f   // 60 % 이상 PWM 금지
#define BOOT_INTEGRAL_FREEZE_MS 300  // 0.3 s 동안 Ki=0 취급
#define PI 3.1415926535f
#define RX_BUF_SIZE 16
#define CPR 2800           // 700 CPR * 4 (Quadrature)
#define DIFF(now,prev) ((int32_t)((now)-(prev)))  // 오버플로우 안전한 차이 계산
#define OUTER_LOOP_COUNT 5  // 5회마다 외부 루프 실행 (100Hz/5 = 20Hz)

// 테일러 근사 매크로 (소각도용)
#define SIN_SMALL_ANGLE(x) ((x) - (x)*(x)*(x)/6.0f + (x)*(x)*(x)*(x)*(x)/120.0f)
#define COS_SMALL_ANGLE(x) (1.0f - (x)*(x)/2.0f + (x)*(x)*(x)*(x)/24.0f)

// 부동소수점 최적화 함수
static inline float fast_sin_small(float x) {
    // |x| < π/6 (30도) 일 때 테일러 근사 사용
    if (fabsf(x) < 0.5236f) {  // π/6 ≈ 0.5236
        return SIN_SMALL_ANGLE(x);
    }
    return sinf(x);  // 큰 각도는 기존 함수 사용
}

static inline float fast_cos_small(float x) {
    // |x| < π/6 (30도) 일 때 테일러 근사 사용
    if (fabsf(x) < 0.5236f) {
        return COS_SMALL_ANGLE(x);
    }
    return cosf(x);
}
/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
/* USER CODE BEGIN PV */
// UART 통신 변수
char uart_buf[8];
char re_data[8];
char uwb_buf[5];  // 4 -> 5 바이트로 확장 (데이터 4 + NULL 종단 1)
float uwb_data;
int x_data, y_data;
float w_L, w_R;
uint32_t PWM1_value, PWM2_value;

// 제어 파라미터
#define V_MAX 0.35f
#define V_BASE 0.1f
#define A_MAX 0.3f
#define R_MIN 0.15f  // 더 급회전 가능 (0.25 → 0.15)
#define MAX_RAD_S 28.0f
#define Kp_dis 1.0f
#define Kd_dis 0.4f
#define Kp_yaw 3.5f
#define Kd_yaw 1.0f
#define Kp_vel 0.5f    // Feed-forward가 주 역할이므로 낮춤
#define Ki_vel 0.3f    // 적분 게인도 낮춤 (Wind-up 방지)
#define Kd_vel 0.05f   // 미분 게인도 낮춤
#define CONTROL_DT 0.05f
#define VELOCITY_DT 0.01f  // 100Hz → 100Hz로 변경 (1ms → 10ms)
#define TIM3_ARR 399.0f  // TIM3 자동재장전 값
#define ANTI_WINDUP 100.0f  // PID 출력 제한에 맞춤
#define MIN_PWM_DUTY 0.07f  // 최소 PWM 듀티 (7%) - 회전 토크 보장
#define PWM_DEADBAND 0.05f  // PWM Deadband (5%)

// 거리별 제어 모드 정의
typedef enum {
    MODE_EMERGENCY_STOP = 0,  // 긴급 정지
    MODE_BACKWARD,            // 후진 (0~20cm)
    MODE_STOP,                // 정지 (20~60cm)
    MODE_TRACKING,            // 추적 (60~90cm)
    MODE_FORWARD              // 전진 (90~200cm)
} control_mode_t;

// 제어 변수
volatile float v_ref = 0.0f;
volatile float w_ref = 0.0f;
volatile float v_prev = 0.0f;
volatile float e_dis_prev = 0.0f;
volatile float theta_prev = 0.0f;
volatile uint32_t control_timer = 0;
volatile uint32_t outer_loop_counter = 0;  // 외부 루프 카운터
volatile uint32_t log_counter = 0;  // 로그 카운터 (메인 루프로 이동)
volatile control_mode_t current_mode = MODE_STOP;  // 현재 제어 모드

// 엔코더 변수
volatile float omega_L_meas = 0.0f;
volatile float omega_R_meas = 0.0f;
volatile float omega_L_ref = 0.0f;
volatile float omega_R_ref = 0.0f;
static int32_t encL_prev = 0, encR_prev = 0;
volatile uint8_t encoder_initialized = 0;  // 엔코더 초기화 플래그

// PID 제어 변수
volatile float integral_L = 0.0f;
volatile float integral_R = 0.0f;
volatile float prev_error_L = 0.0f;
volatile float prev_error_R = 0.0f;

// 적응형 보정 변수
volatile float pwm_bias_L = 0.0f;
volatile float pwm_bias_R = 0.0f;
volatile float speed_bias = 0.0f;
volatile float speed_bias_avg = 0.0f;
volatile uint32_t bias_update_timer = 0;
volatile uint8_t bias_learning_enabled = 0;

// 안전 제어 변수
volatile uint32_t emergency_stop_timer = 0;
volatile uint32_t large_angle_timer = 0;
volatile uint8_t emergency_stop_flag = 0;
volatile float prev_dis = 0.8f;
volatile float prev_theta = 0.0f;

// UWB 거리 및 각도 변수
volatile float dis = 0.8f;
volatile float theta = 0.0f;

// 라이브 익스프레션용 PWM 모니터링 변수
volatile float pwm_L_cmd = 0.0f;  // Live Expression 모니터링용
volatile float pwm_R_cmd = 0.0f;  // Live Expression 모니터링용

uint8_t rx_byte;
char rx_buf[RX_BUF_SIZE];
uint8_t rx_index = 0;
volatile uint8_t rx_flag = 0;
int rx_theta;

const float r = 0.0575f;
const float b = 0.257f;

static uint32_t boot_ms = 0;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */
// 제어 함수 프로토타입
float slew_rate_limit(float v_new, float v_old, float a_max, float dt);
float pid_control(float setpoint, float measurement, float dt, float* integral, float* prev_error, float kp, float ki, float kd);
float distance_control(float dis, float dt);
void curvature_based_control(float dis, float theta, float dt);
void advanced_safety_check(float dis, float theta, float dt);
void calculate_wheel_speeds(void);
void motor_control(void);
void adaptive_speed_correction(void);
void reset_correction_values(void);
void enable_adaptive_correction(void);
void log_control_data(void);
void read_encoders(void);
void inner_loop_control(void);
void outer_loop_control(void);
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
// --- 인터럽트 및 콜백 함수 ---
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
    if (htim->Instance == TIM1) {
        // 100Hz 내부 루프 + 20Hz 외부 루프 통합
        inner_loop_control();
        
        // 5회마다 외부 루프 실행 (20Hz)
        outer_loop_counter++;
        if (outer_loop_counter >= OUTER_LOOP_COUNT) {
            outer_loop_counter = 0;
            outer_loop_control();
        }
    }
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
    if (huart -> Instance == USART1) {
        // 4-byte 고정 패킷: 이스케이프 문자 기준
        // 예: "0.79", "1.23", "2.45" 등
        
        // 이스케이프 문자 검색 (개행문자 \n 또는 캐리지리턴 \r)
        int escape_pos = -1;
        for (int i = 0; i < 4; i++) {
            if (uwb_buf[i] == '\n' || uwb_buf[i] == '\r') {
                escape_pos = i;
                break;
            }
        }
        
        if (escape_pos > 0 && escape_pos <= 4) {  // 이스케이프 문자가 있고 데이터가 있음
            // 4바이트 고정 패킷 파싱: "d.dd" 형태
            // uwb_buf[0]: 일의 자리
            // uwb_buf[1]: 소수점
            // uwb_buf[2]: 소수점 첫째 자리
            // uwb_buf[3]: 소수점 둘째 자리
            
            if (uwb_buf[0] >= '0' && uwb_buf[0] <= '9' &&  // 일의 자리 검증
                uwb_buf[1] == '.' &&                        // 소수점 검증
                uwb_buf[2] >= '0' && uwb_buf[2] <= '9' &&  // 소수점 첫째 자리 검증
                uwb_buf[3] >= '0' && uwb_buf[3] <= '9') {  // 소수점 둘째 자리 검증
                
                // 4바이트 고정 패킷 파싱
                float tmp = (uwb_buf[0] - '0') +                    // 일의 자리
                           (uwb_buf[2] - '0') * 0.1f +             // 소수점 첫째 자리
                           (uwb_buf[3] - '0') * 0.01f;             // 소수점 둘째 자리
                
                if (tmp > 0.0f && tmp < 20.0f) {  // 범위 검증
                    dis = tmp;  // 거리 업데이트
                }
            }
        }
        
        // 다음 수신 준비 (4바이트 고정)
        HAL_UART_Receive_IT(&huart1, (uint8_t*)uwb_buf, 4);
    }
    if (huart->Instance == USART3) {
        if (rx_byte == '/') {
            if (rx_index >= 1 && rx_index < sizeof(rx_buf)) {
                rx_buf[rx_index] = rx_byte;
                rx_buf[rx_index + 1] = '\0';
                rx_flag = 1;
                rx_index = 0;
            } else {
                rx_index = 0;
            }
        } else {
            if (rx_index < RX_BUF_SIZE - 1) {
                rx_buf[rx_index++] = rx_byte;
            } else {
                rx_index = 0;
            }
        }
        HAL_UART_Receive_IT(&huart3, &rx_byte, 1);
    }
}

// --- 제어 함수 구현 ---
float slew_rate_limit(float v_new, float v_old, float a_max, float dt) {
    float dv_max = a_max * dt;
    if (v_new - v_old > dv_max) return v_old + dv_max;
    else if (v_old - v_new > dv_max) return v_old - dv_max;
    return v_new;
}

float pid_control(float setpoint, float measurement, float dt, float* integral, float* prev_error, float kp, float ki, float kd) {
    float error = setpoint - measurement;
    float integral_temp = *integral + error * dt;
    if (integral_temp > ANTI_WINDUP) integral_temp = ANTI_WINDUP;
    else if (integral_temp < -ANTI_WINDUP) integral_temp = -ANTI_WINDUP;
    *integral = integral_temp;
    float derivative = (error - *prev_error) / dt;
    float output = kp * error + ki * (*integral) + kd * derivative;
    *prev_error = error;
    return output;
}

// 거리별 제어 모드 결정
control_mode_t determine_control_mode(float dis) {
    if (dis < 0.20f) return MODE_BACKWARD;      // 0~20cm: 후진
    else if (dis < 0.60f) return MODE_STOP;     // 20~60cm: 정지
    else if (dis < 0.90f) return MODE_TRACKING; // 60~90cm: 추적
    else return MODE_FORWARD;                   // 90cm~: 전진
}

float distance_control(float dis, float dt) {
    control_mode_t new_mode = determine_control_mode(dis);
    
    // 모드가 바뀌면 가속 제한 메모리 리셋
    if (new_mode != current_mode) {
        // 모드 전환 디버깅 로그 (선택사항)
        // printf("Mode: %d->%d, dis=%.2f, v_prev=%.2f\r\n", 
        //        current_mode, new_mode, dis, v_prev);
        
        v_prev = 0.0f;          // 속도 메모리 리셋
        e_dis_prev = 0.0f;      // 오차 메모리 리셋
    }
    current_mode = new_mode;
    
    float v_result = 0.0f;
    
    switch (current_mode) {
        case MODE_BACKWARD:
            // 0~20cm: 강한 후진 (충돌 회피)
            v_result = -0.3f;  // -0.3 m/s 후진
            break;
            
        case MODE_STOP:
            // 20~60cm: 정지 (안전 거리 확보)
            v_result = 0.0f;
            break;
            
        case MODE_TRACKING:
            // 60~90cm: 정밀 추적 (목표: 75cm)
            {
                float e_dis = dis - 0.75f;  // 목표 거리: 75cm
                float de_dis = (e_dis - e_dis_prev) / dt;
                v_result = Kp_dis * e_dis + Kd_dis * de_dis;
                v_result = fmaxf(fminf(v_result, 0.2f), -0.2f);  // ±0.2 m/s 제한
                e_dis_prev = e_dis;
            }
            break;
            
        case MODE_FORWARD:
            // 90cm~: 환자 추적 (목표: 80cm)
            {
                float e_dis = dis - 0.80f;  // 목표 거리: 80cm
                float de_dis = (e_dis - e_dis_prev) / dt;
                v_result = Kp_dis * e_dis + Kd_dis * de_dis;
                v_result = fmaxf(v_result, 0.0f);  // 전진만 허용
                e_dis_prev = e_dis;
            }
            break;
            
        default:
            v_result = 0.0f;
            break;
    }
    
    return v_result;
}

void curvature_based_control(float dis, float theta, float dt) {
    float theta_rad = theta * PI / 180.0f;
    float theta_abs = fabsf(theta_rad);
    v_ref = distance_control(dis, dt);

    // 최소 속도 바닥깔기 (출발 토크 보장)
    if (v_ref > 0 && v_ref < 0.12f) v_ref = 0.12f;  // 최소 0.12 m/s

    // v_theta_limit 계산 (최대 속도 제한)
    float v_theta_limit = V_MAX * (1.0f - fabsf(theta_rad) / (PI / 2.0f));
    v_theta_limit = fmaxf(v_theta_limit, V_BASE); // 최소 속도 보장
    v_ref = fminf(v_ref, v_theta_limit);
    v_ref = slew_rate_limit(v_ref, v_prev, A_MAX, dt);

    // 곡률 기반 회전 제어 (이미지 수식 적용)
    float kappa = 0.0f;
    if (fabsf(theta_rad) > 0.01f) {
        kappa = 2.0f * fast_sin_small(theta_rad) / dis;
    }
    float R = (kappa != 0.0f) ? 1.0f / fabsf(kappa) : 1e6f;
    if (fabsf(R) < R_MIN && kappa != 0.0f) {
        kappa = (theta_rad > 0 ? 1.0f : -1.0f) / R_MIN;
        R = (kappa != 0.0f) ? 1.0f / fabsf(kappa) : 1e6f;
    }

    // w_ref = v_ref * kappa (이미지 수식)
    w_ref = v_ref * kappa;

    // ----- 기존 단순제어 코드 (참고용, 주석처리) -----
    /*
    // 허스키렌즈 각도 직접 비례 회전 (이전 방식)
    const float W_MAX = 0.2f;  // 최대 각속도 (rad/s)
    float w_heading = (-rx_theta / 90.0f) * W_MAX;  // -90~90도 → -0.2~0.2 rad/s
    w_heading = fmaxf(fminf(w_heading, W_MAX), -W_MAX);  // 포화
    w_ref = w_heading;
    */
    // ------------------------------------------

    advanced_safety_check(dis, theta, dt);
    v_prev = v_ref;
    prev_dis = dis;
    prev_theta = theta;
}

void advanced_safety_check(float dis, float theta, float dt) {
    float theta_abs = fabsf(theta);
    
    // 거리 기반 안전 체크 (새로운 다단계 로직과 연동)
    if (dis < 0.10f) {  // 10cm 이하: 긴급 정지
        v_ref = 0.0f; 
        w_ref = 0.0f; 
        emergency_stop_flag = 1;
        current_mode = MODE_EMERGENCY_STOP;
    }
    else if (dis > 1.5f) {  // 1.5m 이상: 속도 제한
        v_ref = fminf(v_ref, 0.25f);
    }
    
    // 각도 기반 안전 체크
    if (theta_abs > 100.0f) { 
        v_ref = 0.0f; 
        w_ref = 0.0f; 
        emergency_stop_flag = 1; 
    }
    if (theta_abs > 60.0f) {
        large_angle_timer++;
        if (large_angle_timer > 2000) { 
            v_ref = 0.0f; 
            w_ref = 0.0f; 
            emergency_stop_flag = 1; 
        }
    } else {
        large_angle_timer = 0;
    }
    
    // 긴급 정지 해제 조건
    if (emergency_stop_flag) {
        emergency_stop_timer++;
        if (emergency_stop_timer > 100) {
            if (dis >= 0.20f && dis <= 1.5f && theta_abs <= 60.0f) {
                emergency_stop_flag = 0;
                emergency_stop_timer = 0;
                large_angle_timer = 0;
            }
        }
    }
}

void calculate_wheel_speeds(void) {
    omega_L_ref = (v_ref - w_ref * b / 2.0f) / r;
    omega_R_ref = (v_ref + w_ref * b / 2.0f) / r;
    omega_L_ref = fmaxf(fminf(omega_L_ref, MAX_RAD_S), -MAX_RAD_S);
    omega_R_ref = fmaxf(fminf(omega_R_ref, MAX_RAD_S), -MAX_RAD_S);
}

void motor_control(void) {
    if (emergency_stop_flag) {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_11, GPIO_PIN_RESET);
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_12, GPIO_PIN_RESET);
        __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_2, 0);
        __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_1, 0);
        return;
    }
    
    // ① Feed-forward PWM 계산 (목표 속도 → PWM)
    float pwm_ff_L = (omega_L_ref / MAX_RAD_S) * TIM3_ARR;  // 선형 매핑
    float pwm_ff_R = (omega_R_ref / MAX_RAD_S) * TIM3_ARR;
    
    // ② PID 보정 PWM 계산 (속도 오차 → ΔPWM)
    float pid_output_L = pid_control(omega_L_ref, omega_L_meas, VELOCITY_DT, &integral_L, &prev_error_L, Kp_vel, Ki_vel, Kd_vel);
    float pid_output_R = pid_control(omega_R_ref, omega_R_meas, VELOCITY_DT, &integral_R, &prev_error_R, Kp_vel, Ki_vel, Kd_vel);
    
    // PID 출력을 ΔPWM으로 제한 (±100 tick 정도)
    const float PID_LIMIT = 100.0f;
    pid_output_L = fmaxf(fminf(pid_output_L, PID_LIMIT), -PID_LIMIT);
    pid_output_R = fmaxf(fminf(pid_output_R, PID_LIMIT), -PID_LIMIT);
    
    // ③ 최종 PWM 합성 (Feed-forward + PID + Bias)
    float pwm_L = pwm_ff_L + pid_output_L + pwm_bias_L;
    float pwm_R = -(pwm_ff_R + pid_output_R) + pwm_bias_R;  // 오른쪽은 하드웨어 부호 반전
    
    // ④ 대칭 포화 (최대 35%)
    const float PWM_MAX = TIM3_ARR * 0.35f;
    pwm_L = fmaxf(fminf(pwm_L, PWM_MAX), -PWM_MAX);
    pwm_R = fmaxf(fminf(pwm_R, PWM_MAX), -PWM_MAX);
    
    // PWM Deadband 적용 (방향 핀 플리커 방지)
    if (fabsf(pwm_L) < PWM_DEADBAND * TIM3_ARR) pwm_L = 0.0f;
    if (fabsf(pwm_R) < PWM_DEADBAND * TIM3_ARR) pwm_R = 0.0f;
    
    // 최소 듀티 바닥깔기 (출발 토크 보장)
    if (pwm_L > 0 && pwm_L < MIN_PWM_DUTY * TIM3_ARR) pwm_L = MIN_PWM_DUTY * TIM3_ARR;
    if (pwm_L < 0 && pwm_L > -MIN_PWM_DUTY * TIM3_ARR) pwm_L = -MIN_PWM_DUTY * TIM3_ARR;
    if (pwm_R > 0 && pwm_R < MIN_PWM_DUTY * TIM3_ARR) pwm_R = MIN_PWM_DUTY * TIM3_ARR;
    if (pwm_R < 0 && pwm_R > -MIN_PWM_DUTY * TIM3_ARR) pwm_R = -MIN_PWM_DUTY * TIM3_ARR;
    
    // 최종 PWM 출력
    if (pwm_L >= 0) {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_11, GPIO_PIN_SET);
        __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_2, (uint32_t)pwm_L);
    } else {
        HAL_GPIO_WritePin(GPIOA, GPIO_PIN_11, GPIO_PIN_RESET);
        __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_2, (uint32_t)(-pwm_L));
    }
    if (pwm_R >= 0) {
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_12, GPIO_PIN_SET);
        __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_1, (uint32_t)pwm_R);
    } else {
        HAL_GPIO_WritePin(GPIOB, GPIO_PIN_12, GPIO_PIN_RESET);
        __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_1, (uint32_t)(-pwm_R));
    }
    
    // Live Expression 기록
    pwm_L_cmd = pwm_L;
    pwm_R_cmd = pwm_R;
}

void adaptive_speed_correction(void) {
    const float STRAIGHT_TH = 0.03f; // rad/s 임계값
    // 1. 참조 대비 잔차 방식 + 2. 직진 게이트 방식 동시 적용
    float ref_delta = omega_R_ref - omega_L_ref;
    float current_bias = 0.0f;
    if (fabsf(w_ref) < STRAIGHT_TH) {
        current_bias = (omega_R_meas - omega_L_meas) - ref_delta;
        // 부동소수점 연산 최적화: 곱셈을 비트 시프트로 대체 가능한 경우
        speed_bias_avg = speed_bias_avg * 0.999f + current_bias * 0.001f;
        bias_update_timer++;
        if (bias_update_timer >= 5) {  // 100Hz * 0.05s = 5회
            bias_update_timer = 0;
            if (fabsf(speed_bias_avg) > 0.5f && bias_learning_enabled) {
                // 부동소수점 연산 최적화: 상수 미리 계산
                const float PWM_ADJUSTMENT_SCALE = 1.5f;
                float pwm_adjustment = (speed_bias_avg / MAX_RAD_S) * TIM3_ARR * PWM_ADJUSTMENT_SCALE;
                if (speed_bias_avg > 0) {
                    pwm_bias_L += pwm_adjustment;
                    pwm_bias_R -= pwm_adjustment * 0.2f;
                } else {
                    pwm_bias_L -= pwm_adjustment;
                    pwm_bias_R += pwm_adjustment * 0.2f;
                }
                pwm_bias_L = fmaxf(fminf(pwm_bias_L, 15.0f), -15.0f);
                pwm_bias_R = fmaxf(fminf(pwm_bias_R, 15.0f), -15.0f);
            }
        }
    }
    /*
    // 기존 방식(참고용)
    if (!bias_learning_enabled && (HAL_GetTick() - boot_ms) > SOFT_START_TIME_MS && fabsf(omega_L_meas) > 1.0f && fabsf(omega_R_meas) > 1.0f) {
        bias_learning_enabled = 1;
    }
    float current_bias = omega_R_meas - omega_L_meas;
    // 부동소수점 연산 최적화: 곱셈을 비트 시프트로 대체 가능한 경우
    speed_bias_avg = speed_bias_avg * 0.999f + current_bias * 0.001f;
    bias_update_timer++;
    if (bias_update_timer >= 5) {  // 100Hz * 0.05s = 5회
        bias_update_timer = 0;
        if (fabsf(speed_bias_avg) > 0.5f && bias_learning_enabled) {
            // 부동소수점 연산 최적화: 상수 미리 계산
            const float PWM_ADJUSTMENT_SCALE = 1.5f;
            float pwm_adjustment = (speed_bias_avg / MAX_RAD_S) * TIM3_ARR * PWM_ADJUSTMENT_SCALE;
            if (speed_bias_avg > 0) {
                pwm_bias_L += pwm_adjustment;
                pwm_bias_R -= pwm_adjustment * 0.2f;
            } else {
                pwm_bias_L -= pwm_adjustment;
                pwm_bias_R += pwm_adjustment * 0.2f;
            }
            pwm_bias_L = fmaxf(fminf(pwm_bias_L, 15.0f), -15.0f);
            pwm_bias_R = fmaxf(fminf(pwm_bias_R, 15.0f), -15.0f);
        }
    }
    */
}

void reset_correction_values(void) {
    pwm_bias_L = 0.0f;
    pwm_bias_R = 0.0f;
    speed_bias = 0.0f;
    speed_bias_avg = 0.0f;
    bias_update_timer = 0;
    integral_L = 0.0f;
    integral_R = 0.0f;
    prev_error_L = 0.0f;
    prev_error_R = 0.0f;
}

void enable_adaptive_correction(void) {
    bias_learning_enabled = 1;
    reset_correction_values();
}

void log_control_data(void) {
    // uint32_t now = HAL_GetTick();
    // uint32_t boot_elapsed = now - boot_ms;
    // char log_buf[128];
    
    // // sprintf 최적화: 정수 연산 우선, 부동소수점 최소화
    // int v_ref_int = (int)(v_ref * 100);  // 0.01 단위로 정수 변환
    // int w_ref_int = (int)(w_ref * 100);
    // int omega_L_int = (int)(omega_L_meas * 10);  // 0.1 단위로 정수 변환
    // int omega_R_int = (int)(omega_R_meas * 10);
    // int pwm_bias_L_int = (int)(pwm_bias_L * 10);
    // int pwm_bias_R_int = (int)(pwm_bias_R * 10);
    
    // // PWM 값 계산 (디버깅용) - 새로운 분리 방식 적용
    // float pid_output_L = pid_control(omega_L_ref, omega_L_meas, VELOCITY_DT, &integral_L, &prev_error_L, Kp_vel, Ki_vel, Kd_vel);
    // float pid_output_R = pid_control(omega_R_ref, omega_R_meas, VELOCITY_DT, &integral_R, &prev_error_R, Kp_vel, Ki_vel, Kd_vel);
    
    // // 각 모터별 직진 PWM 계산
    // float pwm_fwd_L = pid_output_L * PWM_SCALE;
    // float pwm_fwd_R = pid_output_R * PWM_SCALE;
    // pwm_fwd_L = fmaxf(fminf(pwm_fwd_L, PWM_FWD_LIMIT), -PWM_FWD_LIMIT);
    // pwm_fwd_R = fmaxf(fminf(pwm_fwd_R, PWM_FWD_LIMIT), -PWM_FWD_LIMIT);
    
    // // 각 모터별 회전 PWM 계산
    // float pwm_rot_L = -(w_ref / (V_MAX / r)) * PWM_ROT_LIMIT;
    // float pwm_rot_R = (w_ref / (V_MAX / r)) * PWM_ROT_LIMIT;
    // pwm_rot_L = fmaxf(fminf(pwm_rot_L, PWM_ROT_LIMIT), -PWM_ROT_LIMIT);
    // pwm_rot_R = fmaxf(fminf(pwm_rot_R, PWM_ROT_LIMIT), -PWM_ROT_LIMIT);
    
    // // 실제 구동과 동일한 부호 적용
    // float pwm_L = pwm_fwd_L + pwm_rot_L + pwm_bias_L;
    // float pwm_R = -(pwm_fwd_R + pwm_rot_R) + pwm_bias_R;
    
    // int pwm_L_int = (int)(pwm_L * 100 / TIM3_ARR);  // PWM 듀티 %로 변환
    // int pwm_R_int = (int)(pwm_R * 100 / TIM3_ARR);
    
    // // 모드별 문자열 변환
    // const char* mode_str[] = {"EMG", "BWD", "STP", "TRK", "FWD"};
    // const char* current_mode_str = (current_mode < 5) ? mode_str[current_mode] : "UNK";
    
    // // sprintf(log_buf, "T:%lu V:%d.%02d W:%d.%02d OL:%d.%01d OR:%d.%01d PL:%d.%01d PR:%d.%01d PWM:%d%% %d%% %s %s\r\n",
    // //         boot_elapsed, 
    // //         v_ref_int/100, v_ref_int%100,
    // //         w_ref_int/100, w_ref_int%100,
    // //         omega_L_int/10, omega_L_int%10,
    // //         omega_R_int/10, omega_R_int%10,
    // //         pwm_bias_L_int/10, pwm_bias_L_int%10,
    // //         pwm_bias_R_int/10, pwm_bias_R_int%10,
    // //         pwm_L_int, pwm_R_int,
    // //         (boot_elapsed < SOFT_START_TIME_MS) ? "SOFT" : "NORM",
    // //         current_mode_str);
    // HAL_UART_Transmit(&huart2, (uint8_t*)log_buf, strlen(log_buf), 100);
}

void read_encoders(void) {
    int32_t cntL = (int32_t)__HAL_TIM_GET_COUNTER(&htim2);
    int32_t cntR = (int32_t)__HAL_TIM_GET_COUNTER(&htim4);
    
    // 엔코더 초기화 (첫 번째 호출 시)
    if (!encoder_initialized) {
        encL_prev = cntL;
        encR_prev = cntR;
        encoder_initialized = 1;
        omega_L_meas = 0.0f;
        omega_R_meas = 0.0f;
        return;  // 첫 번째는 변화량이 0이므로 스킵
    }
    
    // 변화량 계산 (오버플로우 안전)
    int32_t diffL = DIFF(cntL, encL_prev);
    int32_t diffR = DIFF(cntR, encR_prev);
    encL_prev = cntL;
    encR_prev = cntR;
    
    // 부동소수점 연산 최적화: 상수 미리 계산
    const float ENCODER_SCALE = 2.0f * PI / (CPR * VELOCITY_DT);
    omega_L_meas = (float)diffL * ENCODER_SCALE;
    omega_R_meas = (float)diffR * ENCODER_SCALE;
    
    adaptive_speed_correction();
}

void inner_loop_control(void) {
    uint32_t now = HAL_GetTick();
    if (now - boot_ms < 50) {
        // 엔코더 초기화는 read_encoders에서 처리하므로 제거
        return;
    }
    read_encoders();
#if BOOT_INTEGRAL_FREEZE_MS > 0
    if (now - boot_ms < BOOT_INTEGRAL_FREEZE_MS) {
        integral_L = integral_R = 0.0f;
    }
#endif
    motor_control();
    if (now - boot_ms < SOFT_START_TIME_MS) {
        const uint32_t cap = (uint32_t)(htim3.Init.Period * PWM_SOFT_CAP_RATIO);
        uint32_t pwm1 = __HAL_TIM_GET_COMPARE(&htim3, TIM_CHANNEL_1);
        uint32_t pwm2 = __HAL_TIM_GET_COMPARE(&htim3, TIM_CHANNEL_2);
        __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_1, (pwm1 < cap) ? pwm1 : cap);
        __HAL_TIM_SET_COMPARE(&htim3, TIM_CHANNEL_2, (pwm2 < cap) ? pwm2 : cap);
    }
}

void outer_loop_control(void) {
    uint32_t now = HAL_GetTick();
    curvature_based_control(dis, theta, CONTROL_DT);
    if (now - boot_ms < SOFT_START_TIME_MS) {
        if (w_ref > 1.0f) w_ref = 1.0f;
        if (w_ref < -1.0f) w_ref = -1.0f;
    }
    calculate_wheel_speeds();
    if (emergency_stop_flag) reset_correction_values();
    
    // 로그 카운터만 증가 (실제 출력은 메인 루프에서)
    log_counter++;
    if (log_counter >= 4) {  // 20Hz * 2s = 4회 (100Hz 기준)
        log_counter = 0;
        // log_control_data(); // ISR에서 제거 - 메인 루프로 이동
    }
}
/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{
  /* USER CODE BEGIN 1 */
  /* USER CODE END 1 */
  /* MCU Configuration--------------------------------------------------------*/
  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();
  /* USER CODE BEGIN Init */
  /* USER CODE END Init */
  /* Configure the system clock */
  SystemClock_Config();
  /* USER CODE BEGIN SysInit */
  /* USER CODE END SysInit */
  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_USART2_UART_Init();
  MX_TIM3_Init();
  MX_USART1_UART_Init();
  MX_TIM1_Init();
  MX_TIM2_Init();
  MX_TIM4_Init();
  MX_USART3_UART_Init();
  /* USER CODE BEGIN 2 */
  HAL_TIM_PWM_Start(&htim3, TIM_CHANNEL_1);
  HAL_TIM_PWM_Start(&htim3, TIM_CHANNEL_2);
  boot_ms = HAL_GetTick();
  HAL_TIM_Base_Start_IT(&htim1);  // TIM1만 사용 (100Hz 내부 + 20Hz 외부 루프)
  HAL_TIM_Encoder_Start(&htim2, TIM_CHANNEL_ALL);
  HAL_TIM_Encoder_Start(&htim4, TIM_CHANNEL_ALL);
  enable_adaptive_correction();
  HAL_UART_Receive_IT(&huart1, (uint8_t*)uwb_buf, 4);  // 4바이트로 수정
  HAL_UART_Receive_IT(&huart3, &rx_byte, 1);
  /* USER CODE END 2 */
  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
      if (rx_flag) {
          rx_flag = 0;
          // sscanf 제거 - 정수 파싱으로 대체 (메인 루프 최적화)
          rx_theta = 0;
          int sign = 1;
          int i = 0;
          
          // 부호 처리
          if (rx_buf[0] == '-') {
              sign = -1;
              i = 1;
          } else if (rx_buf[0] == '+') {
              i = 1;
          }
          
          // 숫자 파싱
          while (rx_buf[i] >= '0' && rx_buf[i] <= '9') {
              rx_theta = rx_theta * 10 + (rx_buf[i] - '0');
              i++;
          }
          rx_theta *= sign;
      }
      // 안전한 거리 상한값 설정 (UWB 센서 유효 범위 고려)
      const float DIS_MAX = 2.0f;  // UWB 센서 최대 유효 거리
      const float DIS_MIN = 0.1f;  // UWB 센서 최소 유효 거리
      dis = fmaxf(fminf(dis, DIS_MAX), DIS_MIN);  // Soft-saturate
      theta = (float)rx_theta;  // 부호 뒤집기 제거 - 허스키렌즈 부호 그대로 사용
      // 디버그용 LED 제어
      if (dis >= 0.9f) {
          HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_SET);  // dis >= 0.9m일 때 LED ON
      }
      else {
          HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_RESET); // 그 외에는 LED OFF
      }
      
      // 로그 출력 (ISR에서 메인 루프로 이동)
      static uint32_t main_log_counter = 0;
      main_log_counter++;
      if (main_log_counter >= 200) {  // 100Hz * 2s = 200회
          main_log_counter = 0;
          log_control_data();
      }
      
      // 제어 루프는 타이머 인터럽트에서 실행
  }
  /* USER CODE END WHILE */
  /* USER CODE BEGIN 3 */
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_BYPASS;
  RCC_OscInitStruct.HSEPredivValue = RCC_HSE_PREDIV_DIV1;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL9;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK) { Error_Handler(); }
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK|RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;
  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK) { Error_Handler(); }
}

/* USER CODE BEGIN 4 */
/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  __disable_irq();
  while (1) {}
  /* USER CODE END Error_Handler_Debug */
}

#ifdef  USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */