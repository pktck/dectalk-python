"""Cross-module constants that don't belong with phonemes or commands.

Aggregates the small-but-essential constant headers:

- ``src/dapi/src/include/defs.h`` — bit-position macros (``BIT0`` etc.)
  and the legacy ``TRUE`` / ``FALSE`` / ``success`` / ``failure``
  aliases used throughout the codebase.
- ``src/dapi/src/include/pipe.h`` — pipe-type discriminants
  (``BYTE_PIPE`` etc.).
- ``src/dapi/src/include/usa_def.h`` — US English-only constants and
  the ``PUSA`` macro that font-encodes a US phoneme code.

We keep `defs.h`'s case-variant aliases (``BIT0``, ``bit0``, ``BIT00``,
``bit00``) as separate Python names so call sites can be ported
verbatim. They all evaluate to the same integer.
"""

from __future__ import annotations

from typing import Final

from dectalk.include.cmd_codes import PSFONT
from dectalk.include.phoneme_codes import PFUSA

# -- defs.h: TRUE/FALSE/success/failure ------------------------------------
# Provided as Python ints (not bools) because the C code uses them as the
# numeric values 0 and 1 in some contexts; making them ``bool`` would let
# them silently mix with arithmetic. Call sites that want a Python bool
# should compare explicitly.

TRUE: Final[int] = 1
FALSE: Final[int] = 0
SUCCESS: Final[int] = 1
FAILURE: Final[int] = 0
SUCCESS_LOWER: Final[int] = 1  # ``success`` in C (lowercase variant)
FAILURE_LOWER: Final[int] = 0  # ``failure`` in C
HUNGARY: Final[int] = 1  # legacy magic constant referenced in early DECtalk code


# -- defs.h: bit-position constants -----------------------------------------
# The C source defines BIT0..BIT15, bit0..bit15, BIT00..BIT09, bit00..bit09 —
# all aliases for ``1 << N``. We keep all the variants because grep'ing for
# ``BIT3`` vs ``bit3`` vs ``BIT03`` in the C source returns different sets of
# call sites, and the variants encode original author intent.

BIT0: Final[int] = 1 << 0
BIT1: Final[int] = 1 << 1
BIT2: Final[int] = 1 << 2
BIT3: Final[int] = 1 << 3
BIT4: Final[int] = 1 << 4
BIT5: Final[int] = 1 << 5
BIT6: Final[int] = 1 << 6
BIT7: Final[int] = 1 << 7
BIT8: Final[int] = 1 << 8
BIT9: Final[int] = 1 << 9
BIT10: Final[int] = 1 << 10
BIT11: Final[int] = 1 << 11
BIT12: Final[int] = 1 << 12
BIT13: Final[int] = 1 << 13
BIT14: Final[int] = 1 << 14
BIT15: Final[int] = 1 << 15

# Two-digit aliases for the low 10 bits (BIT00..BIT09 in the C source).
BIT00: Final[int] = BIT0
BIT01: Final[int] = BIT1
BIT02: Final[int] = BIT2
BIT03: Final[int] = BIT3
BIT04: Final[int] = BIT4
BIT05: Final[int] = BIT5
BIT06: Final[int] = BIT6
BIT07: Final[int] = BIT7
BIT08: Final[int] = BIT8
BIT09: Final[int] = BIT9


# -- pipe.h: pipe-type discriminants ---------------------------------------
# Used by ``create_pipe(type, size)`` to choose the cell width. The
# pipes themselves are opaque (``PIPE_T``); we never construct them
# from Python — the C library owns the worker threads that read/write
# the cross-module pipes.

BYTE_PIPE: Final[int] = 0
WORD_PIPE: Final[int] = 1
DWORD_PIPE: Final[int] = 2
QWORD_PIPE: Final[int] = 3
FLOAT_PIPE: Final[int] = 4
DOUBLE_PIPE: Final[int] = 5
VOID_PTR_PIPE: Final[int] = 6

READ_WORD_PIPE_PACKET: Final[int] = 0xFEEDC0DE
"""Magic word identifying a packet boundary in a word pipe."""


# -- usa_def.h --------------------------------------------------------------

NULL_ASCKY: Final[int] = 0xFFFF
"""Sentinel for "no ASCKY translation available" in the ASCKY tables."""


def pusa(value: int) -> int:
    """C macro ``PUSA(x)``: font-encode a US-English phoneme code.

    Equivalent to ``(PFUSA << PSFONT) | (value)``. Returns a 16-bit
    composite phoneme code with the US English font in the high byte
    and ``value`` (the per-language allophone offset) in the low byte.
    """
    return (PFUSA << PSFONT) | (value & 0xFF)


__all__ = [
    "BIT0",
    "BIT00",
    "BIT01",
    "BIT02",
    "BIT03",
    "BIT04",
    "BIT05",
    "BIT06",
    "BIT07",
    "BIT08",
    "BIT09",
    "BIT1",
    "BIT2",
    "BIT3",
    "BIT4",
    "BIT5",
    "BIT6",
    "BIT7",
    "BIT8",
    "BIT9",
    "BIT10",
    "BIT11",
    "BIT12",
    "BIT13",
    "BIT14",
    "BIT15",
    "BYTE_PIPE",
    "DOUBLE_PIPE",
    "DWORD_PIPE",
    "FAILURE",
    "FAILURE_LOWER",
    "FALSE",
    "FLOAT_PIPE",
    "HUNGARY",
    "NULL_ASCKY",
    "QWORD_PIPE",
    "READ_WORD_PIPE_PACKET",
    "SUCCESS",
    "SUCCESS_LOWER",
    "TRUE",
    "VOID_PTR_PIPE",
    "WORD_PIPE",
    "pusa",
]
