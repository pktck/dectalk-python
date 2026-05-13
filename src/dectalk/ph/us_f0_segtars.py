"""US F0 segmental-target tables from ph_drwt02.c.

Translated from ``src/dapi/src/ph/ph_drwt02.c`` lines 659-704.
Two parallel tables provide the per-phoneme F0 delta (in Hz*10)
added to the running F0 contour as each segment is rendered:

- :data:`us_f0msegtars` (male, 59 entries) — for male voices.
- :data:`us_f0fsegtars` (female, 67 entries) — for female voices.

Indexed by the low byte of ``pDph_t->phocur`` (the US allophone
code). The arrays are different lengths because the female table
has trailing tuning values for LY (palatalised L) and a handful
of follow-on slots; the male table stops earlier.

Both tables are from the modern HLSYN build (the active branch on
Linux). The pre-HLSYN values at lines 426-471 of the C source are
a different shape and are not ported here.
"""

from __future__ import annotations

from typing import Final

us_f0msegtars: Final[tuple[int, ...]] = (
    # SI    IY    IH    EY    EH    AE    AA    AY    AW    AH
    50,  140,   80,   50,   30,    0,    0,    0,    0,   20,
    # AO    OW    OY    UH    UW    RR    YU    AX    IX    IR
    0,    30,   60,   80,  140,   50,  140,   30,   70,  110,
    # ER    AR    OR    UR     W     Y     R     L    HX    RX
    0,     0,    0,    0,  100,  140,    0,    0,    0,    0,
    # LX     M     N    NX    EL    D$    EN     F     V    TH
    0,     0,    0,    0,    0,    0,    0,    0,    0,    0,
    # DH     S     Z    SH    ZH     P     B     T     D     K
    0,     0, -200,    0,    0,    0,    0,    0,    0,    0,
    # G    DX    TQ     Q    CH    JH    DF    TZ    CZ
    0,     0,    0,    0,    0,    0,    0,    0,    0,
)  # fmt: skip
"""Male voice F0 segmental delta table (59 entries, Hz times 10)."""


us_f0fsegtars: Final[tuple[int, ...]] = (
    # SI    IY    IH    EY    EH    AE    AA    AY    AW    AH
    50,  140,   80,   50,   30,    0,    0,    0,    0,   20,
    # AO    OW    OY    UH    UW    RR    YU    AX    IX    IR
    0,    30,   60,   80,   40,   50,  140,   30,   70,  110,
    # ER    AR    OR    UR     W     Y     R     L    HX    RX
    50,    0,   30,   90,  -60,  -60,    0,    0,  200,    0,
    # LX     M     N    NX    EL    D$    EN     F     V    TH
    0,     0,    0,    0,    0,  -20,    0,  300,  -60,  300,
    # DH     S     Z    SH    ZH     P     B     T     D     K
    -60,    0,  -60,    0,  -60,  300,  300,  300,  -20,  300,
    # G    DX    TQ     Q    CH    JH
    -20,  -10,    0,    0,  300,  -20,
    # LY trailing tuning slots (RE, X1..X9, Z1 — counting markers)
    0, 1, 2, 3, 4, 0, 0, 0, 0, 0, 0,
)  # fmt: skip
"""Female voice F0 segmental delta table (67 entries, Hz times 10)."""


__all__ = [
    "us_f0fsegtars",
    "us_f0msegtars",
]
