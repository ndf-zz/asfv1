; A complete, but useless FV-1 assembly program
MEM     delay	int(32767*3/5)	; ~0.6 sec delay
EQU     input   ADCL		; use ADCL for input
EQU     output	DACL		; use DACL for output
EQU     vol	REG0		; use REG0 for volume
start:  skp	RUN,main	; skip to main after first sample
	ldax	POT0		; read from POT0
	wrax	vol,0.0		; write volume to register
main:   ldax	input		; read from input
	mulx	vol		; scale by volume
	wra	delay,0.0	; write to delay
	rda	delay^,0.5	; read from delay midpoint
	rda	delay#,0.5	; read from delay end
	wrax	output,0.0	; write to output
