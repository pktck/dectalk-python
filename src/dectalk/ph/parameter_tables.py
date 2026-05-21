"""Klatt-frame parameter-type / init / divtab tables from ph_romi.c.

Translated from ``src/dapi/src/ph/ph_romi.c``. The 16 Klatt voice
parameters (F1..TILT) each have:

- a **type** code in :data:`partyp` (0..4) saying whether the
  target value comes from a constant table, the ``taram[ptram]``
  amplitude table, or the ``flocu[plocu]`` locus table.
- an **initial value** in :data:`parini` used at the start of an
  utterance / after a voice change.

:data:`divtab` is a 50-entry lookup that lets the inner loop use
``mulsh()`` (multiply-shift) for divisions by 1..20+ instead of
expensive C division.
"""

from __future__ import annotations

from typing import Final

# -- Parameter type codes ---------------------------------------------------
#
# Order: F1, F2, F3, FZ, B1, B2, B3, AV, AP, A2, A3, A4, A5, A6, AB, TILT.

partyp: Final[tuple[int, ...]] = (
    # F1, F2, F3, FZ, B1, B2, B3, AV
    3, 3, 3, 1, 4, 4, 4, 0,
    # AP, A2, A3, A4, A5, A6, AB, TILT
    0, 2, 2, 2, 2, 2, 2, 2,
)  # fmt: skip
"""16-entry parameter type code (0..4) per Klatt voice parameter."""


# -- Initial parameter values ----------------------------------------------

parini: Final[tuple[int, ...]] = (
    # F1, F2, F3, FZ, B1, B2, B3, AV
    600, 1600, 2600, 300, 50, 150, 250, 0,
    # AP, A2, A3, A4, A5, A6, AB, TILT
    0, 0, 0, 0, 0, 0, 0, 0,
)  # fmt: skip
"""16-entry default value per Klatt voice parameter (Hz for F/B; dB for A)."""


# -- divtab: mulsh() lookup table for division by 1..50 ---------------------
#
# divtab[n] ≈ 16384 / n (Q14). Used to convert `x / n` into the cheaper
# `(x * divtab[n]) >> 14`. divtab[0] and divtab[1] both equal 16384 (the
# identity); above that the values follow 16384/n closely.

divtab: Final[tuple[int, ...]] = (
    16384, 16384,  8192,  5461,  4096,
     3276,  2730,  2340,  2048,  1820,
     1638,  1489,  1365,  1260,  1170,
     1092,  1024,   964,   910,   862,
      819,   780,   745,   712,   682,
      655,   630,   607,   585,   565,
      546,   528,   512,   496,   482,
      468,   455,   443,   431,   420,
      409,   399,   390,   381,   372,
      364,   356,   349,   341,   334,
)  # fmt: skip
"""50-entry mulsh() lookup: ``divtab[n] = round(16384 / n)`` for n=1..49."""


# -- lineartilt: SPC spectral-tilt linearisation lookup ---------------------
#
# Translated from ph_romi.c lines 96-103. ``send_pars()`` in ph_claus.c
# applies this lookup to ``parstochip[OUT_TLT]`` before shipping the
# frame to the synthesiser: ``delaypars[OUT_TLT] = lineartilt[parstochip[OUT_TLT]]``
# (ph_claus.c line 735). The mapping linearises the PH module's
# internal tilt scale (0..31) to a perceptually-uniform tilt value the
# Klatt source-spectrum filter expects.

lineartilt: Final[tuple[int, ...]] = (
    0,  6,  8, 12, 15, 17, 19, 21, 23, 25,
    26, 27, 28, 29, 30, 31, 32, 33, 34, 35,
    35, 36, 36, 37, 37, 38, 38, 39, 39, 39,
    40, 40,
)  # fmt: skip
"""32-entry tilt-linearisation lookup (ph_romi.c lines 96-103)."""


__all__ = ["divtab", "lineartilt", "parini", "partyp"]
