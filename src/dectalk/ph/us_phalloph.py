# ruff: noqa: PLR0912, PLR0915, N803, SIM102, SIM109, PLR1714 -- faithful port of branchy C source
"""``us_phalloph`` -- US-English allophonic-substitution pass from ph_aloph1.c.

Translated from ``src/dapi/src/ph/ph_aloph1.c`` lines 444-1546.

``phalloph`` is the per-clause allophonic-substitution loop: it walks the
input ``phonemes[]`` / ``sentstruc[]`` arrays and writes substituted
allophones + feature bits into ``allophons[]`` / ``allofeats[]`` (the
output buffers ``make_out_phonol`` appends to). It is also where the
US-English flap rule (``USP_T`` / ``USP_D`` between vowels → ``USP_DF`` /
``USP_DX``), the postvocalic-R rule (``USP_R`` after a vowel collapses
into one of ``USP_RR``/``USP_IR``/``USP_ER``/...), the unstress-vowel
unreduction rules (e.g. ``the [dh ax]`` → ``[dh iy]`` before a syllabic),
and the hat-rise / hat-fall intonation markers live.

This port covers the **ENGLISH_US** path only — German, Spanish, French,
and UK branches are skipped (the C source's ``#ifdef`` walls cleanly
separate them). The function reads from ``pDph_t->phonemes`` /
``pDph_t->sentstruc`` / ``pDph_t->user_durs`` / ``pDph_t->user_f0`` /
``pDph_t->docitation`` / ``pDph_t->nphonetot`` / ``pDph_t->f0mode`` and
writes ``pDph_t->allophons`` / ``pDph_t->allofeats`` / ``pDph_t->user_durs``
/ ``pDph_t->user_f0`` / ``pDph_t->nallotot``.

Bug-for-bug faithfulness notes:

- The C source uses ``goto skiprules`` and ``goto endrul3``; the Python
  port lifts these into nested ``if/else`` blocks with an "applied"
  sentinel that short-circuits the rest of the cascade.
- The C reads ``phonemes[n - 1]`` and ``phonemes[n + 1]`` without bounds
  checks; the Python port wraps these in a small ``_phn`` helper that
  returns :data:`GEN_SIL` when the index is out of range (defensive but
  matching what a freshly-zeroed ``phonemes`` array would give the C
  side at slot 0).
- The ``#ifdef SLOWTALK`` branch (active only when SLOWTALK is defined —
  which it is not in the standard US build) is preserved as a Python
  no-op with a comment, matching CI's build flags.
- The defensive ``if (curr_instruc & FBLOCK)`` early-out preserves the C
  source's behaviour of skipping the whole rules block but still calling
  ``make_out_phonol`` to emit the unmodified phone.
"""

from __future__ import annotations

from typing import cast

from dectalk.include.usp_codes import (
    USP_AA,
    USP_AE,
    USP_AH,
    USP_AO,
    USP_AR,
    USP_AX,
    USP_CH,
    USP_D,
    USP_DF,
    USP_DH,
    USP_DX,
    USP_DZ,
    USP_EH,
    USP_EL,
    USP_EN,
    USP_ER,
    USP_EY,
    USP_F,
    USP_HX,
    USP_IH,
    USP_IR,
    USP_IX,
    USP_IY,
    USP_JH,
    USP_LL,
    USP_LX,
    USP_M,
    USP_N,
    USP_NX,
    USP_OR,
    USP_OW,
    USP_R,
    USP_RR,
    USP_RX,
    USP_T,
    USP_TX,
    USP_UH,
    USP_UR,
    USP_UW,
    USP_YU,
    USP_YX,
)
from dectalk.kernel.adjust_allo import adjust_allo
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.mode_flags import MODE_CITATION
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import (
    AT_BOTTOM_OF_HAT,
    AT_TOP_OF_HAT,
    FBLOCK,
    FBOUNDARY,
    FCBNEXT,
    FEMPHASIS,
    FFIRSTSYL,
    FHAT_BEGINS,
    FHAT_ENDS,
    FMBNEXT,
    FMONOSYL,
    FSTRESS,
    FSTRESS_1,
    FTYPESYL,
    FVPNEXT,
    FWINITC,
)
from dectalk.ph.inton_constants import (
    HAT_F0_SIZES_SPECIFIED,
    HAT_LOCATIONS_SPECIFIED,
    NORMAL,
)
from dectalk.ph.make_out_phonol import make_out_phonol
from dectalk.ph.phoneme_features import (
    FNASAL,
    FSON1,
    FSON2,
    FSYLL,
    FVOWEL,
)
from dectalk.ph.promote_last_2 import promote_last_2
from dectalk.ph.remaining_stresses_til import remaining_stresses_til
from dectalk.ph.timing import phone_feature
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL

# Threshold for "phrase too long to cite" — set by the C source's
# ``if (pDph_t->nphonetot >= 6) { pDph_t->docitation = 0; }``.
_CITATION_MAX_PHONES: int = 6


def us_phalloph(phTTS: TtsHandle) -> None:
    """Apply allophonic substitution + hat-pattern markers to the phoneme stream.

    Faithful translation of the ``ENGLISH_US`` path through the
    function in ``ph_aloph1.c`` line 444. Walks the input phoneme
    stream, applying ~30 substitution rules (postvocalic R collapse,
    flap rule, vowel-unreduce in citation mode, /dh/ after /t,d,n/,
    etc.) and writing the result via :func:`make_out_phonol` into
    the output ``allophons`` / ``allofeats`` arrays.

    The hat-pattern bookkeeping (``FHAT_BEGINS`` / ``FHAT_ENDS``)
    runs after the substitution rules: each stressed syllable in the
    f0mode-``NORMAL`` state gets a hat-rise on the first stress and a
    hat-fall on the last stress (or on an emphasized syllable, or on
    a stressed phrase-end).

    Args:
        phTTS: Two-pointer engine handle (``p_ph_thread_data`` →
            :class:`DphT`, ``p_kernel_share_data`` → :class:`KsdT`).
            Both must be populated.
    """
    p_dph_t = cast(DphT, phTTS.p_ph_thread_data)
    p_ksd_t = cast(KsdT, phTTS.p_kernel_share_data)

    # Local state mirroring the C function's stack variables.
    last_outph: int = GEN_SIL  # C sets via #ifdef ENGLISH branch.
    ph_delcnt: int = 0
    delete_short: bool = False
    hatposition: int = AT_BOTTOM_OF_HAT
    emphasislock: bool = False
    stresses_in_phrase: int = 0
    curr_inf0: int = 0
    sylcount: int = 0  # English-only — counts syllabic phones per word.

    # Input arrays — narrow Optional[list[int]] to list[int] for the body.
    phonemes = cast(list[int], p_dph_t.phonemes)
    sentstruc = cast(list[int], p_dph_t.sentstruc)
    user_durs = cast(list[int], p_dph_t.user_durs)
    user_f0 = p_dph_t.user_f0  # may be None when f0mode == HAT_F0_SIZES_SPECIFIED.

    nphonetot = p_dph_t.nphonetot

    # Reset output state.
    p_dph_t.nallotot = 0

    # "Phrase too long for citing": shut citation mode off if 6+ phones.
    if nphonetot >= _CITATION_MAX_PHONES:
        p_dph_t.docitation = 0

    cite_it: bool = bool(p_ksd_t.modeflag & MODE_CITATION) and bool(p_dph_t.docitation)
    # SLOWTALK branch (not active in the standard US build): if defined,
    # `cite_it = True` when sprate < 100. Preserved as a no-op comment.

    def _phn(idx: int) -> int:
        """Bounds-safe read of ``phonemes[idx]``; out-of-range → GEN_SIL."""
        if 0 <= idx < len(phonemes):
            return phonemes[idx]
        return GEN_SIL

    def _struc(idx: int) -> int:
        """Bounds-safe read of ``sentstruc[idx]``; out-of-range → 0."""
        if 0 <= idx < len(sentstruc):
            return sentstruc[idx]
        return 0

    for n in range(nphonetot):
        # ENGLISH first-syl / FSYLL syllable counter — the C source writes
        # `sylcount = 1` on FFIRSTSYL or `sylcount++` on FSYLL, but never
        # reads the value back inside this function. The Python port
        # mirrors the writes (dead store) for textual parity with the C.
        if (sentstruc[n] & FFIRSTSYL) != 0:
            sylcount = 1
        elif (phone_feature(phonemes[n]) & FSYLL) != 0:
            sylcount += 1

        curr_inph = phonemes[n]
        curr_instruc = sentstruc[n]

        next_inph = phonemes[n + 1] if n < nphonetot - 1 else GEN_SIL

        # Output-array bookkeeping.
        curr_outph = curr_inph
        curr_outstruc = curr_instruc

        if n > 0 and p_dph_t.nallotot > 0:
            last_outph = p_dph_t.allophons[p_dph_t.nallotot - 1]

        # User-prosodic per-phone duration / f0 (cleared after read).
        curr_indur = user_durs[n] if n < len(user_durs) else 0
        if n < len(user_durs):
            user_durs[n] = 0

        if p_dph_t.f0mode != HAT_F0_SIZES_SPECIFIED:
            if user_f0 is not None and n < len(user_f0):
                curr_inf0 = user_f0[n]
                user_f0[n] = 0
            else:
                curr_inf0 = 0

        # Skip allophone rules if current phoneme has feature +FBLOCK.
        skip_rules = (curr_instruc & FBLOCK) != 0

        if not skip_rules:
            # === Morpho-phonemic rules (ENGLISH_US) ============================

            # Rule 1a: "the" → /dh iy/ before a syllabic.
            if (
                (phone_feature(_phn(n + 1)) & FSYLL) != 0
                and curr_inph == USP_AX
                and (curr_instruc & FBOUNDARY) != 0
                and _phn(n - 1) == USP_DH
                and (_struc(n - 1) & FWINITC) != 0
            ):
                curr_outph = USP_IY

            # Rule 1c (the second one, per C comment): "a" before silence
            # in citation mode becomes EY (long-a).
            if curr_inph == USP_AX and next_inph == GEN_SIL and n == 1 and cite_it:
                curr_outph = USP_EY

            # Rule 1b: Unreduce "for" vowel before vowel/sil.
            if (
                curr_inph == USP_F
                and next_inph == USP_RR
                and (
                    ((_struc(n + 1) & FSTRESS) == 0 and (_struc(n + 1) & FTYPESYL) == FMONOSYL)
                    or cite_it
                )
            ):
                if (phone_feature(_phn(n + 2)) & FSYLL) != 0 or _phn(n + 2) == GEN_SIL:
                    if n + 1 < len(phonemes):
                        phonemes[n + 1] = USP_OR
                    next_inph = USP_OR

            # Rule 1c: Unreduce vowel in clause-initial "and" → [ae].
            if (
                curr_inph == GEN_SIL
                and _phn(n + 1) == USP_AE
                and _phn(n + 2) == USP_N
                and _phn(n + 3) == USP_D
                and (((_struc(n + 1) & FSTRESS) == 0 and (_struc(n + 3) & FSTRESS) == 0) or cite_it)
            ):
                if n + 1 < len(phonemes):
                    phonemes[n + 1] = USP_AE
                next_inph = USP_AE

            # Rule 1c (second occurrence in C): "at" → [ae] in citation.
            if curr_inph == GEN_SIL and _phn(n + 1) == USP_EH and _phn(n + 2) == USP_T and cite_it:
                if n + 1 < len(phonemes):
                    phonemes[n + 1] = USP_AE
                next_inph = USP_AE

            # === Phonological rules I ==========================================

            # Rule 2: Postvocalic /R/ and /LL/ allophones.
            if (curr_instruc & (FSTRESS | FWINITC)) == 0 and (
                phone_feature(_phn(n - 1)) & FVOWEL
            ) != 0:
                if curr_inph == USP_LL:
                    curr_outph = USP_LX

                # Special vowel + R combinations.
                if curr_inph == USP_R:
                    curr_outph = USP_RX
                    symlas = _phn(n - 1)
                    if symlas == USP_AX:
                        p_dph_t.allophons[p_dph_t.nallotot - 1] = USP_RR
                        delete_short = True
                    if symlas in (USP_IY, USP_IH):
                        p_dph_t.allophons[p_dph_t.nallotot - 1] = USP_IR
                        delete_short = True
                    if symlas in (USP_EY, USP_EH, USP_AE):
                        p_dph_t.allophons[p_dph_t.nallotot - 1] = USP_ER
                        delete_short = True
                    if symlas in (USP_AA, USP_AH):
                        p_dph_t.allophons[p_dph_t.nallotot - 1] = USP_AR
                        delete_short = True
                    if symlas in (USP_OW, USP_AO):
                        p_dph_t.allophons[p_dph_t.nallotot - 1] = USP_OR
                        delete_short = True
                    if symlas in (USP_UW, USP_UH):
                        p_dph_t.allophons[p_dph_t.nallotot - 1] = USP_UR
                        delete_short = True

            # Rule 3: Unstressed /t/ and /d/ before /y/, /yu/, etc.
            # Uses a goto endrul3 chain in C; we use a sentinel.
            rule3_applied = False

            # Palatalize /t/ or /d/ before unstressed /y/ or /yu/.
            if next_inph in (USP_YU, USP_YX) and (_struc(n + 1) & FSTRESS) == 0:
                if curr_inph == USP_T:
                    curr_outph = USP_CH
                    rule3_applied = True
                elif curr_inph == USP_D:
                    curr_outph = USP_JH
                    rule3_applied = True

            # Glottalize word-final /t/ before sonor cons or /dh/.
            if not rule3_applied and curr_inph == USP_T:
                if (
                    next_inph == USP_LL
                    or next_inph == USP_DH
                    or (
                        (
                            (curr_instruc & FBOUNDARY) >= FMBNEXT
                            and ((phone_feature(next_inph) & FSON2) != 0 or next_inph == USP_HX)
                        )
                        or next_inph == USP_EN
                    )
                ):
                    curr_outph = USP_D
                    if (phone_feature(last_outph) & FSON1) != 0:
                        curr_outph = USP_TX
                    rule3_applied = True

                if not rule3_applied:
                    # NWSNOAA branch active per build flags (default for US):
                    # otherwise (NWSNOAA defined) we'd unconditionally upgrade
                    # `next == UH` to `next == UW`. The standard US build does
                    # NOT define NWSNOAA, so we skip that branch.
                    #
                    # The non-NWSNOAA branch: unreduce "to"'s O before vowel/sil.
                    if next_inph == USP_UH and ((curr_instruc & FSTRESS) == 0 or cite_it):
                        if (phone_feature(_phn(n + 2)) & FSYLL) != 0 or _phn(n + 2) == GEN_SIL:
                            if n + 1 < len(phonemes):
                                phonemes[n + 1] = USP_UW
                        # Flap initial /t/ of "to" after a syllabic.
                        # The HLSYN/CHANGES_AFTER_V43 branch uses Cite_It == 0;
                        # standard US build uses MODE_CITATION == 0. Both are
                        # equivalent for our purposes (cite_it tracks both
                        # conditions when SLOWTALK is off). Match the standard
                        # MODE_CITATION-based branch.
                        elif (
                            (p_ksd_t.modeflag & MODE_CITATION) == 0
                            and (phone_feature(last_outph) & FSYLL) != 0
                            and (phone_feature(last_outph) & FNASAL) == 0
                        ):
                            curr_outph = USP_DF
                            rule3_applied = True

            # Flap rule (non-NWSNOAA): /t/ /d/ between sonorant and syllabic.
            if (
                not rule3_applied
                and curr_inph in (USP_D, USP_T)
                and (curr_instruc & FSTRESS) == 0
                and (phone_feature(last_outph) & FSON1) != 0
                and last_outph != USP_N
                and (phone_feature(next_inph) & FSYLL) != 0
            ):
                # C source has explicit "last_outph != M and != NX and != N"
                # — N is in FSON1 but excluded here; M and NX still need checks.
                if last_outph != USP_M and last_outph != USP_NX:
                    # Flap if consonant is word-final.
                    if (curr_instruc & FBOUNDARY) >= FMBNEXT:
                        curr_outph = USP_DF if curr_inph == USP_T else USP_DX
                    # Or word-initial /t,d/ before reduced vowel.
                    elif (curr_instruc & FWINITC) != 0:
                        if next_inph in (USP_AX, USP_IX):
                            curr_outph = USP_DF if curr_inph == USP_T else USP_DX
                    # Word-internal: previous stressed + next == ow, or
                    # next is one of [ax, rr, iy, ix, el].
                    elif (
                        (
                            (
                                p_dph_t.allofeats[p_dph_t.nallotot - 1] & FSTRESS
                                if p_dph_t.nallotot > 0
                                and p_dph_t.nallotot - 1 < len(p_dph_t.allofeats)
                                else 0
                            )
                            != 0
                            and next_inph == USP_OW
                        )
                        or next_inph == USP_AX
                        or next_inph == USP_RR
                        or next_inph == USP_IY
                        or next_inph == USP_IX
                        or next_inph == USP_EL
                    ):
                        curr_outph = USP_DF if curr_inph == USP_T else USP_DX

            # Rule 4: Unstressed [dh] → dental stop after [t,d], nasal after [n].
            if curr_inph == USP_DH and (curr_instruc & FSTRESS) == 0:
                if last_outph in (USP_T, USP_TX, USP_D):
                    curr_outph = USP_DZ
                if last_outph == USP_N:
                    curr_outph = USP_N

            # Rule 5 is #ifdef NEVER — skipped.

        # === End of skiprules guarded block ====================================

        # GEN_SIL clears the emphasis lock (this runs even when skip_rules is True).
        if curr_inph == GEN_SIL:
            emphasislock = False

        # === Hat-rise / hat-fall location bookkeeping ===========================
        if (
            p_dph_t.f0mode == NORMAL
            and (phone_feature(curr_inph) & FSYLL) != 0
            and (curr_instruc & FSTRESS) != 0
            and not emphasislock
        ):
            # Rise: first stress in phrase (or if FSTRESS_1 yet to come).
            if hatposition != AT_TOP_OF_HAT and (
                (curr_instruc & FSTRESS_1) != 0 or remaining_stresses_til(p_dph_t, n, FCBNEXT) > 0
            ):
                curr_outstruc |= FHAT_BEGINS
                hatposition = AT_TOP_OF_HAT

            if (curr_instruc & FSTRESS_1) != 0:
                stresses_in_phrase += 1

            # Fall on emphasized syll, last clause-stress, or last phrase-stress.
            if hatposition == AT_TOP_OF_HAT and (curr_instruc & FSTRESS_1) != 0:
                if (curr_instruc & FEMPHASIS) == FEMPHASIS:
                    emphasislock = True
                # Fall now if emphasis (non-NWSNOAA branch active in US build).
                if emphasislock:
                    curr_outstruc |= FHAT_ENDS
                    hatposition = AT_BOTTOM_OF_HAT
                    stresses_in_phrase = 0

                # Fall now if last stress in clause.
                if remaining_stresses_til(p_dph_t, n, FCBNEXT) == 0:
                    # Promote last-secondary if at phrase boundary.
                    if (curr_instruc & FBOUNDARY) == FVPNEXT and promote_last_2(p_dph_t, n):
                        pass  # Last secondary stress of next phrase promoted.
                    # English (no GERMAN/SPANISH branch): always fall.
                    curr_outstruc |= FHAT_ENDS
                    hatposition = AT_BOTTOM_OF_HAT
                    stresses_in_phrase = 0

                # Fall if last str in phrase and both phrases have 2+ str.
                if (
                    stresses_in_phrase > 1
                    and remaining_stresses_til(p_dph_t, n, FVPNEXT) == 0
                    and remaining_stresses_til(p_dph_t, n, FCBNEXT) > 1
                ):
                    curr_outstruc |= FHAT_ENDS
                    hatposition = AT_BOTTOM_OF_HAT
                    stresses_in_phrase = 0

        # === Commit-to-output =================================================
        # skiprules: label in C — this section always runs.
        if delete_short:
            # Delete-and-roll-up: bump ph_delcnt and shift the SPC chain.
            ph_delcnt += 1
            adjust_allo(p_ksd_t.spc_pkt_save, n + ph_delcnt, -1)
            # DEBUG_USER_PROSODICS branch (inactive in US build) would add
            # the deleted phone's user_dur onto the previous phone — skipped.
            if curr_inf0 != 0:
                if user_f0 is not None and 0 <= p_dph_t.nallotot - 1 < len(user_f0):
                    user_f0[p_dph_t.nallotot - 1] = curr_inf0
            delete_short = False
        else:
            make_out_phonol(
                p_ksd_t,
                p_dph_t,
                n,
                curr_outph,
                curr_outstruc,
                curr_indur,
                curr_inf0,
            )

    # After loop: restore f0mode if it was HAT_LOCATIONS_SPECIFIED.
    if p_dph_t.f0mode == HAT_LOCATIONS_SPECIFIED:
        p_dph_t.f0mode = NORMAL

    # Zap last (sentinel) position in output arrays.
    while len(p_dph_t.allophons) <= p_dph_t.nallotot:
        p_dph_t.allophons.append(0)
    while len(p_dph_t.allofeats) <= p_dph_t.nallotot:
        p_dph_t.allofeats.append(0)
    p_dph_t.allophons[p_dph_t.nallotot] = GEN_SIL
    p_dph_t.allofeats[p_dph_t.nallotot] = 0

    # The C source calls prphonol() at the end — a debug printer that's
    # an empty body when DEBUGALLO isn't defined. We mirror as a no-op.


__all__ = ["us_phalloph"]
