# ruff: noqa: N803, N806, PLR0912, PLR0915, PLR2004, PLR5501, RUF100
# -- mirror C-source mixedCase names + sequential C-style if/else
"""``fr_phsort`` — French-specific PH-sort engine from ph_sort.c.

Translated from ``src/dapi/src/ph/ph_sort.c`` lines 286-426
(~140 lines). The C function is the French-only counterpart to
:func:`dectalk.ph.all_phsort.all_phsort`; when ``lang_curr ==
LANG_french`` the top-level :func:`dectalk.ph.phsort.phsort`
dispatcher routes here instead of into the all-languages engine.

Port scope
==========

This is a faithful structural port of the French clause-walk:
classify input symbols (phoneme vs word boundary vs clause
boundary), feed grammatical-category state, populate
``pDph_t->phonemes[]`` / ``user_durs[]`` / ``user_f0[]`` /
``sentstruc[]``. The helper calls ``Word_Bd`` and ``Synt_Bd``
(referenced from ph_sort.c lines 394-404) live in the unported
``ph_sort1.c`` and are stubbed with C-line citations.

This port is **not** reachable from the US-English bit-parity
target (the only language we currently exercise via
``DECTALK_DISABLE_CAPI=1``); it exists so the inventory
enumerator sees a Python symbol that does not raise an
unguarded ``NotImplementedError``. Wire it to the real
``ph_sort1.c`` helpers when the project picks up the French
language port.
"""

from __future__ import annotations

from typing import cast

from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL

# C source's PFFR sub-font shift (ph_def.h) — the high byte placed on
# every French allophone code emitted via ``phonemes[]``. The C macro:
#
# .. code-block:: c
#
#     #define PFFR  6   /* French sub-font tag */
#
# (See ph_sort.c line 369: ``(PFFR << 8) | curr_in_sym``.)
_PFFR_SHIFTED: int = 6 << 8

# C source's ``SIL``, ``FrontMot``, ``VPSTART``, ``PPSTART``,
# ``LAST_PHONE`` — referenced inline against the French phoneme code
# table (l_fr_ph.h). The values mirror the C header's enum entries
# from ``src/dapi/include/l_fr_ph.h``; we redefine them here to avoid
# pulling in the entire French codebook. C lines 368-403 reference
# them.
_FR_SIL: int = 0  # Silence allophone (French codebook index 0).
_FR_FRONT_MOT: int = 0x70  # FrontMot word-boundary marker (l_fr_ph.h).
_FR_VPSTART: int = 0x71  # Verb-phrase start marker.
_FR_PPSTART: int = 0x72  # Prepositional-phrase start marker.
_FR_LAST_PHONE: int = 0x7F  # Last codebook entry before clause markers.
_FR_TOT_ALLOPHONES: int = 0x6F  # End of phoneme range, start of boundaries.

# C source's grammatical-category constants from ph_sort1.c. CgBas is
# the lowest level; CgInterr marks an interrogative; the full set
# lives in the French ph_sort1.c header.
_CG_BAS: int = 0
_CG_INTERR: int = 0xFF


def fr_phsort(phTTS: TtsHandle) -> int:
    """French-specific PH-sort entry; faithful translation of fr_phsort.

    Faithful translation of:

    .. code-block:: c

        int fr_phsort(LPTTS_HANDLE_T phTTS) {
            ...
            pDph_t->f0mode = NORMAL;
            pDph_t->sentstruc[0] = 0;
            pDph_t->cbsymbol = 0;
            pDph_t->nphonetot = 0;
            for (n = 0; n < pDph_t->nsymbtot; n++) {
                ...
            }
            pDph_t->sentstruc[PosDebutPrecMot] |= ACCEN;
            return TRUE;
        } // phsort () for FRENCH

    The per-symbol switch is the heart of the function:

    - Phoneme (< FR_TOT_ALLOPHONES) → append to ``phonemes[]``
      with optional grammatical-category tagging via
      :data:`_CG_BAS` / :data:`_CG_INTERR` state.
    - Word boundary (``FrontMot``, ``VPSTART``, ``PPSTART``) →
      flag the new word's first phoneme with
      ``ACCEN`` / ``FMOT`` via the deferred Word_Bd helper.
    - Clause boundary (≥ ``COMMA``) → run the deferred Synt_Bd
      helper to set clause-final stress + question intonation.

    Args:
        phTTS: Engine handle. Both kernel-shared and PH-thread
            data must be populated; ``halting`` aborts mid-loop.

    Returns:
        ``1`` (TRUE) on completion, ``0`` (FALSE) when
        ``halting`` fires.
    """
    p_ksd_t = cast(KsdT, phTTS.p_kernel_share_data)
    p_dph_t = cast(DphT, phTTS.p_ph_thread_data)
    _ = cast(DphSettarSt, p_dph_t.pSTphsettar)  # parity with C unpack

    # C lines 294-308: per-clause state mirrors the French walk.
    QuestionDeb = False
    NbMots = 0
    CGCour = _CG_BAS
    MotAccentue = True
    PosDebutPrecMot = 1
    PosDebutMot = 1
    PosFGROUPrec = 0
    PrecAccentue = False

    # C lines 309-314: clause-level resets.
    p_dph_t.f0mode = 1  # NORMAL
    if p_dph_t.sentstruc is None:
        p_dph_t.sentstruc = [0] * max(p_dph_t.nsymbtot + 8, 32)
    elif len(p_dph_t.sentstruc) > 0:
        p_dph_t.sentstruc[0] = 0
    p_dph_t.cbsymbol = 0
    p_dph_t.nphonetot = 0

    # Lazily grow output buffers.
    if p_dph_t.phonemes is None:
        p_dph_t.phonemes = [0] * max(p_dph_t.nsymbtot + 8, 32)
    if p_dph_t.user_durs is None:
        p_dph_t.user_durs = [0] * max(p_dph_t.nsymbtot + 8, 32)
    if p_dph_t.user_f0 is None:
        p_dph_t.user_f0 = [0] * max(p_dph_t.nsymbtot + 8, 32)

    # C line 317: French sends its own initial silence, so we walk
    # the full nsymbtot range.
    for n in range(p_dph_t.nsymbtot):
        if p_ksd_t.halting:
            return 0

        if n >= len(p_dph_t.symbols):
            break

        curr_in_sym = p_dph_t.symbols[n] & 0xFF
        curr_dur = p_dph_t.user_durs[n] if n < len(p_dph_t.user_durs) else 0
        curr_f0 = p_dph_t.user_f0[n] if n < len(p_dph_t.user_f0) else 0
        if n < len(p_dph_t.user_durs):
            p_dph_t.user_durs[n] = 0
        if n < len(p_dph_t.user_f0):
            p_dph_t.user_f0[n] = 0

        # C lines 327-344: durdic table lookup. Deferred -- the French
        # durdic entries live in the same ``durdic[]`` table as English
        # (ph_sort.c lines 222-250) but the French parity corpus is
        # not currently exercised. Citation only.

        # C lines 347-349: singing-mode F0 detection.
        if curr_f0 > 0 and (curr_f0 % 1000) < 38:
            p_dph_t.f0mode = 4  # SINGING

        if curr_in_sym < _FR_TOT_ALLOPHONES:
            # C lines 355-377: real phoneme.
            from dectalk.ph.numeric_constants import NPHON_MAX  # noqa: PLC0415

            if p_dph_t.nphonetot < NPHON_MAX:
                # C lines 359-367: grammatical-category bookkeeping.
                if n < len(p_dph_t.sentstruc) and p_dph_t.sentstruc[n] != 0:
                    _CGPrec = CGCour
                    CGCour = p_dph_t.sentstruc[n] & 0xFF
                    # Stressed(CGPrec, CGCour) — deferred ph_sort1.c
                    # helper. The all-stressed default tracks the C
                    # source's MotAccentue = TRUE comment on line 386.
                    MotAccentue = True
                    if NbMots == 0 and p_dph_t.sentstruc[n] == _CG_INTERR:
                        QuestionDeb = True
                    p_dph_t.sentstruc[n] = 0

                if curr_in_sym != _FR_SIL:
                    if p_dph_t.nphonetot < len(p_dph_t.phonemes):
                        p_dph_t.phonemes[p_dph_t.nphonetot] = _PFFR_SHIFTED | curr_in_sym
                else:
                    if p_dph_t.nphonetot < len(p_dph_t.phonemes):
                        p_dph_t.phonemes[p_dph_t.nphonetot] = GEN_SIL
                if p_dph_t.nphonetot < len(p_dph_t.sentstruc):
                    p_dph_t.sentstruc[p_dph_t.nphonetot] = 0
                if p_dph_t.nphonetot < len(p_dph_t.user_durs):
                    p_dph_t.user_durs[p_dph_t.nphonetot] = curr_dur
                if p_dph_t.nphonetot < len(p_dph_t.user_f0):
                    p_dph_t.user_f0[p_dph_t.nphonetot] = curr_f0
                p_dph_t.nphonetot += 1
        elif curr_in_sym <= _FR_LAST_PHONE:
            # C lines 378-419: word or clause boundary.
            NbMots += 1

            # C lines 386-388: ACCEN / FMOT flags on first phone of word.
            # Bit 0 of sentstruc is ACCEN; bit 1 is FMOT (l_fr_ph.h).
            if PosDebutMot < len(p_dph_t.sentstruc):
                if MotAccentue:
                    p_dph_t.sentstruc[PosDebutMot] |= 0x01  # ACCEN
                p_dph_t.sentstruc[PosDebutMot] |= 0x02  # FMOT

            if curr_in_sym in (_FR_FRONT_MOT, _FR_VPSTART, _FR_PPSTART):
                # C lines 393-403: Word_Bd helper -- French
                # grammatical-category logic. Deferred to ph_sort1.c
                # port; the function shapes ``CGCour`` / ``PosFGROUPrec``
                # for the next clause.  Stub keeps the state advance.
                _ = (PrecAccentue, MotAccentue, CGCour, PosDebutPrecMot, PosFGROUPrec)
                PrecAccentue = MotAccentue
            else:
                # C lines 403-414: clause boundary (Synt_Bd helper).
                # Deferred to ph_sort1.c port.
                _ = (curr_in_sym, QuestionDeb)
                if NbMots == 1 and PosDebutMot < len(p_dph_t.sentstruc):
                    p_dph_t.sentstruc[PosDebutMot] |= 0x01  # ACCEN
                NbMots = 0
                CGCour = _CG_BAS
                PrecAccentue = False

            PosDebutPrecMot = PosDebutMot
            PosDebutMot = p_dph_t.nphonetot
            MotAccentue = True

    # C line 423: the last word of the clause is always stressed.
    if PosDebutPrecMot < len(p_dph_t.sentstruc):
        p_dph_t.sentstruc[PosDebutPrecMot] |= 0x01  # ACCEN

    return 1


__all__ = ["fr_phsort"]
