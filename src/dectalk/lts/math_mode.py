"""LTS math-mode symbol expansion.

Translated from:

- ``src/dapi/src/lts/ls_math.c`` — the two entry-point functions
  ``ls_math_do_math`` (look up a single character in
  :data:`math_table`) and ``ls_math_flush_ascky`` (convert an ASCKY
  pronunciation string to phoneme codes via :data:`ascky_tab`).
- ``src/dapi/src/lts/l_us_ma1.c`` — the US English math/ASCKY tables.

DECtalk's math mode (``[:mode :math]``) expands math symbols into
spoken pronunciations: ``+`` becomes "plus", ``=`` becomes "equals",
etc. Each math symbol's pronunciation is encoded in **ASCKY** — a
single-byte-per-phoneme notation where each printable character maps
to one phoneme code (see :data:`ascky_tab`). For example ``pl'^s`` is
``P L (primary-stress) AH S`` = "plus".

The C versions write into the LTS→PH pipe via ``ls_util_write_pipe``;
the Python translations return lists of 16-bit phoneme codes
``(PFUSA << PSFONT) | <US_*>`` so callers can route them however
they need.
"""

from __future__ import annotations

from typing import Final

from dectalk.include.cmd_codes import PSFONT
from dectalk.include.defs import pusa
from dectalk.include.phoneme_codes import (
    BLOCK_RULES,
    COMMA,
    HYPHEN,
    MBOUND,
    PFUSA,
    PPSTART,
    S1,
    S2,
    SBOUND,
    SEMPH,
    VPSTART,
    WBOUND,
    USPhoneme,
)

# -- math_table: ASCII math symbol -> ASCKY pronunciation -------------------

math_table: Final[tuple[tuple[int, bytes], ...]] = (
    (ord("+"), b"pl'^s"),  # plus
    (ord("-"), b"m'An|s"),  # minus
    (ord("*"), b"m'^lt|plAd*bA"),  # multiplied by
    (ord("/"), b"d|v'Ad|d*bA"),  # divided by
    (ord("^"), b"tU*Dx*p'WR*xv"),  # to the power of
    (ord("<"), b"l'Es*DEn"),  # less than
    (ord(">"), b"gr'etR*DEn"),  # greater than
    (ord("="), b"'ikwLz"),  # equals
    (ord("%"), b"pRs'Ent"),  # percent
    (ord("."), b"p'Ont"),  # point
)
"""``[(symbol_char_ord, ascky_pronunciation_bytes), ...]`` from ``l_us_ma1.c``."""


# -- ascky_tab: ASCKY character -> 16-bit phoneme code ----------------------
# Each entry is ``(ascky_char_ord, (PFUSA << PSFONT) | <code>)`` where the
# code is either a US allophone (USPhoneme) or a control code from
# l_com_ph.h (WBOUND, COMMA, S1, etc.).


def _u(code: int) -> int:
    """Font-encode a code into the US-English 16-bit composite phoneme."""
    return (PFUSA << PSFONT) + code


ascky_tab: Final[tuple[tuple[int, int], ...]] = (
    # Vowels and diphthongs.
    (ord("e"), _u(USPhoneme.EY)),
    (ord("a"), _u(USPhoneme.AA)),
    (ord("i"), _u(USPhoneme.IY)),
    (ord("E"), _u(USPhoneme.EH)),
    (ord("A"), _u(USPhoneme.AY)),
    (ord("I"), _u(USPhoneme.IH)),
    (ord("O"), _u(USPhoneme.OY)),
    (ord("o"), _u(USPhoneme.OW)),
    (ord("u"), _u(USPhoneme.UW)),
    (ord("^"), _u(USPhoneme.AH)),
    (ord("W"), _u(USPhoneme.AW)),
    (ord("Y"), _u(USPhoneme.YU)),
    (ord("R"), _u(USPhoneme.RR)),
    (ord("c"), _u(USPhoneme.AO)),
    (ord("@"), _u(USPhoneme.AE)),
    (ord("U"), _u(USPhoneme.UH)),
    (ord("|"), _u(USPhoneme.IX)),
    (ord("x"), _u(USPhoneme.AX)),
    # Consonants.
    (ord("p"), _u(USPhoneme.P)),
    (ord("t"), _u(USPhoneme.T)),
    (ord("k"), _u(USPhoneme.K)),
    (ord("f"), _u(USPhoneme.F)),
    (ord("T"), _u(USPhoneme.TH)),
    (ord("s"), _u(USPhoneme.S)),
    (ord("S"), _u(USPhoneme.SH)),
    (ord("C"), _u(USPhoneme.CH)),
    (ord("w"), _u(USPhoneme.W)),
    (ord("y"), _u(USPhoneme.Y)),
    (ord("h"), _u(USPhoneme.HX)),
    (ord("l"), _u(USPhoneme.LL)),
    (ord("L"), _u(USPhoneme.EL)),
    (ord("N"), _u(USPhoneme.EN)),
    (ord("b"), _u(USPhoneme.B)),
    (ord("d"), _u(USPhoneme.D)),
    (ord("g"), _u(USPhoneme.G)),
    (ord("v"), _u(USPhoneme.V)),
    (ord("D"), _u(USPhoneme.DH)),
    (ord("z"), _u(USPhoneme.Z)),
    (ord("Z"), _u(USPhoneme.ZH)),
    (ord("J"), _u(USPhoneme.JH)),
    (ord("m"), _u(USPhoneme.M)),
    (ord("n"), _u(USPhoneme.N)),
    (ord("G"), _u(USPhoneme.NX)),
    (ord("r"), _u(USPhoneme.R)),
    (ord("q"), _u(USPhoneme.Q)),
    (ord("Q"), _u(USPhoneme.TX)),
    (ord("&"), _u(USPhoneme.DX)),
    (ord("F"), _u(USPhoneme.DF)),
    (ord("B"), _u(USPhoneme.IR)),
    (ord("K"), _u(USPhoneme.ER)),
    (ord("P"), _u(USPhoneme.AR)),
    (ord("M"), _u(USPhoneme.OR_)),
    (ord("j"), _u(USPhoneme.UR)),
    # Control / boundary markers.
    (ord(","), _u(COMMA)),
    (ord(" "), _u(WBOUND)),
    (ord("\t"), _u(WBOUND)),
    (ord("'"), _u(S1)),
    (ord("`"), _u(S2)),
    (ord('"'), _u(SEMPH)),
    (ord("#"), _u(HYPHEN)),
    (ord("("), _u(PPSTART)),
    (ord(")"), _u(VPSTART)),
    (ord("*"), _u(MBOUND)),
    (ord("~"), _u(BLOCK_RULES)),
    (ord("-"), _u(SBOUND)),
)
"""``[(ascky_char_ord, font_encoded_phoneme_code), ...]`` from ``l_us_ma1.c``."""


# -- Function translations --------------------------------------------------


def flush_ascky(ascky: bytes) -> list[int]:
    """Convert an ASCKY pronunciation string to phoneme codes.

    Translation of ``ls_math_flush_ascky`` (ls_math.c:130). For each
    byte in ``ascky``, looks up its entry in :data:`ascky_tab` and
    appends the corresponding font-encoded phoneme code to the
    result. Unknown bytes are silently skipped — matching the C
    behaviour where a missing entry leaves the byte unconverted.
    """
    out: list[int] = []
    for byte in ascky:
        for ag, ap in ascky_tab:
            if byte == ag:
                out.append(ap)
                break
    return out


def do_math(check_char: int) -> list[int]:
    """Look up a math symbol and return its phoneme expansion.

    Translation of ``ls_math_do_math`` (ls_math.c:83). If
    ``check_char`` is one of the recognised math symbols
    (:data:`math_table` keys), returns the phoneme codes for its
    expansion; otherwise returns an empty list.

    The C version is gated by ``MODE_MATH`` being enabled and writes
    into the LTS→PH pipe. The Python version is unconditional —
    callers route the returned codes themselves and apply any mode
    gating at the call site.
    """
    for sym, pron in math_table:
        if sym == check_char:
            return flush_ascky(pron)
    return []


__all__ = [
    "ascky_tab",
    "do_math",
    "flush_ascky",
    "math_table",
]

# Silence unused-import linters: pusa is intentionally exposed for callers
# that may want to construct font-encoded codes directly.
_ = pusa
