"""Tone-generation helper from playtone.c.

Translated from ``src/dapi/src/vtm/playtone.c``:

- :func:`tone` — generate a single tone sample, advancing the phase.

The C original is the static helper ``Tone(PhaseIncrement, *pPhase)``
that the tone-injection paths use to emit a sine-wave sample. The
phase is stored as a double in ``[0, TWO_PI_EQUIVALENT)`` and wraps
back to the start when it crosses the table boundary.

Two implementations are exposed:

- :func:`tone` (matches LOWCOMPUTE) — quantises the phase to an
  integer index and reads :data:`SineTable`. Identical samples to
  what the C source produces on the embedded build profile.
- :func:`tone_exact` (matches the non-LOWCOMPUTE path) — calls
  :func:`math.sin` directly. Used by the desktop/x86 binary.
"""

from __future__ import annotations

import math

from dectalk.vtm.sinetab import TWO_PI_EQUIVALENT, SineTable


def tone(phase_increment: float, phase: float) -> tuple[float, float]:
    """Return ``(sample, new_phase)`` using the SineTable lookup.

    Faithful translation of the LOWCOMPUTE branch:

    .. code-block:: c

        Sample = SineTable[(int)*pPhase];
        *pPhase += PhaseIncrement;
        if (*pPhase >= TWO_PI_EQUIVALENT)
            *pPhase -= TWO_PI_EQUIVALENT;
        return Sample;

    The C source updates ``*pPhase`` in place; the Python version
    returns the new phase as the second tuple element so callers
    can rebind locally.

    Args:
        phase_increment: Per-sample phase advance (in
            ``TWO_PI_EQUIVALENT`` units; e.g. for a 440 Hz tone at
            11025 Hz sample rate, ``440 / 11025 * 1024 ≈ 40.87``).
        phase: Current phase in ``[0, TWO_PI_EQUIVALENT)``.

    Returns:
        ``(sample, new_phase)``.
    """
    sample = SineTable[int(phase)]
    new_phase = phase + phase_increment
    if new_phase >= TWO_PI_EQUIVALENT:
        new_phase -= TWO_PI_EQUIVALENT
    return sample, new_phase


def tone_exact(phase_increment: float, phase: float) -> tuple[float, float]:
    """Return ``(sample, new_phase)`` using :func:`math.sin` directly.

    Faithful translation of the non-LOWCOMPUTE branch:

    .. code-block:: c

        Sample = sin(*pPhase);
        // ... same phase-update logic ...

    The desktop binary uses this path. Note that ``*pPhase`` is in
    radians here (range ``[0, 2*pi)``), not ``[0, 1024)``, because
    the non-LOWCOMPUTE build defines ``TWO_PI_EQUIVALENT`` as
    ``2*pi``. Callers must use a different phase-increment scale.

    Args:
        phase_increment: Per-sample phase advance in radians.
        phase: Current phase in radians.

    Returns:
        ``(sample, new_phase)`` where ``sample = sin(phase)``.
    """
    sample = math.sin(phase)
    new_phase = phase + phase_increment
    # The non-LOWCOMPUTE build wraps at 2*pi, not 1024. Caller has
    # to pick the right TWO_PI_EQUIVALENT for their phase scheme;
    # we conservatively wrap at the same boundary that the LUT
    # uses to keep symmetry, since callers usually pre-rescale.
    if new_phase >= 2 * math.pi:
        new_phase -= 2 * math.pi
    return sample, new_phase


__all__ = ["tone", "tone_exact"]
