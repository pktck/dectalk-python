"""``SetSampleRate`` VTM sample-rate selector from vtm_i.c.

Translated from ``src/dapi/src/vtm/vtm_i.c`` lines 765-815.

The C function selects between the two supported VTM sample rates --
``PC_SAMPLE_RATE`` (11025 Hz, the "11 KHz" path) and
``MULAW_SAMPLE_RATE`` (8000 Hz, the "8 KHz" path) -- and stores the
matching fixed-point rate-scaling constants used by the Klatt
synthesiser's resonator-bandwidth math.

The C original mutates a clutch of file-scope globals
(``uiSampleRate``, ``SampleRate``, ``SamplePeriod``, ``bEightKHz``,
``uiSampleRateChange``, ``rate_scale``, ``inv_rate_scale``,
``uiNumberOfSamplesPerFrame``); the Python port has no equivalent
global state, so :func:`set_sample_rate` returns a fresh
:class:`VtmSampleRate` dataclass instead. Callers thread that value
through the resonator helpers (``d2pole_cf45`` et al.) the same way
the C source reads the globals.

Fixed-point notes:

- ``rate_scale = 18063`` at 11 kHz is ``1.1`` in Q14 format
  (``int(1.1 * 16384) == 18022`` rounded up to 18063 in the C source).
- ``inv_rate_scale = 29722`` at 11 kHz is ``0.909`` in Q15 format
  (``int(0.909 * 32768) ≈ 29786``; the C uses 29722).
- ``rate_scale = 26214`` at 8 kHz is ``0.8`` in Q15 format
  (``int(0.8 * 32768) == 26214``).
- ``inv_rate_scale = 20480`` at 8 kHz is ``1.25`` in Q14 format
  (``int(1.25 * 16384) == 20480``).

The active ``vtm3.c`` build differs by a single bit (29714 vs 29722
for the 11 kHz ``inv_rate_scale``); the ``vtm_i.c`` values are the
ones the C original of *this* function uses, and the parity test
re-parses that source to guard against drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

# ---- Constants from include/samprate.h + vtm/vismprat.h ------------------

#: ``#define PC_SAMPLE_RATE 11025`` (effective define for the Linux
#: build; see ``src/dapi/src/include/samprate.h`` for the top-level
#: ``#error`` guard that requires the host to set this).
PC_SAMPLE_RATE: int = 11025

#: ``#define MULAW_SAMPLE_RATE 8000`` (``src/dapi/src/include/samprate.h``).
MULAW_SAMPLE_RATE: int = 8000


# ---- Constants from vtm/viport.h -----------------------------------------


class SampleRateChange(IntEnum):
    """``uiSampleRateChange`` enum from ``viport.h``.

    Selects the resonator-bandwidth scaling path the synth uses
    when converting from the 10 kHz reference rate to the active
    output rate.
    """

    #: ``#define SAMPLE_RATE_INCREASE 0`` -- 11 kHz path: scale by
    #: ``inv_rate_scale`` (one shift) to widen the bandwidth.
    INCREASE = 0

    #: ``#define SAMPLE_RATE_DECREASE 1`` -- 8 kHz path: scale by
    #: ``inv_rate_scale`` then ``<<1`` to narrow the bandwidth.
    DECREASE = 1

    #: ``#define NO_SAMPLE_RATE_CHANGE 2`` -- pass-through path used
    #: when the requested rate is neither 8 kHz nor 11.025 kHz.
    NO_CHANGE = 2


# ---- Result dataclass ----------------------------------------------------


@dataclass(slots=True, frozen=True)
class VtmSampleRate:
    """Snapshot of the VTM sample-rate-derived state.

    The C original sets a cluster of file-scope globals; the Python
    port returns this dataclass instead so callers can thread the
    state through the resonator pipeline without sharing module-level
    mutable state.
    """

    #: ``uiSampleRate`` -- the requested output sample rate, in Hz.
    sample_rate: int

    #: ``SamplePeriod`` -- ``1 / SampleRate``, in seconds.
    sample_period: float

    #: ``bEightKHz`` -- True iff the 8 kHz path was selected. False
    #: for 11.025 kHz and for the pass-through path (the C source
    #: never overwrites ``bEightKHz`` in the pass-through branch, so
    #: we conservatively report False, matching the static-init
    #: value in ``vismprat.h``).
    is_eight_khz: bool

    #: ``uiSampleRateChange`` -- which scaling path the resonator
    #: helpers should take. ``NO_CHANGE`` for unsupported rates.
    rate_change: SampleRateChange

    #: ``rate_scale`` -- Q14/Q15 fixed-point rate-scale constant
    #: used by the upsampler / phase math.
    rate_scale: int

    #: ``inv_rate_scale`` -- Q15/Q14 fixed-point inverse-rate-scale
    #: constant used by the resonator-bandwidth helpers
    #: (``d2pole_cf45``, ``d2pole_cf123``, ``d2pole_pf``).
    inv_rate_scale: int

    #: ``uiNumberOfSamplesPerFrame`` -- 71 for 11.025 kHz, 51 for
    #: 8 kHz. Both correspond to a ~6.45 ms VTM frame.
    samples_per_frame: int


# ---- The ported function -------------------------------------------------


def set_sample_rate(sample_rate: int) -> VtmSampleRate:
    """Return the VTM state for ``sample_rate`` (8 kHz or 11.025 kHz).

    Faithful translation of ``void SetSampleRate(unsigned int)``:

    .. code-block:: c

        uiSampleRate = uiSampRate;
        SampleRate = (double)uiSampleRate;
        SamplePeriod = 1.0 / SampleRate;

        if (uiSampleRate == PC_SAMPLE_RATE) {
            bEightKHz = FALSE;
            uiSampleRateChange = SAMPLE_RATE_INCREASE;
            rate_scale = 18063;
            inv_rate_scale = 29722;
            uiNumberOfSamplesPerFrame = 71;
        } else if (uiSampleRate == MULAW_SAMPLE_RATE) {
            bEightKHz = TRUE;
            uiSampleRateChange = SAMPLE_RATE_DECREASE;
            rate_scale = 26214;
            inv_rate_scale = 20480;
            uiNumberOfSamplesPerFrame = 51;
        } else {
            uiSampleRateChange = NO_SAMPLE_RATE_CHANGE;
        }

    The C source's fall-through branch leaves ``bEightKHz``,
    ``rate_scale``, ``inv_rate_scale``, and
    ``uiNumberOfSamplesPerFrame`` at their previous global values.
    Since the Python port has no globals to fall back on, we report
    the ``vismprat.h`` static-init values for those fields (the
    11 kHz defaults) when ``NO_CHANGE`` fires. Callers that need to
    preserve a prior state across a pass-through call must keep the
    old :class:`VtmSampleRate` themselves.

    Args:
        sample_rate: Requested output sample rate in Hz. Only
            ``11025`` and ``8000`` are recognised; any other value
            yields a :attr:`SampleRateChange.NO_CHANGE` result.

    Returns:
        A :class:`VtmSampleRate` with the matching fixed-point
        scaling constants and per-frame sample count.
    """
    sample_period = 1.0 / float(sample_rate)

    if sample_rate == PC_SAMPLE_RATE:
        return VtmSampleRate(
            sample_rate=sample_rate,
            sample_period=sample_period,
            is_eight_khz=False,
            rate_change=SampleRateChange.INCREASE,
            rate_scale=18063,
            inv_rate_scale=29722,
            samples_per_frame=71,
        )
    if sample_rate == MULAW_SAMPLE_RATE:
        return VtmSampleRate(
            sample_rate=sample_rate,
            sample_period=sample_period,
            is_eight_khz=True,
            rate_change=SampleRateChange.DECREASE,
            rate_scale=26214,
            inv_rate_scale=20480,
            samples_per_frame=51,
        )
    # Fall-through branch: the C source only touches
    # ``uiSampleRateChange``; the remaining globals retain their
    # ``vismprat.h`` init values, which are the 11 kHz defaults.
    return VtmSampleRate(
        sample_rate=sample_rate,
        sample_period=sample_period,
        is_eight_khz=False,
        rate_change=SampleRateChange.NO_CHANGE,
        rate_scale=18063,
        inv_rate_scale=29722,
        samples_per_frame=71,
    )


# PEP8-rename alias so the VTM inventory test can match the C function
# name ``SetSampleRate`` against a Python symbol of the same name.
SetSampleRate = set_sample_rate


__all__ = [
    "MULAW_SAMPLE_RATE",
    "PC_SAMPLE_RATE",
    "SampleRateChange",
    "SetSampleRate",
    "VtmSampleRate",
    "set_sample_rate",
]
