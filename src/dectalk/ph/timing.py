"""Per-phoneme timing dispatch helpers from ph_timng.c / ph_setar.c.

Translated from ``src/dapi/src/ph/ph_timng.c`` and the inline
helpers in ``ph_setar.c``:

- :func:`min_timing` — minimum duration in samples for a phone code.
- :func:`inh_timing` — inherent (typical) duration in samples.
- :func:`phone_feature` — feature-flag lookup for a phone code.
- :func:`begtyp` — begin-segment type lookup.
- :func:`endtyp` — end-segment type lookup.
- :func:`ptram` — parallel-amplitude index for fricatives.
- :func:`burdr` — burst-duration lookup for plosives.
- :func:`place` — place-of-articulation feature bits.
- :func:`plocu` — phoneme-locus index for parallel-amplitude tables.

All dispatch on the phone code's **font field** (the upper 5 bits)
to choose between language-specific tables. This Python port only
ships the US tables; the C source's "OH MY GOD! THEY'VE KILLED
KENNY" default branch returns the US table for unknown fonts, so we
preserve that behaviour to keep US parity intact while leaving
room for the other-language tables to land later.
"""

from __future__ import annotations

from typing import Final

from dectalk.include.cmd_codes import PFONT, PSFONT, PVALUE
from dectalk.include.phoneme_codes import PFUSA
from dectalk.ph.rom_tables import (
    us_begtyp,
    us_burdr,
    us_endtyp,
    us_featb,
    us_inhdr,
    us_mindur,
    us_place,
    us_plocu,
    us_ptram,
)

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


def begtyp(phone: int) -> int:
    """Return the begin-segment type for a phone code.

    Faithful translation of:

    .. code-block:: c

        __inline short begtyp(int phone) {
            return all_begtyp[phone>>8][phone&0xFF];
        }

    The ``all_begtyp`` table is a per-font array of pointers into
    ``us_begtyp`` / ``uk_begtyp`` / etc. For US-font phones the
    lookup is ``us_begtyp[phone & 0xFF]``.

    Args:
        phone: 16-bit font-encoded phone code.

    Returns:
        Begin-segment type code from the language's ``*_begtyp``
        table. The Python port returns ``us_begtyp[code]`` for any
        font (matching the C default branch).
    """
    code = phone & 0xFF
    return us_begtyp[code]


def endtyp(phone: int) -> int:
    """Return the end-segment type for a phone code.

    Faithful translation of:

    .. code-block:: c

        __inline short endtyp(int phone) {
            return all_endtyp[phone>>8][phone&0xFF];
        }

    Args:
        phone: 16-bit font-encoded phone code.

    Returns:
        End-segment type code; see :func:`begtyp` for the dispatch
        semantics.
    """
    code = phone & 0xFF
    return us_endtyp[code]


def ptram(phone: int) -> int:
    """Return the parallel-amplitude index for a phone code (fricatives).

    Faithful translation of:

    .. code-block:: c

        __inline short ptram(int phone) {
            return all_ptram[phone>>8][phone&0xFF];
        }

    Used as an index into the parallel-amplitude tables when
    generating fricative friction noise.

    Args:
        phone: 16-bit font-encoded phone code.

    Returns:
        Index into the per-language amplitude tables.
    """
    code = phone & 0xFF
    return us_ptram[code]


def burdr(phone: int) -> int:
    """Return the burst duration for a plosive phone code.

    Faithful translation of:

    .. code-block:: c

        __inline short burdr(int phone) {
            return all_burdr[phone>>8][phone&0xFF];
        }

    Plosives (P, T, K, B, D, G) have a burst portion before the
    voiced onset; this is its duration in samples.

    Args:
        phone: 16-bit font-encoded phone code.

    Returns:
        Burst duration in samples.
    """
    code = phone & 0xFF
    return us_burdr[code]


def place(phone: int) -> int:
    """Return the place-of-articulation feature bits for a phone code.

    Faithful translation of:

    .. code-block:: c

        __inline short place(int phone) {
            return all_place[phone>>8][phone&0xFF];
        }

    The ``us_place`` table is a bit-field encoding place of
    articulation (labial / dental / alveolar / velar / etc.) plus
    a few coarse F2-back / F2-back-front flags. Consumers test the
    returned value against the ``F2BACKI`` / ``F2BACKF`` bits in
    p_us_st1.c.

    Args:
        phone: 16-bit font-encoded phone code.

    Returns:
        Place-of-articulation feature bits from ``us_place[code]``.
    """
    code = phone & 0xFF
    return us_place[code]


def plocu(index: int) -> int:
    """Return the phoneme-locus index for the parallel-amplitude tables.

    Faithful translation of:

    .. code-block:: c

        __inline short plocu(int index) {
            return all_plocu[index>>8][index&0xFF];
        }

    The ``plocu`` table maps a phone code to an index into the locus
    tables (``{lang}_maleloc`` / ``{lang}_femloc``).  The C source
    dispatches via ``all_plocu[index>>8]`` — the upper byte selects the
    per-language table, the lower byte is the allophone code.

    Args:
        index: 16-bit font-encoded phone code.  The upper byte encodes
            the font (PFUSA=0x1E, PFUK=0x1D, PFGR=0x1C, PFSP=0x1B,
            PFLA=0x1A, PFFR=0x19); the lower byte is the allophone index.

    Returns:
        Index into the per-language locus tables.  Returns ``0`` (no
        locus entry) for fonts without a ``plocu`` table.
    """
    # Lazy imports to avoid circular deps; these modules only exist on
    # branches that include the non-US locus tables (this one).
    from dectalk.ph.fr_locus_tables import fr_plocu  # noqa: PLC0415
    from dectalk.ph.gr_locus_tables import gr_plocu  # noqa: PLC0415
    from dectalk.ph.la_locus_tables import la_plocu  # noqa: PLC0415
    from dectalk.ph.sp_locus_tables import sp_plocu  # noqa: PLC0415
    from dectalk.ph.uk_locus_tables import uk_plocu  # noqa: PLC0415

    _all_plocu: dict[int, tuple[int, ...]] = {
        0x1E: us_plocu,  # PFUSA
        0x1D: uk_plocu,  # PFUK
        0x1C: gr_plocu,  # PFGR
        0x1B: sp_plocu,  # PFSP
        0x1A: la_plocu,  # PFLA
        0x19: fr_plocu,  # PFFR
    }
    font = index >> 8
    code = index & 0xFF
    table = _all_plocu.get(font, us_plocu)
    return table[code] if code < len(table) else 0


__all__ = [
    "begtyp",
    "burdr",
    "endtyp",
    "inh_timing",
    "min_timing",
    "phone_feature",
    "place",
    "plocu",
    "ptram",
]
