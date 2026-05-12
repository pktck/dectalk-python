"""Per-parameter state struct from viphdefs.h.

Translated from ``src/dapi/src/vtm/viphdefs.h``. The ``PARAMETER``
struct holds the runtime state for one Klatt voice parameter
(F1..TILT). The PH module stores one of these per parameter in
``pDph_t->param[VOICE_PARS - 1]`` and updates them each frame to
compute the next target.

Note: not every field is meaningful for every parameter. The C
source notes:

  - ``durlin`` / ``deldip`` apply only to F1, F2, F3, B1, B2, B3.
  - ``tspesh`` / ``pspesh`` apply only to B1, B2, AV, AP, A2, A3,
    A4, A5, A6, AB.

In Python the unused fields stay at 0; readers should know which
parameters they're querying.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Parameter:
    """Per-parameter Klatt-frame state (one of 16 in ``pDph_t->param[]``).

    Faithful translation of:

    .. code-block:: c

        typedef struct Parameters {
            short tarcur;    // current target value
            short durlin;    // diphthong line duration / phone duration
            short deldip;    // delta per update for diphthong
            short dipcum;    // cumulative diphthongization
            short ftran;     // forward transition
            short dftran;    // delta for forward transition
            short btran;     // backward transition
            short dbtran;    // delta for backward transition
            short tbacktr;   // begin of backward transition
            short tspesh;    // duration of special const at phone start
            short pspesh;    // value of special const at phone start
            short tarnex;    // next target value
            short tarlas;    // last target value
            short tarend;    // last-phoneme target value
            short *ndip;     // diphthong specification ptr (or None)
            short *outp;     // output destination ptr (or None)
        } PARAMETER;

    The ``ndip`` and ``outp`` pointers are modelled as ``int | None``
    indices into the parent ``dipspec[]`` / ``parstochip[]`` arrays
    (or ``None`` when not set). This avoids modelling C pointers
    directly while preserving the field's role.

    Attributes:
        tarcur: Current target value.
        durlin: Diphthong line / phoneme duration (frames).
        deldip: Delta value per update for diphthong specification.
        dipcum: Cumulative diphthongization amount since the start of the
            current straight line.
        ftran: Forward transition value.
        dftran: Forward-transition delta per update.
        btran: Backward transition value.
        dbtran: Backward-transition delta per update.
        tbacktr: Start time of the backward transition (relative to
            phoneme onset).
        tspesh: Duration of the special constant at the phone start.
        pspesh: Value of the special constant at the phone start.
        tarnex: Next phoneme's target.
        tarlas: Previous phoneme's target.
        tarend: Final target of the last phoneme.
        ndip: Index into the diphthong-specification table (or None).
        outp: Index into the parstochip output array (or None).
    """

    tarcur: int = 0
    durlin: int = 0
    deldip: int = 0
    dipcum: int = 0
    ftran: int = 0
    dftran: int = 0
    btran: int = 0
    dbtran: int = 0
    tbacktr: int = 0
    tspesh: int = 0
    pspesh: int = 0
    tarnex: int = 0
    tarlas: int = 0
    tarend: int = 0
    ndip: int | None = None
    outp: int | None = None


__all__ = ["Parameter"]
