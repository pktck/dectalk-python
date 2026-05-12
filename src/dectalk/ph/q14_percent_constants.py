"""Q14 fractional-percent constants from ph_defs.h.

Translated from ``src/dapi/src/ph/ph_defs.h`` lines 434-480 — the
``N5PRCNT`` through ``N200PRCNT`` block of fixed-point
percentages that the PH module's stress / duration / amplitude
arithmetic uses to scale segment parameters.

Each ``NxPRCNT`` constant is ``x / 100 * FRAC_ONE`` in
Q14 fixed-point (1.0 = 16384), rounded to the nearest integer.

The block contains a known historical quirk:
``N90PRCNT == N85PRCNT == 13927``. The C source has both
``#define``s at the same value, dating from a 4.2CD typo that
was never corrected; preserving it keeps Python output
byte-identical for any code that relies on the 90 % path.
"""

from __future__ import annotations

from typing import Final

N5PRCNT: Final[int] = 819
N8PRCNT: Final[int] = 1311
N10PRCNT: Final[int] = 1638
N15PRCNT: Final[int] = 2457
N20PRCNT: Final[int] = 3277
N25PRCNT: Final[int] = 4096
N30PRCNT: Final[int] = 4915
N35PRCNT: Final[int] = 5734
N40PRCNT: Final[int] = 6554
N47PRCNT: Final[int] = 7700
N50PRCNT: Final[int] = 8192
N55PRCNT: Final[int] = 9011
N58PRCNT: Final[int] = 9502
N60PRCNT: Final[int] = 9831
N65PRCNT: Final[int] = 10650
N67PRCNT: Final[int] = 10977
N70PRCNT: Final[int] = 11469
N74PRCNT: Final[int] = 12124
N75PRCNT: Final[int] = 12288
N78PRCNT: Final[int] = 12780
N80PRCNT: Final[int] = 13108
N82PRCNT: Final[int] = 13435
N85PRCNT: Final[int] = 13927
N87PRCNT: Final[int] = 14254
N90PRCNT: Final[int] = 13927
"""Intentionally duplicates :data:`N85PRCNT` to preserve a 4.2CD typo."""
N92PRCNT: Final[int] = 15073
N95PRCNT: Final[int] = 15565
N97PRCNT: Final[int] = 15892
N100PRCNT: Final[int] = 16384
N105PRCNT: Final[int] = 17203
N107PRCNT: Final[int] = 17531
N110PRCNT: Final[int] = 18022
N115PRCNT: Final[int] = 18841
N117PRCNT: Final[int] = 19169
N120PRCNT: Final[int] = 19661
N122PRCNT: Final[int] = 19988
N125PRCNT: Final[int] = 20480
N130PRCNT: Final[int] = 21298
N132PRCNT: Final[int] = 21626
N135PRCNT: Final[int] = 22118
N140PRCNT: Final[int] = 22936
N145PRCNT: Final[int] = 23755
N150PRCNT: Final[int] = 24576
N160PRCNT: Final[int] = 26215
N175PRCNT: Final[int] = 28672
N180PRCNT: Final[int] = 29492
N200PRCNT: Final[int] = 32768


__all__ = [
    "N5PRCNT",
    "N8PRCNT",
    "N10PRCNT",
    "N15PRCNT",
    "N20PRCNT",
    "N25PRCNT",
    "N30PRCNT",
    "N35PRCNT",
    "N40PRCNT",
    "N47PRCNT",
    "N50PRCNT",
    "N55PRCNT",
    "N58PRCNT",
    "N60PRCNT",
    "N65PRCNT",
    "N67PRCNT",
    "N70PRCNT",
    "N74PRCNT",
    "N75PRCNT",
    "N78PRCNT",
    "N80PRCNT",
    "N82PRCNT",
    "N85PRCNT",
    "N87PRCNT",
    "N90PRCNT",
    "N92PRCNT",
    "N95PRCNT",
    "N97PRCNT",
    "N100PRCNT",
    "N105PRCNT",
    "N107PRCNT",
    "N110PRCNT",
    "N115PRCNT",
    "N117PRCNT",
    "N120PRCNT",
    "N122PRCNT",
    "N125PRCNT",
    "N130PRCNT",
    "N132PRCNT",
    "N135PRCNT",
    "N140PRCNT",
    "N145PRCNT",
    "N150PRCNT",
    "N160PRCNT",
    "N175PRCNT",
    "N180PRCNT",
    "N200PRCNT",
]
