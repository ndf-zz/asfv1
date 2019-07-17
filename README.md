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

### Features

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

	skp	NEG|GEZ,target		; impossible skip

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


### Program Syntax

An Fv-1 assembly program is made up of zero to 128 instructions with 
optional target labels and any number of optional assembly directives.
Assembly directives allow assigning constant values to text labels
and the reservation of memory locations. All mnemonics, labels,
jump targets, and reserved names are case-insensitive.

Each instruction is represented by a mnemonic followed by zero 
or more operands separated by commas. Each operand is an expression
that follows the Python expression syntax closely. Formally, a valid
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

## LINKS:

- FV-1 disassembler: <https://github.com/ndf-zz/disfv1>
- Dervish eurorack FV-1 module: <http://gbiswell.myzen.co.uk/dervish/Readme_First.html>
- Spin FV-1 website: <http://spinsemi.com/products.html>
- Datasheet: <http://spinsemi.com/Products/datasheets/spn1001/FV-1.pdf>
- AN0001: <http://spinsemi.com/Products/appnotes/spn1001/AN-0001.pdf>
