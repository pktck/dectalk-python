"""Voice-parameter setter from ph_vset.c.

Translated from ``src/dapi/src/ph/ph_vset.c`` lines 175-229.

:func:`setparam` clamps a requested voice parameter value to its
``LIMIT`` table range and writes it to ``pDph_t->curspdef[which]``.

The C source has two paths based on ``pVtm_t->bDoTuning`` (the
autotune flag):

- When autotuning, the raw ``value`` is clamped to the LIMIT range
  and stored.
- When not autotuning, the per-voice ``tunedef[voice][which]``
  offset is *added* first (unless voice is Variable Val), then
  clamped, then stored.

Either way, the function sets ``loadspdef = TRUE`` to ask the
synth side to reload the speaker definition on the next clause.

The Python port takes a :class:`DphT` plus the small handful of
scalar args the function reads from ``pKsd_t`` / ``pVtm_t`` so
callers can use it without porting full KSD/VTM struct skeletons.
"""

from __future__ import annotations

from dectalk.include.cmd_codes import SPD_OQ, SPD_SEX
from dectalk.include.dectalk import Voice
from dectalk.ph.dph_t import DphT
from dectalk.ph.queue_structs import Limit


def setparam(
    p_dph_t: DphT,
    which: int,
    value: int,
    *,
    limit_table: tuple[Limit, ...],
    last_voice: int,
    b_do_tuning: bool,
) -> None:
    """Clamp + store a voice-parameter value into ``curspdef[which]``.

    Faithful translation of:

    .. code-block:: c

        void setparam(LPTTS_HANDLE_T phTTS, int which, int value) {
            LIMIT *lp;
            int voice = pKsd_t->last_voice;
            if (which < SPD_SEX || which > SPD_OQ) return;
            lp = &limit[which];
            if (pVtm_t->bDoTuning) {
                if (value < lp->l_min) value = lp->l_min;
                else if (value > lp->l_max) value = lp->l_max;
                pDph_t->curspdef[which] = value;
            } else {
                if (voice != VARIABLE_VAL)
                    value += pDph_t->tunedef[voice][which];
                if (value < lp->l_min) value = lp->l_min;
                else if (value > lp->l_max) value = lp->l_max;
                pDph_t->curspdef[which] = value;
            }
            pDph_t->loadspdef = TRUE;
        }

    Args:
        p_dph_t: PH thread-state to mutate.
        which: Parameter index (must be in ``SPD_SEX..SPD_OQ``).
            Out-of-range indices are silently ignored.
        value: Requested value (pre-tune offset).
        limit_table: ``LIMIT[]`` table (typically
            :data:`dectalk.ph.voice_limits.limit`).
        last_voice: Currently-active voice index (``pKsd_t->last_voice``).
            When this isn't :data:`Voice.VARIABLE_VAL` and autotuning
            is off, the per-voice tune offset is added before clamping.
        b_do_tuning: True if the autotuner is running (skip the tune
            offset).
    """
    if which < SPD_SEX or which > SPD_OQ:
        return

    lp = limit_table[which]

    if (
        not b_do_tuning
        and last_voice != Voice.VARIABLE_VAL
        and 0 <= last_voice < len(p_dph_t.tunedef)
    ):
        # Add per-voice tune offset, if a tunedef row is loaded.
        row = p_dph_t.tunedef[last_voice]
        if which < len(row):
            value += row[which]

    # Clamp.
    value = max(lp.l_min, min(value, lp.l_max))

    # Store + ask for reload.
    if len(p_dph_t.curspdef) <= which:
        # Grow curspdef to at least ``which + 1`` entries.
        p_dph_t.curspdef.extend([0] * (which + 1 - len(p_dph_t.curspdef)))
    p_dph_t.curspdef[which] = value
    p_dph_t.loadspdef = 1  # TRUE


__all__ = ["setparam"]
