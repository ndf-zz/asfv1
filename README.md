# asfv1

Alternate Assembler for Spin Semi FV-1

Copyright (C) 2017-2021 Nathan Fraser

An alternate assembler for the Spin Semiconductor FV-1 DSP. This
assembler aims to replicate some of the behaviour of the Spin FV-1
assembler in standard Python, for developers who are unable or
unwilling to use the Spin provided IDE.

## Requirements

- Python \>= 2.6

## Installation

Make sure your system has a python interpreter
(preferably python3), then install from the
[Python Package Index](https://pypi.org/)
using the
[pip](https://pip.pypa.io/en/stable/)
command:

	$ pip3 install asfv1

or

	$ pip install asfv1

For system-specific installation instructions see
[System Specific Installation](#system-specific-installation)
below.

## Description

asfv1 reads a single FV-1 DSP program then parses and assembles it.
If no errors are encountered, machine code is written to an output
file. If the output filename ends with 'hex', an Intel hex
encoded output is produced, otherwise raw binary data is written.

	usage: asfv1 [-h] [-q] [-v] [-c] [-s] [-p {0,1,2,3,4,5,6,7}] [-b]
             	infile outfile

 - `infile` : Filename for an ASCII, utf-8 or utf-16 encoded text file
   containing FV-1 assembly (see [Assembly Program Syntax](#assembly-program-syntax) below)

 - `outfile` : Filename for assembled output. If filename ends with 'hex',
   an Intel hex file is written.

 - `-h`, `--help` : Show a help message and exit

 - `-q`, `--quiet` : Suppress warning messages 

 - `-v`, `--version` : Print program version and exit

 - `-c`, `--clamp` : Clamp out of range instruction operand values without error.
   A warning message is printed for each clamped operand.

 - `-s`, `--spinreals` : Interpret integer literals `1` and `2` as 1.0 and 2.0
   respectively. This option should be used with SpinASM assembly.

 - `-p {0,1,2,3,4,5,6,7}` : Nominate one of the eight available program
   slots on an FV-1 eeprom as the target. When this option is used with
   binary output, machine code is offset appropriately in the target
   file, allowing for assembly into an existing binary bank file. When
   Intel HEX output is requested, the output file will include a single
   program and relevant offset information for the target program.

 - `-b`, `--binary` : Force output in binary format, even if `outfile`
   ends with 'hex'.

## Assembly Program Syntax

An FV-1 assembly program recognised by asfv1 closely resembles
the [SpinIDE](http://spinsemi.com/products.html) (.spn) format.
Input is an ASCII, utf-8 or utf-16 encoded
text file containing zero to 128 FV-1
[instructions](#instructions) with optional
[targets](#jump-targets), [labels](#label-assignment),
[comments](#comments) and [assembly directives](#memory-allocation).
All text is matched case-insensitively and runs of whitespace characters
(newline, tab, space) are condensed.
Each of the input instructions is assembled into a single 32 bit
machine code. If less than 128 assembly instructions are input,
the unallocated program space is padded with 'NOP' instructions
(0x00000011).

For [example](example.asm):

	; A complete, but useless FV-1 assembly program
	MEM	delay	int(32767*3/5)	; ~0.6 sec delay
	EQU	input	ADCL		; use ADCL for input
	EQU	output	DACL		; use DACL for output
	EQU	vol	REG0		; use REG0 for volume
	start:	skp	RUN,main	; skip to main after first sample
		ldax	POT0		; read from POT0
		wrax	vol,0.0		; write volume to register
	main:	ldax	input		; read from input
		mulx	vol		; scale by volume
		wra	delay,0.0	; write to delay
		rda	delay^,0.5	; read from delay midpoint
		rda	delay#,0.5	; read from delay end
		wrax	output,0.0	; write to output

When assembled with asfv1, the resulting machine code contains
9 instructions and padding with NOP instructions:

	$ asfv1 -q example.asm example.bin
	$ hd example.bin 
	00000000  80 40 00 11 00 00 02 05  00 00 04 06 00 00 02 85  |.@..............|
	00000010  00 00 04 0a 00 00 00 02  20 04 cc c0 20 09 99 80  |........ ... ...|
	00000020  00 00 02 c6 00 00 00 11  00 00 00 11 00 00 00 11  |................|
	00000030  00 00 00 11 00 00 00 11  00 00 00 11 00 00 00 11  |................|
	*
	00000200

### Comments 

A semicolon character ';' starts comment text. The assembler will
ignore all text including the ';' up to the end of a line.
Examples:

	; Comment out a whole line
	target:	or	0xffffff	; comment to end of line
	trget2:		; comment between target and instruction
		and	0x000000	; comment follows instruction
		; xor 0xa5a5a5		; instruction commented out
	; excessive commenting:
	addr02: cho			; op=0x14 interpolated memory access
			rdal,		; type=0x3 read offset(LFO) into ACC
			SIN1,		; lfo=0x1 use SIN1 LFO
			COS|REG		; flags=0xb register LFO and use COS output

### Label Assignment

	EQU	LABEL	EXPRESSION

Directive 'EQU' assigns the constant value resulting from the
evaluation of 'EXPRESSION' (see
[Operand Expressions](#operand-expressions)
below) to the text label 'LABEL'.
LABEL must begin with one alphabetic character in the set [A-Z,a-z]
followed by any number of alphanumeric characters or underscores:
[A-Z,a-z,0-9,_].
EXPRESSION can contain any previously assigned labels, including
those pre-defined by the assembler (see
[Pre-defined Labels](#pre-defined-labels) below). For
compatibility with SpinASM, the order of 'EQU' and 'LABEL'
may be swapped. Examples:

	EQU	input	ADCL		; assign value of ADCL (0x14) to 'input'
	EQU	r3_7	3/7		; assign the value 3/7 to 'r3_7'
	inve	EQU	1/r3_7		; assign the inverse of 'r3_7' to 'inve'

EQU does not generate any code in the program, it merely reserves
the name for subsequent use. The parser evaluates all expressions
in-place so a label must be declared before it is used:

		or	missing		; error
	EQU	missing	123		; missing is used before definition

	parse error: Undefined label missing on line ...

Re-defining an already assigned label is allowed, but will generate 
a warning message:

	EQU	POT0	POT1		; point POT0 to POT1

	warning: Label POT0 re-defined on line ...

Labels, mnemonics and operators are matched case insensitively:

	EQU	Label_One	-1.0	; assign 1.0 to 'LABEL_ONE'
	eQu	lABEL_oNE	-1.0	; assign 1.0 to 'LABEL_ONE' again
		Or	label_one	; or -1.0
		oR	LABEL_ONE	; or -1.0
		OR	LABEL_ONE	; or -1.0
		or	lAbEl_OnE	; or -1.0

### Memory Allocation

	MEM	LABEL	EXPRESSION

Addresses in the FV-1's 32768 sample circular buffer can be assigned
by the assembler using the 'MEM' directive. MEM reserves a portion
of memory that represents a delay of 'EXPRESSION' samples between
the start point and end point, and assigns three labels:

	LABEL	start of delay segment
	LABEL^	midpoint of delay segment
	LABEL#	end of delay segment

EXPRESSION must define an integer number of samples
or a parse error will be generated:

	MEM	invalid	123.4556	; invalid memory definition

	Memory INVALID length 123.4556 not integer on line 42

	MEM	third	32767//3	; valid due to integer divide
	MEM	d0_13	int(0.13*32767)	; valid due to explicit type cast

LABEL has the same requirements as for [EQU](#label-assignment), and
the assigned labels can be used in any expression. Eg:

	MEM	Del_A	375		; declare a 375 sample delay called 'DEL_A'
		wra	DEL_A,0.0	; write to start of delay, DEL_A=0
		rda	del_a^,0.5	; read 0.5*midpoint of delay, DEL_A^=187
		rda	DeL_A#,0.5	; add to 0.5*end of delay, DEL_A#=375

The assembler keeps track of allocated memory, placing each new
segment immediately after those previously defined. Each segment 
with a delay of LENGTH, will consume LENGTH+1 samples of memory.
An attempt to use more than the available space will trigger
a parse error:

	MEM	long	0x7f00		; long:0 long#:0x7f00
	MEM	short	0x00ff		; short:0x7f01 short#:0x8000 (error)

	parse error: Delay exhausted: requested 255 exceeds 254 available on line ...

The caret character '^' is also used in expressions as
the bitwise XOR operator, so expressions which reference
a delay may need to be explicitly parenthesised if used with '^':

		or	delay^0xffff	; parse error - delay label takes caret

	parse error: Unexpected INTEGER 0xffff on line ...

		or	(delay)^0xffff	; OK - parentheses enforce ordering
		or	delay^^0xffff	; OK 

### Jump Targets

Jump targets label a particular address in the program output
and can be placed between instructions anywhere in a source file.
A jump target is a text label followed by a colon ':' character:

			skp	1,TARGET1	; skip offset is 3
			skp	2,TARGET2	; skip offset is 2
			skp	4,TARGET3	; skip offset is 1
			or	0xff	Target1:	; target after instr
	TARGET2:			; target on its own line
	tarGET3:	and	0x12	; all three targets point to this instruction

Use of an already defined label for a target will result in a parse error:

	EQU	error	-1
	error:	or	0x800000

	parse error: Target ERROR already assigned on line ...

Target labels are not assigned values until parsing is complete
and they can only be used as a destination for a
[skip instruction](#skp-conditions-offset). For example, 
the following attempt to offset from a target generates a
parse error:

		skp	NEG,target	; skip to target if negative
		skp	0,target+1	; error - invalid expression
	target:	clr			; clear ACC
		wrax	DACL,0.0	; output only positive

	parse error: Unexpected OPERATOR + on line ...

To achieve the desired if/else behaviour, use a second target:

		skp	NEG,ifpart	; skip to target if negative
		skp	0,elsept	; else, skip ahead
	ifpart:	clr			; clear ACC
	elsept:	wrax	DACL,0.0	; output >= 0


### Instructions

An instruction is represented by a mnemonic text followed by zero 
or more [operand expressions](#operand-expressions) separated by commas:

Mnemonic | Operands | Description
--- | --- | ---
[rda](#rda-address-multiplier)	|	ADDRESS,MULTIPLIER	| multiply delay[ADDRESS] and accumulate
[rmpa](#rmpa-multiplier)	|	MULTIPLER		| multiply delay[(*ADDR_PTR)] and accumulate
[wra](#wra-address-multiplier)	|	ADDRESS,MULTIPLIER	| write delay[ADDRESS] and multiply
[wrap](#wrap-address-multiplier)	|	ADDRESS,MULTIPLIER	| write delay[ADDRESS], multiply and add LR
[rdax](#rdax-register-multiplier)	|	REGISTER,MULTIPLIER	| multiply (*REGISTER) and accumulate
[rdfx](#rdfx-register-multiplier)	|	REGISTER,MULTIPLIER	| subtract (*REGISTER), multiply and add (*REGISTER)
[ldax](#ldax-register)	|	REGISTER		| load (*REGISTER)
[wrax](#wrax-register-multiplier)	|	REGISTER,MULTIPLIER	| write (*REGISTER) and multiply
[wrhx](#wrhx-register-multiplier)	|	REGISTER,MULTIPLIER	| write (*REGISTER) and highpass shelf
[wrlx](#wrlx-register-multiplier)	|	REGISTER,MULTIPLIER	| write (*REGISTER) and lowpass shelf
[maxx](#maxx-register-multiplier)	|	REGISTER,MULTIPLIER	| load maximum of absolute values
[absa](#absa)	|				| load absolute value of ACC
[mulx](#mulx-register)	|	REGISTER		| multiply by (*REGISTER)
[log](#log-multiplier-offset)	|	MULTIPLIER,OFFSET	| log2(ACC), multiply and offset
[exp](#exp-multiplier-offset)	|	MULTIPLIER,OFFSET	| 2\*\*(ACC), multiply and offset
[sof](#sof-multiplier-offset)	|	MULTIPLIER,OFFSET	| multiply and offset
[and](#and-value)	|	VALUE			| bitwise AND
[clr](#clr)	|				| clear ACC
[or](#or-value)	|	VALUE			| bitwise OR
[xor](#xor-value)	|	VALUE			| bitwise XOR
[not](#not)	|				| bitwise negation
[skp](#skp-conditions-offset)	|	CONDITIONS,OFFSET	| skip offset instructions if all conditions met
[jmp](#jmp-offset)	|	OFFSET	| jump offset instructions
[nop](#nop)	|				| no operation
[wlds](#wlds-lfo-frequency-amplitude)	|	LFO,FREQUENCY,AMPLITUDE	| ajdust SIN LFO
[wldr](#wldr-lfo-frequency-amplitude)	|	LFO,FREQUENCY,AMPLITUDE	| adjust RMP LFO
[jam](#jam-lfo)	|	LFO			| reset LFO
[cho](#cho-rda-lfo-flags-address)	|	TYPE,LFO,FLAGS,ADDRESS	| interpolated memory access
[raw](#raw-u32)	|	U32			| insert U32 opcode

Each operand must evaluate to a single constant numeric
value. The sizes and types are specific to each instruction
(see [Instruction Reference](#instruction-reference) below).

### Operand Expressions

Operand expressions are any valid combination
of labels, numbers, parentheses and the following
operators, listed from highest to lowest precedence. Operators
on the same line have the same precedence, and are evaluated
left to right - except for '**' (power) which works 
[as in the python intepreter](https://docs.python.org/3/reference/expressions.html#the-power-operator).

Operator | Function | Note
--- | --- | ---
`\|`	|	bitwise or	| valid for integers only
`^`	|	bitwise xor	| valid for integers only
`&`	|	bitwise and	| valid for integers only
`<< >>` |	shift left, shift right	| valid for integers only
`+ -`	|	add, subtract	|
`* // /` |	multiply, divide	| `//` forces integer divide
`+ - ~ int`	|	unary plus, minus, invert bits, integer cast	| `!` is an alias for `~`
`**`	|	power	| Binds right: `-10**-2` = `-0.01`

The following numeric entry formats are recognised:

Literal	| Value | Type
--- | --- | ---
`123`	| 123 | Decimal integer
`0x123`	| 291 | Hexadecimal integer
`$123`	| 291 | Hexadecimal integer
`0b1010_1111`	| 175 | Binary integer
`%0101_1111`	| 175 | Binary integer ('_' is ignored)
`1.124`	| 1.124 | Floating point number
`1.124e-3`	| 0.001124 | Floating point number with exponent

The final value of an expression will be either an
integer, which is used for the instruction operand
unchanged or a floating point value which is later converted
to the closest fixed-point integer of the required size
(see [Fixed Point Conversion](#fixed-point-conversion) below).
The unary `int` operator will force a floating-point value
to be rounded and converted to the nearest integer:

	MEM	d0_23	int(0.23*0x8000) ; ~0.23 second delay = 7537 samples

If the result of the expression is a complex number, or if the
expression cannot be evaluated, a parse error is generated:

	EQU	j	(-1)**(1/2)	; j=sqrt(-1)

	parse error: Expression result (6.123233995736766e-17+1j) invalid type on line ...

	EQU	ns	1024<<(-1)	; impossible negative shift

	parse error: negative shift count on line ...

	EQU	tms	(1024/13)&0x123	; type mismatch

	parse error: unsupported operand type(s) for &: 'float' and 'int' on line ...

More formally, a valid operand expression matches the
following grammar:

	expression ::= or_expr
	or_expr ::= xor_expr | or_expr "|" xor_expr
	xor_expr ::= and_expr | xor_expr "^" and_expr
	and_expr ::= shift_expr | and_expr "&" shift_expr
	shift_expr ::= a_expr | shift_expr "<<" a_expr | shift_expr ">>" a_expr
	a_expr ::=  m_expr | a_expr "+" m_expr | a_expr "-" m_expr
	m_expr ::=  u_expr | m_expr "*" u_expr | m_expr "//" u_expr | m_expr "/" u_expr
	u_expr ::=  power | "-" u_expr | "+" u_expr | "~" u_expr | "int" u_expr
	power ::= atom ["**" u_expr]
	atom ::= label | literal | "(" expression ")"

Where label is a text label, and literal is a number. Expressions 
are parsed and evaluated in-place by asfv1. All labels must be defined
before they are referenced in an expression.

### Fixed Point Conversion

For instructions that require fixed-point real values as
input, asfv1 automatically converts real expression results
from an intermediate floating-point value to the nearest
equivalent signed fixed-point integer. This value is then
masked to the correct number of bits and placed in machine
code. The conversion is performed for all types by computing
the multiplication:

	fixed = int(round(floating * REFERENCE)) & MASK

Where REFERENCE is the equivalent integer value of +1.0 in the 
desired number format and floating is the saturated intermediate
floating-point value. The following table lists the sizes and range
of each of the FV-1 number formats. 

	Name	Bits	Refval	Minval	Maxval
	S4_6	11	64	-16.0	15.984375
	S1_9	11	512	-2.0	1.998046875
	S_10	11	1024	-1.0	0.9990234375
	S1_14	16	16384	-2.0	1.99993896484375
	S_15	16	32768	-1.0	0.999969482421875
	S_23	24	8388608	-1.0	0.9999998807907104

For example, the following entries all generate the same
code:

		or	-0.4335784912109375		; S_23 real value
		or	-0x377f80&0xffffff		; signed 23bit int to unsigned 24 bit int
		or	0xc88080			; unsigned 24bit int in hexadecimal
		or	13140096			; unsigned 24bit int in decimal
		or	1<<23|2**22|1<<19|2**15|1<<7	; unsigned 24bit int by bitwise or
		or	0b110010001000000010000000	; unsigned 24bit int in binary
		or	int(-0.4335784912109375*2**23)&0xffffff	; S_23 to unsigned 24bit conversion

### Pre-defined Labels

The following text labels are pre-defined by asfv1.
Refer to the FV-1 datasheet for information on the 
function of registers.

Label | Value | Description
--- | --- | ---
`SIN0_RATE`	|	`0x00`	|	SIN0 rate control register
`SIN0_RANGE`	|	`0x01`	|	SIN0 range control register
`SIN1_RATE`	|	`0x02`	|	SIN1 rate control register
`SIN1_RANGE`	|	`0x03`	|	SIN1 range control register
`RMP0_RATE`	|	`0x04`	|	RMP0 rate control register
`RMP0_RANGE`	|	`0x05`	|	RMP0 range control register
`RMP1_RATE`	|	`0x06`	|	RMP1 rate control register
`RMP1_RANGE`	|	`0x07`	|	RMP1 range control register
`POT0`	|	`0x10`	|	POT0 input register
`POT1`	|	`0x11`	|	POT1 input register
`POT2`	|	`0x12`	|	POT2 input register
`ADCL`	|	`0x14`	|	Left AD input register
`ADCR`	|	`0x15`	|	Right AD input register
`DACL`	|	`0x16`	|	Left DA output register
`DACR`	|	`0x17`	|	Right DA output register
`ADDR_PTR`	|	`0x18`	|	Delay address pointer
`REG0` - `REG31`	|	`0x20` - `0x3f`	|	General purpose registers
`SIN0`	|	`0x00`	|	SIN0 LFO selector
`SIN1`	|	`0x01`	|	SIN1 LFO selector
`RMP0`	|	`0x02`	|	RMP0 LFO selector
`RMP1`	|	`0x03`	|	RMP1 LFO selector
`RDA`	|	`0x00`	|	CHO type selector
`SOF`	|	`0x02`	|	CHO type selector
`RDAL`	|	`0x03`	|	CHO type selector
`SIN`	|	`0x00`	|	CHO flag
`COS`	|	`0x01`	|	CHO flag
`REG`	|	`0x02`	|	CHO flag
`COMPC`	|	`0x04`	|	CHO flag
`COMPA`	|	`0x08`	|	CHO flag
`RPTR2`	|	`0x10`	|	CHO flag
`NA`	|	`0x20`	|	CHO flag
`RUN`	|	`0x10`	|	SKP condition flag
`ZRC`	|	`0x08`	|	SKP condition flag
`ZRO`	|	`0x04`	|	SKP condition flag
`GEZ`	|	`0x02`	|	SKP condition flag
`NEG`	|	`0x01`	|	SKP condition flag

Pre-defined labels may be re-defined within a source file, 
however, the re-defined value only applies to label references
*following* the assignment. Any re-definition will issue a
warning message:

		ldax	POT0	; load POT0 (0x10)
	EQU	POT0	ADCL	; re-define POT0 to be 0x14
		ldax	POT0	; load from ADCL (0x14)

	warning: Label POT0 re-defined on line ...

## Instruction Reference

### rda ADDRESS, MULTIPLIER

Multiply and accumulate a sample from delay memory.

	ADDRESS:	Real S_15 or Unsigned 15bit integer delay address
	MULTIPLIER:	Real S1_9 or Unsigned 11bit integer
	Assembly:	MULTIPLIER<<21 | ADDRESS<<5 | 0b00000

Action:

	ACC <- ACC + MULTIPLIER * delay[ADDRESS]
	PACC <- ACC
	LR <- delay[ADDRESS]

Example:	

		rda	pdel^+324,0.1	; add 0.1 * delay[pdel^+324] to ACC
		rda	pdel#,0.3	; add 0.3 * delay[pdel#] to ACC
		rda	0.3,0.5		; add 0.5 * delay[0x2666] to ACC

### rmpa MULTIPLIER

Multiply and accumulate a sample from the delay memory, using
the contents of ADDR_PTR as the delay address.

	MULTIPLIER:	Real S1_9 or Unsigned 11bit integer
	Assembly:	MULTIPLIER<<21 | 0b00001

Action:

	ACC <- ACC + MULTIPLIER * delay[(*ADDR_PTR)>>8]
	PACC <- ACC
	LR <- delay[(*ADDR_PTR)>>8]

Notes:

   - 15 bit delay addresses in ADDR_PTR are left shifted 8 bits,
     so they can be accessed using the real S_23 value 0->0.9999 or
     directly by multiplying the desired integer delay address by 256.

Example:	

		or	1234<<8		; load 1234*256 into ACC
		wrax	ADDR_PTR,0.0	; save to ADDR_PTR and clear ACC
		rmpa	0.25		; add 0.25 * delay[1234] to ACC
		clr
		or	0.5		; load 0.5 into ACC
		wrax	ADDR_PTR,0.0	; save the address pointer
		rmpa	0.7		; add 0.7 * delay[0x4000]

### wra ADDRESS, MULTIPLIER

Write ACC to delay memory and scale by multiplier.

	ADDRESS:	Real S_15 or Unsigned 15bit integer delay address
	MULTIPLIER:	Real S1_9 or Unsigned 11bit integer
	Assembly:	MULTIPLIER<<21 | ADDRESS<<5 | 0b00010

Action:

	delay[ADDRESS] <- ACC
	PACC <- ACC
	ACC <- MULTIPLIER * ACC

Example:	

		wra	pdel^+324,0.25	; write ACC to delay[pdel^+324] scale ACC by 0.25
		wra	pdel#,0.0	; write ACC to delay[pdel#] clear ACC

### wrap ADDRESS, MULTIPLIER

Write ACC to delay memory, multiply ACC, add to LR and save to ACC.

	ADDRESS:	Real S_15 or Unsigned 15bit integer delay address
	MULTIPLIER:	Real S1_9 or Unsigned 11bit integer
	Assembly:	MULTIPLIER<<21 | ADDRESS<<5 | 0b00011

Action:

	delay[ADDRESS] <- ACC
	ACC <- LR + MULTIPLIER * ACC
	PACC <- ACC

Example:	

		ldax	ADCL		; read from left input
		wrap	0x1000,0.3	; write ACC to delay[0x1000] scale ACC by 0.3 add to LR

### rdax REGISTER, MULTIPLIER

Multiply and accumulate contents of register.

	REGISTER:	Unsigned 6bit integer register address
	MULTIPLIER:	Real S1_14 or Unsigned 16bit integer
	Assembly:	MULTIPLIER<<16 | REGISTER<<5 | 0b00100

Action:

	ACC <- ACC + MULTIPLIER * (*REGISTER)
	PACC <- ACC

Example:	

		rdax	POT0,0.11	; add 0.11*POT0 to ACC
		rdax	REG8,-0.66	; subtract 0.66*REG8 from ACC

### rdfx REGISTER, MULTIPLIER

Subtract register content from ACC, multiply and add to register content.

	REGISTER:	Unsigned 6bit integer register address
	MULTIPLIER:	Real S1_14 or Unsigned 16bit integer
	Assembly:	MULTIPLIER<<16 | REGISTER<<5 | 0b00101

Action:

	ACC <- (*REGISTER) + MULTIPLIER * (ACC - (*REGISTER))
	PACC <- ACC

Example:	

		rdfx	ADCL,0.0	; transfer ADCL content to ACC
		rdfx	REG0,0.3	; average using temp reg
		wrlx	REG0,0.0	; infinite shelf LPF

### ldax REGISTER

Copy register content to ACC. Assembles to rdax with a multiplier
of 0.0.

	REGISTER:	Unsigned 6bit integer register address
	Assembly:	REGISTER<<5 | 0b00101

Action:

	ACC <- (*REGISTER)
	PACC <- ACC

Example:	

		ldax	ADCL		; load ADCL content into ACC
		wrax	DACL,0.0	; write ACC to DACL

### wrax REGISTER, MULTIPLIER

Copy ACC to REGISTER, and multiply ACC.

	REGISTER:	Unsigned 6bit integer register address
	MULTIPLIER:	Real S1_14 or Unsigned 16bit integer
	Assembly:	MULTIPLIER<<16 | REGISTER<<5 | 0b00110

Action:

	(*REGISTER) <- ACC
	ACC <- MULTIPLIER * ACC
	PACC <- ACC

Example:	

		wrax	REG0,-1.0	; copy ACC into REG0 and invert ACC
		wrax	DACL,0.0	; copy ACC into DAC and clear ACC

### wrhx REGISTER, MULTIPLIER

Copy ACC to REGISTER, multiply ACC and add to PACC.

	REGISTER:	Unsigned 6bit integer register address
	MULTIPLIER:	Real S1_14 or Unsigned 16bit integer
	Assembly:	MULTIPLIER<<16 | REGISTER<<5 | 0b00111

Action:

	(*REGISTER) <- ACC
	ACC <- PACC + MULTIPLIER * ACC
	PACC <- ACC

Example:	

		rdfx	REG0,0.3	; average using temp reg
		wrhx	REG0,-0.5	; -6dB shelf highpass filter
		wrhx	REG1,0.0	; swap PACC and ACC

### wrlx REGISTER, MULTIPLIER

Copy ACC to REGISTER, subtract ACC from PACC, multiply and add to PACC.

	REGISTER:	Unsigned 6bit integer register address
	MULTIPLIER:	Real S1_14 or Unsigned 16bit integer
	Assembly:	MULTIPLIER<<16 | REGISTER<<5 | 0b01000

Action:

	(*REGISTER) <- ACC
	ACC <- PACC + MULTIPLIER * (PACC - ACC)
	PACC <- ACC

Example:	

		rdfx	REG0,0.3	; average using temp reg
		wrlx	REG0,-0.5	; -6dB shelf lowpass filter
		wrlx	REG1,0.0	; swap PACC and ACC

### maxx REGISTER, MULTIPLIER

Copy the maximum of the absolute value of ACC and the 
absolute value of REGISTER content times MULTIPLIER into ACC.

	REGISTER:	Unsigned 6bit integer register address
	MULTIPLIER:	Real S1_14 or Unsigned 16bit integer
	Assembly:	MULTIPLIER<<16 | REGISTER<<5 | 0b01001

Action:

	ACC <- maximum (abs (ACC), abs (MULTIPLIER * (*REGISTER)))
	PACC <- ACC

Example:	

		ldax	ADCL		; copy ADCL to ACC
		maxx	ADCR,1.0	; copy max of left and right to ACC
		maxx	0,0		; absolute value of ACC

### absa

Copy the absolute value of ACC back into ACC. Assembles to maxx
with null register and zero multiplier.

	Assembly:	0b01001

Action:

	ACC <- abs (ACC)
	PACC <- ACC

Example:	

		ldax	ADCL		; copy ADCL to ACC
		absa			; absolute value of ACC

### mulx REGISTER

Multiply ACC by the content of REGISTER.

	REGISTER:	Unsigned 6bit integer register address
	Assembly:	REGISTER<<5 | 0b01010

Action:

	ACC <- ACC * (*REGISTER)
	PACC <- ACC

Example:	

		ldax	ADCL		; copy ADCL to ACC
		mulx	POT0		; scale input by POT0

### log MULTIPLIER, OFFSET

Compute the base 2 log of the absolute value of ACC,
multiply and then add offset. Input ACC is S_23,
result ACC is S4_19.

	MULTIPLIER:	Real S1_14 or Unsigned 16bit integer
	OFFSET:		Real S_10 or Unsigned 11bit integer
	Assembly:	MULTIPLIER<<16 | OFFSET<<5 | 0b01011

Action:

	ACC <- OFFSET + MULTIPLIER * log2 (abs (ACC))
	PACC <- ACC

Notes:

   - OFFSET is input as a real S_10 value, however it represents
     an S4_6 offset of the accumulator, which is in S4_19 after the log.

Example:	

		log	0.5,0.0		; 2*log2(a) = log2(a**2)
		exp	1.0,0.0		; a = 2**(0.5 * log2(a**2))	[square root]

### exp MULTIPLIER, OFFSET

Raise 2 to the power of ACC, multiply and add OFFSET.
Input ACC is S4_16, result ACC is S_23.

	MULTIPLIER:	Real S1_14 or Unsigned 16bit integer
	OFFSET:		Real S_10 or Unsigned 11bit integer
	Assembly:	MULTIPLIER<<16 | OFFSET<<5 | 0b01100

Action:

	ACC <- OFFSET + MULTIPLIER * 2**ACC
	PACC <- ACC

Example:	

		log	1.0,4.0		; log2(16*a) = log2(16) + log2(a)
		exp	1.0,0.0		; 16*a = 2**(4+log2(a))	[x16 gain]

### sof MULTIPLIER, OFFSET

Scale ACC and then add an offset.

	MULTIPLIER:	Real S1_14 or Unsigned 16bit integer
	OFFSET:		Real S_10 or Unsigned 11bit integer
	Assembly:	MULTIPLIER<<16 | OFFSET<<5 | 0b01101

Action:

	ACC <- OFFSET + MULTIPLIER * ACC
	PACC <- ACC

Example:	

		sof	1.5,-0.4	; multiply acc by 1.5 and subtract 0.4

### and VALUE

Perform a bitwise AND of ACC and VALUE

	VALUE:		Real S_23 or Unsigned 24bit integer
	Assembly:	VALUE<<8 | 0b01110

Action:

	ACC <- ACC & VALUE
	PACC <- ACC

Example:	

		ldax	POT0		; load POT0 into ACC
		and	0x700000	; mask pot to 8 steps
		and	0		; clear ACC

### clr

Perform a bitwise AND of ACC with zero - clearing ACC

	Assembly:	0b01110

Action:

	ACC <- 0
	PACC <- ACC

Example:	

		clr			; clear ACC
		rda	1234,1.0	; load delay[1234]

### or VALUE

Perform a bitwise OR of ACC and VALUE

	VALUE:		Real S_23 or Unsigned 24bit integer
	Assembly:	VALUE<<8 | 0b01111

Action:

	ACC <- ACC | VALUE
	PACC <- ACC

Example:	

		clr			; clear ACC
		or	-2.3427e-4	; load an immediate value into ACC
		or	0x0a40f1	; set specific bits in ACC

### xor VALUE

Perform a bitwise XOR of ACC and VALUE

	VALUE:		Real S_23 or Unsigned 24bit integer
	Assembly:	VALUE<<8 | 0b10000

Action:

	ACC <- ACC ^ VALUE
	PACC <- ACC

Example:	

		ldax	POT0		; load POT0
		and	0x7f0000	; mask off lower bits
		xor	0x150000	; compare with 0x150000
		skp	ZRO,equal	; if same, skip to equal
		xor	0x150000	; else restore original value

### not

Perform a bitwise negation of ACC by XOR with 0xffffff.

	Assembly:	0xffffff<<8 | 0b10000

Action:

	ACC <- ~ACC
	PACC <- ACC

Example:	

		ldax	POT0		; load POT0
		not			; invert all bits

### skp CONDITIONS, OFFSET

Skip over OFFSET instructions if all flagged CONDITIONS are met.

	CONDITIONS:	Unsigned 5bit flags
	OFFSET:		Unsigned 6bit integer or target label
	Assembly:	CONDITIONS<<27 | OFFSET<<21 | 0b10001

Condition Flags:
	
	NEG	0x01	ACC is less than zero
	GEZ	0x02	ACC is greater than or equal to zero
	ZRO	0x04	ACC is zero
	ZRC	0x08	sign of ACC and PACC differ
	RUN	0x10	Program has completed at least one iteration

Notes:

 - if no condition flags are set, the skip is always performed.

 - if OFFSET starts with a label, it is assumed to be a jump target,
   which should be present later in the program. An attempt to skip
   backward will raise an error:

		start:	clr
			skp	0,start		; try to skip backward

		parse error: Target START does not follow SKP on line ...

 - the maximum possible skip offset is 63, an error will be generated if
   the named target is out of range:

			skp	0,target
			[>63 instructions]
		target: clr
	
		parse error: Offset from SKP to TARGET (0x40) too large on line ...

 - To force computation of an offset, wrap an expression in parentheses:

		EQU	three	3
			skp	0,three+3	; error - three is not a target

		parse error: Unexpected OPERATOR + on line ...
		parse error: Undefined target THREE for SKP on line ...

			skp	0,(three+3)	; ok, offset is evaluated as expression

 - if mutually exclusive conditions are specified, the skip is
   assembled but never performed, turning the instruction into NOP:

			skp	NEG|ZRO,target	; ACC cannot be negative AND zero

Example:	

		skp	0,target	; unconditionally skip to target
		ldax	ADCL		; read in ADCL
		ldax	REG0		; load a previous value
		skp	ZRC|NEG,target	; skip to target on positive zero crossing
		skp	RUN,1		; skip 1 instruction except on first run

### jmp OFFSET

Perform an unconditional skip over OFFSET instructions.

	OFFSET:		Unsigned 6bit integer or target label
	Assembly:	OFFSET<<21 | 0b10001

Notes:

 - jmp is assembled as skp 0,OFFSET. See skp above for details on 
   specifying jmp targets.

Example:	

		jmp	target		; unconditionally skip to target
		jmp	3		; always skip over 3 instructions

### nop

No operation, equivalent to skp 0,0. Use for padding, or blocking.

	Assembly:	0b10001

Example:	

		nop nop nop nop		; reserve 4 instruction slots

### wlds LFO, FREQUENCY, AMPLITUDE

Adjust SIN LFO with coefficients FREQUENCY and AMPLITUDE.

	LFO:		1bit integer (0 = SIN0 or 1 = SIN1)
	FREQUENCY:	Unsigned 9bit integer
	AMPLITUDE:	Real S_15 or Unsigned 15bit integer
	Assembly:	LFO<<29 | FREQUENCY<<20 | AMPLITUDE<<5 | 0b10010

Notes:

 - FREQUENCY coefficient is related to LFO rate (f) in Hz
   by the following:

		FREQUENCY = int (2**18 * pi * f / Fs)
		f = FREQUENCY * Fs / (2**18 * pi)
	
   Where Fs is the sample rate. For a 32768Hz crystal, the SIN 
   LFO ranges from 0Hz up to about 20Hz.

 - AMPLITUDE coefficient specifies the peak-to-peak amplitude
   of the LFO in delay samples, and may be entered using a real
   value. Negative amplitudes work as with SINx_RANGE register.

 - The frequency and amplitude of SIN LFOs can also be set
   by writing to registers: SIN0_RATE, SIN0_RANGE, SIN1_RATE,
   and SIN1_RANGE. 

Example:	

		wlds	SIN0,511,1	; Set SIN0 to 20Hz, amplitude 1 sample
		wlds	SIN1,1,0x7fff	; Set SIN1 to 0.04Hz and full delay length
		or	0.5
		wrax	SIN0_RATE,0.0	; Set SIN0 to ~10Hz
		ldax	POT0
		wrax	SIN0_RANGE,0.0	; Set SIN0 range from POT0

### wldr LFO, FREQUENCY, AMPLITUDE

Adjust RMP LFO with coefficients FREQUENCY and AMPLITUDE.

	LFO:		1bit integer (0 = RMP0 or 1 = RMP1)
	FREQUENCY:	Real S_15 or Signed 16bit integer
	AMPLITUDE:	2bit integer (0=4096, 1=2048, 2=1024, 3=512)
	Assembly:	(LFO|0x2)<<29 | FREQUENCY<<13 | AMPLITUDE<<5 | 0b10010

Notes:

 - LFO may also be set using pre-defined labels RMP0 and RMP1.

 - AMPLITUDE may also be set by entering one of the specific
   integer values: 4096, 2048, 1024 or 512.

 - FREQUENCY may be entered using a real value, which has the same
   interpretation as the RMPx_RATE register.

 - The frequency and amplitude of RMP LFOs can also be set
   by writing to registers: RMP0_RATE, RMP0_RANGE, RMP1_RATE,
   and RMP1_RANGE. 

Example:	

		wldr	RMP0,32767,0	; Set RMP0 to max rate, 4096 amplitude
		wldr	RMP1,-1923,512	; Set RMP1 to 512 and a negative frequency

### jam LFO

Reset specified ramp LFO to start.

	LFO:		1bit integer (0 = RMP0 or 1 = RMP1)
	Assembly:	(LFO|0x2)<<6 | 0b10011

Note:

- LFO may also be set using pre-defined labels RMP0 and RMP1.

Example:	

		jam	RMP0		; reset RMP0 lfo

### cho rda, LFO, FLAGS, ADDRESS

Read from delay memory at ADDRESS + offset (LFO) according to
FLAGS, multiply the result by coeff (LFO) and accumulate.

	LFO:		2bit integer (SIN0, SIN1, RMP0 or RMP1)
	FLAGS:		6bit integer flags
	ADDRESS:	Real S_15 or Unsigned 16bit integer
	Assembly:	FLAGS<<24 | LFO<<21 | ADDRESS<<5 | 0x10100

Action:

	ACC <- ACC + coeff (LFO) * delay[ADDRESS + offset (LFO)]
	PACC <- ACC

Flags:

	COS	0x01	use cosine output of SIN LFO 
	REG	0x02	'register' LFO state (see note below)
	COMPC	0x04	complement coefficient: 1 - coeff (LFO) 
	COMPA	0x08	complement address offset: 1 - offset (LFO)
	RPTR2	0x10	use second, half-off ramp 
	NA	0x20	offset (LFO) = 0.0, coeff (LFO) = crossfade coefficient

Notes:

 - offset (LFO) is the coarse LFO delay offset, based on flag settings
   to a whole sample

 - coeff (LFO) is an interpolation coefficient, based on flag settings
   and the LFO fine position between whole samples

 - the first use of cho in a program with any LFO must include the
   REG flag in order to 'register' the LFO state and get valid data

 - flags that are not relevant for the chosen LFO or cho mode are ignored

Example:

		cho	rda,SIN0,REG|COMPC,20	; load first half of interpolation
		cho	rda,SIN0,0,21		; add second half of interpolation

### cho sof, LFO, FLAGS, OFFSET

Multiply ACC by coeff (LFO), and add OFFSET.

	LFO:		2bit integer (SIN0, SIN1, RMP0 or RMP1)
	FLAGS:		6bit integer flags (see cho rda)
	OFFSET:		Real S_15 or Unsigned 16bit integer
	Assembly:	0x2<<30 | FLAGS<<24 | LFO<<21 | OFFSET<<5 | 0x10100

Action:

	ACC <- coeff (LFO) * ACC + OFFSET
	PACC <- ACC

Example:

		ldax	ADCL			; load AD
		cho	sof,RMP0,REG|COMPC|NA,0	; tremolo - scale ACC by RMP0 xfade

### cho rdal, LFO [, FLAGS]

Read the specified LFO address offset value into ACC
according to optional FLAGS. If FLAGS are omitted, a default
value of REG (0x2) is assembled.

	LFO:		2bit integer (SIN0, SIN1, RMP0 or RMP1)
	FLAGS:		6bit integer flags (see cho rda and notes)
	Assembly:	0x3<<30 | FLAGS<<24 | LFO<<21 | 0x10100

Action:

	ACC <- ACC + offset (LFO)
	PACC <- ACC

Notes:

 - REG flag must be set in order to get a meaningful value in ACC
   value (this is the default if FLAGS are omitted)

 - Only COS flag has any affect on the instruction, and only when used with
   SIN LFO. 

Example:

		cho	rdal,SIN0,REG	; load the SIN value and 'register' LFO
		wrax	DACL,0.0	; output to left channel
		cho	rdal,SIN0,COS	; load the COS value
		wrax	DACR,0.0	; output to right channel

### raw U32

Copy the unsigned 32 bit value in U32 directly to the output program.

	U32:		Unsigned 32bit integer
	Assembly:	U32

Example:

		raw	0x4000000f	; manually assemble "or 0.5"
		skp	0,1		; skip over the next instruction
		raw	0xa899fbda	; place a signature in the binary

## System Specific Installation

The preferred method for installation is to use your system's
packaged pip3 command to fetch and install asfv1 from
[PyPi](https://pypi.org/) and set it up to work with a python3
interpreter.

### Linux with apt (Debian, Ubuntu)

	$ sudo apt install python3-venv python3-pip
	$ pip3 install asfv1

### Linux with yum (Fedora 21)

	$ sudo yum install python3 python3-wheel
	$ pip3 install asfv1

### Linux with dnf (Fedora 22)

	$ sudo dnf install python3 python3-wheel
	$ pip3 install asfv1

### Arch Linux

	$ sudo pacman -S python-pip
	$ pip install asfv1

### MacOS

Download a copy of the &quot;Latest Python 3 Release&quot;
for Mac OS from
[python.org](https://www.python.org/downloads/mac-osx/).
Install the package, then open a terminal and run:

	$ pip3 install asfv1

### Windows

Download a copy of the &quot;Latest Python 3 Release&quot;
for Windows from
[python.org](https://www.python.org/downloads/windows/).
Install the package, then open a command prompt and run:

	C:\> pip3 install asfv1

For more detailed information, please refer to the 
[Python package installation documentation](https://packaging.python.org/tutorials/installing-packages/)
and
[installing pip with packaging managers](https://packaging.python.org/guides/installing-using-linux-tools/#installing-pip-setuptools-wheel-with-linux-package-managers)
at
[packaging.python.org](https://packaging.python.org/).

### Install from Source

If you would prefer to not use pip, or if your system is provided with
and older version of Python (eg MacOS), asfv1 can be installed using
the included setup.py script. Fetch a copy of the latest source package,
unpack it and then run the installer as root:

	$ sudo python ./setup.py install

Alternatively, the main source file can be run directly with a python
interpreter without the need to install any files:

	$ python ./asfv1.py infile.asm outfile.bin

## Links

- FV-1 disassembler: <https://github.com/ndf-zz/disfv1>
- FV-1 test suite: <https://github.com/ndf-zz/fv1testing>
- Dervish eurorack FV-1 module: <http://gbiswell.myzen.co.uk/dervish/Readme_First.html>
- Spin FV-1 website: <http://spinsemi.com/products.html>
- Datasheet: <http://spinsemi.com/Products/datasheets/spn1001/FV-1.pdf>
- AN0001: <http://spinsemi.com/Products/appnotes/spn1001/AN-0001.pdf>
