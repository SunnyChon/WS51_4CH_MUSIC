#include <WS51F6240.H>
#include "intrins.h"

//SYS FREQ
#define SYSFRQ 16000000

//MUSIC BPM
#define BPS 2

//TOTAL LENGTH OF NOTE TABLE
const uint32_t FPOS = 0;

//NOTE 2 FREQ
const uint16_t code TONE_TABLE[] = {0};

//CH FREQ
uint16_t CH1F = 0;
uint16_t CH2F = 0;
uint16_t CH3F = 0;
uint16_t CH4F = 0;

//CH HDUTY
uint16_t CH1HD = 0;
uint16_t CH2HD = 0;
uint16_t CH3HD = 0;
uint16_t CH4HD = 0;

//NOTE TABLE
const char code CH1T[] = {0};
const char code CH2T[] = {0};
const char code CH3T[] = {0};
const char code CH4T[] = {0};

//DELAY 1MS
static void delay_1ms(void)
{
	int j;
	for(j=0;j<1700;++j);
}
	
//DELAY MS
void delay(unsigned int ms)
{unsigned int i;
for (i=0;i<ms ;i++){delay_1ms();}}

//SETUP PWM
void setupPWM() {
	PWM0DIVL = 0xFF;
  PWM0DIVH = 0x00;
  PWM0DUTL = 0x00;
  PWM0DUTH = 0x00;
	
  PWM1DIVL = 0xFF;
  PWM1DIVH = 0x00;
  PWM1DUTL = 0x00;
  PWM1DUTH = 0x00;
	
  PWM2DIVL = 0xFF;
  PWM2DIVH = 0x00;
  PWM2DUTL = 0x00;
	PWM2DUTH = 0x00;
	
  PWM3DIVL = 0xFF;
  PWM3DIVH = 0x00;
  PWM3DUTL = 0x00;
  PWM3DUTH = 0x00;
	
  PWMRUN = 0x0F;
	PWM0PS = 0x09;
	PWM1PS = 0x0A;
	PWM2PS = 0x0B;
	PWM3PS = 0x0C;
}

void setFreq(uint32_t CPOS){
	CH1F = SYSFRQ / TONE_TABLE[CH1T[CPOS]];
	CH2F = SYSFRQ / TONE_TABLE[CH2T[CPOS]];
	CH3F = SYSFRQ / TONE_TABLE[CH3T[CPOS]];
	CH4F = SYSFRQ / TONE_TABLE[CH4T[CPOS]];
	CH1HD = CH1F / 2;
	CH2HD = CH2F / 2;
	CH3HD = CH3F / 2;
	CH4HD = CH4F / 2;
	
	//*high = (uint8_t)(input >> 8);
	//*low  = (uint8_t)(input & 0xFF);
  PWM0DIVL = (uint8_t)(CH1F & 0xFF);
  PWM0DIVH = (uint8_t)(CH1F >> 8);
  PWM0DUTL = (uint8_t)(CH1HD & 0xFF);
  PWM0DUTH = (uint8_t)(CH1HD >> 8);
	
  PWM1DIVL = (uint8_t)(CH2F & 0xFF);
  PWM1DIVH = (uint8_t)(CH2F >> 8);
  PWM1DUTL = (uint8_t)(CH2HD & 0xFF);
  PWM1DUTH = (uint8_t)(CH2HD >> 8);
	
  PWM2DIVL = (uint8_t)(CH3F & 0xFF);
  PWM2DIVH = (uint8_t)(CH3F >> 8);
  PWM2DUTL = (uint8_t)(CH3HD & 0xFF);
	PWM2DUTH = (uint8_t)(CH3HD >> 8);
	
  PWM3DIVL = (uint8_t)(CH4F & 0xFF);
  PWM3DIVH = (uint8_t)(CH4F >> 8);
  PWM3DUTL = (uint8_t)(CH4HD & 0xFF);
  PWM3DUTH = (uint8_t)(CH4HD >> 8);
}

void playMusic() {
	uint32_t i;
	for (i = 0;i < FPOS;i++){
		delay(1000 / BPS);
		setFreq(i);
	}
}

void main(){
	SCCON = 0x00; //16MHz RC
	setupPWM(); //Reset PWM register
	P11F = 0x03; //CH1 PINMODE
	P12F = 0x03; //CH2 PINMODE
	P13F = 0x03; //CH3 PINMODE
	P14F = 0x03; //CH4 PINMODE
  playMusic();
}