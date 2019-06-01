asfv1
=====

Alternate Assembler for Spin Semi FV-1

Copyright (C) 2017 Nathan Fraser

An alternate assembler for the Spin Semiconductor FV-1 DSP.
This assembler aims to replicate some of the behaviour of
the Spin FV-1 assembler in standard Python, for developers
who are unable or unwilling to use the Spin provided IDE.

REQUIREMENTS:
-------------

  - Python >= 3

INSTALLATION:
-------------

  - pip3 install asfv1

OVERVIEW:
---------

asfv1 is based on information in the FV-1 datasheet and AN0001
"Basics of the LFOs in the FV-1". It assembles a DSP program
into machine code, ready for uploading to the FV-1.

There are some minor quirks:

 - Signed fixed point arguments (S1.14, S1.9, S.10) may be
   entered using an unsigned integer equivalent value. This 
   causes a conflict with SpinASM, when entries like -1 and 1
   are interpreted differently depending on how they are used.
   For Spin-like behaviour use option -s (--spinreals).

 - By default, immediate values that would overflow available
   argument sizes will generate an error and abort assembly.
   Command line option -c (--clamp) will instead restrict the
   value, where possible, and issue a warning.

 - Unlike the Spin assembler, non-sensical but othwerwise valid
   arguments are assembled without error.

 - Real numbers differ very slightly from those in the
   datasheet. Specifically:

        - Max S.23 0x7fffff = 0.9999998807907104

        - Max S.15   0x7fff = 0.999969482421875

        - Max S1.14  0x7fff = 1.99993896484375

        - Max S.10    0x3ff = 0.9990234375

        - Max S1.9    0x3ff = 1.998046875

        - Max S4.6    0x3ff = 15.984375

 - Raw data can be inserted into the program using the RAW
   instruction. RAW takes a 32bit integer operand and places
   it in the output without change.

 - This assembler builds a single DSP program from a single
   source file, and always outputs exactly 128 instructions.
   If the program length is less than 128 instructions, the
   remaining instruction slots are skipped with an explicit
   SKP. Command line option -n (--noskip) will leave only
   SKP 0,0 instructions.

 - Input is assumed to be utf-8 text.

 - By default the output is written to an intel hex file at
   offset 0x0000 (program 0). To select an alternate offset, 
   command line option -p can select a target program from 0 to 7.
   When output is set to binary with -b (--binary), the program
   number option is ignored.

For more information on the FV-1, refer to the Spin website:

 Web Site: http://spinsemi.com/products.html

 Datasheet: http://spinsemi.com/Products/datasheets/spn1001/FV-1.pdf

 AN0001: http://spinsemi.com/Products/appnotes/spn1001/AN-0001.pdf

