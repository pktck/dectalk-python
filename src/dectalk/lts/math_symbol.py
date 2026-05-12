"""Math-symbol-to-pronunciation struct from ls_math.c.

Translated from ``src/dapi/src/lts/ls_math.c``. ``math_symbols`` is
the C struct mapping a math-mode character (``+``, ``-``, ``=``,
etc.) to the ASCKY pronunciation string the synthesizer should
emit (``"pl'^s"`` for ``+``, ``"m'An|s"`` for ``-``, …).

Note: The actual mapping data is already exposed as a tuple of
``(byte, bytes)`` pairs in :data:`dectalk.lts.math_mode.math_table`.
This module just provides the per-row struct shape for callers that
need a named-record handle.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MathSymbol:
    """One math-symbol → pronunciation entry.

    Faithful translation of:

    .. code-block:: c

        struct math_symbols {
            unsigned char  sym;
            unsigned char *sym_pron;
        };

    Attributes:
        sym: Math character byte (e.g. ``ord('+')``).
        sym_pron: ASCKY pronunciation string (e.g. ``b"pl'^s"`` for
            ``plus``).
    """

    sym: int = 0
    sym_pron: bytes = b""


__all__ = ["MathSymbol"]
