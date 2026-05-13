"""``prdurs`` / ``prphdurs`` debug-print stubs from ph_timng.c.

Translated from ``src/dapi/src/ph/ph_timng.c`` lines 331-356 and
369-398.

Both functions are debug-only print helpers gated entirely by
``#ifdef EABDEBUG`` (with an additional ``#ifdef VERBOSE`` nest
in :func:`prphdurs`). The Linux build defines neither flag — both
functions compile to empty bodies and are kept here for ABI
parity / call-site preservation.

``prdurs`` is called from ``ph_sttr2.c``'s timing rules with the
per-rule duration values; ``prphdurs`` would be called at the end
of the timing pass to dump every allophone's final duration to
stdout for debugging.
"""

from __future__ import annotations

from dectalk.ph.dph_t import DphT


def prdurs(
    p_dph_t: DphT,
    phocur: int,
    durinh: int,
    durmin: int,
    deldur: int,
    prcnt: int,
    n: int,
) -> None:
    """Debug-print per-rule duration values.

    Faithful translation of:

    .. code-block:: c

        void prdurs(PDPH_T pDph_t, short phocur, short durinh,
                    short durmin, short deldur, short prcnt, int n) {
        #ifdef EABDEBUG
            if (n == 0)
                printf("Init:inhdur=%3d ...");
            else
                printf("Rule %2d: ...");
        #endif
        }

    The ``EABDEBUG`` flag is not defined in the Linux build, so the
    body is empty; the Python port mirrors that with a no-op.

    Args:
        p_dph_t: PH thread state (unused on non-debug builds).
        phocur: Current phone code.
        durinh: Inherent duration in frame quanta.
        durmin: Minimum duration in frame quanta.
        deldur: Duration delta.
        prcnt: Percent contraction (Q7 fixed-point).
        n: Rule number (0 = init pass).
    """
    del p_dph_t, phocur, durinh, durmin, deldur, prcnt, n


def prphdurs(p_dph_t: DphT) -> None:
    """Debug-print final allophone durations.

    Faithful translation of:

    .. code-block:: c

        void prphdurs(PDPH_T pDph_t) {
        #ifdef EABDEBUG
        #ifdef VERBOSE
            // print every allodur[n] + allofeats[n]
        #endif
        #endif
        }

    Both ``EABDEBUG`` and ``VERBOSE`` are undefined in the Linux
    build, so the body is empty; the Python port mirrors that with
    a no-op.

    Args:
        p_dph_t: PH thread state (unused on non-debug builds).
    """
    del p_dph_t


__all__ = ["prdurs", "prphdurs"]
