"""Language prefix recogniser from cm_phon.c.

Translated from ``src/dapi/src/cmd/cm_phon.c`` and the
``language_prefixes`` table in ``src/dapi/src/kernel/usa_init.c``:

- :data:`language_prefixes` — 12-byte table of 2-letter ISO language
  codes (``us``, ``uk``, ``sp``, ``gr``, ``la``, ``fr``).
- :func:`cm_phon_lookup_language` — case-insensitive lookup of a
  2-byte sequence in the language-prefix table; returns the language
  index (0..5) or -1 on no match.
"""

from __future__ import annotations

from typing import Final

from dectalk.lts.char_features import ls_lower

language_prefixes: Final[bytes] = (
    b"us"
    b"uk"
    b"sp"
    b"gr"
    b"la"
    b"fr"
)
"""Two-letter ISO codes for the six DECtalk languages.

Index 0 is US English, 1 UK English, 2 Castilian Spanish, 3 German,
4 Latin-American Spanish, 5 French.
"""

language_size: Final[int] = len(language_prefixes)
"""Total bytes in :data:`language_prefixes` (12)."""


def cm_phon_lookup_language(ph1: int, ph2: int) -> int:
    """Return the language index for a 2-letter language code, or -1.

    Faithful translation of:

    .. code-block:: c

        int cm_phon_lookup_language(LPTTS_HANDLE_T phTTS,
                                     unsigned char ph1,
                                     unsigned char ph2) {
            int i;
            ph1 = par_lower[ph1];
            ph2 = par_lower[ph2];
            for (i = 0; i < language_size; i += 2) {
                if (ph1 == language_prefixes[i]
                && ph2 == language_prefixes[i+1])
                    return i/2;
            }
            return -1;
        }

    The ``phTTS`` parameter is unused in the C source (the
    PCMD/PKSD reads are commented out). The Python port omits it.

    Args:
        ph1: First byte of the language code (case-folded via
            ``ls_lower``).
        ph2: Second byte.

    Returns:
        Index 0..5 if the (lowercased) bytes match a known language
        code, or ``-1`` on no match.
    """
    p1 = ls_lower[ph1]
    p2 = ls_lower[ph2]
    for i in range(0, language_size, 2):
        if p1 == language_prefixes[i] and p2 == language_prefixes[i + 1]:
            return i // 2
    return -1


__all__ = ["cm_phon_lookup_language", "language_prefixes", "language_size"]
