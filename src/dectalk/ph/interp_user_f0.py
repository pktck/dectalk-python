"""``interp_user_f0`` helper from ph_sort.c.

Translated from ``src/dapi/src/ph/ph_sort.c`` lines 1731-1803.

Interprets user-supplied prosodic ``dur`` and ``f0`` values
attached to a symbol. The interpretation depends on the symbol
type:

- For stress/hat symbols (``S1``, ``SEMPH``, ``HAT_RISE``,
  ``HAT_FALL``) with ``f0mode != PHONE_TARGETS_SPECIFIED`` and
  ``!= SINGING``, the dur/f0 become *stress-impulse commands*:
  the f0 value is clamped to ``[0, 199]``, then bumped by 200
  (HAT_RISE), 400 (HAT_FALL), or 1000 (S1/SEMPH) to encode the
  gesture type.  The triple is stored at
  ``user_f0[mf0]`` / ``user_offset[mf0]``, ``mf0`` is bumped, and
  ``f0mode`` switches to ``HAT_F0_SIZES_SPECIFIED``.
- For other symbols with ``f0`` set, the values become note
  commands (small ``f0 % 1000``) or phone-target commands,
  switching ``f0mode`` accordingly.

The C source uses ``short *`` mutable pointers for ``curr_dur``,
``curr_f0``, and ``mf0``; the Python port wraps each in a single-
element ``list[int]`` to preserve the in-place mutation.
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import HAT_FALL, HAT_RISE, S1, SEMPH
from dectalk.ph.dph_t import DphT
from dectalk.ph.inton_constants import (
    HAT_F0_SIZES_SPECIFIED,
    PHONE_TARGETS_SPECIFIED,
    SINGING,
)

_F0_CLAMP = 199
_HAT_RISE_OFFSET = 200
_HAT_FALL_OFFSET = 400
_STRESS_OFFSET = 1000
_SINGING_NOTE_LIMIT = 37  # f0 % 1000 <= 37 → SINGING (notes C2..C5).


def _is_stress_or_hat(sym: int) -> bool:
    """Return True for the stress / hat impulse symbols."""
    return sym in (S1, SEMPH, HAT_RISE, HAT_FALL)


def interp_user_f0(  # noqa: PLR0912
    p_dph_t: DphT,
    curr_dur: list[int],
    curr_f0: list[int],
    curr_in_sym: int,
    mf0: list[int],
) -> None:
    """Interpret a (dur, f0) pair attached to a symbol.

    Faithful translation of:

    .. code-block:: c

        static void interp_user_f0(PDPH_T pDph_t, short *psCurr_dur,
                                   short *psCurr_f0, short curr_in_sym,
                                   short *psMf0) {
            if ((curr_in_sym == S1 || curr_in_sym == SEMPH
                 || curr_in_sym == HAT_RISE || curr_in_sym == HAT_FALL)
                && pDph_t->f0mode != PHONE_TARGETS_SPECIFIED
                && pDph_t->f0mode != SINGING) {
                if (*psCurr_f0 != 0
                    || pDph_t->f0mode == HAT_F0_SIZES_SPECIFIED) {
                    if (*psCurr_f0 < 0) *psCurr_f0 = -*psCurr_f0;
                    if (*psCurr_f0 > 199) *psCurr_f0 = 199;
                    if (curr_in_sym == HAT_RISE) *psCurr_f0 += 200;
                    else if (curr_in_sym == HAT_FALL) *psCurr_f0 += 400;
                    else *psCurr_f0 += 1000;
                    pDph_t->user_f0[*psMf0] = *psCurr_f0;
                    pDph_t->user_offset[*psMf0] = *psCurr_dur;
                    *psCurr_dur = 0;
                    *psCurr_f0 = 0;
                    pDph_t->f0mode = HAT_F0_SIZES_SPECIFIED;
                }
                (*psMf0)++;
            }
            else if (*psCurr_f0 != 0) {
                if (pDph_t->f0mode != HAT_F0_SIZES_SPECIFIED) {
                    if (pDph_t->f0mode != PHONE_TARGETS_SPECIFIED
                        && *psCurr_f0 % 1000 <= 37)
                        pDph_t->f0mode = SINGING;
                    else if (pDph_t->f0mode != SINGING)
                        pDph_t->f0mode = PHONE_TARGETS_SPECIFIED;
                    /* else: mixed-mode error, reset */
                }
                /* else: phoneme/symbol intermix error, reset */
            }
        }

    Args:
        p_dph_t: PH thread state.
        curr_dur: Single-element list wrapping the C ``short *psCurr_dur``.
        curr_f0: Single-element list wrapping the C ``short *psCurr_f0``.
        curr_in_sym: The current input symbol (S1 / HAT_RISE / etc.).
        mf0: Single-element list wrapping the C ``short *psMf0``
            (number of stress/hat symbols seen so far).
    """
    is_hat_or_stress = _is_stress_or_hat(curr_in_sym) and p_dph_t.f0mode not in (
        PHONE_TARGETS_SPECIFIED,
        SINGING,
    )

    if is_hat_or_stress:
        if curr_f0[0] != 0 or p_dph_t.f0mode == HAT_F0_SIZES_SPECIFIED:
            # Truncate unreasonable f0 gestures.
            if curr_f0[0] < 0:
                curr_f0[0] = -curr_f0[0]
            curr_f0[0] = min(curr_f0[0], _F0_CLAMP)
            # Attach gesture-type flag.
            if curr_in_sym == HAT_RISE:
                curr_f0[0] += _HAT_RISE_OFFSET
            elif curr_in_sym == HAT_FALL:
                curr_f0[0] += _HAT_FALL_OFFSET
            else:
                curr_f0[0] += _STRESS_OFFSET

            # Grow + write.
            user_f0 = p_dph_t.user_f0 if p_dph_t.user_f0 is not None else []
            p_dph_t.user_f0 = user_f0
            user_offset = p_dph_t.user_offset if p_dph_t.user_offset is not None else []
            p_dph_t.user_offset = user_offset
            while len(user_f0) <= mf0[0]:
                user_f0.append(0)
            while len(user_offset) <= mf0[0]:
                user_offset.append(0)
            user_f0[mf0[0]] = curr_f0[0]
            user_offset[mf0[0]] = curr_dur[0]

            curr_dur[0] = 0
            curr_f0[0] = 0
            p_dph_t.f0mode = HAT_F0_SIZES_SPECIFIED
        # mf0 counts # of HAT_RISE, HAT_FALL, S1, & SEMPH symbols.
        mf0[0] += 1
    elif curr_f0[0] != 0:
        if p_dph_t.f0mode != HAT_F0_SIZES_SPECIFIED:
            if (
                p_dph_t.f0mode != PHONE_TARGETS_SPECIFIED
                and (curr_f0[0] % 1000) <= _SINGING_NOTE_LIMIT
            ):
                p_dph_t.f0mode = SINGING
            elif p_dph_t.f0mode != SINGING:
                p_dph_t.f0mode = PHONE_TARGETS_SPECIFIED
            else:
                # Singing + phoneme-targets intermix: reset.
                curr_dur[0] = 0
                curr_f0[0] = 0
        else:
            # Phoneme f0 + stress/hat intermix: reset.
            curr_dur[0] = 0
            curr_f0[0] = 0


__all__ = ["interp_user_f0"]
