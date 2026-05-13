"""``vv_coartic_across_c`` cross-consonant V-to-V coarticulation helper.

Translated from ``src/dapi/src/ph/ph_sttr2.c`` lines 357-380.

Compute the cross-consonant vowel-to-vowel coarticulation
boundary value (``vvbouval``) and transition duration
(``vvdurtran``) for the ``pDphsettar`` struct. The DECtalk 4.2CD
source effectively zeroes both fields on every code path — the
arithmetic that would have produced a non-zero boundary blend is
commented out, so the function reduces to writing zeros.

The dur-cons > NF100MS branch and the else branch both end up
writing ``vvbouval = 0`` and ``vvdurtran = 0``; the original
formula (``mlsh1(...)`` and ``NF80MS - (dur_cons >> 2)``) is
preserved in the docstring for parity.
"""

from __future__ import annotations

from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.frame_counts import NF100MS


def vv_coartic_across_c(
    p_dph_t: DphT,
    remote_v: int,
    remote_tar: int,
    current_v: int,
    current_tar: int,
    middle_c: int,
    dur_cons: int,
) -> None:
    """Reset ``vvbouval`` / ``vvdurtran`` on the per-target struct.

    Faithful translation of:

    .. code-block:: c

        static void vv_coartic_across_c (PDPH_T pDph_t,
                                         short remoteV, short remotetar,
                                         short currentV, short currenttar,
                                         short middleC, short dur_cons) {
            PDPHSETTAR_ST pDphsettar = pDph_t->pSTphsettar;
            if (dur_cons > NF100MS) {
                pDphsettar->vvbouval = 0;
                pDphsettar->vvdurtran = 0;
            } else {
                // The active arithmetic is commented out in the
                // C source — both fields end up zero either way.
                pDphsettar->vvbouval = 0;
                // mlsh1 (((remotetar - currenttar) *
                //         (NF100MS - dur_cons)), 460);
                pDphsettar->vvdurtran = 0;
                // NF80MS - (dur_cons >> 2);
            }
        }

    Args:
        p_dph_t: PH thread state (used only for ``pSTphsettar``
            access).
        remote_v: Remote-syllable vowel phone code.
        remote_tar: Remote-syllable formant target.
        current_v: Current-syllable vowel phone code.
        current_tar: Current-syllable formant target.
        middle_c: Intervening consonant phone code.
        dur_cons: Consonant duration in frame quanta.
    """
    del remote_v, remote_tar, current_v, current_tar, middle_c
    pdphsettar = p_dph_t.pSTphsettar
    if not isinstance(pdphsettar, DphSettarSt):
        return
    if dur_cons > NF100MS:
        pdphsettar.vvbouval = 0
        pdphsettar.vvdurtran = 0
    else:
        pdphsettar.vvbouval = 0
        pdphsettar.vvdurtran = 0


__all__ = ["vv_coartic_across_c"]
