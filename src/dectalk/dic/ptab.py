"""DECtalk-ASCII-phoneme to allophone code lookup table.

Translated from ``src/dapi/src/dic/dic.c``. The ``ptab`` table maps
single-byte phoneme glyphs (the "ASCII phoneme" notation DECtalk
dictionaries and the C source's voice-tuning use) to the numeric
allophone codes that the LTS/PH engines pass through the pipeline.

The dictionary file format (``dtalk_us.dic``) stores word
pronunciations using these single-byte glyphs; the dictionary loader
calls ``ptab[]`` to translate them into pipeline phoneme codes.

Each glyph follows DECtalk's convention:

- vowels: ``e=EY a=AA i=IY E=EH A=AY I=IH O=OY o=OW u=UW``
- mid/r-coloured: ``^=AH W=AW Y=YU R=RR c=AO @=AE U=UH``
- reduced: ``|=IX x=AX``
- stops/fricatives: ``p=P t=T k=K f=F T=TH s=S S=SH C=CH``
- nasals/liquids: ``w=W y=Y h=HX l=LL L=EL N=EN m=M n=N G=NX r=R``
- voiced obstruents: ``b=B d=D g=G v=V D=DH z=Z Z=ZH J=JH``
- glottal/flap: ``q=Q Q=TX &=DX``
- D/T discriminator: ``F=DF``
- r-coloured fillers: ``B=IR K=ER P=AR M=OR j=UR``

The Python translation flattens the C ``struct PTAB { char glyph;
char code; }`` table into a ``dict[str, int]`` for O(1) lookup.
"""

from __future__ import annotations

from typing import Final

from dectalk.include.phoneme_codes import (
    BLOCK_RULES,
    COMMA,
    HYPHEN,
    MBOUND,
    PPSTART,
    S1,
    S2,
    SBOUND,
    SEMPH,
    VPSTART,
    WBOUND,
    USPhoneme,
)

# Language-independent punctuation/boundary glyphs. The C source appends
# these 12 entries to every ``PTAB ptab[]`` initialiser regardless of
# the active language #ifdef.
_COMMON_GLYPHS: Final[dict[str, int]] = {
    ",": COMMA,
    " ": WBOUND,
    "\t": WBOUND,
    "'": S1,
    "`": S2,
    '"': SEMPH,
    "#": HYPHEN,
    "(": PPSTART,
    ")": VPSTART,
    "*": MBOUND,
    "~": BLOCK_RULES,
    "-": SBOUND,
}

ptab_us: Final[dict[str, int]] = {
    "e": int(USPhoneme.EY),
    "a": int(USPhoneme.AA),
    "i": int(USPhoneme.IY),
    "E": int(USPhoneme.EH),
    "A": int(USPhoneme.AY),
    "I": int(USPhoneme.IH),
    "O": int(USPhoneme.OY),
    "o": int(USPhoneme.OW),
    "u": int(USPhoneme.UW),
    "^": int(USPhoneme.AH),
    "W": int(USPhoneme.AW),
    "Y": int(USPhoneme.YU),
    "R": int(USPhoneme.RR),
    "c": int(USPhoneme.AO),
    "@": int(USPhoneme.AE),
    "U": int(USPhoneme.UH),
    "|": int(USPhoneme.IX),
    "x": int(USPhoneme.AX),
    "p": int(USPhoneme.P),
    "t": int(USPhoneme.T),
    "k": int(USPhoneme.K),
    "f": int(USPhoneme.F),
    "T": int(USPhoneme.TH),
    "s": int(USPhoneme.S),
    "S": int(USPhoneme.SH),
    "C": int(USPhoneme.CH),
    "w": int(USPhoneme.W),
    "y": int(USPhoneme.Y),
    "h": int(USPhoneme.HX),
    "l": int(USPhoneme.LL),
    "L": int(USPhoneme.EL),
    "N": int(USPhoneme.EN),
    "b": int(USPhoneme.B),
    "d": int(USPhoneme.D),
    "g": int(USPhoneme.G),
    "v": int(USPhoneme.V),
    "D": int(USPhoneme.DH),
    "z": int(USPhoneme.Z),
    "Z": int(USPhoneme.ZH),
    "J": int(USPhoneme.JH),
    "m": int(USPhoneme.M),
    "n": int(USPhoneme.N),
    "G": int(USPhoneme.NX),
    "r": int(USPhoneme.R),
    "q": int(USPhoneme.Q),
    "Q": int(USPhoneme.TX),
    "&": int(USPhoneme.DX),
    "F": int(USPhoneme.DF),
    "B": int(USPhoneme.IR),
    "K": int(USPhoneme.ER),
    "P": int(USPhoneme.AR),
    "M": int(USPhoneme.OR_),
    "j": int(USPhoneme.UR),
    # Language-independent suffix block.
    **_COMMON_GLYPHS,
}


__all__ = ["ptab_us"]
