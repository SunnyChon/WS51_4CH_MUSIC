Variables:
SYSFRQ : System clock frequency
BPS : How many ticks per seconds
FPOS : The length of the data

Lists:
TONE_TABLE : The list of tones
CH1T : Note list of Channel 1
CH2T : Note list of Channel 2
CH3T : Note list of Channel 3
CH4T : Note list of Channel 4

MCU details:
Flash : 16384B
RAM : 256B + 1024B
Clock : Internal 16MHz RC
Core : 1T enhanced 8051 core

Data example:
BPS : 2
FPOS : 8
CH1T:
0,
0,
0,
0,
0,
2,
0,
1,

CH2T:
0,
0,
0,
0,
0,
2,
0,
1,

CH3T:
0,
0,
0,
0,
0,
2,
0,
1,

CH4T:
0,
0,
0,
0,
0,
2,
0,
1,

TONE_TABLE:
440,
660,
1010,

*This will play a 4 seconds sound with 0 = 440hz , 1 = 660hz , 2 = 1010hz

TODO :	 Write a python program to let the user select a midi file and it's tracks , map all tones the midi file used
	    to the TONE_TABLE list. Map all selected tracks(4 of them) to the CHnT lists , change the BPS variable based on the midi file to match the speed , change the FPOS variable to match the speed of the midi file.