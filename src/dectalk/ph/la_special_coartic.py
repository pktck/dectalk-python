"""``la_special_coartic`` -- Latin American Spanish coarticulation rules.

Translated from ``src/dapi/src/ph/p_la_st1.c`` line 343 (~22 lines body).

Called from :func:`make_dip` when the current segment is a diphthongised
vowel and ``par_type == FORM_FREQ``. Returns the sum of two
``span_spec_coart`` calls (vowel paired with previous and next phone).

The C source links the file into a single translation unit alongside
``p_sp_st1.c`` (via ``ph_sttr1.c``), so the ``span_spec_coart`` call
in ``la_special_coartic`` resolves to the **Spanish** helper defined
in ``p_sp_st1.c`` (using ``sp_place[]`` and ``SPP_*`` codes). The
parallel ``la_spec_coart`` helper defined in ``p_la_st1.c`` is dead
code in the active flow -- it is never called, only declared. We
mirror the linker's resolution: this Python port delegates to
:func:`~dectalk.ph.sp_special_coartic.span_spec_coart`.

This works at runtime because Spanish and Latin American Spanish
share the same low-byte phoneme numbering (``LA_E == SP_E == 2``,
etc., from ``l_all_ph.h``), and the ``& PVALUE`` mask in the helper
strips the language-font bits before any switch.
"""

from __future__ import annotations

from dectalk.ph.dph_t import DphT
from dectalk.ph.get_phone import get_phone
from dectalk.ph.sp_special_coartic import span_spec_coart


def la_special_coartic(p_dph_t: DphT, nfon: int, diphpos: int) -> int:
    """Compute the LA coarticulation delta for one diphthong segment.

    Faithful translation of the C static helper. The C body calls
    ``span_spec_coart`` -- a symbol resolved at link time to the
    Spanish helper in ``p_sp_st1.c``; the Python port mirrors that
    resolution by importing
    :func:`~dectalk.ph.sp_special_coartic.span_spec_coart` directly.

    Args:
        p_dph_t: Per-thread PH state with populated ``allofeats`` and
            ``pSTphsettar.np`` set to the current parameter index.
        nfon: Index into ``allophons[]`` for the current phone.
        diphpos: Diphthong-position counter (unused by the C body, kept
            for signature parity).

    Returns:
        Signed delta (Hz) to apply to the formant target.
    """
    del diphpos  # unused -- mirrors C source (passed but ignored)
    foncur = get_phone(p_dph_t, nfon)
    fonnex = get_phone(p_dph_t, nfon + 1)
    fonlas = get_phone(p_dph_t, nfon - 1)

    # This assumes that changes are mostly symmetric.
    temp = span_spec_coart(p_dph_t, foncur, fonlas)
    temp += span_spec_coart(p_dph_t, foncur, fonnex)
    return temp


__all__ = ["la_special_coartic"]
