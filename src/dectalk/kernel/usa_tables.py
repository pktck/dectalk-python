"""Per-byte character pronunciation table for US English.

Translated from ``src/dapi/src/include/usa_type.tab`` (included by
``src/dapi/src/kernel/usa.c``). When DECtalk needs to "say a character
by name" — when spelling out a word, reading a non-letter symbol, or
in math-mode — it indexes into this 256-entry array by byte value to
get the spoken pronunciation.

The strings use DECtalk's "ASCII phoneme" representation, where each
ASCII glyph stands for a phoneme/marker:

- ``'`` primary stress
- `` ` `` secondary stress
- ``#`` clause boundary
- ``*`` syllable boundary
- ``|`` word-internal phoneme separator
- ``:`` upper-case prefix (says "capital")
- Letters/digits map to specific phonemes (e.g. ``A`` = AY, ``^`` = AH,
  ``E`` = EH, ``i`` = IY, ``W`` = AA, ``y`` = Y consonant).

Empty strings mean the byte is silent (e.g. NUL, most control
characters, undefined latin-1 codepoints).

This is a parity table — the strings are copied byte-for-byte from
the C source. The DECtalk-ASCII format is not interpreted here; that
job belongs to the LTS engine that reads these strings during
character-by-character pronunciation.
"""

from __future__ import annotations

from typing import Final

# 256-entry array indexed by byte value 0..255.
# Translated verbatim from usa_type.tab.

usa_type: Final[tuple[str, ...]] = (
    "n'^l",  # 0x00 NUL
    "",  # 0x01
    "",  # 0x02
    "",  # 0x03
    "",  # 0x04
    "",  # 0x05
    "",  # 0x06
    "b'El",  # 0x07 BEL
    "b'@k*spes",  # 0x08 BS
    "t@b",  # 0x09 HT
    "l'An*fid",  # 0x0A LF
    "v'Rt|kL*t@b",  # 0x0B VT
    "f'crm*fid",  # 0x0C FF
    "'EntR",  # 0x0D CR
    "",  # 0x0E
    "",  # 0x0F
    "",  # 0x10
    "",  # 0x11
    "",  # 0x12
    "",  # 0x13
    "",  # 0x14
    "",  # 0x15
    "",  # 0x16
    "",  # 0x17
    "",  # 0x18
    "",  # 0x19
    "",  # 0x1A
    "",  # 0x1B
    "|sk'ep",  # 0x1C ESC
    "",  # 0x1D
    "",  # 0x1E
    "",  # 0x1F
    "sp'es",  # 0x20 space
    "Eksklxm'eSxn pOnt",  # 0x21 !
    "kw'ot",  # 0x22 "
    "n'^mbR sAn",  # 0x23 #
    "d'alR",  # 0x24 $
    "pRs'Ent",  # 0x25 %
    "'@nd",  # 0x26 &
    "xp'astrxf`i",  # 0x27 '
    "l'Eft pR`EnTxs|s",  # 0x28 (
    "r'At pR`EnTxs|s",  # 0x29 )
    "'@stR|sk",  # 0x2A *
    "+",  # 0x2B (literal "+" — handled as a phoneme/control elsewhere)
    "k'amx",  # 0x2C ,
    "d'@S",  # 0x2D -
    "p'irixd",  # 0x2E .
    "sl'@S",  # 0x2F /
    "z'iro",  # 0x30 0
    "w'^n",  # 0x31 1
    "t'u",  # 0x32 2
    "Tr'i",  # 0x33 3
    "f'or",  # 0x34 4
    "f'Av",  # 0x35 5
    "s'Iks",  # 0x36 6
    "s'Evxn",  # 0x37 7
    "'et",  # 0x38 8
    "n'An",  # 0x39 9
    "k'olxn",  # 0x3A :
    "s'Emi#kolxn",  # 0x3B ;
    "l'Eft `@GgL#br@k|t",  # 0x3C <
    "'ikwLz",  # 0x3D =
    "r'At `@GgL#br@k|t",  # 0x3E >
    "kw'EsCxn mark",  # 0x3F ?
    "'@t",  # 0x40 @
    ":'e",  # 0x41 A
    ":b'i",  # 0x42 B
    ":s'i",  # 0x43 C
    ":d'i",  # 0x44 D
    ":'i",  # 0x45 E
    ":'Ef",  # 0x46 F
    ":J'i",  # 0x47 G
    ":'eC",  # 0x48 H
    ":'A",  # 0x49 I
    ":J'e",  # 0x4A J
    ":k'e",  # 0x4B K
    ":'El",  # 0x4C L
    ":'Em",  # 0x4D M
    ":'En",  # 0x4E N
    ":'o",  # 0x4F O
    ":p'i",  # 0x50 P
    ":k'Y",  # 0x51 Q
    ":'ar",  # 0x52 R
    ":'Es",  # 0x53 S
    ":t'i",  # 0x54 T
    ":y'u",  # 0x55 U
    ":v'i",  # 0x56 V
    ":d'^bL*yu",  # 0x57 W
    ":'Eks",  # 0x58 X
    ":w'A",  # 0x59 Y
    ":z'i",  # 0x5A Z
    "l'Eft skw'Er#br`@k|t",  # 0x5B [
    "b'@ksl`@S",  # 0x5C \
    "r'At skw'Er#br`@k|t",  # 0x5D ]
    "k'Erxt",  # 0x5E ^
    "'^ndRskor",  # 0x5F _
    "`@ksEnt gr'av",  # 0x60 `
    "'e",  # 0x61 a
    "b'i",  # 0x62 b
    "s'i",  # 0x63 c
    "d'i",  # 0x64 d
    "'i",  # 0x65 e
    "'Ef",  # 0x66 f
    "J'i",  # 0x67 g
    "'eC",  # 0x68 h
    "'A",  # 0x69 i
    "J'e",  # 0x6A j
    "k'e",  # 0x6B k
    "'El",  # 0x6C l
    "'Em",  # 0x6D m
    "'En",  # 0x6E n
    "'o",  # 0x6F o
    "p'i",  # 0x70 p
    "k'Y",  # 0x71 q
    "'ar",  # 0x72 r
    "'Es",  # 0x73 s
    "t'i",  # 0x74 t
    "y'u",  # 0x75 u
    "v'i",  # 0x76 v
    "d'^bL*yu",  # 0x77 w
    "'Eks",  # 0x78 x
    "w'A",  # 0x79 y
    "z'i",  # 0x7A z
    "l'Eft k'Rli#br`@k|t",  # 0x7B {
    "v'Rt|kL b'ar",  # 0x7C |
    "r'At k'Rli#br`@k|t",  # 0x7D }
    "t'Ildx",  # 0x7E ~
    "",  # 0x7F DEL
    "y'uro",  # 0x80 euro
    "",  # 0x81
    "",  # 0x82
    "",  # 0x83
    "",  # 0x84
    "",  # 0x85
    "",  # 0x86
    "",  # 0x87
    "",  # 0x88
    "",  # 0x89
    "",  # 0x8A
    "",  # 0x8B
    "",  # 0x8C
    "",  # 0x8D
    "",  # 0x8E
    "",  # 0x8F
    "",  # 0x90
    "",  # 0x91
    "",  # 0x92
    "",  # 0x93
    "",  # 0x94
    "",  # 0x95
    "",  # 0x96
    "",  # 0x97
    "",  # 0x98
    "",  # 0x99
    "",  # 0x9A
    "",  # 0x9B
    "",  # 0x9C
    "",  # 0x9D
    "",  # 0x9E
    "",  # 0x9F
    "",  # 0xA0 NBSP
    "|nv'Rt|d Eksklxm'eS|n pOnt",  # 0xA1 inverted !
    "s'Ent",  # 0xA2 cent
    "p'Wnd",  # 0xA3 pound
    "",  # 0xA4 currency
    "y'En",  # 0xA5 yen
    "br'okxn b'ar",  # 0xA6 broken bar
    "s'EkS|n",  # 0xA7 section
    "",  # 0xA8 diaeresis
    "k'api*rAt",  # 0xA9 (c)
    "f'Em|n|n 'ord|nL",  # 0xAA feminine ordinal
    "'opxn '@GgL kw'ot",  # 0xAB
    "n'at",  # 0xAC not
    "s'cft h'Afxn",  # 0xAD soft hyphen
    "r'EJ|stxrd tr'edm`ark",  # 0xAE (R)
    "m'@krxn",  # 0xAF macron
    "d|gr'i",  # 0xB0 degree
    "pl'^s or m'An|s",  # 0xB1 plus/minus
    "s'upRskrIpt t'u",  # 0xB2 superscript 2
    "s'upRskrIpt Tr'i",  # 0xB3 superscript 3
    "xky'ut",  # 0xB4 acute
    "m'Akro",  # 0xB5 micro
    "p'erxgr@f",  # 0xB6 paragraph
    "d'at",  # 0xB7 middle dot
    "sxd'Ilx",  # 0xB8 cedilla
    "s'upRskrIp w'^n",  # 0xB9 superscript 1
    "",  # 0xBA masculine ordinal
    "kl'oz '@GgL kw'ot",  # 0xBB
    "w^n kw'ortR",  # 0xBC 1/4
    "w^n h'@f",  # 0xBD 1/2
    "Tri kw'ortRz",  # 0xBE 3/4
    "|nv'Rt|d kw'EsC|n mark",  # 0xBF inverted ?
    ":'e gr'av",  # 0xC0 A grave
    ":'e xk'Yt",  # 0xC1 A acute
    ":'e s'RkxmflEks",  # 0xC2 A circumflex
    ":'e t'Ildx",  # 0xC3 A tilde
    ":'e 'umlWt",  # 0xC4 A umlaut
    ":'@Ggstrxm",  # 0xC5 A ring
    ":'e 'i l'IgxCR",  # 0xC6 AE
    ":s'i s|d'Ilx",  # 0xC7 C cedilla
    ":'i gr'av",  # 0xC8 E grave
    ":'i xk'Yt",  # 0xC9 E acute
    ":'i s'RkxmflEks",  # 0xCA E circumflex
    ":'i 'umlWt",  # 0xCB E umlaut
    ":'A gr'av",  # 0xCC I grave
    ":'A xk'Yt",  # 0xCD I acute
    ":'A s'RkxmflEks",  # 0xCE I circumflex
    ":'A 'umlWt",  # 0xCF I umlaut
    ":'ET",  # 0xD0 ETH
    ":'En t'Ildx",  # 0xD1 N tilde
    ":'o gr'av",  # 0xD2 O grave
    ":'o xk'Yt",  # 0xD3 O acute
    ":'o s'RkxmflEks",  # 0xD4 O circumflex
    ":'o t'Ildx",  # 0xD5 O tilde
    ":'o 'umlWt",  # 0xD6 O umlaut
    "",  # 0xD7 multiply
    ":'o sl'@S",  # 0xD8 O slash
    ":'Y gr'av",  # 0xD9 U grave
    ":'Y xk'Yt",  # 0xDA U acute
    ":'Y s'RkxmflEks",  # 0xDB U circumflex
    ":'Y 'umlWt",  # 0xDC U umlaut
    ":w'A xky'ut",  # 0xDD Y acute
    ":T'crn",  # 0xDE thorn
    "S'arp#'Es",  # 0xDF eszett
    "'e gr'av",  # 0xE0 a grave
    "'e xk'Yt",  # 0xE1 a acute
    "'e s'RkxmflEks",  # 0xE2 a circumflex
    "'e t'Ildx",  # 0xE3 a tilde
    "'e 'umlWt",  # 0xE4 a umlaut
    "'@Ggstrxm",  # 0xE5 a ring
    "'e 'i l'IgxCR",  # 0xE6 ae
    "s'i s|d'Ilx",  # 0xE7 c cedilla
    "'i gr'av",  # 0xE8 e grave
    "'i xk'Yt",  # 0xE9 e acute
    "'i s'RkxmflEks",  # 0xEA e circumflex
    "'i 'umlWt",  # 0xEB e umlaut
    "'A gr'av",  # 0xEC i grave
    "'A xk'Yt",  # 0xED i acute
    "'A s'RkxmflEks",  # 0xEE i circumflex
    "'A 'umlWt",  # 0xEF i umlaut
    "'Et",  # 0xF0 eth
    "'En t'Ildx",  # 0xF1 n tilde
    "'o gr'av",  # 0xF2 o grave
    "'o xk'Yt",  # 0xF3 o acute
    "'o s'RkxmflEks",  # 0xF4 o circumflex
    "'o t'Ildx",  # 0xF5 o tilde
    "'o 'umlWt",  # 0xF6 o umlaut
    "",  # 0xF7 divide
    "'o sl'@S",  # 0xF8 o slash
    "'Y gr'av",  # 0xF9 u grave
    "'Y xk'Yt",  # 0xFA u acute
    "'Y s'RkxmflEks",  # 0xFB u circumflex
    "'Y 'umlWt",  # 0xFC u umlaut
    "w'A xky'ut",  # 0xFD y acute
    "T'crn",  # 0xFE thorn
    "w'A 'umlWt",  # 0xFF y umlaut
)


# usa_error: per-error-code spoken messages used by the LTS engine.
# Translated from usa_err.tab.

usa_error: Final[tuple[str, ...]] = (
    "Command error in command parser",
    "Command error in string value",
    "Command error in numeric value",
    "Command error in command",
    "Command error in parameter",
    "Command error in phoneme",
    "Error: Out of memory. ",
    "Error: Unable to open file. ",
    "Error: Bad wave file format. ",
    "Error: Unsupported wave file format. ",
    "Error: Unsupported audio format. ",
    "Error: Bad command flush. ",
)


__all__ = ["usa_error", "usa_type"]
