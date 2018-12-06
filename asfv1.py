#!/usr/bin/python3
#
# asfv1: Alternate FV-1 Assembler
# Copyright (C) 2017 Nathan Fraser
#
# An alternate assembler for the Spin Semiconductor FV-1 DSP.
# This assembler aims to replicate some of the behaviour of
# the Spin FV-1 assembler in standard Python, for developers
# who are unable or unwilling to use the Spin provided IDE.
#
# It is based on information in the FV-1 datasheet and AN0001
# "Basics of the LFOs in the FV-1".
#
# There are some minor quirks:
#
#  - This assembler builds a single DSP program from a single
#    source file, and always outputs exactly 128 instructions.
#    If the program length is less than 128 instructions, the
#    remaining instruction slots are skipped with an explicit
#    SKP. Command line option -n (--noskip) will leave only
#    SKP 0,0 instructions.
#
#  - By default, immediate values that would overflow available
#    argument sizes will generate an error and abort assembly.
#    Command line option -c (--clamp) will instead restrict the
#    value, where possible, and issue a warning.
#
#  - Unlike the Spin assembler, non-sensical but othwerwise valid
#    arguments are assembled without error.
#
#  - Signed fixed point arguments (S1.14, S1.9, S.10) may be
#    entered using an unsigned integer equivalent value. This 
#    causes a conflict with SpinASM, when entries like -1 and 1
#    are interpreted differently depending on how they are used.
#    In asfv1, all operands are treated alike, so to specify
#    a real number, the decimal part is compulsory: Eg -1.0, 1.0.
#
#  - Real numbers differ very slightly from those in the
#    datasheet. Specifically:
#
#        Max S.23 0x7fffff = 0.9999998807907104
#        Max S.15   0x7fff = 0.999969482421875
#        Max S1.14  0x7fff = 1.99993896484375
#        Max S.10    0x3ff = 0.9990234375
#        Max S1.9    0x3ff = 1.998046875
#        Max S4.6    0x3ff = 15.984375
#
#  - Input is assumed to be utf-8 text.
#
#  - By default the output is written to an intel hex file at
#    offset 0x0000 (program 0). To select an alternate offset, 
#    command line option -p can select a target program from 0 to 7.
#    When output is set to binary with -b (--binary), the program
#    number option is ignored.
#
# For more information on the FV-1, refer to the Spin website:
#
#  Web Site: http://spinsemi.com/products.html
#  Datasheet: http://spinsemi.com/Products/datasheets/spn1001/FV-1.pdf
#  AN0001: http://spinsemi.com/Products/appnotes/spn1001/AN-0001.pdf
#
# To upload assembled DSP programs to the FV-1 development
# board using the Cypress USB connection, please see the
# related project fv1prog.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import sys
import shlex

# Constants
VERSION = '1.0.5'
PROGLEN = 128
DELAYSIZE = 32767
MAX_S1_14 = 1.99993896484375
MIN_S1_14 = -2.0
SZ_S1_14 = 16384.0
MAX_S1_9 = 1.998046875
MIN_S1_9 = -2.0
SZ_S1_9 = 512.0
MAX_S_10 = 0.9990234375
MIN_S_10 = -1.0
SZ_S_10 = 1024.0
MAX_S_15 = 0.999969482421875
MIN_S_15 = -1.0
SZ_S_15 = 32768.0
MAX_S4_6 = 15.984375
MIN_S4_6 = -16.0
SZ_S4_6 = 64.0
MAX_S_23 = 0.9999998807907104
MIN_S_23 = -1.0
SZ_S_23 = 8388608.0

# Bit Masks
M1 = 0x01
M2 = 0x03
M5 = 0x1f
M6 = 0x3f
M8 = 0xff
M9 = 0x1ff
M11 = 0x7ff
M14 = 0x3fff
M15 = 0x7fff
M16 = 0xffff
M24 = 0xffffff
M27 = 0x7ffffff

def quiet(msg):
    pass

def warning(msg):
    print(msg, file=sys.stderr)

def error(msg):
    print(msg, file=sys.stderr)

def tob32(val):
    """Return provided 32 bit value as a string of four bytes."""
    ret = bytearray(4)
    ret[0] = (val>>24)&M8
    ret[1] = (val>>16)&M8
    ret[2] = (val>>8)&M8
    ret[3] = val&M8
    return ret

def bintoihex(buf, spos=0x0000):
    """Convert binary buffer to ihex and return as string."""
    c = 0
    olen = len(buf)
    ret = ""
    # 16 byte lines
    while (c+0x10) <= olen:
        adr = c + spos
        l = ':10{0:04X}00'.format(adr)
        sum = 0x10+((adr>>8)&M8)+(adr&M8)
        for j in range(0,0x10):
            nb = buf[c+j]
            l += '{0:02X}'.format(nb)
            sum = (sum + nb)&M8
        l += '{0:02X}'.format((~sum+1)&M8)
        ret += l + '\n'
        c += 0x10
    # remainder
    if c < olen:
        rem = olen-c
        sum = rem
        adr = c + spos
        l = ':{0:02X}{1:04X}00'.format(rem,adr)   # rem < 0x10
        sum += ((adr>>8)&M8)+(adr&M8)
        for j in range(0,rem):
            nb = buf[c+j]
            l += '{0:02X}'.format(nb)
            sum = (sum + nb)&M8
        l += '{0:02X}'.format((~sum+1)&M8)
        ret += l + '\n'
    ret += ':00000001FF\n'        # EOF
    return ret

# Machine instruction table
op_tbl = {
	# mnemonic: [opcode, (arglen,left shift), ...]
	'SOF':  [0b01101, (M16,16),(M11,5)],
        'AND':  [0b01110, (M24,8)],
        'OR' :  [0b01111, (M24,8)],
        'XOR':  [0b10000, (M24,8)],
        'LOG':  [0b01011, (M16,16),(M11,5)],
	'EXP':  [0b01100, (M16,16),(M11,5)],
	'SKP':  [0b10001, (M5,27),(M6,21)],	# note 1
	'RDAX': [0b00100, (M6,5),(M16,16)],
        'WRAX': [0b00110, (M6,5),(M16,16)],
        'MAXX': [0b01001, (M6,5),(M16,16)],
        'MULX': [0b01010, (M6,5)],
        'RDFX': [0b00101, (M6,5),(M16,16)],
        'WRLX': [0b01000, (M6,5),(M16,16)],
        'WRHX': [0b00111, (M6,5),(M16,16)],
        'RDA':  [0b00000, (M15,5),(M11,21)],
        'RMPA': [0b00001, (M11,21)],
        'WRA':  [0b00010, (M15,5),(M11,21)],
        'WRAP': [0b00011, (M15,5),(M11,21)],
        'WLDS': [0b10010, (M1,29),(M9,20),(M15,5)],
        'WLDR': [0b10010, (M2,29),(M16,13),(M2,5)], # CHECK
        'JAM':  [0b10011, (M2,6)],
        'CHO':  [0b10100, (M2,30),(M2,21),(M6,24),(M16,5)], # CHECK
	'CLR':	[0b01110, (M24,8)], # pseudo: AND $0
	'NOT':	[0b10000, (M24,8)], # pseudo: XOR $ffffff
	'NOP':	[0b10001, (M27,5)], # pseudo: SKP 0,0 note 2
	'ABSA':	[0b01001, (M6,5),(M16,16)], # pseudo: MAXX $0,$0
	'LDAX':	[0b00101, (M6,5),(M16,16)], # psuedo: RDFX REG,$0
        'RAW':  [0b11111, (M27,5)],         # marking instruction
	# Notes:
	# 1. In SpinASM IDE , condition flags expand to shifted values,
        # 2. NOP is not documented, but expands to SKP 0,0 in SpinASM
}

def op_gen(mcode):
    """Generate a machine instruction using the op gen table."""
    gen = op_tbl[mcode[0]]
    ret = gen[0]	# opcode
    nargs = len(gen)
    i = 1
    while i < nargs:
        if i < len(mcode):	# or assume they are same len
            ret |= (mcode[i]&gen[i][0]) << gen[i][1]
        i += 1
    return ret

class fv1parse(object):
    def __init__(self, source=None, clamp=True, skip=False, wfunc=None):
        self.program = bytearray(512)
        self.doclamp = clamp
        self.doskip = skip
        self.dowarn = wfunc
        self.delaymem = 0
        self.prevline = 0
        self.sline = 0
        self.icnt = 0
        self.sym = None
        self.source = source.split('\n')
        self.linebuf = []
        self.pl = []	# parse list
        self.mem = {}	# delay memory
        self.jmptbl = { # jump table for skips
        }
        self.symtbl = {	# symbol table
		'SIN0_RATE':	0x00,
                'SIN0_RANGE':	0x01,
		'SIN1_RATE':	0x02,
		'SIN1_RANGE':	0x03,
		'RMP0_RATE':	0x04,
		'RMP0_RANGE':	0x05,
		'RMP1_RATE':	0x06,
		'RMP1_RANGE':	0x07,
		'POT0':		0x10,
		'POT1':		0x11,
		'POT2':		0x12,
		'ADCL':		0x14,
		'ADCR':		0x15,
		'DACL':		0x16,
		'DACR':		0x17,
		'ADDR_PTR':	0x18,
		'REG0':		0x20,
		'REG1':		0x21,
		'REG2':		0x22,
		'REG3':		0x23,
		'REG4':		0x24,
		'REG5':		0x25,
		'REG6':		0x26,
		'REG7':		0x27,
		'REG8':		0x28,
		'REG9':		0x29,
		'REG10':	0x2a,
		'REG11':	0x2b,
		'REG12':	0x2c,
		'REG13':	0x2d,
		'REG14':	0x2e,
		'REG15':	0x2f,
		'REG16':	0x30,
		'REG17':	0x31,
		'REG18':	0x32,
		'REG19':	0x33,
		'REG20':	0x34,
		'REG21':	0x35,
		'REG22':	0x36,
		'REG23':	0x37,
		'REG24':	0x38,
		'REG25':	0x39,
		'REG26':	0x3a,
		'REG27':	0x3b,
		'REG28':	0x3c,
		'REG29':	0x3d,
		'REG30':	0x3e,
		'REG31':	0x3f,
		'SIN0':		0x00,
		'SIN1':		0x01,
		'RMP0':		0x02,
		'RMP1':		0x03,
		'RDA':		0x00,
		'SOF':		0x02,
		'RDAL':		0x03,
		'SIN':		0x00,
		'COS':		0x01,
		'REG':		0x02,
		'COMPC':	0x04,
		'COMPA':	0x08,
		'RPTR2':	0x10,
		'NA':		0x20,
		'RUN':		0x10,
		'ZRC':		0x08,
		'ZRO':		0x04,
		'GEZ':		0x02,
		'NEG':		0x01,
        }

    def __mkopcodes__(self):
        """Convert the parse list into machine code for output."""
        proglen = len(self.pl)
        self.dowarn('info: Read {} instructions from input'.format(
                proglen))

        # pad free space with empty SKP instructions
        icnt = proglen
        while icnt < PROGLEN:
            self.pl.append({'cmd':['SKP',0x00,0x00],
                            'addr':icnt,
                            'target':None})
            icnt += 1
        
        # if required, skip over unused instructions
        if self.doskip:
            icnt = proglen
            while icnt < PROGLEN:
                skplen = PROGLEN - icnt - 1
                if skplen > 63:
                    skplen = 63
                # replace skp at icnt
                self.pl[icnt]={'cmd':['SKP',0x00,skplen],
                               'addr':icnt,
                               'target':None}
                icnt += skplen + 1

        # convert program to machine code and prepare for output
        cnt = 0
        for i in self.pl:
            oft = cnt * 4
            nop = tob32(op_gen(i['cmd']))
            self.program[oft] = nop[0]
            self.program[oft+1] = nop[1]
            self.program[oft+2] = nop[2]
            self.program[oft+3] = nop[3]
            cnt += 1

    def __register__(self):
        """Fetch a register definition."""
        reg = self.__expression__()
        if type(reg) is not int or reg < 0 or reg > 63:
            self.parseerror('Invalid register definition ' + repr(reg),
                            self.prevline)
        return reg

    def __offset__(self):
        """Fetch a skip offset definition."""
        oft = self.__expression__()
        if type(oft) is not int or oft < 0 or oft > M6:
            self.parseerror('Invalid skip offset ' + repr(oft),
                            self.prevline)
        return oft

    def __condition__(self):
        """Fetch a skip condition code."""
        cond = self.__expression__()
        if type(cond) is not int or cond < 0 or cond > M5:
            self.parseerror('Invalid skip condition code ' + repr(cond),
                            self.prevline)
        return cond

    def __choflags__(self, lfo=None):
        """Fetch CHO condition flags."""
        flags = self.__expression__()
        if type(flags) is not int or flags < 0 or flags > M6:
            self.parseerror('Invalid CHO condition flags ' + repr(flags),
                            self.prevline)
        oflags = flags
        if lfo&0x02: # RMP0/RMP1
            flags = oflags & 0x3e
            if oflags != flags:
                self.parsewarn('Cleared invalid Ramp LFO condition flags to: '
                                 + hex(flags), self.prevline)
        else:
            flags = oflags & 0x0f
            if oflags != flags:
                self.parsewarn('Cleared invalid Sine LFO condition flags to: '
                                 + hex(flags), self.prevline)
        return flags

    def __delayaddr__(self):
        """Fetch a delay line address."""
        oft = self.__expression__()
        if type(oft) is int:
            if oft < 0 or oft > M15:
                if self.doclamp:
                    if oft < 0:
                        oft = 0
                    elif oft > M15:
                        oft = M15
                    self.parsewarn('Delay line address clamped to ' + hex(oft),
                                   self.prevline)
                else:
                    self.parseerror('Invalid delay line address ' + hex(oft),
                                    self.prevline)
        else:
            self.parseerror('Invalid delay line address ' + repr(oft),
                            self.prevline)
        return oft

    def __s1_14__(self):
        """Fetch a 16 bit real argument."""
        arg = self.__expression__()
        if type(arg) is int:
            if arg < 0 or arg > M16:
                if self.doclamp:
                    if arg < 0:
                        arg = 0
                    elif arg > M16:
                        arg = M16
                    self.parsewarn('S1.14 arg clamped to ' + hex(arg),
                                   self.prevline)
                else:
                    self.parseerror('Invalid S1.14 arg ' + hex(arg),
                                    self.prevline)
        else:
            if arg < MIN_S1_14 or arg > MAX_S1_14:
                if self.doclamp:
                    if arg < MIN_S1_14:
                        arg = MIN_S1_14
                    elif arg > MAX_S1_14:
                        arg = MAX_S1_14
                    self.parsewarn('S1.14 arg clamped to ' + repr(arg),
                                   self.prevline)
                else:
                    self.parseerror('Invalid S1.14 arg ' + repr(arg),
                                    self.prevline)
            arg = int(arg * SZ_S1_14)
        return arg

    def __s_10__(self):
        """Fetch an 11 bit S.10 real argument."""
        arg = self.__expression__()
        if type(arg) is int:
            if arg < 0 or arg > M11:
                if self.doclamp:
                    if arg < 0:
                        arg = 0
                    elif arg > M11:
                        arg = M11
                    self.parsewarn('S.10 arg clamped to ' + hex(arg),
                                   self.prevline)
                else:
                    self.parseerror('Invalid S.10 arg ' + hex(arg),
                                    self.prevline)
        else:
            if arg < MIN_S_10 or arg > MAX_S_10:
                if self.doclamp:
                    if arg < MIN_S_10:
                        arg = MIN_S_10
                    elif arg > MAX_S_10:
                        arg = MAX_S_10
                    self.parsewarn('S.10 arg clamped to ' + repr(arg),
                                   self.prevline)
                else:
                    self.parseerror('Invalid S.10 arg ' + repr(arg),
                                    self.prevline)
            arg = int(arg * SZ_S_10)
        return arg

    def __s_15__(self):
        """Fetch a 16 bit S.15 real argument."""
        arg = self.__expression__()
        if type(arg) is int:
            if arg < 0 or arg > M16:
                if self.doclamp:
                    if arg < 0:
                        arg = 0
                    elif arg > M16:
                        arg = M16
                    self.parsewarn('S.15 arg clamped to ' + hex(arg),
                                   self.prevline)
                else:
                    self.parseerror('Invalid S.15 arg ' + hex(arg),
                                    self.prevline)
        else:
            if arg < MIN_S_15 or arg > MAX_S_15:
                if self.doclamp:
                    if arg < MIN_S_15:
                        arg = MIN_S_15
                    elif arg > MAX_S_15:
                        arg = MAX_S_15
                    self.parsewarn('S.15 arg clamped to ' + repr(arg),
                                   self.prevline)
                else:
                    self.parseerror('Invalid S.15 arg ' + repr(arg),
                                    self.prevline)
            arg = int(arg * SZ_S_15)
        return arg

    def __u_27__(self):
        """Fetch a raw 27 bit data string."""
        arg = self.__expression__()
        if type(arg) is int:
            if arg < 0 or arg > M27:
                if self.doclamp:
                    if arg < 0:
                        arg = 0
                    elif arg > M27:
                        arg = M27
                    self.parsewarn('U.27 arg clamped to ' + hex(arg),
                                   self.prevline)
                else:
                    self.parseerror('Invalid U.27 arg ' + hex(arg),
                                    self.prevline)
        else:
            self.parseerror('Invalid U.27 arg ' + hex(arg),
                            self.prevline)
        return arg

    def __s_23__(self):
        """Fetch a 24 bit S.23 real or mask argument."""
        arg = self.__expression__()
        if type(arg) is int:
            if arg < 0 or arg > M24:
                if self.doclamp:
                    if arg < 0:
                        arg = 0
                    elif arg > M24:
                        arg = M24
                    self.parsewarn('S.23 arg clamped to ' + hex(arg),
                                   self.prevline)
                else:
                    self.parseerror('Invalid S.23 arg ' + hex(arg),
                                    self.prevline)
        else:
            if arg < MIN_S_23 or arg > MAX_S_23:
                if self.doclamp:
                    if arg < MIN_S_23:
                        arg = MIN_S_23
                    elif arg > MAX_S_23:
                        arg = MAX_S_23
                    self.parsewarn('S.23 arg clamped to ' + repr(arg),
                                   self.prevline)
                else:
                    self.parseerror('Invalid S.23 arg ' + repr(arg),
                                    self.prevline)
            arg = int(arg * SZ_S_23)
        return arg

    def __s1_9__(self):
        """Fetch an 11 bit real argument."""
        arg = self.__expression__()
        if type(arg) is int:
            if arg < 0 or arg > M11:
                if self.doclamp:
                    if arg < 0:
                        arg = 0
                    elif arg > M11:
                        arg = M11
                    self.parsewarn('S1.9 arg clamped to ' + hex(arg),
                                   self.prevline)
                else:
                    self.parseerror('Invalid S1.9 arg ' + hex(arg),
                                    self.prevline)
        else:
            if arg < MIN_S1_9 or arg > MAX_S1_9:
                if self.doclamp:
                    if arg < MIN_S1_9:
                        arg = MIN_S1_9
                    elif arg > MAX_S1_9:
                        arg = MAX_S1_9
                    self.parsewarn('S1.9 arg clamped to ' + repr(arg),
                                   self.prevline)
                else:
                    self.parseerror('Invalid S1.9 arg ' + repr(arg),
                                    self.prevline)
            arg = int(arg * SZ_S1_9)
        return arg

    def __s4_6__(self):
        """Fetch an 11 bit S4.6 argument."""
        arg = self.__expression__()
        if type(arg) is int:
            if arg < 0 or arg > M11:
                if self.doclamp:
                    if arg < 0:
                        arg = 0
                    elif arg > M11:
                        arg = M11
                    self.parsewarn('S4.6 arg clamped to ' + hex(arg),
                                   self.prevline)
                else:
                    self.parseerror('Invalid S4.6 arg ' + hex(arg),
                                    self.prevline)
        else:
            if arg < MIN_S4_6 or arg > MAX_S4_6:
                if self.doclamp:
                    if arg < MIN_S4_6:
                        arg = MIN_S4_6
                    elif arg > MAX_S4_6:
                        arg = MAX_S4_6
                    self.parsewarn('S4.6 arg clamped to ' + repr(arg),
                                   self.prevline)
                else:
                    self.parseerror('Invalid S4.6 arg ' + repr(arg),
                                    self.prevline)
            arg = int(arg * SZ_S4_6)
        return arg

    def __lfo__(self):
        """Select an LFO."""
        # there is some ambiguity here - but it is resolved in
        # WLDS by clearing the MSB, and in WLDR by ORing with 0x2
        lfo = self.__expression__()
        if type(lfo) is not int or lfo < 0 or lfo > 3:
            self.parseerror('Invalid LFO definition ' + repr(lfo),
                            self.prevline)
        return lfo

    def __lfo_sinfreq__(self):
        """Fetch a sine LFO frequency value."""
        freq = self.__expression__()
        if type(freq) is int:
            if freq < 0 or freq > M9:
                if self.doclamp:
                    if freq < 0:
                        freq = 0
                    elif freq > M9:
                        freq = M9
                    self.parsewarn('Sine lfo frequency clamped to '
                                   + hex(freq), self.prevline)
                else:
                    self.parseerror('Invalid sine lfo frequency '
                                   + hex(freq), self.prevline)
        else:
            self.parseerror('Invalid sine lfo frequency '
                            + repr(freq), self.prevline)
        return freq

    def __lfo_rampfreq__(self):
        """Fetch a ramp LFO coefficient value."""
        freq = self.__expression__()
        if type(freq) is int:
            if freq < -16384 or freq > 32767:
                if self.doclamp:
                    if freq < -16384:
                        freq = -16384
                    elif freq > 32767:
                        freq = 32767
                    self.parsewarn('Ramp lfo coefficient clamped to '
                                   + repr(freq), self.prevline)
                else:
                    self.parseerror('Invalid ramp lfo coefficient '
                                   + repr(freq), self.prevline)
        else:
            self.parseerror('Invalid ramp lfo coefficient '
                            + repr(freq), self.prevline)
        return freq

    def __lfo_sinamp__(self):
        """Fetch a sine LFO amplitude value."""
        amp = self.__expression__()
        if type(amp) is int:
            if amp < 0 or amp > M15:
                if self.doclamp:
                    if amp < 0:
                        amp = 0
                    elif amp > M15:
                        amp = M15
                    self.parsewarn('Sine lfo amplitude clamped to ' + hex(amp),
                                   self.prevline)
                else:
                    self.parseerror('Invalid sine lfo amplitude ' + hex(amp),
                                    self.prevline)
        else:
            self.parseerror('Invalid sine lfo amplitude ' + repr(amp),
                            self.prevline)
        return amp

    def __lfo_rampamp__(self):
        """Fetch a ramp LFO amplitude value."""
        amp = self.__expression__()
        rampamps = {4096:0, 2048:1, 1024:2, 512:3, 0:0, 1:1, 2:2, 3:3}
        if type(amp) is int:
            if amp in rampamps:
                amp = rampamps[amp]
            else:
                self.parseerror('Invalid ramp lfo amplitude ' + repr(amp),
                                 self.prevline)
        else:
            self.parseerror('Invalid ramp lfo amplitude ' + repr(amp),
                            self.prevline)
        return amp

    def __next__(self):
        """Fetch next symbol."""
        self.sym = None
        self.prevline = self.sline	# line of last fetched symbol
        while self.sym is None:
            if len(self.linebuf) == 0:	# nothing in line buf yet
                if len(self.source) > 0:	# still some lines in source
                    self.sline += 1
                    llex = shlex.shlex(self.source.pop(0))
                    llex.commenters = ';'
                    self.linebuf = [t for t in llex]
                else:
                    self.sym = {'type': 'EOF', 'txt':None, 'val': 0x00}
            if len(self.linebuf) > 0:
                if self.linebuf[0] in op_tbl:	# MNEMONIC
                    self.sym = {'type': 'MNEMONIC',
                                'txt': self.linebuf.pop(0),
                                'val': 0x0}
                elif self.linebuf[0] in ['EQU', 'MEM']:
                    self.sym = {'type': 'ASSEMBLER',
                                'txt': self.linebuf.pop(0),
                                'val': 0x0}
                elif self.linebuf[0] in ['+','-','!','|']:
                    self.sym = {'type': 'OPERATOR',
                                'txt': self.linebuf.pop(0),
                                'val': 0x0}
                elif self.linebuf[0][0] in ['%', '$']:
                    # SpinASM style integers
                    pref = self.linebuf.pop(0)
                    base = 2
                    if pref == '$':
                        base = 16
                    if len(self.linebuf) > 0:
                        ht = self.linebuf.pop(0)
                        try:
                            ival = int(ht.replace('_',''),base)
                            self.sym = {'type': 'INTEGER',
                                        'txt': pref+ht,
                                        'val': ival}
                        except:
                            self.scanerror('Invalid integer literal '
                                    + repr(pref+ht))
                    else:
                        self.scanerror('End of line scanning for integer')
                elif self.linebuf[0][0].isdigit(): # INTEGER or FLOAT
                    intpart = self.linebuf.pop(0)
                    if len(self.linebuf) > 0 and self.linebuf[0] == '.':
                        self.linebuf.pop(0)
                        if len(self.linebuf) > 0:
                            frac = self.linebuf.pop(0)
                            try:
                                ival = float(intpart+'.'+frac)
                                self.sym = {'type': 'FLOAT',
                                            'txt': intpart+'.'+frac,
                                            'val': ival}
                            except:
                                self.scanerror('Invalid numeric literal '
                                        + repr(intpart+'.'+frac))
                        else:
                            self.scanerror('End of line scanning numeric')
                    else:	# assume integer
                        base = 10
                        if intpart.startswith('0X'):
                            base = 16
                        elif intpart.startswith('0B'):
                            base = 2
                        try:
                            ival = int(intpart, base)
                            self.sym = {'type': 'INTEGER',
                                        'txt': intpart,
                                        'val': ival}
                        except:
                            self.scanerror('Invalid integer literal '
                                    + repr(intpart))

                elif self.linebuf[0][0].isalpha(): # NAME or LABEL
                    lbl = self.linebuf.pop(0)
                    if len(self.linebuf) > 0 and self.linebuf[0] == ':':
                        self.sym = {'type': 'LABEL',
                                    'txt': lbl,
                                    'val': None}
                        self.linebuf.pop(0)
                    else:
                        mod = ''
                        if len(self.linebuf) > 0 and self.linebuf[0] in [
                                               '^','#']:
                            mod = self.linebuf.pop(0)
                        self.sym = {'type': 'NAME',
                                    'txt': lbl+mod,
                                    'val': 0x0}
                elif self.linebuf[0] == ',':	# ARGSEP
                    self.sym = {'type': 'ARGSEP',
                                'txt': self.linebuf.pop(0),
                                'val': 0x0}
                elif self.linebuf[0] == '\ufeff':
                    self.linebuf.pop(0) # ignore BOM
                else:
                    self.scanerror('Unrecognised input '
                                    + repr(self.linebuf.pop(0)))

    def scanerror(self, msg):
        """Emit scan error and abort assembly."""
        error('scan error: ' + msg + ' on line {}'.format(self.sline))
        sys.exit(-1)

    def parsewarn(self, msg, line=None):
        """Emit parse warning."""
        if line is None:
            line = self.sline
        self.dowarn('warning: ' + msg + ' on line {}'.format(line))

    def parseerror(self, msg, line=None):
        """Emit parse error and abort assembly."""
        if line is None:
            line = self.sline
        error('parse error: ' + msg + ' on line {}'.format(line))
        sys.exit(-2)

    def __accept__(self,stype):
        """Accept the next symbol if type stype."""
        if self.sym['type'] == stype:
            self.__next__()
        else:
            self.parseerror('Expected {} but saw {}/{}'.format(
                             stype, self.sym['type'], repr(self.sym['txt'])))

    def __instruction__(self):
        """Parse an instruction."""
        if self.icnt >= PROGLEN:
            self.parseerror('Maximum program length exceeded')
        mnemonic = self.sym['txt']
        self.__accept__('MNEMONIC')
        if mnemonic in ['AND', 'OR', 'XOR', ]:
            # accumulator commands, accept one 24 bit argument
            mask = self.__s_23__()
            self.pl.append({'cmd':[mnemonic, mask],'addr':self.icnt})
            self.icnt += 1
        elif mnemonic in ['SOF', 'EXP', ]:
            mult = self.__s1_14__()
            self.__accept__('ARGSEP')
            oft = self.__s_10__()
            self.pl.append({'cmd':[mnemonic, mult, oft], 'addr':self.icnt})
            self.icnt += 1
        elif mnemonic in ['LOG', ]:
            mult = self.__s1_14__()
            self.__accept__('ARGSEP')
            oft = self.__s4_6__()
            self.pl.append({'cmd':[mnemonic, mult, oft], 'addr':self.icnt})
            self.icnt += 1
        elif mnemonic in ['RDAX', 'WRAX', 'MAXX', 'RDFX', 'WRLX', 'WRHX',]:
            reg = self.__register__()
            self.__accept__('ARGSEP')
            mult = self.__s1_14__()
            self.pl.append({'cmd':[mnemonic, reg, mult], 'addr':self.icnt})
            self.icnt += 1
        elif mnemonic in ['MULX', ]:
            reg = self.__register__()
            self.pl.append({'cmd':[mnemonic, reg], 'addr':self.icnt})
            self.icnt += 1
        elif mnemonic == 'SKP':
            condition = self.__condition__()
            self.__accept__('ARGSEP')
            target = None
            offset = 0x00
            sourceline = self.sline
            if self.sym['type'] == 'NAME':
                target = self.sym['txt']
                self.__accept__('NAME')
            else:
                offset = self.__offset__()
            self.pl.append({'cmd':['SKP', condition, offset],
                            'target':target,
                            'addr':self.icnt,
                            'line':sourceline})
            self.icnt += 1
        elif mnemonic in ['RDA', 'WRA', 'WRAP',] :
            addr = self.__delayaddr__()
            self.__accept__('ARGSEP')
            mult = self.__s1_9__()
            self.pl.append({'cmd':[mnemonic, addr, mult], 'addr':self.icnt})
            self.icnt += 1
        elif mnemonic == 'RMPA':
            mult = self.__s1_9__()
            self.pl.append({'cmd':[mnemonic, mult], 'addr':self.icnt})
            self.icnt += 1
        elif mnemonic == 'WLDS':
            lfo = self.__lfo__()&0x01
            self.__accept__('ARGSEP')
            freq = self.__lfo_sinfreq__()
            self.__accept__('ARGSEP')
            amp = self.__lfo_sinamp__()
            self.pl.append({'cmd':[mnemonic, lfo, freq, amp],
                            'addr':self.icnt})
            self.icnt += 1
        elif mnemonic == 'WLDR':
            lfo = self.__lfo__()|0x02
            self.__accept__('ARGSEP')
            freq = self.__lfo_rampfreq__()
            self.__accept__('ARGSEP')
            amp = self.__lfo_rampamp__()
            self.pl.append({'cmd':[mnemonic, lfo, freq, amp],
                            'addr':self.icnt})
            self.icnt += 1
        elif mnemonic == 'CHO':
            if self.sym['type'] == 'MNEMONIC' or self.sym['txt'] in [
                                                 'SOF', 'RDA', 'RDAL']:
                chotype = self.symtbl[self.sym['txt']]
                self.__next__()
                self.__accept__('ARGSEP')
                lfo = self.__lfo__()
                flags = 0b000010
                arg = 0x00
                if chotype != 0x03:	# RDAL	 (dodgey)
                    self.__accept__('ARGSEP')
                    flags = self.__choflags__(lfo)
                    self.__accept__('ARGSEP')
                    if chotype == 0x00:	# RDA
                        arg = self.__delayaddr__()
                    else:		# SOF
                        arg = self.__s_15__()
                self.pl.append({'cmd':['CHO', chotype, lfo, flags, arg],
                                'addr':self.icnt})
                self.icnt += 1
        elif mnemonic == 'JAM':
            lfo = self.__lfo__()|0x02
            self.pl.append({'cmd':[mnemonic, lfo], 'addr':self.icnt})
            self.icnt += 1
        elif mnemonic == 'CLR':
            # pseudo command
            self.pl.append({'cmd':['AND', 0x00],'addr':self.icnt})
            self.icnt += 1
        elif mnemonic == 'NOT':
            # pseudo command XOR
            self.pl.append({'cmd':['XOR', 0xffffff],'addr':self.icnt})
            self.icnt += 1
        elif mnemonic == 'NOP':
            # pseudo command SKP 0,0
            self.pl.append({'cmd':['NOP', 0x0],'addr':self.icnt})
            self.icnt += 1
        elif mnemonic == 'ABSA':
            # pseudo command MAXX $0,$0
            self.pl.append({'cmd':['MAXX', 0x0, 0x0],'addr':self.icnt})
            self.icnt += 1
        elif mnemonic == 'LDAX':
            # pseudo command RDFX REG,$0
            reg = self.__register__()
            self.pl.append({'cmd':['RDFX', reg, 0x0],'addr':self.icnt})
            self.icnt += 1
        elif mnemonic == 'RAW':
            # marking instruction
            mark = self.__u_27__()
            self.pl.append({'cmd':['RAW', mark],'addr':self.icnt})
            self.icnt += 1
        else:
            self.parseerror('Unexpected instruction {}'.format(
                             repr(self.sym['txt'])))

    def __deref__(self, symbol):
        """Return a value defined in the symbol table."""
        seen = set()
        look = symbol
        while True:
            if look in seen: # should not be possible - check
                self.parseerror('Circular definition of symbol '
                                 + repr(symbol))
            if look in self.symtbl:
                look = self.symtbl[look]
                if type(look) is not str:
                    break
            else:
                self.parseerror('Value ' + repr(look) 
                      + ' undefined for symbol ' + repr(symbol))
            seen.add(symbol)
        return look

    def __expression__(self):
        """Parse an operand expression."""
        # ignore type and let python promote as required
        # expression ::= [+|-] term ( +|- term )*

        # Optional leading sign
        sign = '+'
        if self.sym['type'] == 'OPERATOR' and self.sym['txt'] in ['+','-']:
            sign = self.sym['txt']
            self.__next__()

        # First term
        acc = self.__term__()
        if sign == '-':
            acc = 0 - acc

        # Remaining terms
        while self.sym['type'] == 'OPERATOR' and self.sym['txt'] in ['+','-']:
            sign = self.sym['txt']
            self.__next__()
            nterm = self.__term__()
            if sign == '-':
                acc -= nterm
            else:
                acc += nterm
        return acc

    def __term__(self):
        """Parse an operand term."""
        # term ::= factor (| factor)*

        acc = self.__factor__()
        while self.sym['type'] == 'OPERATOR' and self.sym['txt'] == '|':
            self.__next__()
            nfact = self.__factor__()
            if type(acc) is float or type(nfact) is float:
                self.parseerror('Invalid bitwise operation on real value',
                                 self.prefline)
            acc |= nfact
        return acc

    def __factor__(self):
        """Parse an operand factor."""
        # factor ::= [!] immediate
        bitneg = False
        if self.sym['type'] == 'OPERATOR' and self.sym['txt'] == '!':
            bitneg = True
            self.__next__()
        ret = None
        if self.sym['type'] == 'NAME':
            stxt = self.sym['txt']
            if stxt in self.symtbl:
                ret = self.__deref__(stxt)
            else:
                self.parseerror('Undefined symbol ' + repr(stxt))
        elif self.sym['type'] in ['INTEGER', 'FLOAT']:
            ret = self.sym['val']
        else:
            self.parseerror('Expected IMMEDIATE but saw {}/{}'.format(
                              self.sym['type'], repr(self.sym['txt'])))
        self.__next__()

        if bitneg:
            if type(ret) is int:
                ret = ~ret
            else:
                self.parseerror('Invalid operand for negation',
                                 self.prevline)
        return ret

    def __label__(self):
        """Parse a label assignment."""
        if self.sym['type'] == 'LABEL':
            lbl = self.sym['txt']
            oft = self.icnt
            if lbl in self.jmptbl and oft != self.jmptbl[lbl]:
                self.parseerror('Label {} redefined'.format(lbl))
            self.jmptbl[lbl] = oft
            self.__next__()
        else:
            self.parseerror('Expected LABEL but saw {}/{}'.format(
                              self.sym['type'], repr(self.sym['txt'])))

    def __assembler__(self):
        """Parse mem or equ statement."""
        typ = None
        arg1 = None
        arg2 = None
        if self.sym['type'] == 'NAME':
            arg1 = self.sym['txt']
            self.__next__()
        if self.sym['type'] == 'ASSEMBLER':
            typ = self.sym['txt']
            self.__next__()
        else:
            self.parseerror('Expected EQU or MEM but saw {}/{}'.format(
                             self.sym['type'], repr(self.sym['txt'])))
        if arg1 is None:
            if self.sym['type'] == 'NAME':
                arg1 = self.sym['txt']
                self.__next__()
            else:
                self.parseerror('Expected NAME but saw {}/{}'.format(
                             self.sym['type'], repr(self.sym['txt'])))

        # strip the modifier and check for re-definition
        arg1 = arg1.rstrip('^#')
        if arg1 in self.symtbl:
            self.parsewarn('Symbol ' + repr(arg1) + ' re-defined')

        # then fetch the second argument
        arg2 = self.__expression__()
         
        # now process assembler directive
        if type(arg2) is str:
            if arg2 in self.symtbl:
                arg2 = self.symtbl[arg2]
            else:
                self.parseerror('Name {} undefined'.format(arg2))
        if typ == 'MEM':
            # check memory and assign the extra labels
            baseval = self.delaymem
            if type(arg2) is not int:
                self.parseerror('Memory ' + repr(arg1)
                                  + ' length ' + repr(arg2) 
                                  + ' not integer')
                
            if arg2 < 0 or arg2 > DELAYSIZE:	# not as in datasheet
                if self.doclamp:
                    if arg2 < 0:
                        arg2 = 0
                    elif arg2 > DELAYSIZE:
                        arg2 = DELAYSIZE
                else:
                    self.parseerror('Invalid memory size {}'.format(arg2))
            top = self.delaymem + arg2	# top ptr goes to largest addr+1
            if top > DELAYSIZE:
                self.parseerror(
                   'Delay memory exhausted:{} exceeds {} available'.format(
                          arg2, DELAYSIZE-self.delaymem))
            self.symtbl[arg1] = self.delaymem
            self.symtbl[arg1+'#'] = top
            self.symtbl[arg1+'^'] = self.delaymem+arg2//2
            self.delaymem = top + 1	# check this?
        else:
            self.symtbl[arg1] = arg2	# re-assign symbol table entry

    def parse(self):
        """Parse input."""
        self.__next__()
        while self.sym['type'] != 'EOF':
            if self.sym['type'] == 'LABEL':
                self.__label__()
            elif self.sym['type'] == 'MNEMONIC':
                self.__instruction__()
            elif self.sym['type'] == 'NAME' or self.sym['type'] == 'ASSEMBLER':
                self.__assembler__()
            else:
                self.parseerror('Unexpected input {}/{}'.format(
                                  self.sym['type'], repr(self.sym['txt'])))
        # patch skip targets if required
        for i in self.pl:
            if i['cmd'][0] == 'SKP':
                if i['target'] is not None:
                    if i['target'] in self.jmptbl:
                        iloc = i['addr']
                        dest = self.jmptbl[i['target']]
                        if dest > iloc:
                            oft = dest - iloc - 1
                            if oft > M6:
                                self.parseerror('Offset from SKP to ' 
                                                + repr(i['target'])
                                                + ' (' + hex(oft) 
                                                + ') too large',
                                                i['line'])
                            else:
                                i['cmd'][2] = oft
                        else:
                            self.parseerror('Target '
                                            + repr(i['target'])
                                            +' does not follow SKP',
                                            i['line'])
                    else:
                        self.parseerror('Undefined target for SKP ' 
                                        + repr(i['target']),
                                        i['line'])
                else:
                    pass	# assume offset is immediate
        self.__mkopcodes__()

def main():
    parser = argparse.ArgumentParser(
                description='Assemble a single FV-1 DSP program.')
    parser.add_argument('infile',
                        nargs='?',
                        type=argparse.FileType('r'),
                        help='program source file',
                        default=sys.stdin) 
    parser.add_argument('outfile',
                        nargs='?',
                        help='assembled output file',
                        default=sys.stdout) 
    parser.add_argument('-q', '--quiet',
                        action='store_true',
                        help='suppress warnings')
    parser.add_argument('-c', '--clamp',
                        action='store_true',
                        help='clamp out of range values without error')
    parser.add_argument('-n', '--noskip',
                        action='store_false',
                        help="don't skip unused instruction space")
    parser.add_argument('-p',
                        help='target program number (hex output)',
                        type=int, choices=range(0,8))
    parser.add_argument('-b', '--binary',
                        action='store_true',
                        help='write binary output instead of hex')
    args = parser.parse_args()
    dowarn = warning
    if args.quiet:
        dowarn = quiet
    dowarn('FV-1 Assembler v' + VERSION)
    dowarn('info: Reading input from ' + args.infile.name)
    inbuf = args.infile.buffer.read()
    encoding = 'utf-8'
    # check for BOM
    if len(inbuf) > 2 and inbuf[0] == 0xFF and inbuf[1] == 0xFE:
        dowarn('info: Input encoding set to UTF-16LE by BOM')
        encoding = 'utf-16le'
    elif len(inbuf) > 2 and inbuf[0] == 0xFE and inbuf[1] == 0xFF:
        dowarn('info: Input encoding set to UTF-16BE by BOM')
        encoding = 'utf-16be'
    # or assume windows encoded 'ANSI'
    elif len(inbuf) > 7 and inbuf[7] == 0x00:
        dowarn('info: Input encoding set to UTF-16LE')
        encoding = 'utf-16le'

    fp = fv1parse(inbuf.decode(encoding,'replace').upper(),
                  clamp=args.clamp, skip=args.noskip, wfunc=dowarn)
    fp.parse()
    
    ofile = None
    if args.outfile is sys.stdout:
        ofile = args.outfile.buffer
    else:
        try:
            ofile = open(args.outfile, 'wb')
        except Exception as e:
            error('error: writing output: ' + str(e))
            sys.exit(-1)
    if args.binary and ofile.isatty():
        args.binary = False
        dowarn('warning: Terminal output forced to hex')
    if args.binary:
        dowarn('info: Writing binary output to ' + ofile.name)
        ofile.write(fp.program)
    else:
        baseoft = 0
        if args.p is not None:
            baseoft = args.p * 512
            dowarn('info: Selected program {0} at offset 0x{1:04X}'.format(
                    args.p, baseoft))
        dowarn('info: Writing hex output to ' + ofile.name)
        ofile.write(bintoihex(fp.program, baseoft).encode('ASCII','ignore'))
    ofile.close()
if __name__ == '__main__':
    main()
