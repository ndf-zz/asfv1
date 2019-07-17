#!/usr/bin/python3
#
# asfv1: Alternate FV-1 Assembler
# Copyright (C) 2017-2019 Nathan Fraser
#
# An alternate assembler for the Spin Semiconductor FV-1 DSP.
# For more information on the FV-1, refer to the Spin website:
#
#  Web Site: http://spinsemi.com/products.html
#  Datasheet: http://spinsemi.com/Products/datasheets/spn1001/FV-1.pdf
#  AN0001: http://spinsemi.com/Products/appnotes/spn1001/AN-0001.pdf
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
import struct

# Constants
VERSION = '1.2.0'
PROGLEN = 128
DELAYSIZE = 32767

# Fixed point reals SN.D with one sign bit (S),
# N integer bits and D fractional bits:
#
#	REF_... reference value at +1.0: 2**D
#	MIN_... smallest real number: -2**(N+D)/2**D == -2**N
#	MAX_... largest real number: (2**(N+D)-1)/REF
#
REF_S1_14 = 2.0**14			# 16384.0
MIN_S1_14 = -2.0**1			# -2.0
MAX_S1_14 = (2.0**(1+14)-1.0)/REF_S1_14	# 1.99993896484375

REF_S1_9 = 2.0**9			# 512.0
MIN_S1_9 = -2.0**1			# -2.0
MAX_S1_9 = (2.0**(1+9)-1.0)/REF_S1_9	# 1.998046875

REF_S_10 = 2.0**10			# 1024.0
MIN_S_10 = -2.0**0			# -1.0
MAX_S_10 = (2.0**(0+10)-1.0)/REF_S_10	# 0.9990234375

REF_S_15 = 2.0**15			# 32768.0
MIN_S_15 = -2.0**0			# -1.0
MAX_S_15 = (2.0**(0+15)-1.0)/REF_S_15	# 0.999969482421875

REF_S4_6 = 2.0**6			# 64.0
MIN_S4_6 = -2.0**4			# -16.0
MAX_S4_6 = (2.0**(4+6)-1.0)/REF_S4_6	# 15.984375

REF_S_23 = 2.0**23			# 8388608.0
MIN_S_23 = -2.0**0			# -1.0
MAX_S_23 = (2.0**(0+23)-1.0)/REF_S_23	# 0.9999998807907104

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
M32 = 0xffffffff

def quiet(msg):
    pass

def warning(msg):
    print(msg, file=sys.stderr)

def error(msg):
    print(msg, file=sys.stderr)

def bintoihex(buf, spos=0x0000, width=4):
    """Convert binary buffer to ihex and return as string."""
    c = 0
    olen = len(buf)
    ret = ""
    while(c < olen):
        rem = olen-c
        if rem > width:
            rem = width
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
        c += rem
    ret += ':00000001FF\n'        # EOF
    return ret

# Machine instruction table
op_tbl = {
        # mnemonic: [opcode, (arglen,left shift), ...]
        'RDA':  [0b00000, (M15,5),(M11,21)],
        'RMPA': [0b00001, (M11,21)],
        'WRA':  [0b00010, (M15,5),(M11,21)],
        'WRAP': [0b00011, (M15,5),(M11,21)],
        'RDAX': [0b00100, (M6,5),(M16,16)],
        'RDFX': [0b00101, (M6,5),(M16,16)],
        'LDAX':	[0b00101, (M6,5),(M16,16)], # psuedo: RDFX REG,$0
        'WRAX': [0b00110, (M6,5),(M16,16)],
        'WRHX': [0b00111, (M6,5),(M16,16)],
        'WRLX': [0b01000, (M6,5),(M16,16)],
        'MAXX': [0b01001, (M6,5),(M16,16)],
        'ABSA':	[0b01001, (M6,5),(M16,16)], # pseudo: MAXX $0,$0
        'MULX': [0b01010, (M6,5)],
        'LOG':  [0b01011, (M16,16),(M11,5)],
        'EXP':  [0b01100, (M16,16),(M11,5)],
        'SOF':  [0b01101, (M16,16),(M11,5)],
        'AND':  [0b01110, (M24,8)],
        'CLR':	[0b01110, (M24,8)], # pseudo: AND $0
        'OR' :  [0b01111, (M24,8)],
        'XOR':  [0b10000, (M24,8)],
        'NOT':	[0b10000, (M24,8)], # pseudo: XOR $ffffff
        'SKP':  [0b10001, (M5,27),(M6,21)],	# note 1
        'NOP':	[0b10001, (M27,5)], # pseudo: SKP 0,0 note 2
        'WLDS': [0b10010, (M1,29),(M9,20),(M15,5)],
        'WLDR': [0b10010, (M2,29),(M16,13),(M2,5)], # CHECK
        'JAM':  [0b10011, (M2,6)],
        'CHO':  [0b10100, (M2,30),(M2,21),(M6,24),(M16,5)], # CHECK
        'RAW':  [0b00000, (M32,0)],         # direct data insertion
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
    def __init__(self, source=None, clamp=True, skip=False,
                 spinreals=False, wfunc=None):
        self.program = bytearray(512)
        self.doclamp = clamp
        self.doskip = skip
        self.spinreals = spinreals
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
        oft = 0
        for i in self.pl:
            struct.pack_into('>I', self.program, oft, op_gen(i['cmd']))
            oft += 4

    def __register__(self, mnemonic=''):
        """Fetch a register definition."""
        reg = self.__expression__()
        if type(reg) is not int or reg < 0 or reg > 63:
            xtra = ''
            if mnemonic:
                xtra = 'for ' + mnemonic + ': '
            self.parseerror('Invalid register definition ' + xtra + repr(reg))
        return reg

    def __offset__(self, mnemonic=''):
        """Fetch a skip offset definition."""
        xtra = ''
        if mnemonic:
            xtra = 'for ' + mnemonic + ': '
        oft = self.__expression__()
        if self.spinreals and type(oft) is float:
            oft = int(oft)
            self.parsewarn('Converted skip offset to integer '+xtra+repr(oft))
        if type(oft) is not int or oft < 0 or oft > M6:
            self.parseerror('Invalid skip offset ' + xtra + repr(oft))
        return oft

    def __condition__(self, mnemonic=''):
        """Fetch a skip condition code."""
        cond = self.__expression__()
        if type(cond) is not int or cond < 0 or cond > M5:
            xtra = ''
            if mnemonic:
                xtra = 'for ' + mnemonic + ': '
            self.parseerror('Invalid skip condition code '+xtra+repr(cond))
        return cond

    def __choflags__(self, lfo=None):
        """Fetch CHO condition flags."""
        flags = self.__expression__()
        if type(flags) is not int or flags < 0 or flags > M6:
            self.parseerror('Invalid condition flags for CHO: '+repr(flags))
        oflags = flags
        if lfo&0x02: # RMP0/RMP1
            flags = oflags & 0x3e
            if oflags != flags:
                self.parsewarn('Cleared invalid Ramp LFO flags for CHO: '
                                 + hex(flags))
        else:
            flags = oflags & 0x0f
            if oflags != flags:
                self.parsewarn('Cleared invalid Sine LFO flags for CHO: '
                                 + hex(flags))
        return flags

    def __s1_14__(self, mnemonic=''):
        """Fetch a 16 bit real argument."""
        xtra = ''
        if mnemonic:
            xtra = 'for ' + mnemonic + ': '
        arg = self.__expression__()
        if type(arg) is int:
            if arg < 0 or arg > M16:
                if self.doclamp:
                    if arg < 0:
                        arg = 0
                    elif arg > M16:
                        arg = M16
                    self.parsewarn('S1.14 arg clamped ' + xtra + hex(arg))
                else:
                    self.parseerror('Invalid S1.14 arg ' + xtra + hex(arg))
        else:
            if arg < MIN_S1_14 or arg > MAX_S1_14:
                if self.doclamp:
                    if arg < MIN_S1_14:
                        arg = MIN_S1_14
                    elif arg > MAX_S1_14:
                        arg = MAX_S1_14
                    self.parsewarn('S1.14 arg clamped ' + xtra + repr(arg))
                else:
                    self.parseerror('Invalid S1.14 arg ' + xtra + repr(arg))
            arg = int(round(arg * REF_S1_14))
        return arg

    def __s_10__(self, mnemonic=''):
        """Fetch an 11 bit S.10 real argument."""
        xtra = ''
        if mnemonic:
            xtra = 'for ' + mnemonic + ': '
        arg = self.__expression__()
        if type(arg) is int:
            if arg < 0 or arg > M11:
                if self.doclamp:
                    if arg < 0:
                        arg = 0
                    elif arg > M11:
                        arg = M11
                    self.parsewarn('S.10 arg clamped ' + xtra + hex(arg))
                else:
                    self.parseerror('Invalid S.10 arg ' + xtra + hex(arg))
        else:
            if arg < MIN_S_10 or arg > MAX_S_10:
                if self.doclamp:
                    if arg < MIN_S_10:
                        arg = MIN_S_10
                    elif arg > MAX_S_10:
                        arg = MAX_S_10
                    self.parsewarn('S.10 arg clamped ' + xtra + repr(arg))
                else:
                    self.parseerror('Invalid S.10 arg ' + xtra + repr(arg))
            arg = int(round(arg * REF_S_10))
        return arg

    def __s_15__(self, mnemonic=''):
        """Fetch a 16 bit S.15 real argument."""
        xtra = ''
        if mnemonic:
            xtra = 'for ' + mnemonic + ': '
        arg = self.__expression__()
        if type(arg) is int:
            if arg < 0 or arg > M16:
                if self.doclamp:
                    if arg < 0:
                        arg = 0
                    elif arg > M16:
                        arg = M16
                    self.parsewarn('S.15 arg clamped ' + xtra + hex(arg))
                else:
                    self.parseerror('Invalid S.15 arg ' + xtra + hex(arg))
        else:
            if arg < MIN_S_15 or arg > MAX_S_15:
                if self.doclamp:
                    if arg < MIN_S_15:
                        arg = MIN_S_15
                    elif arg > MAX_S_15:
                        arg = MAX_S_15
                    self.parsewarn('S.15 arg clamped ' + xtra + repr(arg))
                else:
                    self.parseerror('Invalid S.15 arg ' + xtra + repr(arg))
            arg = int(round(arg * REF_S_15))
        return arg

    def __u_32__(self, mnemonic=''):
        """Fetch a raw 32 bit data string."""
        xtra = ''
        if mnemonic:
            xtra = 'for ' + mnemonic + ': '
        arg = self.__expression__()
        if type(arg) is int:
            if arg < 0 or arg > M32:
                if self.doclamp:
                    if arg < 0:
                        arg = 0
                    elif arg > M32:
                        arg = M32
                    self.parsewarn('U.32 arg clamped ' + xtra + hex(arg))
                else:
                    self.parseerror('Invalid U.32 arg ' + xtra + hex(arg))
        else:
            self.parseerror('Invalid U.32 arg ' + xtra + repr(arg))
        return arg

    def __s_23__(self, mnemonic=''):
        """Fetch a 24 bit S.23 real or mask argument."""
        xtra = ''
        if mnemonic:
            xtra = 'for ' + mnemonic + ': '
        arg = self.__expression__()
        if type(arg) is int:
            if arg < 0 or arg > M24:
                if self.doclamp:
                    if arg < 0:
                        arg = 0
                    elif arg > M24:
                        arg = M24
                    self.parsewarn('S.23 arg clamped ' + xtra + hex(arg))
                else:
                    self.parseerror('Invalid S.23 arg ' + xtra + hex(arg))
        else:
            if arg < MIN_S_23 or arg > MAX_S_23:
                if self.doclamp:
                    if arg < MIN_S_23:
                        arg = MIN_S_23
                    elif arg > MAX_S_23:
                        arg = MAX_S_23
                    self.parsewarn('S.23 arg clamped ' + xtra + repr(arg))
                else:
                    self.parseerror('Invalid S.23 arg ' + xtra + repr(arg))
            arg = int(round(arg * REF_S_23))
        return arg

    def __s1_9__(self, mnemonic=''):
        """Fetch an 11 bit real argument."""
        xtra = ''
        if mnemonic:
            xtra = 'for ' + mnemonic + ': '
        arg = self.__expression__()
        if type(arg) is int:
            if arg < 0 or arg > M11:
                if self.doclamp:
                    if arg < 0:
                        arg = 0
                    elif arg > M11:
                        arg = M11
                    self.parsewarn('S1.9 arg clamped ' + xtra + hex(arg))
                else:
                    self.parseerror('Invalid S1.9 arg ' + xtra + hex(arg))
        else:
            if arg < MIN_S1_9 or arg > MAX_S1_9:
                if self.doclamp:
                    if arg < MIN_S1_9:
                        arg = MIN_S1_9
                    elif arg > MAX_S1_9:
                        arg = MAX_S1_9
                    self.parsewarn('S1.9 arg clamped ' + xtra + repr(arg))
                else:
                    self.parseerror('Invalid S1.9 arg ' + xtra + repr(arg))
            arg = int(round(arg * REF_S1_9))
        return arg

    def __s4_6__(self, mnemonic=''):
        """Fetch an 11 bit S4.6 argument."""
        xtra = ''
        if mnemonic:
            xtra = 'for ' + mnemonic + ': '
        arg = self.__expression__()
        if type(arg) is int:
            if arg < 0 or arg > M11:
                if self.doclamp:
                    if arg < 0:
                        arg = 0
                    elif arg > M11:
                        arg = M11
                    self.parsewarn('S4.6 arg clamped ' + xtra + hex(arg))
                else:
                    self.parseerror('Invalid S4.6 arg ' + xtra + hex(arg))
        else:
            if arg < MIN_S4_6 or arg > MAX_S4_6:
                if self.doclamp:
                    if arg < MIN_S4_6:
                        arg = MIN_S4_6
                    elif arg > MAX_S4_6:
                        arg = MAX_S4_6
                    self.parsewarn('S4.6 arg clamped ' + xtra + repr(arg))
                else:
                    self.parseerror('Invalid S4.6 arg ' + xtra + repr(arg))
            arg = int(round(arg * REF_S4_6))
        return arg

    def __lfo__(self, mnemonic=''):
        """Select an LFO."""
        # there is some ambiguity here - but it is resolved in
        # WLDS by clearing the MSB, and in WLDR by ORing with 0x2
        xtra = ''
        if mnemonic:
            xtra = 'for ' + mnemonic + ': '
        lfo = self.__expression__()
        if type(lfo) is not int or lfo < 0 or lfo > 3:
            self.parseerror('Invalid LFO definition ' + xtra + repr(lfo))
        return lfo

    def __lfo_sinfreq__(self, mnemonic=''):
        """Fetch a sine LFO frequency value."""
        xtra = ''
        if mnemonic:
            xtra = 'for ' + mnemonic + ': '
        freq = self.__expression__()
        if type(freq) is int:
            if freq < 0 or freq > M9:
                if self.doclamp:
                    if freq < 0:
                        freq = 0
                    elif freq > M9:
                        freq = M9
                    self.parsewarn('SIN LFO frequency clamped '
                                   + xtra + hex(freq))
                else:
                    self.parseerror('Invalid SIN LFO frequency '
                                   + xtra + hex(freq))
        else:
            self.parseerror('Invalid SIN LFO frequency ' + xtra + repr(freq))
        return freq

    def __lfo_rampfreq__(self, mnemonic=''):
        """Fetch a ramp LFO coefficient value."""
        xtra = ''
        if mnemonic:
            xtra = 'for ' + mnemonic + ': '
        freq = self.__expression__()
        if type(freq) is int:
            if freq < -16384 or freq > 32767:
                if self.doclamp:
                    if freq < -16384:
                        freq = -16384
                    elif freq > 32767:
                        freq = 32767
                    self.parsewarn('RMP LFO coefficient clamped '
                                   + xtra + repr(freq))
                else:
                    self.parseerror('Invalid RMP LFO coefficient '
                                   + xtra + repr(freq))
        else:
            self.parseerror('Invalid RMP LFO coefficient '+xtra+repr(freq))
        return freq

    def __lfo_sinamp__(self, mnemonic=''):
        """Fetch a SIN LFO amplitude value."""
        xtra = ''
        if mnemonic:
            xtra = 'for ' + mnemonic + ': '
        amp = self.__expression__()
        if type(amp) is int:
            if amp < 0 or amp > M15:
                if self.doclamp:
                    if amp < 0:
                        amp = 0
                    elif amp > M15:
                        amp = M15
                    self.parsewarn('SIN LFO amplitude clamped '+xtra+hex(amp))
                else:
                    self.parseerror('Invalid SIN LFO amplitude '+xtra+hex(amp))
        else:
            self.parseerror('Invalid SIN LFO amplitude ' +xtra+ repr(amp))
        return amp

    def __lfo_rampamp__(self, mnemonic=''):
        """Fetch a RMP LFO amplitude value."""
        xtra = ''
        if mnemonic:
            xtra = 'for ' + mnemonic + ': '
        amp = self.__expression__()
        rampamps = {4096:0, 2048:1, 1024:2, 512:3, 0:0, 1:1, 2:2, 3:3}
        if type(amp) is int:
            if amp in rampamps:
                amp = rampamps[amp]
            else:
                self.parseerror('Invalid RMP LFO amplitude '+xtra+repr(amp))
        else:
            self.parseerror('Invalid RMP LFO amplitude '+xtra+repr(amp))
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
                    self.sym = {'type': 'EOF', 'txt':None,
                                'stxt':None, 'val': 0x00}
            if len(self.linebuf) > 0:
                stxt = self.linebuf[0].upper()
                if stxt in op_tbl:	# MNEMONIC
                    self.sym = {'type': 'MNEMONIC',
                                'txt': self.linebuf.pop(0),
                                'stxt': stxt,
                                'val': 0x0}
                elif stxt in ['EQU', 'MEM']:
                    self.sym = {'type': 'ASSEMBLER',
                                'txt': self.linebuf.pop(0),
                                'stxt': stxt,
                                'val': 0x0}
                elif stxt in ['<','>','*','/']:
                    optxt = self.linebuf.pop(0)
                    if self.linebuf[0] == optxt: # **, //, <<, >>
                        optxt += self.linebuf.pop(0)
                    if optxt in ['<','>']:
                        self.scanerror('Invalid operator ' + repr(optxt))
                    self.sym = {'type': 'OPERATOR',
                                'txt': optxt,
                                'stxt': optxt,
                                'val': 0x0}
                elif stxt in ['|','^','&','+','-','~','(',')']:
                    self.sym = {'type': 'OPERATOR',
                                'txt': self.linebuf.pop(0),
                                'stxt': stxt,
                                'val': 0x0}
                elif stxt[0] in ['%', '$']:
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
                                        'stxt': pref+ht,
                                        'val': ival}
                        except:
                            self.scanerror('Invalid integer literal '
                                    + repr(pref+ht))
                    else:
                        self.scanerror('End of line scanning for integer')
                elif stxt[0].isdigit(): # INTEGER or FLOAT
                    intpart = self.linebuf.pop(0).lower()
                    if len(self.linebuf) > 0 and self.linebuf[0] == '.':
                        self.linebuf.pop(0)
                        if len(self.linebuf) > 0:
                            frac = self.linebuf.pop(0)
                            if frac.endswith('e'):
                                esign = self.linebuf.pop(0)
                                eval = self.linebuf.pop(0)
                                frac = frac+esign+eval
                            try:
                                ival = float(intpart+'.'+frac)
                                self.sym = {'type': 'FLOAT',
                                            'txt': intpart+'.'+frac,
                                            'stxt': intpart+'.'+frac,
                                            'val': ival}
                            except:
                                self.scanerror('Invalid numeric literal '
                                        + repr(intpart+'.'+frac))
                        else:
                            self.scanerror('End of line scanning numeric')
                    elif self.spinreals and intpart in ['2', '1']:
                        try:
                            ival = float(intpart)
                            self.sym = {'type': 'FLOAT',
                                        'stxt': intpart+'.0',
                                        'txt': intpart,
                                        'val': ival}
                        except:
                            self.scanerror('Invalid Spin real literal '
                                        + repr(intpart))
                    else:	# assume integer
                        base = 10
                        if intpart.startswith('0x'):
                            base = 16
                        elif intpart.startswith('0b'):
                            base = 2
                        try:
                            ival = int(intpart, base)
                            self.sym = {'type': 'INTEGER',
                                        'txt': intpart,
                                        'stxt': intpart,
                                        'val': ival}
                        except:
                            self.scanerror('Invalid integer literal '
                                    + repr(intpart))

                elif stxt[0].isalpha(): # NAME or LABEL
                    lbl = self.linebuf.pop(0)
                    if len(self.linebuf) > 0 and self.linebuf[0] == ':':
                        self.sym = {'type': 'LABEL',
                                    'txt': lbl,
                                    'stxt': stxt,
                                    'val': None}
                        self.linebuf.pop(0)
                    else:
                        mod = ''
                        if len(self.linebuf) > 0 and self.linebuf[0] in [
                                               '^','#']:
                            mod = self.linebuf.pop(0)
                        self.sym = {'type': 'NAME',
                                    'txt': lbl+mod,
                                    'stxt': stxt+mod,
                                    'val': 0x0}
                elif stxt == ',':	# ARGSEP
                    self.sym = {'type': 'ARGSEP',
                                'txt': self.linebuf.pop(0),
                                'stxt': stxt,
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
            line = self.prevline
        self.dowarn('warning: ' + msg + ' on line {}'.format(line))

    def parseerror(self, msg, line=None):
        """Emit parse error and abort assembly."""
        if line is None:
            line = self.prevline
        error('parse error: ' + msg + ' on line {}'.format(line))
        sys.exit(-2)

    def __accept__(self,stype,message=None):
        """Accept the next symbol if type matches stype."""
        if self.sym['type'] == stype:
            self.__next__()
        else:
            if message is not None:
                self.parseerror(message)
            else:
                self.parseerror('Expected {} but saw {}/{}'.format(
                             stype, self.sym['type'], repr(self.sym['txt'])),
                                 self.sline)

    def __instruction__(self):
        """Parse an instruction."""
        mnemonic = self.sym['stxt']
        opmsg = 'Missing required operand for '+mnemonic
        self.__accept__('MNEMONIC')
        if self.icnt >= PROGLEN:
            self.parseerror('Max program exceeded by {}'.format(mnemonic))
        if mnemonic in ['AND', 'OR', 'XOR', ]:
            # accumulator commands, accept one 24 bit argument
            mask = self.__s_23__(mnemonic)
            self.pl.append({'cmd':[mnemonic, mask],'addr':self.icnt})
            self.icnt += 1
        elif mnemonic in ['SOF', 'EXP', ]:
            mult = self.__s1_14__(mnemonic)
            self.__accept__('ARGSEP',opmsg)
            oft = self.__s_10__(mnemonic)
            self.pl.append({'cmd':[mnemonic, mult, oft], 'addr':self.icnt})
            self.icnt += 1
        elif mnemonic in ['LOG', ]:
            mult = self.__s1_14__(mnemonic)
            self.__accept__('ARGSEP',opmsg)
            oft = self.__s4_6__(mnemonic)
            self.pl.append({'cmd':[mnemonic, mult, oft], 'addr':self.icnt})
            self.icnt += 1
        elif mnemonic in ['RDAX', 'WRAX', 'MAXX', 'RDFX', 'WRLX', 'WRHX',]:
            reg = self.__register__(mnemonic)
            self.__accept__('ARGSEP',opmsg)
            mult = self.__s1_14__(mnemonic)
            self.pl.append({'cmd':[mnemonic, reg, mult], 'addr':self.icnt})
            self.icnt += 1
        elif mnemonic in ['MULX', ]:
            reg = self.__register__(mnemonic)
            self.pl.append({'cmd':[mnemonic, reg], 'addr':self.icnt})
            self.icnt += 1
        elif mnemonic == 'SKP':
            condition = self.__condition__(mnemonic)
            self.__accept__('ARGSEP',opmsg)
            target = None
            offset = 0x00
            sourceline = self.sline
            if self.sym['type'] == 'NAME':
                target = self.sym['stxt']
                self.__accept__('NAME')
            else:
                offset = self.__offset__(mnemonic)
            self.pl.append({'cmd':['SKP', condition, offset],
                            'target':target,
                            'addr':self.icnt,
                            'line':sourceline})
            self.icnt += 1
        elif mnemonic in ['RDA', 'WRA', 'WRAP',] :
            addr = self.__s_15__(mnemonic)	# allow float memory addr
            self.__accept__('ARGSEP',opmsg)
            mult = self.__s1_9__(mnemonic)
            self.pl.append({'cmd':[mnemonic, addr, mult], 'addr':self.icnt})
            self.icnt += 1
        elif mnemonic == 'RMPA':
            mult = self.__s1_9__(mnemonic)
            self.pl.append({'cmd':[mnemonic, mult], 'addr':self.icnt})
            self.icnt += 1
        elif mnemonic == 'WLDS':
            lfo = self.__lfo__(mnemonic)&0x01
            self.__accept__('ARGSEP',opmsg)
            freq = self.__lfo_sinfreq__(mnemonic)
            self.__accept__('ARGSEP',opmsg)
            amp = self.__lfo_sinamp__(mnemonic)
            self.pl.append({'cmd':[mnemonic, lfo, freq, amp],
                            'addr':self.icnt})
            self.icnt += 1
        elif mnemonic == 'WLDR':
            lfo = self.__lfo__()|0x02
            self.__accept__('ARGSEP',opmsg)
            freq = self.__lfo_rampfreq__(mnemonic)
            self.__accept__('ARGSEP',opmsg)
            amp = self.__lfo_rampamp__(mnemonic)
            self.pl.append({'cmd':[mnemonic, lfo, freq, amp],
                            'addr':self.icnt})
            self.icnt += 1
        elif mnemonic == 'CHO':
            if self.sym['type'] == 'MNEMONIC' or self.sym['stxt'] in [
                                                 'SOF', 'RDA', 'RDAL']:
                chotype = self.symtbl[self.sym['stxt']]
                self.__next__()
                self.__accept__('ARGSEP',opmsg)
                lfo = self.__lfo__(mnemonic)
                flags = 0b000010
                arg = 0x00
                if chotype != 0x03:
                    self.__accept__('ARGSEP',opmsg)
                    flags = self.__choflags__(lfo)
                    self.__accept__('ARGSEP',opmsg)
                    arg = self.__s_15__(mnemonic) # allow float memory addr
                else:
                    if self.sym['type'] == 'ARGSEP':
                        self.__accept__('ARGSEP')
                        flags = self.__choflags__(lfo)

                self.pl.append({'cmd':['CHO', chotype, lfo, flags, arg],
                                'addr':self.icnt})
                self.icnt += 1
        elif mnemonic == 'JAM':
            lfo = self.__lfo__(mnemonic)|0x02
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
            reg = self.__register__(mnemonic)
            self.pl.append({'cmd':['RDFX', reg, 0x0],'addr':self.icnt})
            self.icnt += 1
        elif mnemonic == 'RAW':
            # direct data insertion
            mark = self.__u_32__(mnemonic)
            self.pl.append({'cmd':['RAW', mark],'addr':self.icnt})
            self.icnt += 1
        else:
            self.parseerror('Unexpected instruction {}'.format(
                             repr(self.sym['txt'])))
        if self.sym['type'] == 'ARGSEP':
            self.parseerror('Excess operands for ' + mnemonic)

    def __deref__(self, symbol):
        """Return a value defined in the symbol table."""
        seen = set()
        look = symbol
        while True:
            if look in seen:
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
        acc = None
        try:
            acc = self.__xor_expr__()
            while self.sym['type'] == 'OPERATOR' and self.sym['stxt'] == '|':
                self.__next__()
                rarg = self.__xor_expr__()
                if type(acc) is int and type(rarg) is int:
                    acc |= rarg
                else:
                    self.parseerror('Invalid types for bitwise or (|)')
        except Exception as e:
            self.parseerror(str(e))
        return acc

    def __xor_expr__(self):
        """Parse an xor expression."""
        acc = self.__and_expr__()
        while self.sym['type'] == 'OPERATOR' and self.sym['stxt'] == '^':
            self.__next__()
            rarg = self.__and_expr__()
            if type(acc) is int and type(rarg) is int:
                acc ^= rarg
            else:
                self.parseerror('Invalid types for bitwise xor (^)')
        return acc

    def __and_expr__(self):
        """Parse an and expression."""
        acc = self.__shift_expr__()
        while self.sym['type'] == 'OPERATOR' and self.sym['stxt'] == '&':
            self.__next__()
            rarg = self.__shift_expr__()
            if type(acc) is int and type(rarg) is int:
                acc &= rarg
            else:
                self.parseerror('Invalid types for bitwise and (&)')
        return acc

    def __shift_expr__(self):
        """Parse a bitwise shift expression."""
        acc = self.__a_expr__()
        while self.sym['type']=='OPERATOR' and self.sym['stxt'] in ['<<','>>']:
            op = self.sym['stxt']
            self.__next__()
            rarg = self.__shift_expr__()
            if type(acc) is int and type(rarg) is int:
                if op == '<<':
                    acc <<= rarg
                else:
                    acc >>= rarg
            else:
                self.parseerror('Invalid types for shift ({})'.format(op))
        return acc

    def __a_expr__(self):
        """Parse an addition expression."""
        acc = self.__m_expr__()
        while self.sym['type']=='OPERATOR' and self.sym['stxt'] in ['+','-']:
            op = self.sym['stxt']
            self.__next__()
            if op == '+':
                acc += self.__m_expr__()
            else:
                acc -= self.__m_expr__()
        return acc

    def __m_expr__(self):
        """Parse a multiplication expression."""
        acc = self.__u_expr__()
        while self.sym['type']=='OPERATOR' and self.sym['stxt'] in [
                                                          '*','//','/']:
            op = self.sym['stxt']
            self.__next__()
            rarg = self.__u_expr__()
            if op == '*':
                acc *= rarg
            elif op == '//':
                acc //= rarg
            else:
                acc /= rarg
        return acc

    def __u_expr__(self):
        """Parse a unary operator."""
        acc = None
        if self.sym['type'] == 'OPERATOR' and self.sym['stxt'] in [
                                                     '+','-','~','!']:
            op = self.sym['stxt']
            self.__next__()
            acc = self.__u_expr__()
            if op == '-':
                acc = -acc
            elif op == '~' or op == '!':
                if type(acc) is int:
                    acc = ~acc
                else:
                    self.parseerror('Invalid type for unary {}'.format(op))
        else:
            acc = self.__power__()
        return acc

    def __power__(self):
        """Parse an exponent."""
        acc = self.__atom__()
        if self.sym['type'] == 'OPERATOR' and self.sym['stxt'] == '**':
            self.__next__()
            acc = acc ** self.__u_expr__()
        return acc

    def __atom__(self):
        """Parse an atom or start a new expression."""
        ret = None
        if self.sym['type'] == 'OPERATOR' and self.sym['txt'] == '(':
            self.__next__()
            ret = self.__expression__()
            if self.sym['type'] == 'OPERATOR' and self.sym['txt'] == ')':
                self.__next__()
            else:
                self.parseerror("Expected ')' but saw {}/{}".format(
                              self.sym['type'], repr(self.sym['txt'])))
        elif self.sym['type'] == 'NAME':
            stxt = self.sym['stxt']
            if stxt in self.symtbl:
                ret = self.__deref__(stxt)
                self.__next__()
            else:
                self.parseerror('Undefined symbol ' + repr(self.sym['txt']))
        elif self.sym['type'] in ['INTEGER', 'FLOAT']:
            ret = self.sym['val']
            self.__next__()
        else:
            self.parseerror('Expected name or value but saw {}/{}'.format(
                              self.sym['type'], repr(self.sym['txt'])))
        return ret

    def __label__(self):
        """Parse a label assignment."""
        if self.sym['type'] == 'LABEL':
            lbl = self.sym['stxt']
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
            arg1 = self.sym['stxt']
            self.__next__()
        if self.sym['type'] == 'ASSEMBLER':
            typ = self.sym['stxt']
            self.__next__()
        else:
            self.parseerror('Expected EQU or MEM but saw {}/{}'.format(
                             self.sym['type'], repr(self.sym['txt'])))
        if arg1 is None:
            if self.sym['type'] == 'NAME':
                arg1 = self.sym['stxt']
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
            if self.delaymem > DELAYSIZE:
                self.parseerror('Delay exhausted.',self.prevline)
            elif top > DELAYSIZE:
                self.parseerror(
            'Delay exhausted: requested {} exceeds {} available'.format(
                          arg2, DELAYSIZE-self.delaymem),self.prevline)
            self.symtbl[arg1] = self.delaymem
            self.symtbl[arg1+'#'] = top
            self.symtbl[arg1+'^'] = self.delaymem+arg2//2
            self.delaymem = top+1
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
                        type=argparse.FileType('r'),
                        help='program source file')
    parser.add_argument('outfile',
                        nargs='?',
                        help='assembled output file',
                        default=sys.stdout) 
    parser.add_argument('-q', '--quiet',
                        action='store_true',
                        help='suppress warnings')
    parser.add_argument('-v', '--version',
                        action='version',
                        help='print version',
                        version='%(prog)s ' + VERSION)
    parser.add_argument('-c', '--clamp',
                        action='store_true',
                        help='clamp out of range values without error')
    parser.add_argument('-n', '--noskip',
                        action='store_false',
                        help="don't skip unused instruction space")
    parser.add_argument('-s', '--spinreals',
                        action='store_true',
                        help="read literals 2 and 1 as 2.0 and 1.0")
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

    fp = fv1parse(inbuf.decode(encoding,'replace'),
                  clamp=args.clamp, skip=args.noskip,
                  spinreals=args.spinreals, wfunc=dowarn)
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
