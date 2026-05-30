"""F0 command queueing helper from ph_inton0.c.

Translated from ``src/dapi/src/ph/ph_inton0.c`` lines 2049-2084 — the
**second** ``make_f0_command`` definition, active for the production
``ENGLISH_US`` + ``OLD_INTONATION_AND_TIMING`` build. (The first
definition at line 1159 is the ``NWSNOAA`` / ``ENGLISH_UK`` variant and
carries an extra ``type`` parameter.)

Unlike the HLSYN ``ph_inton2.c`` queue helper — which stored four
parallel arrays (``f0tim`` / ``f0tar`` / ``f0type`` / ``f0length``) — the
production helper stores **only** ``f0tim`` and ``f0tar``. The command
*type* is no longer a parameter: it is encoded into the ``tar`` value and
decoded downstream by ``pht0draw``:

- ``tar == 0``     → reset baseline,
- ``tar >= 2000``  → user note (``set_user_target``),
- ``tar`` even     → STEP (``tarhat += tar``),
- ``tar`` odd      → IMPULSE (``tarimp = 2 * tar``).

The ``rulenumber`` and ``length`` parameters are retained to match the C
signature (callers pass them positionally) but are otherwise inert here:
``rulenumber`` feeds only a debug ``printf`` in the C source, and
``length`` is unused by the production build.
"""

from __future__ import annotations

from dectalk.ph.dph_t import DphT
from dectalk.ph.numeric_constants import NPHON_MAX

# Lazy-grow the two stored f0 arrays to NPHON_MAX entries on first call.
_F0_BUF_SIZE: int = NPHON_MAX


def _ensure_f0_buffers(p_dph_t: DphT) -> None:
    """Ensure ``f0tim`` and ``f0tar`` are at least ``NPHON_MAX`` long."""
    for arr_name in ("f0tim", "f0tar"):
        arr = getattr(p_dph_t, arr_name)
        if len(arr) < _F0_BUF_SIZE:
            arr.extend([0] * (_F0_BUF_SIZE - len(arr)))


def make_f0_command(
    p_dph_t: DphT,
    rulenumber: int,
    tar: int,
    delay: int,
    length: int,
    ps_cumdur: list[int],
) -> None:
    """Append one F0 command (``f0tim`` + ``f0tar``) to ``p_dph_t``'s queue.

    Faithful translation of:

    .. code-block:: c

        static void make_f0_command (PDPH_T pDph_t, short rulenumber,
                                     short tar, short delay,
                                     short length, short *psCumdur) {
            if ((delay + *psCumdur) < 0)
                delay = -(*psCumdur);
            pDph_t->f0tim[pDph_t->nf0tot] = *psCumdur + delay;
            pDph_t->f0tar[pDph_t->nf0tot] = tar;
            *psCumdur = (-delay);
            if (pDph_t->nf0tot < NPHON_MAX - 1)
                pDph_t->nf0tot++;
        }

    Args:
        p_dph_t: PH thread-state instance to mutate.
        rulenumber: Originating intonation-rule index. Inert here (debug
            ``printf`` only in the C source); kept for signature parity.
        tar: F0 target — also the *type-encoding* value (see module
            docstring). Stored verbatim in ``f0tar``.
        delay: Frame delay relative to the last command (can be negative;
            clamped to ``-*ps_cumdur`` if it would drive cumdur below 0).
        length: Gesture length in frames. Inert in the production build;
            kept for signature parity.
        ps_cumdur: Single-element list holding the elapsed-frames counter.
            Updated in place to ``-delay`` after queueing.
    """
    del rulenumber, length  # Inert in the production build (signature parity).
    _ensure_f0_buffers(p_dph_t)

    # Clamp negative delay so cumdur stays >= 0.
    if (delay + ps_cumdur[0]) < 0:
        delay = -ps_cumdur[0]

    n = p_dph_t.nf0tot
    if 0 <= n < _F0_BUF_SIZE:
        p_dph_t.f0tim[n] = ps_cumdur[0] + delay
        p_dph_t.f0tar[n] = tar

    # Reset elapsed-time counter.
    ps_cumdur[0] = -delay

    # Bump count, capped at NPHON_MAX - 1.
    if p_dph_t.nf0tot < NPHON_MAX - 1:
        p_dph_t.nf0tot += 1


__all__ = ["make_f0_command"]
