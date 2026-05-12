"""Boundary-phoneme → feature-bit table from ph_romi.c.

Translated from ``src/dapi/src/ph/ph_romi.c``. ``bounftab`` is an
11-entry lookup: input phoneme codes ``SBOUND`` (108) through
``EXCLAIM`` (118) map to the corresponding ``F*NEXT`` bit-flag
the PH module ORs into ``pDph_t->sentstruc`` to mark the next
segment's following boundary type.

The C source has two variants in ``ph_romi.c``: the active branch
(non-Spanish) uses :data:`~dectalk.ph.feature_bits.FSYBNEXT` for
``SBOUND``; the ``#ifdef SPANISH_not`` branch uses ``FSBOUND``.
This port follows the active branch.
"""

from __future__ import annotations

from typing import Final

from dectalk.ph.feature_bits import (
    FCBNEXT,
    FEXCLNEXT,
    FMBNEXT,
    FPERNEXT,
    FPPNEXT,
    FQUENEXT,
    FRELNEXT,
    FSYBNEXT,
    FVPNEXT,
    FWBNEXT,
)

bounftab: Final[tuple[int, ...]] = (
    FSYBNEXT,   # SBOUND  (108)
    FMBNEXT,    # MBOUND  (109)
    FMBNEXT,    # HYPHEN  (110)
    FWBNEXT,    # WBOUND  (111)
    FPPNEXT,    # PPSTART (112)
    FVPNEXT,    # VPSTART (113)
    FRELNEXT,   # RELSTART (114)
    FCBNEXT,    # COMMA   (115)
    FPERNEXT,   # PERIOD  (116)
    FQUENEXT,   # QUEST   (117)
    FEXCLNEXT,  # EXCLAIM (118)
)  # fmt: skip
"""Boundary phoneme code → feature-bit lookup (SBOUND..EXCLAIM, 11 entries)."""


__all__ = ["bounftab"]
