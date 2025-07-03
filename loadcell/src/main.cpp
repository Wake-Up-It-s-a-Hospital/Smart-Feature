#include <Wire.h>
#include <MPU6050.h>
#include <math.h>

MPU6050 imu;

// 수학 상수 및 물리 상수 정의
#define PI 3.1415926535
#define DEG_TO_RAD (PI / 180.0)
#define RAD_TO_DEG (180.0 / PI)
#define G 9.81f // 중력 가속도 (m/s²)

// 상보 필터 파라미터
#define ALPHA 0.98f 
#define BETA 0.02f  

// 타이밍 변수
unsigned long last_update_time = 0;
float dt = 0.0; // 루프 주기 (초)

// 오일러 각도 변수 (자세)
float roll = 0, pitch = 0, yaw = 0;

// 환자의 속도 및 위치 추정 변수
float vx = 0, vy = 0, vz = 0;
float px = 0, py = 0, pz = 0;

// 1. 오프셋 변수 선언
float ax_offset = 0, ay_offset = 0, az_offset = 0;
bool offset_calibrated = false;

/*
 * 6축 IMU용 상보 필터 함수
 * 자이로스코프의 빠른 응답과 가속도계의 중력 기반 보정을 결합하여 안정적인 자세 각도를 계산합니다.
 */
void complementary_filter(float ax, float ay, float az, float gx, float gy, float gz, float filter_dt) {
    float roll_acc, pitch_acc;

    // 가속도계로부터 Roll, Pitch 각도 계산
    roll_acc = atan2f(ay, sqrtf(ax * ax + az * az)) * RAD_TO_DEG;
    pitch_acc = atan2f(-ax, sqrtf(ay * ay + az * az)) * RAD_TO_DEG;
    
    // 자이로스코프 적분과 가속도계 각도를 융합
    roll = ALPHA * (roll + gx * filter_dt) + BETA * roll_acc;
    pitch = ALPHA * (pitch + gy * filter_dt) + BETA * pitch_acc;
    yaw += gz * filter_dt; // Yaw는 자이로스코프 적분만 사용 (드리프트 발생 가능)
}

/*
 * IMU 데이터를 기반으로 환자의 움직임을 업데이트하는 함수
 * 1. 상보 필터로 자세 계산
 * 2. 회전 행렬을 이용해 센서 좌표계의 가속도를 세계 좌표계로 변환
 * 3. 중력 성분 제거
 * 4. 가속도를 이중적분하여 속도와 위치 계산
 */
void update_motion(float ax, float ay, float az, float gx, float gy, float gz, float motion_dt) {
    // 1. 상보 필터로 자세(Roll, Pitch, Yaw) 업데이트
    complementary_filter(ax, ay, az, gx, gy, gz, motion_dt);
    
    // 2. 오일러 각도를 라디안으로 변환
    float roll_rad = roll * DEG_TO_RAD;
    float pitch_rad = pitch * DEG_TO_RAD;
    float yaw_rad = yaw * DEG_TO_RAD;
    
    // 3. 회전 행렬 계산 (ZYX 순서)
    float cr = cosf(roll_rad), sr = sinf(roll_rad);
    float cp = cosf(pitch_rad), sp = sinf(pitch_rad);
    float cy = cosf(yaw_rad), sy = sinf(yaw_rad);
    
    float R[3][3] = {
        {cp * cy, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr},
        {cp * sy, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr},
        {  -sp  ,           cp * sr     ,           cp * cr     }
    };
    
    // 4. 센서 좌표계 가속도를 세계 좌표계로 변환
    float ax_world = R[0][0] * ax + R[0][1] * ay + R[0][2] * az;
    float ay_world = R[1][0] * ax + R[1][1] * ay + R[1][2] * az;
    float az_world = R[2][0] * ax + R[2][1] * ay + R[2][2] * az;
    
    // 5. roll, pitch를 이용한 중력 벡터 계산
    float g_x = -G * sin(pitch_rad);
    float g_y = G * sin(roll_rad) * cos(pitch_rad);
    float g_z = G * cos(roll_rad) * cos(pitch_rad);
    
    // 6. 각 축에서 중력 성분 제거
    float ax_gravity_free = ax_world - g_x;
    float ay_gravity_free = ay_world - g_y;
    float az_gravity_free = az_world - g_z;
    
    // 7. 속도 적분
    vx += ax_gravity_free * motion_dt;
    vy += ay_gravity_free * motion_dt;
    vz += az_gravity_free * motion_dt;
    
    // 8. 위치 적분
    px += vx * motion_dt;
    py += vy * motion_dt;
    pz += vz * motion_dt;
}

// 2. setup()에서 오프셋 보정 (초기 100회 평균)
void calibrate_offset() {
    long sum_ax = 0, sum_ay = 0, sum_az = 0;
    int N = 100;
    int16_t ax, ay, az, gx, gy, gz;
    for (int i = 0; i < N; i++) {
        imu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);
        sum_ax += ax;
        sum_ay += ay;
        sum_az += az;
        delay(5);
    }
    ax_offset = (sum_ax / (float)N) / 16384.0f * G;
    ay_offset = (sum_ay / (float)N) / 16384.0f * G;
    az_offset = (sum_az / (float)N) / 16384.0f * G - G; // 중력 보정
    offset_calibrated = true;
}

void setup() {
    Serial.begin(115200);
    Wire.begin(21, 22); // SDA=21, SCL=22
    imu.initialize();

    if (!imu.testConnection()) {
        Serial.println("MPU6050 연결 실패");
        while (1);
    }
    Serial.println("MPU6050 연결 성공");

    // 초기 시간 기록
    last_update_time = millis();
    calibrate_offset();
}

void loop() {
    // 1. 시간 간격(dt) 계산
    unsigned long current_time = millis();
    dt = (current_time - last_update_time) / 1000.0f; // 초 단위로 변환
    last_update_time = current_time;

    // 2. MPU6050 센서 원시 데이터 읽기
    int16_t ax_raw, ay_raw, az_raw;
    int16_t gx_raw, gy_raw, gz_raw;
    imu.getMotion6(&ax_raw, &ay_raw, &az_raw, &gx_raw, &gy_raw, &gz_raw);

    // 3. 원시 데이터를 물리 단위로 변환
    // 가속도: g (1g = 9.81 m/s^2), 자이로: deg/s
    // MPU6050의 기본 감도 설정 (A_SCALE__2G, G_SCALE_250_DPS) 기준
    float ax_ms2 = (ax_raw / 16384.0f) * G - ax_offset;
    float ay_ms2 = (ay_raw / 16384.0f) * G - ay_offset;
    float az_ms2 = (az_raw / 16384.0f) * G - az_offset;
    float gx_dps = gx_raw / 131.0f;
    float gy_dps = gy_raw / 131.0f;
    float gz_dps = gz_raw / 131.0f;

    // 임계값 적용 (노이즈 무시)
    if (fabs(ax_ms2) < 0.05) ax_ms2 = 0;
    if (fabs(ay_ms2) < 0.05) ay_ms2 = 0;
    if (fabs(az_ms2) < 0.05) az_ms2 = 0;

    // 4. 움직임 및 위치 업데이트
    update_motion(ax_ms2, ay_ms2, az_ms2, gx_dps, gy_dps, gz_dps, dt);

    // 속도 감쇠 적용
    vx *= 0.98;
    vy *= 0.98;
    vz *= 0.98;

    // 5. 계산된 상대 위치 시리얼로 출력
    char debug_msg[256];
    sprintf(debug_msg, "Pos: [X:%.2f, Y:%.2f, Z:%.2f], Attitude: [R:%.1f, P:%.1f, Y:%.1f]\nAccel: [%.3f, %.3f, %.3f] m/s^2\nGyro: [%.3f, %.3f, %.3f] deg/s\n",
        px, py, pz, roll, pitch, yaw,
        ax_ms2, ay_ms2, az_ms2,
        gx_dps, gy_dps, gz_dps);
    Serial.print(debug_msg);

    delay(500); // 시리얼 출력 과부하 방지
}
