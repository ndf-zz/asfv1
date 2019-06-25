asfv1
=====

Alternate Assembler for Spin Semi FV-1

Copyright (C) 2017-2019 Nathan Fraser

An alternate assembler for the Spin Semiconductor FV-1 DSP. This
assembler aims to replicate some of the behaviour of the Spin FV-1
assembler in standard Python, for developers who are unable or unwilling
to use the Spin provided IDE.

REQUIREMENTS:
-------------

- Python \>= 3

INSTALLATION:
-------------

- pip3 install asfv1

USAGE:
------

  asfv1 input.asm output.hex

OVERVIEW:
---------

asfv1 is based on information in the FV-1 datasheet and AN0001 "Basics
of the LFOs in the FV-1". It assembles a DSP program into machine code,
ready for uploading to the FV-1.

There are some minor quirks:

- Signed fixed point arguments (S1.14, S1.9, S.10) may be entered
  using an unsigned integer equivalent value. This causes a conflict
  with SpinASM, when entries like -1 and 1 are interpreted
  differently depending on how they are used. For Spin-like
  behaviour use option -s (--spinreals).

- By default, immediate values that would overflow available
  argument sizes will generate an error and abort assembly. Command
  line option -c (--clamp) will instead restrict the value, where
  possible, and issue a warning.

- Unlike the Spin assembler, non-sensical but othwerwise valid
  arguments are assembled without error.

- Raw data can be inserted into the program using the RAW
  instruction. RAW takes a 32bit integer operand and places it in
  the output without change.

- This assembler builds a single DSP program from a single source
  file, and always outputs exactly 128 instructions. If the program
  length is less than 128 instructions, the remaining instruction
  slots are skipped with an explicit SKP. Command line option -n
  (--noskip) will leave only SKP 0,0 instructions.

- Input is assumed to be utf-8 text.

- By default the output is written to an intel hex file at offset
  0x0000 (program 0). To select an alternate offset, command line
  option -p can select a target program from 0 to 7. When output is
  set to binary with -b (--binary), the program number option is
  ignored.

LINKS:
------

- FV-1 disassembler: <https://github.com/ndf-zz/disfv1>

- Spin FV-1 website: <http://spinsemi.com/products.html>

- Datasheet: <http://spinsemi.com/Products/datasheets/spn1001/FV-1.pdf>

- AN0001: <http://spinsemi.com/Products/appnotes/spn1001/AN-0001.pdf>
