# asfv1

Alternate Assembler for Spin Semi FV-1

Copyright (C) 2017-2019 Nathan Fraser

An alternate assembler for the Spin Semiconductor FV-1 DSP. This
assembler aims to replicate some of the behaviour of the Spin FV-1
assembler in standard Python, for developers who are unable or unwilling
to use the Spin provided IDE.


## REQUIREMENTS:

- Python \>= 3


## INSTALLATION:

	$ pip3 install asfv1


## USAGE:

	$ asfv1 input.asm output.hex

	$ asfv1 -b input.asm output.bin

	$ asfv1 -h
	usage: asfv1 [-h] [-q] [-v] [-c] [-n] [-s] [-p {0,1,2,3,4,5,6,7}] [-b]
	             infile [outfile]
	
	Assemble a single FV-1 DSP program.
	
	positional arguments:
	  infile                program source file
	  outfile               assembled output file
	
	optional arguments:
	  -h, --help            show this help message and exit
	  -q, --quiet           suppress warnings
	  -v, --version         print version
	  -c, --clamp           clamp out of range values without error
	  -n, --noskip          don't skip unused instruction space
	  -s, --spinreals       read literals 2 and 1 as 2.0 and 1.0
	  -p {0,1,2,3,4,5,6,7}  target program number (hex output)
	  -b, --binary          write binary output instead of hex


## DESCRIPTION:

asfv1 assembles a Spin Fv-1 DSP program into machine code, ready for
uploading to the device. It is based on information in the FV-1
datasheet and AN0001 "Basics of the LFOs in the FV-1".

## FEATURES:

All instruction operands are treated as numeric expressions
and can be entered directly as an unsigned integer or, where
reasonable, a real-valued equivalent. For example, the following
entries all generate the same code:

	or	-0.4335784912109375
	or	-0x377f80&0xffffff
	or	0xc88080
	or	1<<23|2**22|1<<19|2**15|1<<7

To enter a real value, the decimal portion is compulsory
otherwise the value will be interpreted as an integer:

	rdax	REG0,1		; multiply REG0 by 6.103515625e-05
	rdax	REG0,1.0	; multiply REG0 by 1.0

In SpinASM, entries -1, 1, -2 and 2 are interpreted
differently depending on how they are used. To get the Spin-like
behaviour, use option -s (--spinreals).

Operand expressions support the following arithmetic and
bitwise operators, listed in order of precedence from lowest
to highest:

	|	bitwise or
	^	bitwise xor
	&	bitwise and
	<<	bitwise left shift
	>>	bitwise right shift
	+	add
	-	subtract
	*	multiply
	//	integer divide
	/	divide
	-	unary minus
	+	unary plus
	~	unary negate (! in spinasm)
	**	power
	( )	parentheses

Expressions can be used in any operand, as long as the
final value is a constant integer or real number appropriate
for the instruction. Invalid combinations of real numbers and
integer values will generate an error eg:

	parse error: Invalid types for bitwise or (|) on line ...

By default, immediate values that would overflow available
argument sizes will generate an error and abort assembly. Command
line option -c (--clamp) will instead restrict the value, where
possible, and issue a warning eg:

	sof	2.0,0.0

	warning: S1.14 arg clamped for SOF: 1.99993896484375 on line ...
	
Non-sensical but otherwise valid arguments are assembled
without error eg:

	skp	NEG|GEZ,target		; an impossible skip

Instruction cho rdal can accept explicit condition flags as with
other cho instructions in order to access COS and RPTR2 eg:

	cho	rdal,SIN0,COS|REG	; read cosine lfo directly

Raw data can be inserted into the program using a 'RAW'
instruction. RAW takes a 32bit integer operand and places it in
the output without change, eg:

	raw	0xdeadbeef		; insert raw data

By default the output is written to an intel hex file at offset
0x0000 (program 0). To select an alternate offset, command line
option -p can select a target program from 0 to 7. When output is
set to binary with -b (--binary), the program number option is
ignored.


## PROGRAM SYNTAX:

An FV-1 assembly program is made up of zero to 128 instructions with 
optional target labels and any number of optional comments, 
or assembly directives. All mnemonics, labels, jump targets, and
reserved names are matched case-insensitively. Each of the input
instructions is assembled into a single 32 bit machine code for
the FV-1. If less than 128 asssembly instructions are input,
the unallocated program space is padded with 'NOP' instructions.
Example:

	; A complete, but useless FV-1 assembly program
	MEM	delay	32767*3//5	; ~0.6 sec delay
	EQU	input	ADCL		; read input from ADCL
	EQU	output	DACL		; write output to DACL
	EQU	vol	REG0		; use REG0 for volume
	start:	skp	run,main	; skip to main after first sample
		ldax	POT0		; read from POT0
		wrax	vol,0.0		; write volume to register
	main:	ldax	input		; read from input
		mulx	vol		; scale by volume
		wra	delay,0.0	; write to delay
		rda	delay^,0.5	; read from delay midpoint
		rda	delay#,0.5	; read from delay end
		wrax	output,0.0	; write to output

### Comments 

A semicolon character ';' starts comment text. the assembler will
ignore all text including the ';' up to the end of a line. Examples:

	; Comment out the whole line
	target:	or	0xffffff	; comment to end of line
	target:		; comment between target and instruction
		and	0x000000	; comment 

### Label Assignment

	EQU	SYMBOL	EXPRESSION

Directive 'EQU' assigns the constant value resulting from the
evaluation of 'EXPRESSION' (see below) to the text label 'SYMBOL'.
EXPRESSION can contain any previously assigned symbols, including
those pre-defined by the assembler (see Constants below). For
compatability with SpinASM, the order of 'EQU' and 'SYMBOL'
may be swapped. Examples:

	EQU	input	ADCL		; assign ADCL (0x14) to 'input'
	EQU	ratio	3/7		; assign the value 3/7 to 'ratio'
	inve	EQU	1/ratio		; assign the invese of ratio to 'inve'

EQU does not generate any code in the program, it merely reserves
the name for subsequent use. The parser evaluates all expressions
in-place so a name must be declared before it is used:

		or	missing		; error
	EQU	missing	123		; missing is used before definition

	parse error: Undefined symbol 'missing' on line ...

Re-defining an already assigned name is allowed, but will generate 
a warning message:

	EQU	POT0	POT1		; point POT0 to POT1

	warning: Symbol 'POT0' re-defined on line ...

### Memory Allocation

	MEM	NAME	EXPRESSION

Addresses in the FV-1's 32768 sample circular buffer can be assigned
by the assembler using the 'MEM' directive. MEM reserves a portion
of memory that represents a delay of 'EXPRESSION' samples between
the start point and end point.
It declares three pointers:

	NAME	start of delay segment
	NAME^	midpoint of delay segment
	NAME#	end of delay segment

For example:

	MEM	delay	375		; declare a 375 sample delay
		wra	delay,0.0	; write to start of delay
		rda	delay^,0.5	; read 0.5* midpoint of delay
		rda	delay#,0.5	; add to 0.5* end of delay

EXPRESSION must define an integer number of samples
or a parse error will be generated:

	MEM	invalid	123.4556	; invalid memory definition

	parse error: Memory 'INVALID' length 123.4556 not integer on line ...

	mem	third	32767//3	; valid due to integer divide

The assembler keeps track of allocated memory, placing each new
segment immediately after those previously defined. Each segment 
with a delay of LENGTH, will consume LENGTH+1 samples of memory and
an attempt to use more than the available space will cause a parse error:

	MEM	long	0x7f00		; long:0 long#:0x7f00
	MEM	short	0x00ff		; short:0x7f01 short#:0x8000 (error)

	parse error: Delay exhausted: requested 255 exceeds 254 available on line ...

Since the caret charater '^' is an operator in expressions for the 
bitwise XOR operation, expressions which reference a delay may
need to be explicitly parenthesised if used with '^':

		or	delay^0xffff	; parse error - delay label takes caret

	parse error: Unexpected input INTEGER/'0xffff' on line ...

		or	(delay)^0xffff	; OK - parentheses enforce ordering
		or	delay^^0xffff	; OK 

### Jump Targets

Jump targets label a particular address in the program output
and can be placed between instructions anywhere in a source file.

			or	0xff	target1:	; target after instr
	target2:			; target on its own line
	target3:	and	0x12	; all three targets are the same

Use of a predefined symbol or a previously equated name will result
in a parser error:

	EQU	error	-1
	error:	or	0x800000

	parse error: Label ERROR already assigned on line ...


### Instructions

### Operand Expressions

Each instruction is represented by a mnemonic followed by zero 
or more operands separated by commas. Each operand is an expression
that follows the Python expression syntax very closely. Formally, a valid
instruction matches the following grammar:

	instruction ::= mnemonic [op_expr (',' op_expr)*]
	op_expr ::= xor_expr | op_expr "|" xor_expr
	or_expr ::= and_expr | xor_expr "^" and_expr
	and_expr ::= shift_expr | and_expr "&" shift_expr
	shift_expr ::= a_expr | shift_expr "<<" a_expr | shift_expr ">>" a_expr
	a_expr ::=  m_expr | a_expr "+" m_expr | a_expr "-" m_expr
	m_expr ::=  u_expr | m_expr "*" u_expr | m_expr "//" u_expr | m_expr "/" u_expr
	u_expr ::=  power | "-" u_expr | "+" u_expr | "~" u_expr
	power ::= atom ["**" u_expr]
	atom ::= identifier | literal | "(" op_expr ")"

## INSTRUCTION REFERENCE:

## LINKS:

- FV-1 disassembler: <https://github.com/ndf-zz/disfv1>
- FV-1 test suite: <https://github.com/ndf-zz/fv1testing>
- Dervish eurorack FV-1 module: <http://gbiswell.myzen.co.uk/dervish/Readme_First.html>
- Spin FV-1 website: <http://spinsemi.com/products.html>
- Datasheet: <http://spinsemi.com/Products/datasheets/spn1001/FV-1.pdf>
- AN0001: <http://spinsemi.com/Products/appnotes/spn1001/AN-0001.pdf>
