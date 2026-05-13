"""Per-phoneme PH parameter initializer from ph_claus.c.

Translated from ``src/dapi/src/ph/ph_claus.c`` lines 627-633.

:func:`init_pars` is called at the start of each phoneme to reset
the per-phoneme parameter cursors:

- ``tcum`` → -1 (frame counter relative to phoneme start; -1
  means "before any frames").
- ``nphone`` → -1 (current phoneme index; -1 means "no phoneme
  selected yet").
- ``durfon`` → 0 (duration of current phoneme in frames).
- ``openquo`` → ``alloopenq[0]`` (open-quotient initial value
  from the per-phoneme open-quotient array).

The C source declares this ``static`` (file-local), but it's
useful as part of the public per-thread init API.
"""

from __future__ import annotations

from dectalk.ph.dph_t import DphT


def init_pars(p_dph_t: DphT) -> None:
    """Reset per-phoneme parameter cursors on ``p_dph_t``.

    Faithful translation of:

    .. code-block:: c

        static void init_pars(PDPH_T pDph_t) {
            pDph_t->tcum = -1;
            pDph_t->nphone = -1;
            pDph_t->durfon = 0;
            pDph_t->openquo = pDph_t->alloopenq[0];
        }

    Args:
        p_dph_t: PH thread-state instance to mutate.
    """
    p_dph_t.tcum = -1
    p_dph_t.nphone = -1
    p_dph_t.durfon = 0
    # ``alloopenq`` may be empty if init_phclause hasn't been called
    # yet; treat as 0 in that case (matches uninitialised C behaviour
    # — the array is zero-filled by init_phclause on first call).
    if p_dph_t.alloopenq:
        p_dph_t.openquo = p_dph_t.alloopenq[0]
    else:
        p_dph_t.openquo = 0


__all__ = ["init_pars"]
