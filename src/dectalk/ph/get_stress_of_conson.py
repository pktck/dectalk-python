"""``get_stress_of_conson`` helper from p_us_sr1.c.

Translated from ``src/dapi/src/ph/p_us_sr1.c`` lines 70-161.

Scans forward from a consonant symbol looking for a stress marker
(``S1`` / ``S2`` / ``SEMPH``) before encountering a vowel or a
syllable boundary. When a stress marker is found, the run of
consonants between ``msym`` and the marker is tested via
:func:`~dectalk.ph.cluster_check.us_phcluster` to decide whether the
first consonant is a legitimate member of a legal onset cluster.
If so, the corresponding stress feature (``FSTRESS_1`` /
``FSTRESS_2`` / ``FEMPHASIS``) is OR'd onto the current phoneme's
``sentstruc[]`` entry via :func:`add_feature`.

Used by ``ph_sort.c`` during stress assignment to propagate a
following stress symbol back onto a consonant that belongs to the
stressed syllable's onset cluster (e.g. the ``str`` in
``stress``).
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import EXCLAIM, S1, S2, SBOUND, SEMPH
from dectalk.include.usp_codes import USP_S
from dectalk.ph.cluster_check import CLUSTER_TRYS, NOCLUSTER, us_phcluster
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FEMPHASIS, FSTRESS_1, FSTRESS_2
from dectalk.ph.make_phone import add_feature
from dectalk.ph.phoneme_features import FSYLL
from dectalk.ph.timing import phone_feature

# Mask for the low-byte phoneme value (PVALUE in the C source).
_PVALUE: int = 0x00FF

# Maximum legal English-onset cluster length (e.g. /str/, /skr/, /spl/).
# More than 3 leading consonants means the first cannot be part of the cluster.
_MAX_ONSET_CLUSTER: int = 3
# The triple-cluster rule kicks in at exactly 3 consonants between msym and
# the stress marker.
_TRIPLE_CLUSTER: int = 3
# Phone codes ≥ 100 are control tokens (S1/S2/SEMPH/SBOUND/COMMA/…) and
# do not have entries in us_featb; the C source's blind ``phone_feature``
# lookup for these is UB.  See the body of get_stress_of_conson for why
# this guard preserves C parity.
_PHONE_TABLE_LIMIT: int = 100


def get_stress_of_conson(p_dph_t: DphT, msym: int, compound_destress: int) -> None:
    """Propagate a following stress marker onto the current consonant.

    Faithful translation of:

    .. code-block:: c

        static void get_stress_of_conson(LPTTS_HANDLE_T phTTS,
                                         short msym,
                                         short compound_destress) {
            PDPH_T pDph_t = phTTS->pPHThreadData;
            short m, mcl = 0, cl = 0, sy = 0, stresslevel = 0;
            stresslevel = FNOSTRESS;
            for (m = msym + 1; m < pDph_t->nsymbtot; m++) {
                sy = pDph_t->symbols[m] & PVALUE;
                if (sy == S1 || sy == S2 || sy == SEMPH) {
                    mcl = m - msym;
                    if (mcl > 3) return;
                    if (mcl != 1) {
                        cl = us_phcluster(pDph_t->symbols[m - 2],
                                          pDph_t->symbols[m - 1]);
                        if (cl == NOCLUSTER) return;
                        if (mcl == 3
                            && (cl != CLUSTER_TRYS
                                || pDph_t->symbols[m - 3] != USP_S))
                            return;
                    }
                    if (sy == S1)
                        add_feature(pDph_t, FSTRESS_1, CURRPHONE);
                    if (sy == S2)
                        add_feature(pDph_t, FSTRESS_2, CURRPHONE);
                    if (sy == SEMPH)
                        add_feature(pDph_t, FEMPHASIS, CURRPHONE);
                    return;
                }
                if ((phone_feature(pDph_t, sy) & FSYLL) IS_PLUS)
                    return;             /* No stress before vowel */
                if (sy >= SBOUND && sy <= EXCLAIM)
                    return;             /* No vowel before syllable ends */
            }
        }

    The C source guards the cluster check with a ``mcl > 3`` early
    exit, then either skips the cluster test (``mcl == 1``) or asks
    :func:`us_phcluster` whether the two consonants closest to the
    vowel form a legal onset. For ``mcl == 3`` an additional rule
    requires the leading consonant to be /s/ and the inner pair to
    be a CLUSTER_TRYS combo (e.g. /spr/, /str/, /skr/).

    The ``compound_destress`` parameter is accepted for API parity
    with the C call site (``ph_sort.c`` line 1443) but is unused in
    the body — same as the C source.

    The C file also contains a dead-code ``#if defined(HLSYN) ||
    defined(CHANGES_AFTER_V43)`` block that the production build
    never enables; we omit it.

    The C source compares ``pDph_t->symbols[m - 3] != USP_S`` against
    the **font-encoded** value of /s/. The ``symbols[]`` storage in
    DECtalk holds font-encoded phoneme codes for allophones (with the
    PFUSA byte in the high byte) and raw control codes (``S1`` /
    ``S2`` / ``SEMPH`` / ``SBOUND`` / etc., which fit in the low byte
    and never collide with valid font-encoded values). The
    ``& PVALUE`` mask extracts the raw low-byte token so a phoneme
    like ``USP_S == 0x1E29`` becomes ``41`` and a control code like
    ``S1 == 103`` is unchanged.

    Args:
        p_dph_t: PH thread state.
        msym: Index of the current consonant in ``symbols[]``.
        compound_destress: Unused — preserved for C-API parity.
    """
    del compound_destress  # Unused (matches C signature).
    symbols = p_dph_t.symbols
    for m in range(msym + 1, p_dph_t.nsymbtot):
        sy = symbols[m] & _PVALUE
        # Scan forward from present consonant for a stress marker.
        if sy in (S1, S2, SEMPH):
            mcl = m - msym  # Number of consonants in potential cluster.
            # 1st of more than 3 consonants in a row is not a cluster member.
            if mcl > _MAX_ONSET_CLUSTER:
                return
            # One consonant is always stressable.
            if mcl != 1:
                # Is the pair next to the vowel a legal cluster?
                cl = us_phcluster(symbols[m - 2], symbols[m - 1])
                if cl == NOCLUSTER:
                    return
                # For triples, also require the leading /s/ + CLUSTER_TRYS pair.
                if mcl == _TRIPLE_CLUSTER and (cl != CLUSTER_TRYS or symbols[m - 3] != USP_S):
                    return
            currphone = p_dph_t.nphonetot - 1
            if sy == S1:
                add_feature(p_dph_t, FSTRESS_1, currphone)
            if sy == S2:
                add_feature(p_dph_t, FSTRESS_2, currphone)
            if sy == SEMPH:
                add_feature(p_dph_t, FEMPHASIS, currphone)
            return
        # No stress before vowel.
        #
        # The C source unconditionally calls ``phone_feature(pDph_t, sy)``
        # here. ``us_featb`` is sized to the allophone range (0..100),
        # so reading past it for a control-code ``sy >= 100`` is C UB.
        # In practice the C array's tail bytes have FSYLL=0, so the C
        # binary falls through to the boundary check below. We guard
        # the lookup explicitly to keep Python bit-equivalent without
        # invoking UB-style array reads.
        if sy < _PHONE_TABLE_LIMIT and (phone_feature(sy) & FSYLL) != 0:
            return
        # No vowel before syllable ends.
        if SBOUND <= sy <= EXCLAIM:
            return


__all__ = ["get_stress_of_conson"]
