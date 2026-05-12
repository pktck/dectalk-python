r"""USA phoneme→ASCII glyph forward table from usa_phon.tab.

Translated from ``src/dapi/src/include/usa_phon.tab``. The
``usa_ascky`` table is the inverse of :data:`usa_ascky_rev`:
indexed by font-encoded phoneme code (low byte), it returns the
single ASCII glyph that represents that phoneme.

The C source uses this table for debug printing only — the runtime
phoneme stream uses the numeric codes directly. Embedding the
table here lets debug tools and tests round-trip codes through
glyphs without an external library.

Layout (matches the C source byte-for-byte):

- Indices 0..56 — 57 US allophones (``_``, ``i``, ``I``, ..., ``F``).
- Indices 57..58 — placeholders ``X`` / ``V`` for the null range.
- Indices 59..99 — zero bytes (padding to the control-code offset).
- Indices 100..122 — 23 control codes (``~``, ``=``, backtick, ``'``,
  double-quote, ``/``, backslash, ``<``, ``-``, ``*``, ``#``, space,
  ``(``, ``)``, ``;``, ``,``, ``.``, ``?``, ``!``, ``+``, ``^``,
  ``&``, ``>``).
"""

from __future__ import annotations

from typing import Final

usa_ascky: Final[bytes] = (
    # 0..56 — allophones
    b"_iIeE@aAW^coOUuRYx|BKPMjwyrlhRlmnGLDNfvTDszSZpbtdkg&QqCJF"
    # 57..58 — null-range placeholders
    b"XV"
    # 59..99 — zero padding (41 bytes)
    + b"\x00" * 41
    # 100..122 — control codes
    + b"~=`'\"/\\<-*# ();,.?!+^&>"
)


def usa_phone_to_glyph(code: int) -> int:
    """Return the ASCII glyph for a phoneme code, or 0 if out of range.

    Faithful translation of the table-lookup pattern in the C
    source's debug print paths:

    .. code-block:: c

        char c = usa_ascky[phone_code & PVALUE];

    Args:
        code: Phoneme code (low byte of a font-encoded value).

    Returns:
        ASCII glyph byte (0..127), or ``0`` if ``code`` is out of
        the table's range.
    """
    if 0 <= code < len(usa_ascky):
        return usa_ascky[code]
    return 0


__all__ = ["usa_ascky", "usa_phone_to_glyph"]
