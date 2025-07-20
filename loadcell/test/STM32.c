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
#include "adc.h"
#include "eth.h"
#include "tim.h"
#include "usart.h"
#include "usb_otg.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */
char uart_buf[8];
char re_data[8];
char uwb_buf[4];
char fe_data[5];
float uwb_data;
int x_data, y_data;
float w_L, w_R;
uint32_t PWM1_value, PWM2_value;
uint32_t spin_value;

float r = 0.0575;
float b = 0.257;
float dis, theta, V, W, W_test;
float K_v = 1.5;
float K_w = 1.5;

#define PI 3.1415926535

#define RX_BUF_SIZE 32

uint8_t rx_byte;
char rx_buf[RX_BUF_SIZE];
uint8_t rx_index = 0;
volatile uint8_t rx_flag = 0;
int rx_theta;
uint8_t current_mode;
volatile uint8_t send_flag = 0;
char tx_buf[5];

uint8_t rx_byte2;
char rx_buf2[RX_BUF_SIZE];
uint8_t rx_index2 = 0;
volatile uint8_t rx_flag2 = 0;
int rx_theta2;
volatile uint8_t send_flag2 = 0;
char tx_buf2[2];

int active_theta;

uint32_t IC_Val1 = 0, IC_Val2 = 0, IC_Val3 = 0, IC_Val4 = 0, IC_Val5 = 0;
uint32_t IC_Val6 = 0, IC_Val7 = 0, IC_Val8 = 0;
uint32_t Difference1 = 0, Difference2 = 0, Difference3 = 0, Difference4 = 0;
uint8_t Is_First_Captured1 = 0, Is_First_Captured2 = 0, Is_First_Captured3 = 0, Is_First_Captured4 = 0;
uint16_t Distance1 = 0, Distance2 = 0, Distance3 = 0, Distance4 = 0;

uint8_t sensor_part1 = 0, sensor_part2 = 0, sensor_part3 = 0, sensor_part4 = 0;
uint32_t delay_count = 0;
uint32_t ultra_count = 0;
uint8_t ultra_delay1 = 0, ultra_delay2 = 0, ultra_delay3 = 0, ultra_delay4 = 0;

uint32_t adc_value = 0;
float voltage = 0.0;
float real_voltage = 0.0;
uint32_t adc_delay = 0;
uint8_t BatteryLevel = 1;
volatile uint8_t Battery_per = 3;

float theta_buffer[21];
volatile uint8_t lost_state = 0;
uint32_t sampling_count = 0;
int all_zero = 0;

unsigned int minPWM = 14; //when ultrasonnic detected, other side wheel speed
unsigned int sideThreshold = 35; //set side ultrasonic detecting range
unsigned int frontThreshold = 20; //set front ultrasonic detecting range

uint8_t mode = 0;
uint32_t current_tick_1;
uint32_t old_tick_1;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
void shift_and_store(float new_value) {
    // 뒤로 한 칸씩 밀기 (4 <- 3 <- 2 <- 1 <- 0)
    for (int i = 21 - 1; i > 0; i--) {
        theta_buffer[i] = theta_buffer[i - 1];
    }
    // 0번째에 새 값 삽입
    theta_buffer[0] = new_value;
}

void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
	if (htim->Instance == TIM2) {
		if (ultra_delay1 == 1) {
			if (ultra_count >= 10) {
				HAL_GPIO_WritePin(GPIOE, GPIO_PIN_2, RESET);
				__HAL_TIM_ENABLE_IT(&htim3, TIM_IT_CC1);
				ultra_count = 0;
				ultra_delay1 = 0;
			}
			else {
				ultra_count++;
			}
		}
		else if (ultra_delay2 == 1) {
			if (ultra_count >= 10) {
				HAL_GPIO_WritePin(GPIOE, GPIO_PIN_4, RESET);
				__HAL_TIM_ENABLE_IT(&htim3, TIM_IT_CC2);
				ultra_count = 0;
				ultra_delay2 = 0;
			}
			else {
				ultra_count++;
			}
		}
		else if (ultra_delay3 == 1) {
			if (ultra_count >= 10) {
				HAL_GPIO_WritePin(GPIOE, GPIO_PIN_5, RESET);
				__HAL_TIM_ENABLE_IT(&htim3, TIM_IT_CC3);
				ultra_count = 0;
				ultra_delay3 = 0;
			}
			else {
				ultra_count++;
			}
		}
		else if (ultra_delay4 == 1) {
			if (ultra_count >= 10) {
				HAL_GPIO_WritePin(GPIOE, GPIO_PIN_6, RESET);
				__HAL_TIM_ENABLE_IT(&htim3, TIM_IT_CC4);
				ultra_count = 0;
				ultra_delay4 = 0;
			}
			else {
				ultra_count++;
			}
		}
		else if (sensor_part1 == 1) {
			delay_count++;
		}
		else if (sensor_part2 == 1) {
			delay_count++;
		}
		else if (sensor_part3 == 1) {
			delay_count++;
		}
		else if (sensor_part4 == 1) {
			delay_count++;
		}

		if (adc_delay >= 500000) {
			HAL_ADC_Start(&hadc1);
			adc_value = HAL_ADC_GetValue(&hadc1);
	        voltage = (adc_value / 4095.0f) * 3.3f;
	        real_voltage = voltage * ((11.0f + 3.0f) / 3.0f);
	        real_voltage = roundf(real_voltage * 10) / 10.0f;
	        if (real_voltage > 12.8) {
	        	BatteryLevel = 1;
	        }
	        else if (real_voltage <= 12.8) {
	        	BatteryLevel = 0;
	        }

	        if (real_voltage >= 13.4) {
	        	Battery_per = 3;
	        }
	        else if (real_voltage >= 13.2 && real_voltage < 13.4) {
	        	Battery_per = 2;
	        }
	        else if (real_voltage >= 13.0 && real_voltage < 13.2) {
	        	Battery_per = 1;
	        }
	        else if (real_voltage >= 0 && real_voltage < 13.0) {
	        	Battery_per = 0;
	        }

	        HAL_ADC_Stop(&hadc1);

	        adc_delay = 0;
		}
		else if (adc_delay < 500000) {
			adc_delay++;
		}

		if (sampling_count >= 10000) {
			shift_and_store(theta);
			sampling_count = 0;
		}
		else if (sampling_count < 10000) {
			sampling_count++;
		}
	}
}

void HAL_TIM_IC_CaptureCallback(TIM_HandleTypeDef *htim)
{
	if (htim->Instance == TIM3) {
		if (htim->Channel == HAL_TIM_ACTIVE_CHANNEL_1)
		{
			if (Is_First_Captured1 == 0)
			{
				IC_Val1 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_1);
				Is_First_Captured1 = 1;

				__HAL_TIM_SET_CAPTUREPOLARITY(htim, TIM_CHANNEL_1, TIM_INPUTCHANNELPOLARITY_FALLING);
			}

			else if (Is_First_Captured1 == 1)
			{
				IC_Val2 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_1);
				__HAL_TIM_SET_COUNTER(htim, 0);

				if (IC_Val2 > IC_Val1)
				{
					Difference1 = IC_Val2-IC_Val1;
				}

				else if (IC_Val1 > IC_Val2)
				{
					Difference1 = (0xffff - IC_Val1) + IC_Val2;
				}

				Distance1 = Difference1 * .034/2;
				Is_First_Captured1 = 0;

				__HAL_TIM_SET_CAPTUREPOLARITY(htim, TIM_CHANNEL_1, TIM_INPUTCHANNELPOLARITY_RISING);
				__HAL_TIM_DISABLE_IT(&htim3, TIM_IT_CC1);
			}
		}

		if (htim->Channel == HAL_TIM_ACTIVE_CHANNEL_2)
		{
			if (Is_First_Captured2 == 0)
			{
				IC_Val3 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_2);
				Is_First_Captured2 = 1;

				__HAL_TIM_SET_CAPTUREPOLARITY(htim, TIM_CHANNEL_2, TIM_INPUTCHANNELPOLARITY_FALLING);
			}

			else if (Is_First_Captured2 == 1)
			{
				IC_Val4 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_2);
				__HAL_TIM_SET_COUNTER(htim, 0);

				if (IC_Val4 > IC_Val3)
				{
					Difference2 = IC_Val4 - IC_Val3;
				}

				else if (IC_Val3 > IC_Val4)
				{
					Difference2 = (0xffff - IC_Val3) + IC_Val4;
				}

				Distance2 = Difference2 * .034/2;
				Is_First_Captured2 = 0;

				__HAL_TIM_SET_CAPTUREPOLARITY(htim, TIM_CHANNEL_2, TIM_INPUTCHANNELPOLARITY_RISING);
				__HAL_TIM_DISABLE_IT(&htim3, TIM_IT_CC2);
			}
		}

		if (htim->Channel == HAL_TIM_ACTIVE_CHANNEL_3)
		{
			if (Is_First_Captured3 == 0)
			{
				IC_Val5 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_3);
				Is_First_Captured3 = 1;

				__HAL_TIM_SET_CAPTUREPOLARITY(htim, TIM_CHANNEL_3, TIM_INPUTCHANNELPOLARITY_FALLING);
			}

			else if (Is_First_Captured3 == 1)
			{
				IC_Val6 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_3);
				__HAL_TIM_SET_COUNTER(htim, 0);

				if (IC_Val6 > IC_Val5)
				{
					Difference3 = IC_Val6 - IC_Val5;
				}

				else if (IC_Val5 > IC_Val6)
				{
					Difference3 = (0xffff - IC_Val5) + IC_Val6;
				}

				Distance3 = Difference3 * .034/2;
				Is_First_Captured3 = 0;

				__HAL_TIM_SET_CAPTUREPOLARITY(htim, TIM_CHANNEL_3, TIM_INPUTCHANNELPOLARITY_RISING);
				__HAL_TIM_DISABLE_IT(&htim3, TIM_IT_CC3);
			}
		}

		if (htim->Channel == HAL_TIM_ACTIVE_CHANNEL_4)
		{
			if (Is_First_Captured4 == 0)
			{
				IC_Val7 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_4);
				Is_First_Captured4 = 1;

				__HAL_TIM_SET_CAPTUREPOLARITY(htim, TIM_CHANNEL_4, TIM_INPUTCHANNELPOLARITY_FALLING);
			}

			else if (Is_First_Captured4 == 1)
			{
				IC_Val8 = HAL_TIM_ReadCapturedValue(htim, TIM_CHANNEL_4);
				__HAL_TIM_SET_COUNTER(htim, 0);

				if (IC_Val8 > IC_Val7)
				{
					Difference4 = IC_Val8 - IC_Val7;
				}

				else if (IC_Val7 > IC_Val8)
				{
					Difference4 = (0xffff - IC_Val7) + IC_Val8;
				}

				Distance4 = Difference4 * .034/2;
				Is_First_Captured4 = 0;

				__HAL_TIM_SET_CAPTUREPOLARITY(htim, TIM_CHANNEL_4, TIM_INPUTCHANNELPOLARITY_RISING);
				__HAL_TIM_DISABLE_IT(&htim3, TIM_IT_CC4);
			}
		}
	}
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart) {
	if (huart -> Instance == UART4) {
		for (int i = 0; i < 4; i++) {
			if (uwb_buf[(i + 1) % 4] == '.') {
				for (int j = 0; j < 4; j++) {
					fe_data[j] = uwb_buf[(i + j) % 4];
				}
			}
		}

		fe_data[4] = '\0';

		sscanf(fe_data, "%f", &dis);

		dis = roundf(dis * 100) / 100;

		HAL_UART_Receive_IT(&huart4, &uwb_buf, 4);
	}

    if (huart->Instance == USART2) {
		if (rx_byte == '.') {
			rx_buf[rx_index] = rx_byte;
			rx_buf[rx_index + 1] = '\0';
			rx_flag = 1;
			rx_index = 0;
		} else {
			if (rx_index < RX_BUF_SIZE - 1) {
				rx_buf[rx_index++] = rx_byte;
			} else {
				rx_index = 0;
			}
		}
		send_flag = 1;

		HAL_UART_Receive_IT(&huart2, &rx_byte, 1);
    }

	if (huart -> Instance == USART6) {
		if (rx_byte2 == '/') {
			rx_buf2[rx_index2] = rx_byte2;
			rx_buf2[rx_index2 + 1] = '\0';
			rx_flag2 = 1;
			rx_index2 = 0;
		} else {
			if (rx_index2 < RX_BUF_SIZE - 1) {
				rx_buf2[rx_index2++] = rx_byte2;
			} else {
				rx_index2 = 0;
			}
		}
		send_flag2 = 1;

		HAL_UART_Receive_IT(&huart6, &rx_byte2, 1);
	}
}

void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin) {
	if (GPIO_Pin == GPIO_PIN_3) {
		current_tick_1 = HAL_GetTick();
	}
	if (GPIO_Pin == GPIO_PIN_3 && (current_tick_1 - old_tick_1 > 300)) {
		if (mode == 0) {
			mode = 1;
		}
		else if (mode == 1) {
			mode = 0;
		}

		if (lost_state == 1) {
			lost_state = 0;
		}
		else if (lost_state == 0) {
			lost_state = 1;
		}
		old_tick_1 = current_tick_1;
	}
}

void HCSR04_Read1 (void)
{
	HAL_GPIO_WritePin(GPIOE, GPIO_PIN_2, SET);
	delay_count = 0;
	ultra_delay1 = 1;
}

void HCSR04_Read2 (void)
{
	HAL_GPIO_WritePin(GPIOE, GPIO_PIN_4, SET);
	delay_count = 0;
	ultra_delay2 = 1;
}

void HCSR04_Read3 (void)
{
	HAL_GPIO_WritePin(GPIOE, GPIO_PIN_5, SET);
	delay_count = 0;
	ultra_delay3 = 1;
}
void HCSR04_Read4 (void)
{
	HAL_GPIO_WritePin(GPIOE, GPIO_PIN_6, SET);
	delay_count = 0;
	ultra_delay4 = 1;
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
  MX_ETH_Init();
  MX_USART3_UART_Init();
  MX_USB_OTG_FS_PCD_Init();
  MX_TIM1_Init();
  MX_TIM2_Init();
  MX_TIM3_Init();
  MX_UART4_Init();
  MX_USART2_UART_Init();
  MX_USART6_UART_Init();
  MX_ADC1_Init();
  /* USER CODE BEGIN 2 */
  HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1);
  HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_2);

  HAL_UART_Receive_IT(&huart2, &rx_byte, 1);
  HAL_UART_Receive_IT(&huart6, &rx_byte2, 1);
  HAL_UART_Receive_IT(&huart4, &uwb_buf, 4);

  HAL_TIM_IC_Start_IT(&htim3, TIM_CHANNEL_1);
  HAL_TIM_IC_Start_IT(&htim3, TIM_CHANNEL_2);
  HAL_TIM_IC_Start_IT(&htim3, TIM_CHANNEL_3);
  HAL_TIM_IC_Start_IT(&htim3, TIM_CHANNEL_4);
  HAL_TIM_Base_Start_IT(&htim2);

  sensor_part4 = 1;

  HAL_GPIO_WritePin(GPIOG, GPIO_PIN_2, SET);
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
	  //ultra sensor
	  if (sensor_part4 == 1 && delay_count >= 6000) {
		  sensor_part4 = 0;
		  HCSR04_Read1();
		  sensor_part1 = 1;
	  }

	  if (sensor_part1 == 1 && delay_count >= 6000) {
		  sensor_part1 = 0;
		  HCSR04_Read2();
		  sensor_part2 = 1;
	  }

	  if (sensor_part2 == 1 && delay_count >= 6000) {
		  sensor_part2 = 0;
		  HCSR04_Read3();
		  sensor_part3 = 1;
	  }
	  if (sensor_part3 == 1 && delay_count >= 6000) {
		  sensor_part3 = 0;
		  HCSR04_Read4();
		  sensor_part4 = 1;
	  }

	  //Annotation due to overcurrent issues
	  //if button == 1, motor off
	  if (current_mode == 1) {
		  HAL_GPIO_WritePin(GPIOF, GPIO_PIN_13, SET);
	  }
	  else if (current_mode == 0) {
		  HAL_GPIO_WritePin(GPIOF, GPIO_PIN_13, RESET);
	  }

	  //send data to left_husky
	  if (send_flag) {
		  tx_buf[0] = '0' + BatteryLevel;
		  tx_buf[1] = '/';
		  tx_buf[2] = '0' + lost_state;
		  tx_buf[3] = '/';
		  tx_buf[6] = '\0';

		  HAL_UART_Transmit(&huart2, (uint8_t *)tx_buf, 5, HAL_MAX_DELAY);

		  //HAL_UART_Transmit(&huart2, &tx_buf, 5, HAL_MAX_DELAY);

		  send_flag = 0;
	  }

	  if (send_flag2) {
		  tx_buf2[0] = '0' + Battery_per;
		  tx_buf2[1] = '\n';

		  HAL_UART_Transmit(&huart6, (uint8_t *)tx_buf2, 2, HAL_MAX_DELAY);

		  //HAL_UART_Transmit(&huart, &tx_buf2, 2, HAL_MAX_DELAY);

		  send_flag2 = 0;
	  }

	  //huskylens UART flag
	  if (rx_flag) {
	      rx_flag = 0;

	      sscanf(rx_buf, "%d/%d.", &rx_theta, &current_mode);
	  }
	  if (rx_flag2) {
	      rx_flag2 = 0;

	      sscanf(rx_buf2, "%d/", &rx_theta2);
	  }

	  //distance limit
	  if (dis > 1.30) {
		  dis = 1.30;
	  }

	  //theta define
	  if (rx_theta != 999) {
		  active_theta = rx_theta;
	  } else if (rx_theta2 != 999) {
		  active_theta = rx_theta2;
	  } else {
		  active_theta = 0;
	  }
	  theta = active_theta;

	  //Husky value 0 in manual state
	  if (current_mode == 0) {
		  theta = 0;
	  }

	  //callback lost_state
/*	  if (lost_state == 1 && dis < 0.3) {
		  lost_state = 0;
	  }*/

	  //lost scene define
/*
	  all_zero = 1;
	  for (int i = 0; i < 20; i++) {
		  if (theta_buffer[i] != 0) {
			  all_zero = 0;
			  break;
		  }
	  }

	  if (all_zero) {
		  if (theta_buffer[20] > 45 || theta_buffer[20] < -45) {
			  lost_state = 1;
		  }
	  }
*/

	  //Defining V by distance
	  if (dis >= 1.0) {
		  V = K_v * (dis - 0.6);
	  }
/*	  else if (dis < 1.1 && (theta < -15 || theta > 15)) {
		  V = 0;
	  }*/

	  //differential drive kinematics
	  W = K_w * theta * PI / 180;

	  w_L = (V + W * b / 2) / r;
	  w_R = (V - W * b / 2) / r;

	  PWM1_value = w_L / 26.28 * 100;
	  PWM2_value = w_R / 26.28 * 100;

	  if (dis >= 1.1 && dis <= 1.2) {
		  if (theta > 15) {
			  PWM1_value += 24;
			  PWM2_value = 0;
		  }
		  else if (theta < -15) {
			  PWM1_value = 0;
			  PWM2_value += 24;
		  }
	  }

	  //PWM negative redefined
	  if (PWM1_value < 0) {
		  PWM1_value = 0;
	  }

	  if (PWM2_value < 0) {
		  PWM2_value = 0;
	  }

	  //MAX PWM redefined
	  if (PWM1_value > 99) {
	    	PWM1_value = 99;
	  }
	  if (PWM2_value > 99) {
		  PWM2_value = 99;
	  }

	  // spin at one point
	  if (dis < 1.1 && (theta > 15 || theta < -15)) {
		  //spin_value = (PWM1_value + PWM2_value) * 3 + 24;
		  spin_value = 27;
	  }

	  //Avoid by ultrasonic sensor
	  if(dis > 0.6) // ultrasonic activate distance => up to 0.6m
	  {
		if (Distance1 <= sideThreshold) //side right ultrasonic sensor detected
		{
		   if(Distance1 <= 10) //minimum threshold set 0.1m
		   {
			  PWM1_value = minPWM; //minimum PWM value = 14
		   }

		   PWM1_value = PWM1_value * (Distance1/35);
		}

		else if(Distance2 <= frontThreshold)  //front right ultrasonic sensor detected
		{
		   if(Distance2 <= 10) //minimum threshold set 0.1m
		   {
			  PWM1_value = minPWM;
		   }
		   PWM1_value = PWM1_value * (Distance2/20);
		}

		else if(Distance4 <= sideThreshold) //front left ultrasonic sensor detected
		{
		   if(Distance4 <= 10) //minimum threshold set 0.1m
		   {
			  PWM2_value = minPWM;
		   }

		   PWM2_value = PWM2_value * (Distance4/35);
		}

		else if(Distance3 <= frontThreshold) //side left ultrasonic sensor detected
		{
		   if(Distance3 <= 10) //minimum threshold set 0.1m
		   {
			  PWM2_value = minPWM;
		   }
		   PWM2_value = PWM2_value * (Distance3/20);
		}
	  }

	  if (lost_state == 1 || current_mode == 0) {
		  PWM1_value = 0;
		  PWM2_value = 0;
		  spin_value = 0;
	  }

	  //final driving
	  if (theta > 15) {
		  if (dis >= 1.1) {
		  	  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_15, RESET);
	  	  	  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_9, RESET);
			  __HAL_TIM_SET_COMPARE(&htim1,TIM_CHANNEL_1, PWM1_value);
			  __HAL_TIM_SET_COMPARE(&htim1,TIM_CHANNEL_2, PWM2_value);
		  }
		  else if (dis < 1.1) {
			  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_15, RESET);
	  	  	  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_9, SET);
			  __HAL_TIM_SET_COMPARE(&htim1,TIM_CHANNEL_1, spin_value);
			  __HAL_TIM_SET_COMPARE(&htim1,TIM_CHANNEL_2, spin_value);
		  }
	  }
	  else if (theta < -15) {
		  if (dis >= 1.1) {
		  	  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_15, RESET);
	  	  	  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_9, RESET);
			  __HAL_TIM_SET_COMPARE(&htim1,TIM_CHANNEL_1, PWM1_value);
			  __HAL_TIM_SET_COMPARE(&htim1,TIM_CHANNEL_2, PWM2_value);
		  }
		  else if (dis < 1.1) {
			  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_15, SET);
	  	  	  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_9, RESET);
			  __HAL_TIM_SET_COMPARE(&htim1,TIM_CHANNEL_1, spin_value);
			  __HAL_TIM_SET_COMPARE(&htim1,TIM_CHANNEL_2, spin_value);
		  }
	  }
	  else if (theta >= -15 && theta <= 15) {
		  if (dis >= 1.0) {
			  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_15, RESET);
	  	  	  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_9, RESET);
			  __HAL_TIM_SET_COMPARE(&htim1,TIM_CHANNEL_1, PWM1_value);
			  __HAL_TIM_SET_COMPARE(&htim1,TIM_CHANNEL_2, PWM2_value);
		  }
		  else if (dis < 1.0) {
		  	  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_15, RESET);
	  	  	  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_9, RESET);
			  __HAL_TIM_SET_COMPARE(&htim1,TIM_CHANNEL_1, 0);
			  __HAL_TIM_SET_COMPARE(&htim1,TIM_CHANNEL_2, 0);
		  }
	  }
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
  }
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

  /** Configure LSE Drive Capability
  */
  HAL_PWR_EnableBkUpAccess();

  /** Configure the main internal regulator output voltage
  */
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE3);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_BYPASS;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = 4;
  RCC_OscInitStruct.PLL.PLLN = 72;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = 3;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
  {
    Error_Handler();
  }
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
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
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
