"""F0 command queueing helper from ph_inton2.c.

Translated from ``src/dapi/src/ph/ph_inton2.c`` lines 2041-2081.

:func:`make_f0_command` is the queue-side of the F0 intonation
gesture pipeline. The intonation engine builds a sequence of F0
commands (type, target Hz, delay, length) and appends them to
the running ``f0tim`` / ``f0tar`` / ``f0type`` / ``f0length``
arrays on the PH thread state.

The function tracks elapsed time since the last command via a
single-cell ``psCumdur`` argument — the caller passes a pointer
in C; the Python port takes a single-element list ``[int]``.

Each call advances ``nf0tot`` (number of queued commands) until
it hits the ``NPHON_MAX - 1`` cap; past that, further commands
are silently dropped.
"""

from __future__ import annotations

from dectalk.ph.dph_t import DphT
from dectalk.ph.numeric_constants import NPHON_MAX

# Lazy-grow the four f0 arrays to NPHON_MAX entries on first call.
_F0_BUF_SIZE: int = NPHON_MAX


def _ensure_f0_buffers(p_dph_t: DphT) -> None:
    """Ensure the four f0 arrays are at least ``NPHON_MAX`` long."""
    for arr_name in ("f0tim", "f0tar", "f0type", "f0length"):
        arr = getattr(p_dph_t, arr_name)
        if len(arr) < _F0_BUF_SIZE:
            arr.extend([0] * (_F0_BUF_SIZE - len(arr)))


def make_f0_command(
    p_dph_t: DphT,
    f0_type: int,
    rulenumber: int,
    tar: int,
    delay: int,
    length: int,
    ps_cumdur: list[int],
    nphon: int,
) -> None:
    """Append one F0 command to ``p_dph_t``'s f0 queue.

    Faithful translation of:

    .. code-block:: c

        static void make_f0_command(LPTTS_HANDLE_T phTTS, short type,
                                    short rulenumber, short tar,
                                    short delay, short length,
                                    short *psCumdur, short nphon) {
            // Clamp negative delay so cumdur stays >= 0.
            if ((delay + *psCumdur) < 0)
                delay = -(*psCumdur);
            // Append command.
            pDph_t->f0tim[pDph_t->nf0tot]    = *psCumdur + delay;
            pDph_t->f0tar[pDph_t->nf0tot]    = tar;
            pDph_t->f0type[pDph_t->nf0tot]   = type;
            pDph_t->f0length[pDph_t->nf0tot] = length;
            // Reset elapsed-time counter.
            *psCumdur = -delay;
            // Bump count (capped at NPHON_MAX - 1).
            if (pDph_t->nf0tot < NPHON_MAX - 1)
                pDph_t->nf0tot++;
        }

    Args:
        p_dph_t: PH thread-state instance to mutate.
        f0_type: F0-command type code (CGesture / QGesture / etc.).
            Named ``f0_type`` rather than ``type`` to avoid shadowing
            the Python builtin.
        rulenumber: Rule index — passed through for debug logging.
        tar: F0 target in Hz times 10 (deciHz).
        delay: Frame delay relative to the last command (can be negative;
            clamped to ``-*ps_cumdur`` if it would underflow).
        length: Duration of the gesture in frames.
        ps_cumdur: Single-element list holding the elapsed-frames
            counter. Updated in-place: set to ``-delay`` after queueing.
        nphon: Current phoneme index — passed through for debug.
    """
    _ensure_f0_buffers(p_dph_t)

    # Clamp negative delay so cumdur stays >= 0.
    if (delay + ps_cumdur[0]) < 0:
        delay = -ps_cumdur[0]

    n = p_dph_t.nf0tot
    if 0 <= n < _F0_BUF_SIZE:
        p_dph_t.f0tim[n] = ps_cumdur[0] + delay
        p_dph_t.f0tar[n] = tar
        p_dph_t.f0type[n] = f0_type
        p_dph_t.f0length[n] = length

    # Reset elapsed-time counter.
    ps_cumdur[0] = -delay

    # Bump count, capped at NPHON_MAX - 1.
    if p_dph_t.nf0tot < NPHON_MAX - 1:
        p_dph_t.nf0tot += 1


__all__ = ["make_f0_command"]
