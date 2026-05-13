# ruff: noqa: N815, RUF100
"""N-prefixed Klatt per-frame parameters used by the HL-to-LL bridge.

Translated from ``src/dapi/src/ph/hlsynapi.h`` (the ``tagLLFrame`` struct
near line 389). There are *two* different ``LLFrame`` structs in the
DECtalk C source:

1. ``src/dapi/src/hlsyn/llsyn.h`` -- non-prefixed fields (``F0``, ``AV``,
   ``OQ``, ...). Used by the LL Klatt synthesiser proper and ported as
   :class:`dectalk.hlsyn.llsyn.LLFrame`.
2. ``src/dapi/src/ph/hlsynapi.h`` -- N-prefixed fields (``NF0``, ``NAV``,
   ...). Used by the HL-to-LL bridge code in ``hlsyn/hlframe.c``. This
   module ports that variant.

Fields are named exactly as in the C struct (``NFTP``, ``NDF1``, ...) so
the parity test can re-parse ``hlsynapi.h`` and match attribute-by-
attribute. The ``# ruff: noqa: N815`` directive at the top of this file
disables the ``mixedCase`` lint defensively -- in practice every current
field is all-uppercase, but keeping the directive future-proofs us
against the C struct gaining a ``Ncamel`` style field.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LLFrameN:
    """Per-frame Klatt synthesis parameters, N-prefixed variant.

    Mirrors the C ``tagLLFrame`` struct in ``ph/hlsynapi.h``. Every field
    is a ``short`` in C; we use Python ``int`` (unbounded) here since we
    only care about value equivalence.
    """

    NF0: int = 0
    NAV: int = 0
    NOQ: int = 0
    NSQ: int = 0
    NTL: int = 0
    NFL: int = 0
    NDI: int = 0
    NAH: int = 0
    NAF: int = 0

    NF1: int = 0
    NB1: int = 0
    NDF1: int = 0
    NDB1: int = 0
    NF2: int = 0
    NB2: int = 0
    NF3: int = 0
    NB3: int = 0
    NF4: int = 0
    NB4: int = 0
    NF5: int = 0
    NB5: int = 0
    NF6: int = 0
    NB6: int = 0

    NFNP: int = 0
    NBNP: int = 0
    NFNZ: int = 0
    NBNZ: int = 0
    NFTP: int = 0
    NBTP: int = 0
    NFTZ: int = 0
    NBTZ: int = 0

    NA2F: int = 0
    NA3F: int = 0
    NA4F: int = 0
    NA5F: int = 0
    NA6F: int = 0
    NAB: int = 0
    NB2F: int = 0
    NB3F: int = 0
    NB4F: int = 0
    NB5F: int = 0
    NB6F: int = 0

    NANV: int = 0
    NA1V: int = 0
    NA2V: int = 0
    NA3V: int = 0
    NA4V: int = 0
    NATV: int = 0
