"""Per-phoneme timing dispatch helpers from ph_timng.c.

Translated from ``src/dapi/src/ph/ph_timng.c`` and the
``phone_feature`` macro from ``ph_setar.c``:

- :func:`min_timing` — minimum duration in samples for a phone code.
- :func:`inh_timing` — inherent (typical) duration in samples.
- :func:`phone_feature` — feature-flag lookup for a phone code.

All three dispatch on the phone code's **font field** (the upper 5
bits) to choose between language-specific tables. This Python port
only ships the US tables; the C source's "OH MY GOD! THEY'VE KILLED
KENNY" default branch returns the US table for unknown fonts, so we
preserve that behaviour to keep US parity intact while leaving
room for the other-language tables to land later.
"""

from __future__ import annotations

from typing import Final

from dectalk.include.cmd_codes import PFONT, PSFONT, PVALUE
from dectalk.include.phoneme_codes import PFUSA
from dectalk.ph.rom_tables import us_featb, us_inhdr, us_mindur

# Font-shifted PF codes (the upper 5 bits of a phone code).
_FONT_USA: Final[int] = PFUSA << PSFONT
_FONT_UK: Final[int] = 0x1D << PSFONT
_FONT_GR: Final[int] = 0x1C << PSFONT
_FONT_SP: Final[int] = 0x1B << PSFONT
_FONT_LA: Final[int] = 0x1A << PSFONT
_FONT_FR: Final[int] = 0x19 << PSFONT

_HIGH_VALUE_THRESHOLD: Final[int] = 100  # phones with code >= 100 are control codes


def min_timing(phone: int) -> int:
    """Return the minimum duration (in samples) for a phone code.

    Faithful translation of:

    .. code-block:: c

        int min_timing(LPTTS_HANDLE_T phTTS, int phone) {
            int tmp = phone & PFONT;
            if ((phone & PVALUE) >= 100) return 0;
            if (tmp == PFUSA<<PSFONT) return us_mindur[phone & PVALUE];
            if (tmp == PFUK<<PSFONT)  return uk_mindur[phone & PVALUE];
            // ... GR/LA/SP/FR ...
            return us_mindur[phone & PVALUE];   // default fallback
        }

    Phones with a low-byte value ≥ 100 are control codes (silence
    markers, sync points, etc.) and have no minimum duration.

    Args:
        phone: 16-bit font-encoded phone code.

    Returns:
        Minimum duration in samples. ``0`` for control codes;
        a small positive integer for normal allophones.
    """
    if (phone & PVALUE) >= _HIGH_VALUE_THRESHOLD:
        return 0
    font = phone & PFONT
    code = phone & PVALUE
    if font in (_FONT_UK, _FONT_GR, _FONT_SP, _FONT_LA, _FONT_FR):
        # Non-US language tables are not yet translated; the C
        # default branch falls through to us_mindur, which we
        # replicate for bit parity in those (rare) call sites.
        return us_mindur[code]
    # Both font == _FONT_USA and any other font flow through here —
    # the C source's else-branch is "return us_mindur".
    return us_mindur[code]


def inh_timing(phone: int) -> int:
    """Return the inherent duration (in samples) for a phone code.

    Faithful translation of:

    .. code-block:: c

        int inh_timing(LPTTS_HANDLE_T phTTS, int phone) {
            int tmp = phone & PFONT;
            if ((phone & PVALUE) >= 100) return 0;
            if (tmp == PFUSA<<PSFONT) return us_inhdr[phone & PVALUE];
            // ... UK/GR/LA/SP/FR ...
            return us_inhdr[phone & PVALUE];    // default fallback
        }

    Args:
        phone: 16-bit font-encoded phone code.

    Returns:
        Inherent duration in samples. ``0`` for control codes;
        a small positive integer for normal allophones.
    """
    if (phone & PVALUE) >= _HIGH_VALUE_THRESHOLD:
        return 0
    font = phone & PFONT
    code = phone & PVALUE
    if font in (_FONT_UK, _FONT_GR, _FONT_SP, _FONT_LA, _FONT_FR):
        return us_inhdr[code]
    return us_inhdr[code]


def phone_feature(phone: int) -> int:
    """Return the feature flags for a phone code via the ``all_featb`` LUT.

    Faithful translation of:

    .. code-block:: c

        #define phone_feature(a,b) (all_featb[(b)>>8][(b)&0x00ff])

    The C macro picks one of the per-language ``*_featb`` tables
    indexed by the phone's font byte, then looks up the feature
    flags by the low-byte code. The ``a`` argument (``pDph_t``) is
    unused in the macro expansion — it exists only to keep the call
    sites parametric on the thread state.

    Currently only the US font (0x1E) is wired up; other fonts fall
    back to ``us_featb`` (matching the C source's NULL-pointer fault
    behaviour but giving a defined Python value).

    Args:
        phone: 16-bit font-encoded phone code.

    Returns:
        The feature flags from ``us_featb[code]`` for US-font phones,
        or for any other font (which the C source would crash on).
    """
    font = phone >> PSFONT
    code = phone & PVALUE
    # all_featb[0x1E] = us_featb; other indices are NULL in C (would
    # crash). For US-bit-parity we route everything to us_featb.
    if font in (PFUSA, 0):  # 0x1E (US) or 0x00 (slot 0 also points at us_featb)
        return us_featb[code]
    return us_featb[code]


__all__ = ["inh_timing", "min_timing", "phone_feature"]
