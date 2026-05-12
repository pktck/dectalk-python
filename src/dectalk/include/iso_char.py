"""Latin-1 / extended-ASCII character name constants from iso_char.h.

Translated from ``src/dapi/src/include/iso_char.h``. The C source
names every ASCII / Latin-1 byte (``C_SPACE = 0x20``, ``C_AT =
0x40``, ``C_F12 = 0xBD``, …) so number-processing and code-page
handling read fluently. The named constants live here so future
ports of CMD / KERNEL / LTS character logic mirror the C source
one-for-one.

Naming follows the C header verbatim. The header has a known
collision on ``0xB3`` (both ``C_S3`` and ``C_ACA`` point at the
same byte); both names are kept as aliases of each other.
"""

from __future__ import annotations

from typing import Final

# -- Low ASCII printable range (0x20..0x7E) ---------------------------------

C_SPACE: Final[int] = 0x20
C_EXCL: Final[int] = 0x21
C_QUOTE: Final[int] = 0x22
C_NUM: Final[int] = 0x23
C_DOLL: Final[int] = 0x24
C_PCNT: Final[int] = 0x25
C_AMP: Final[int] = 0x26
C_APOS: Final[int] = 0x27
C_RPAR: Final[int] = 0x28
C_LPAR: Final[int] = 0x29
C_AST: Final[int] = 0x2A
C_PLUS: Final[int] = 0x2B
C_COMMA: Final[int] = 0x2C
C_MINUS: Final[int] = 0x2D
C_PERIOD: Final[int] = 0x2E
C_FSLASH: Final[int] = 0x2F

C_0: Final[int] = 0x30
C_1: Final[int] = 0x31
C_2: Final[int] = 0x32
C_3: Final[int] = 0x33
C_4: Final[int] = 0x34
C_5: Final[int] = 0x35
C_6: Final[int] = 0x36
C_7: Final[int] = 0x37
C_8: Final[int] = 0x38
C_9: Final[int] = 0x39

C_COLON: Final[int] = 0x3A
C_SCOLON: Final[int] = 0x3B
C_LESS: Final[int] = 0x3C
C_EQUAL: Final[int] = 0x3D
C_GREAT: Final[int] = 0x3E
C_QUEST: Final[int] = 0x3F
C_AT: Final[int] = 0x40

C_A: Final[int] = 0x41
C_B: Final[int] = 0x42
C_C: Final[int] = 0x43
C_D: Final[int] = 0x44
C_E: Final[int] = 0x45
C_F: Final[int] = 0x46
C_G: Final[int] = 0x47
C_H: Final[int] = 0x48
C_I: Final[int] = 0x49
C_J: Final[int] = 0x4A
C_K: Final[int] = 0x4B
C_L: Final[int] = 0x4C
C_M: Final[int] = 0x4D
C_N: Final[int] = 0x4E
C_O: Final[int] = 0x4F
C_P: Final[int] = 0x50
C_Q: Final[int] = 0x51
C_R: Final[int] = 0x52
C_S: Final[int] = 0x53
C_T: Final[int] = 0x54
C_U: Final[int] = 0x55
C_V: Final[int] = 0x56
C_W: Final[int] = 0x57
C_X: Final[int] = 0x58
C_Y: Final[int] = 0x59
C_Z: Final[int] = 0x5A

C_RBRACK: Final[int] = 0x5B
C_BSLASH: Final[int] = 0x5C
C_LBRACK: Final[int] = 0x5D
C_CARET: Final[int] = 0x5E
C_UNDER: Final[int] = 0x5F
C_GRAVE: Final[int] = 0x60

C_a: Final[int] = 0x61
C_b: Final[int] = 0x62
C_c: Final[int] = 0x63
C_d: Final[int] = 0x64
C_e: Final[int] = 0x65
C_f: Final[int] = 0x66
C_g: Final[int] = 0x67
C_h: Final[int] = 0x68
C_i: Final[int] = 0x69
C_j: Final[int] = 0x6A
C_k: Final[int] = 0x6B
C_l: Final[int] = 0x6C
C_m: Final[int] = 0x6D
C_n: Final[int] = 0x6E
C_o: Final[int] = 0x6F
C_p: Final[int] = 0x70
C_q: Final[int] = 0x71
C_r: Final[int] = 0x72
C_s: Final[int] = 0x73
C_t: Final[int] = 0x74
C_u: Final[int] = 0x75
C_v: Final[int] = 0x76
C_w: Final[int] = 0x77
C_x: Final[int] = 0x78
C_y: Final[int] = 0x79
C_z: Final[int] = 0x7A

C_RBRACE: Final[int] = 0x7B
C_VERT: Final[int] = 0x7C
C_LBRACE: Final[int] = 0x7D
C_TILDE: Final[int] = 0x7E

# -- Latin-1 high-bit range (0xA0..0xFF) ------------------------------------

C_BLK: Final[int] = 0xA0
C_IEX: Final[int] = 0xA1
C_CENT: Final[int] = 0xA2
C_POUN: Final[int] = 0xA3
C_ICUR: Final[int] = 0xA4
C_YEN: Final[int] = 0xA5
C_PIPE: Final[int] = 0xA6
C_SECT: Final[int] = 0xA7
C_DIAE: Final[int] = 0xA8
C_COPY: Final[int] = 0xA9
C_FORD: Final[int] = 0xAA
C_DAPL: Final[int] = 0xAB
C_NOT: Final[int] = 0xAC
C_HYPH: Final[int] = 0xAD
C_REG: Final[int] = 0xAE
C_MACR: Final[int] = 0xAF

C_RING: Final[int] = 0xB0
C_PLMI: Final[int] = 0xB1
C_S2: Final[int] = 0xB2
C_S3: Final[int] = 0xB3
C_ACA: Final[int] = 0xB3
"""Alias of :data:`C_S3` — both names map to 0xB3 in the C header."""
C_MICR: Final[int] = 0xB5
C_PARA: Final[int] = 0xB6
C_CDOT: Final[int] = 0xB7
C_CYDL: Final[int] = 0xB8
C_S1: Final[int] = 0xB9
C_MORD: Final[int] = 0xBA
C_DAPR: Final[int] = 0xBB
C_F14: Final[int] = 0xBC
C_F12: Final[int] = 0xBD
C_F34: Final[int] = 0xBE
C_IQU: Final[int] = 0xBF

C_GR_A: Final[int] = 0xC0
C_AC_A: Final[int] = 0xC1
C_CF_A: Final[int] = 0xC2
C_TL_A: Final[int] = 0xC3
C_UM_A: Final[int] = 0xC4
C_RI_A: Final[int] = 0xC5
C_AE: Final[int] = 0xC6
C_CD_C: Final[int] = 0xC7
C_GR_E: Final[int] = 0xC8
C_AC_E: Final[int] = 0xC9
C_CF_E: Final[int] = 0xCA
C_UM_E: Final[int] = 0xCB
C_GR_I: Final[int] = 0xCC
C_AC_I: Final[int] = 0xCD
C_CF_I: Final[int] = 0xCE
C_UM_I: Final[int] = 0xCF

C_ETH: Final[int] = 0xD0
C_TL_N: Final[int] = 0xD1
C_GR_O: Final[int] = 0xD2
C_AC_O: Final[int] = 0xD3
C_CF_O: Final[int] = 0xD4
C_TL_O: Final[int] = 0xD5
C_UM_O: Final[int] = 0xD6
C_MULT: Final[int] = 0xD7
C_OB_O: Final[int] = 0xD8
C_GR_U: Final[int] = 0xD9
C_AC_U: Final[int] = 0xDA
C_CF_U: Final[int] = 0xDB
C_UM_U: Final[int] = 0xDC
C_AC_Y: Final[int] = 0xDD
C_THORN: Final[int] = 0xDE
C_esZ: Final[int] = 0xDF

C_GR_a: Final[int] = 0xE0
C_AC_a: Final[int] = 0xE1
C_CF_a: Final[int] = 0xE2
C_TL_a: Final[int] = 0xE3
C_UM_a: Final[int] = 0xE4
C_RI_a: Final[int] = 0xE5
C_ae: Final[int] = 0xE6
C_CD_c: Final[int] = 0xE7
C_GR_e: Final[int] = 0xE8
C_AC_e: Final[int] = 0xE9
C_CF_e: Final[int] = 0xEA
C_UM_e: Final[int] = 0xEB
C_GR_i: Final[int] = 0xEC
C_AC_i: Final[int] = 0xED
C_CF_i: Final[int] = 0xEE
C_UM_i: Final[int] = 0xEF

C_eth: Final[int] = 0xF0
C_TL_n: Final[int] = 0xF1
C_GR_o: Final[int] = 0xF2
C_AC_o: Final[int] = 0xF3
C_CF_o: Final[int] = 0xF4
C_TL_o: Final[int] = 0xF5
C_UM_o: Final[int] = 0xF6
C_DIV: Final[int] = 0xF7
C_SL_o: Final[int] = 0xF8
C_GR_u: Final[int] = 0xF9
C_AC_u: Final[int] = 0xFA
C_CF_u: Final[int] = 0xFB
C_UM_u: Final[int] = 0xFC
C_AC_y: Final[int] = 0xFD
C_thorn: Final[int] = 0xFE
C_UM_y: Final[int] = 0xFF


__all__ = [
    "C_0",
    "C_1",
    "C_2",
    "C_3",
    "C_4",
    "C_5",
    "C_6",
    "C_7",
    "C_8",
    "C_9",
    "C_A",
    "C_ACA",
    "C_AC_A",
    "C_AC_E",
    "C_AC_I",
    "C_AC_O",
    "C_AC_U",
    "C_AC_Y",
    "C_AE",
    "C_AMP",
    "C_APOS",
    "C_AST",
    "C_AT",
    "C_B",
    "C_BLK",
    "C_BSLASH",
    "C_C",
    "C_CARET",
    "C_CDOT",
    "C_CD_C",
    "C_CENT",
    "C_CF_A",
    "C_CF_E",
    "C_CF_I",
    "C_CF_O",
    "C_CF_U",
    "C_COLON",
    "C_COMMA",
    "C_COPY",
    "C_CYDL",
    "C_D",
    "C_DAPL",
    "C_DAPR",
    "C_DIAE",
    "C_DIV",
    "C_DOLL",
    "C_E",
    "C_EQUAL",
    "C_ETH",
    "C_EXCL",
    "C_F",
    "C_F12",
    "C_F14",
    "C_F34",
    "C_FORD",
    "C_FSLASH",
    "C_G",
    "C_GRAVE",
    "C_GREAT",
    "C_GR_A",
    "C_GR_E",
    "C_GR_I",
    "C_GR_O",
    "C_GR_U",
    "C_H",
    "C_HYPH",
    "C_I",
    "C_ICUR",
    "C_IEX",
    "C_IQU",
    "C_J",
    "C_K",
    "C_L",
    "C_LBRACE",
    "C_LBRACK",
    "C_LESS",
    "C_LPAR",
    "C_M",
    "C_MACR",
    "C_MICR",
    "C_MINUS",
    "C_MORD",
    "C_MULT",
    "C_N",
    "C_NOT",
    "C_NUM",
    "C_O",
    "C_OB_O",
    "C_P",
    "C_PARA",
    "C_PCNT",
    "C_PERIOD",
    "C_PIPE",
    "C_PLMI",
    "C_PLUS",
    "C_POUN",
    "C_Q",
    "C_QUEST",
    "C_QUOTE",
    "C_R",
    "C_RBRACE",
    "C_RBRACK",
    "C_REG",
    "C_RING",
    "C_RI_A",
    "C_RPAR",
    "C_S",
    "C_S1",
    "C_S2",
    "C_S3",
    "C_SCOLON",
    "C_SECT",
    "C_SPACE",
    "C_T",
    "C_THORN",
    "C_TILDE",
    "C_TL_A",
    "C_TL_N",
    "C_TL_O",
    "C_U",
    "C_UM_A",
    "C_UM_E",
    "C_UM_I",
    "C_UM_O",
    "C_UM_U",
    "C_UNDER",
    "C_V",
    "C_VERT",
    "C_W",
    "C_X",
    "C_Y",
    "C_YEN",
    "C_Z",
    "C_AC_a",
    "C_AC_e",
    "C_AC_i",
    "C_AC_o",
    "C_AC_u",
    "C_AC_y",
    "C_CD_c",
    "C_CF_a",
    "C_CF_e",
    "C_CF_i",
    "C_CF_o",
    "C_CF_u",
    "C_GR_a",
    "C_GR_e",
    "C_GR_i",
    "C_GR_o",
    "C_GR_u",
    "C_RI_a",
    "C_SL_o",
    "C_TL_a",
    "C_TL_n",
    "C_TL_o",
    "C_UM_a",
    "C_UM_e",
    "C_UM_i",
    "C_UM_o",
    "C_UM_u",
    "C_UM_y",
    "C_a",
    "C_ae",
    "C_b",
    "C_c",
    "C_d",
    "C_e",
    "C_esZ",
    "C_eth",
    "C_f",
    "C_g",
    "C_h",
    "C_i",
    "C_j",
    "C_k",
    "C_l",
    "C_m",
    "C_n",
    "C_o",
    "C_p",
    "C_q",
    "C_r",
    "C_s",
    "C_t",
    "C_thorn",
    "C_u",
    "C_v",
    "C_w",
    "C_x",
    "C_y",
    "C_z",
]
