"""``set_user_target`` helper from ph_drwt02.c.

Translated from ``src/dapi/src/ph/ph_drwt02.c`` lines 2183-2256.

Handles user-specified F0 commands when ``f0mode`` is one of the
"targets-supplied-by-user" modes (singing, phone-targets,
time-value pairs). Two encodings share the same command word:

- Values ``1..37`` are 1-based indices into :data:`notetab` (sung
  notes C2..C5). A vibrato switch fires and the contour glides
  toward the target over 16 frames.
- Values ``> 37`` are direct F0 specifications in Hz (scaled by
  10 in the resulting :data:`tarseg`). The contour glides linearly
  to the target either over ``dtimf0`` frames (if
  ``f0mode == TIME_VALUE_SPECIFIED``) or over the duration of the
  current phoneme (otherwise).

Values in ``(1500, 6000]`` are additionally treated as a
"pressure command" — the thousands digit encodes how much to drop
``spressure`` from its baseline of 600. The remaining ``value %
1000`` is then re-interpreted under the rules above.
"""

from __future__ import annotations

from typing import Final

from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.getcosine import HIGHEST_F0, LOWEST_F0
from dectalk.ph.inton_constants import TIME_VALUE_SPECIFIED
from dectalk.ph.notetab import notetab

# Pressure-encoding boundary: command words above this carry a
# thousands-digit pressure offset.
_PRESSURE_THRESHOLD: Final[int] = 1500

# Pressure-encoding divisor / multiplier: ``spressure = (6 - tmp) * 100``
# where ``tmp = raw / _PRESSURE_DIVISOR``.
_PRESSURE_DIVISOR: Final[int] = 1000
_PRESSURE_BASELINE: Final[int] = 6
_PRESSURE_STEP: Final[int] = 100

# Maximum 1-based notetab index — values up to this map to sung notes;
# higher values map to direct F0 specifications in Hz.
_MAX_NOTETAB_INDEX: Final[int] = 37


def _c_div(a: int, b: int) -> int:
    """Return ``a / b`` with C truncate-toward-zero integer semantics."""
    if (a < 0) ^ (b < 0):
        return -(abs(a) // abs(b))
    return abs(a) // abs(b)


def _c_mod(a: int, b: int) -> int:
    """Return ``a % b`` with C truncate-toward-zero remainder semantics."""
    return a - _c_div(a, b) * b


def _apply_pressure_offset(p_dph_t: DphT, raw: int) -> None:
    """Decode and apply the thousands-digit pressure-offset half of the cmd."""
    tmp = _c_div(raw, _PRESSURE_DIVISOR)
    if tmp > 0:
        p_dph_t.spressure = (_PRESSURE_BASELINE - tmp) * _PRESSURE_STEP
    else:
        p_dph_t.spressure = 0


def _set_sung_note_target(pdphsettar: DphSettarSt, p_dph_t: DphT, note_index: int) -> None:
    """Resolve a 1-based notetab index into the per-frame contour delta."""
    pdphsettar.newnote = notetab[note_index - 1]
    pdphsettar.vibsw = 1
    # delnote*4 so transition happens over 16 frames (100 ms).
    pdphsettar.delnote = (pdphsettar.newnote - p_dph_t.f0) >> 2


def _set_linear_glide_target(
    pdphsettar: DphSettarSt, p_dph_t: DphT, ps_f0command: list[int]
) -> None:
    """Resolve a direct-Hz F0 command into a linear glide per-frame delta."""
    ps_f0command[0] *= 10
    if ps_f0command[0] < LOWEST_F0:
        ps_f0command[0] = LOWEST_F0
    elif ps_f0command[0] > HIGHEST_F0:
        ps_f0command[0] = HIGHEST_F0
    pdphsettar.newnote = ps_f0command[0]
    pdphsettar.vibsw = 0

    # Compute duration of linear transition.
    trandur = 0
    if p_dph_t.f0mode == TIME_VALUE_SPECIFIED:
        trandur = pdphsettar.dtimf0
        # Dur since last f0 command.
        if trandur == 0:
            p_dph_t.f0 = pdphsettar.newnote
    else:
        # Dur of cur phoneme — ``allodurs[npg+1]`` (with bounds guard).
        idx = pdphsettar.npg + 1
        if 0 <= idx < len(p_dph_t.allodurs):
            trandur = p_dph_t.allodurs[idx]

    # Compute incremental change to f0*10 every frame (40 = 10 * 4).
    pdphsettar.delnote = (pdphsettar.newnote - p_dph_t.f0) << 2
    if pdphsettar.delnote > 0:
        pdphsettar.delnote += trandur - 1  # Round upward.
    if pdphsettar.delnote < 0:
        pdphsettar.delnote -= trandur - 1  # Round downward (away from zero).
    if trandur != 0:
        pdphsettar.delnote = _c_div(pdphsettar.delnote, trandur)
    # else: instantaneous jump (was an 8-frame transition in older code).


def set_user_target(p_dph_t: DphT, ps_f0command: list[int]) -> None:
    """Resolve a user-spec F0 command into a sung note or linear glide.

    Faithful translation of:

    .. code-block:: c

        static void set_user_target(PDPH_T pDph_t, short *psF0command) {
            short trandur=0;
            PDPHSETTAR_ST pDphsettar = pDph_t->pSTphsettar;
            int tmp;

            if (*psF0command > 1500) {
                tmp = (*psF0command / 1000);
                if (tmp > 0) {
                    tmp = (6-tmp)*100;
                    pDph_t->spressure = tmp;
                } else {
                    pDph_t->spressure = 0;
                }
            }
            *psF0command = *psF0command%1000;   /* 2000 is offset flag */

            if (*psF0command <= 37) {
                /* Pointer to C5, highest possible sung note */
                pDphsettar->newnote = notetab[*psF0command-1];
                pDphsettar->vibsw = 1;
                /* delnote*4 so transition happens over 16 frames (100 ms) */
                pDphsettar->delnote = ((pDphsettar->newnote - pDph_t->f0) >> 2);
            }
            else {                                              /* Straight-lines */
                *psF0command *= 10;
                if (*psF0command < LOWEST_F0)  *psF0command = LOWEST_F0;
                else if (*psF0command > HIGHEST_F0) *psF0command = HIGHEST_F0;
                pDphsettar->newnote = *psF0command;
                pDphsettar->vibsw = 0;
                /* Compute duration of linear transition */
                if (pDph_t->f0mode == TIME_VALUE_SPECIFIED) {
                    trandur = pDphsettar->dtimf0;
                    /* Dur since last f0 command */
                    if (trandur == 0)
                        pDph_t->f0 = pDphsettar->newnote;
                }
                else {
                    trandur = pDph_t->allodurs[pDphsettar->npg+1]; /* Dur of cur phoneme */
                }
                /* Compute incremental change to f0*10 every frame */
                pDphsettar->delnote = (pDphsettar->newnote - pDph_t->f0) << 2; /* f0 change * 40 */
                if (pDphsettar->delnote > 0) {
                    pDphsettar->delnote += (trandur - 1);   /* Round upward */
                }
                if (pDphsettar->delnote < 0) {
                    pDphsettar->delnote -= (trandur - 1);   /* Round downward */
                }
                if (trandur != 0) {
                    pDphsettar->delnote /= trandur;
                }
            }
            pDphsettar->delcum = 0;
            pDphsettar->f0start = pDph_t->f0;
        }

    Notes on faithful detail:

    - The "pressure" branch fires when the *raw* command word
      exceeds 1500. The thousands digit is ``raw // 1000`` in C
      (truncate); for the in-range inputs ``1501..5999`` that's
      always ``1..5``, so ``spressure`` is set to ``(6 - tmp) * 100``
      (i.e. 500, 400, 300, 200, 100). The C ``else`` branch
      (``tmp <= 0``) is dead code under those bounds but the port
      preserves it.
    - ``*psF0command = *psF0command % 1000`` runs unconditionally —
      it strips the pressure-offset for all branches below.
    - For the sung-note branch, ``ps_f0command[0] - 1`` indexes
      :data:`notetab` (1-based to 0-based). Values outside
      ``1..37`` raise ``IndexError`` in C (undefined-but-likely
      out-of-bounds read); the port keeps the same indexing.
    - The linear-glide branch clamps the *10x* F0 to
      ``[LOWEST_F0, HIGHEST_F0]`` (500..5121, both in deciHz),
      writes the clamped target, and then computes a per-frame
      delta scaled by 40. The pre-division rounding (``+ trandur - 1``
      when positive, ``- trandur + 1`` when negative) gives
      "round away from zero" after the subsequent C-truncate
      division.
    - ``delnote /= trandur`` is C integer division (truncate toward
      zero). The Python port uses :func:`_c_div` to preserve the
      sign behaviour vs. Python's ``//`` (which floors).
    - The ``short *psF0command`` argument is modelled as a
      single-element ``list[int]`` mutated in place.

    Args:
        p_dph_t: PH thread state (mutated in-place — sets ``f0``,
            ``spressure`` plus several ``pSTphsettar`` fields).
        ps_f0command: Single-element list cell holding the user
            F0 command word. Stripped of its pressure offset and
            (for the linear-glide branch) scaled to 10x Hz and
            clamped on return.
    """
    pdphsettar = p_dph_t.pSTphsettar
    if not isinstance(pdphsettar, DphSettarSt):
        return

    # Pressure-offset extraction: thousands digit encodes a
    # pressure drop in steps of 100 from a baseline of 600.
    if ps_f0command[0] > _PRESSURE_THRESHOLD:
        _apply_pressure_offset(p_dph_t, ps_f0command[0])

    # Strip the pressure offset (comment in C says "2000 is offset flag").
    ps_f0command[0] = _c_mod(ps_f0command[0], _PRESSURE_DIVISOR)

    if ps_f0command[0] <= _MAX_NOTETAB_INDEX:
        # Sung-note path: index 1..37 → notetab → 16-frame glide.
        _set_sung_note_target(pdphsettar, p_dph_t, ps_f0command[0])
    else:
        # Straight-line glide path: command is direct F0 in Hz.
        _set_linear_glide_target(pdphsettar, p_dph_t, ps_f0command)

    pdphsettar.delcum = 0
    pdphsettar.f0start = p_dph_t.f0


__all__ = ["set_user_target"]
