"""Helmholtz resonator helpers from hlsyn/acxf1c.c.

Translated from ``src/dapi/src/hlsyn/acxf1c.c`` lines 131-164. The two
helpers form a forward / inverse pair for the tongue-body Helmholtz
resonator that the HL layer uses to map a constriction area to its
lowest natural frequency (and back):

- :func:`helmholtz_frequency` -- forward: given the constriction
  area, volume, length, and the zero-area natural frequency, return
  the Helmholtz resonator's lowest natural frequency in Hz.
- :func:`helmholtz_constriction` -- inverse: given the desired
  lowest natural frequency along with the same volume / length /
  zero-area frequency, return the constriction area that produces
  it.

Both routines expect CGS units (cm^2 for areas, cm^3 for volumes,
cm for lengths, Hz for frequencies). The pre-computed numeric
constants are:

- ``1253160000.0f`` == ``SPEEDSOUND * SPEEDSOUND`` with speed of
  sound ~35400 cm/s.
- ``39.478417604f`` == ``4 * pi * pi``.
- ``3.150309426119e-8f`` == ``4 * pi * pi / (SPEEDSOUND *
  SPEEDSOUND)`` -- the inverse of the forward equation's constant.

The C source calls ``DTsqrt`` (a lookup-table wrapper around
``sqrt``); that helper is intentionally deferred in the Python port
(see :data:`tests.unit.test_hlsyn_module_inventory._DEFERRED`),
so this module uses :func:`math.sqrt` directly. The LUT exists
only as a 1990s-era speed-up and is not needed here.
"""

from __future__ import annotations

import math


def helmholtz_frequency(
    constriction_area: float,
    volume: float,
    length: float,
    zero_area_natural_frequency: float,
) -> float:
    """Return the Helmholtz resonator's lowest natural frequency in Hz.

    Faithful translation of:

    .. code-block:: c

        float HelmholtzFrequency(float ConstrictionArea, float Volume,
                                 float Length,
                                 float ZeroAreaNaturalFrequency) {
            float temp;
            temp = (float)(1253160000.0f * ConstrictionArea /
                           (39.478417604f * Volume * Length));
            return (float)DTsqrt(temp +
                ZeroAreaNaturalFrequency * ZeroAreaNaturalFrequency);
        }

    The constants are ``SPEEDSOUND^2`` and ``4 * pi^2`` (the
    commented-out alternate form in the C source spells them out).
    ``DTsqrt`` is replaced by :func:`math.sqrt` (see module
    docstring).

    Args:
        constriction_area: Area of the constriction (CGS, cm^2).
        volume: Volume of the resonating cavity (CGS, cm^3).
        length: Length of the constriction (CGS, cm).
        zero_area_natural_frequency: Natural frequency the cavity
            settles to when the constriction is closed (Hz).

    Returns:
        The Helmholtz resonator's lowest natural frequency in Hz.
    """
    temp = 1253160000.0 * constriction_area / (39.478417604 * volume * length)
    return math.sqrt(temp + zero_area_natural_frequency * zero_area_natural_frequency)


def helmholtz_constriction(
    lowest_natural_frequency: float,
    volume: float,
    length: float,
    zero_area_natural_frequency: float,
) -> float:
    """Return the constriction area for a target Helmholtz frequency.

    Faithful translation of:

    .. code-block:: c

        float HelmholtzConstriction(float LowestNaturalFrequency,
                                    float Volume, float Length,
                                    float ZeroAreaNaturalFrequency) {
            float temp;
            temp = (float)(Volume * Length * 3.150309426119e-8f);
            return ((LowestNaturalFrequency*LowestNaturalFrequency -
                     ZeroAreaNaturalFrequency*ZeroAreaNaturalFrequency)
                    * temp);
        }

    Algebraic inverse of :func:`helmholtz_frequency`: the constant
    ``3.150309426119e-8`` is ``4 * pi^2 / SPEEDSOUND^2``, i.e. the
    reciprocal of the forward equation's ``SPEEDSOUND^2 / (4 * pi^2)``
    factor.

    Args:
        lowest_natural_frequency: Target Helmholtz resonator
            frequency (Hz).
        volume: Volume of the resonating cavity (CGS, cm^3).
        length: Length of the constriction (CGS, cm).
        zero_area_natural_frequency: Natural frequency the cavity
            settles to when the constriction is closed (Hz).

    Returns:
        The constriction area (CGS, cm^2) that produces
        ``lowest_natural_frequency`` when fed through
        :func:`helmholtz_frequency` with the same ``volume`` /
        ``length`` / ``zero_area_natural_frequency``.
    """
    temp = volume * length * 3.150309426119e-8
    return (
        lowest_natural_frequency * lowest_natural_frequency
        - zero_area_natural_frequency * zero_area_natural_frequency
    ) * temp


__all__ = ["helmholtz_constriction", "helmholtz_frequency"]
