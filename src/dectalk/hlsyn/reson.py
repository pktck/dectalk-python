"""Second-order resonator and anti-resonator (formant filter primitive).

Translated from `src/dapi/src/hlsyn/reson.c` and `reson.h` in the DECtalk
4.2CD source (originally SenSyn 2.2 by Andrew W. Howitt / Eric P. Carlson).

The original C exposes a per-sample `AdvanceResonator(r, x)` API. We keep a
faithful per-sample wrapper for parity with the C, and additionally provide a
vectorized `process` method that uses `scipy.signal.lfilter` for the hot
inner loop — Python per-sample loops would be ~100x too slow for real-time
synthesis.

A second-order pole-pair resonator implements:
    y[n] = A*x[n] + B*y[n-1] + C*y[n-2]
where A, B, C are computed from the formant centre frequency `CF`, bandwidth
`BW`, and sample frequency `SF`. An anti-resonator (zero pair) inverts the
shaping.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

# scipy ships no type stubs as of scipy 1.17; suppress narrowly on the import.
from scipy.signal import (
    lfilter,  # pyright: ignore[reportMissingTypeStubs,reportUnknownVariableType]
)

# Numerical guards from the C source. The denormal threshold prevents very
# small non-zero outputs from accumulating into round-off noise on x87 FPUs;
# we keep the same value for behaviour parity.
MIN_RESON: Final[float] = 1e-4

# A second-order filter needs the two most recent outputs to seed its state.
_STATE_HISTORY: Final[int] = 2


@dataclass(slots=True)
class Resonator:
    """Second-order IIR pole-pair resonator (or zero-pair anti-resonator).

    Filter equation: ``y[n] = A * x[n] + B * y[n-1] + C * y[n-2]``.

    Attributes:
        a: First numerator/feed-forward coefficient ``A``.
        b: Feedback coefficient on the previous output ``B``.
        c: Feedback coefficient on the output two samples ago ``C``.
        z1: Most-recent state sample (``y[n-1]`` for resonator, ``x[n-1]``
            for anti-resonator).
        z2: Second-most-recent state sample.
    """

    a: float = 0.0
    b: float = 0.0
    c: float = 0.0
    z1: float = 0.0
    z2: float = 0.0

    def clear(self) -> None:
        """Reset filter memory (state) without disturbing coefficients."""
        self.z1 = 0.0
        self.z2 = 0.0

    def advance(self, x: float) -> float:
        """Advance the resonator by one sample.

        Equivalent to the C `AdvanceResonator` function.

        Args:
            x: Input sample.

        Returns:
            Filtered output sample. Outputs whose magnitude falls below
            :data:`MIN_RESON` are flushed to zero to suppress denormals.
        """
        y = self.a * x + self.b * self.z1 + self.c * self.z2
        if abs(y) < MIN_RESON:
            y = 0.0
        self.z2 = self.z1
        self.z1 = y
        return y

    def advance_anti(self, x: float) -> float:
        """Advance the anti-resonator by one sample.

        Equivalent to the C `AdvanceAntiResonator`. Same coefficient form as
        :meth:`advance`, but the state holds **input** samples rather than
        outputs (this is what makes the filter a zero pair rather than a
        pole pair).

        Args:
            x: Input sample.

        Returns:
            Filtered output sample.
        """
        y = self.a * x + self.b * self.z1 + self.c * self.z2
        self.z2 = self.z1
        self.z1 = x
        return y

    def set_pole_pair(self, cf_hz: float, bw_hz: float, sf_hz: float) -> None:
        """Compute pole-pair coefficients for the given centre frequency and bandwidth.

        Args:
            cf_hz: Centre (formant) frequency in Hertz.
            bw_hz: -3 dB bandwidth in Hertz.
            sf_hz: Sample frequency in Hertz (typically 11025 for DECtalk).
        """
        pi_t = math.pi / sf_hz
        magnitude = math.exp(-pi_t * bw_hz)
        angle = 2.0 * pi_t * cf_hz
        self.c = -magnitude * magnitude
        self.b = magnitude * math.cos(angle) * 2.0
        self.a = 1.0 - self.b - self.c

    def inter_pole_pair(self, cf_hz: float, bw_hz: float, sf_hz: float) -> None:
        """Update pole-pair coefficients with a smooth state-rescaling.

        When the formant target changes mid-utterance, simply replacing the
        coefficients causes a click; the original :meth:`set_pole_pair`
        rescales the filter state to preserve continuity of the output level.
        Equivalent to the C `InterPolePair`.

        Args:
            cf_hz: New centre frequency in Hertz.
            bw_hz: New bandwidth in Hertz.
            sf_hz: Sample frequency in Hertz.
        """
        old_a = self.a
        self.set_pole_pair(cf_hz, bw_hz, sf_hz)
        if old_a and old_a != self.a:
            scale = math.sqrt(self.a / old_a)
            self.z1 *= scale
            self.z2 *= scale

    def set_zero_pair(self, cf_hz: float, bw_hz: float, sf_hz: float) -> None:
        """Compute zero-pair (anti-resonator) coefficients.

        Implements the C `SetZeroPair`: starts from a pole pair and inverts
        the response by negating ``B`` / ``C`` and reciprocating ``A``.

        Args:
            cf_hz: Centre (anti-formant) frequency in Hertz.
            bw_hz: Bandwidth in Hertz.
            sf_hz: Sample frequency in Hertz.
        """
        self.set_pole_pair(cf_hz, bw_hz, sf_hz)
        self.a = 1.0 / self.a
        self.b *= -self.a
        self.c *= -self.a

    def process(self, x: NDArray[np.float64]) -> NDArray[np.float64]:
        """Filter a buffer of samples vectorized via `scipy.signal.lfilter`.

        Equivalent to calling :meth:`advance` repeatedly but ~100x faster on
        real-world frame sizes. The filter state (``z1``, ``z2``) is updated
        in-place so subsequent calls continue from the correct memory.

        Args:
            x: 1-D float64 array of input samples.

        Returns:
            1-D float64 array of filtered output samples (same length as ``x``).
        """
        # Standard biquad: y = (A x + B y[-1] + C y[-2]) - the C does no
        # second-order zero on the input, so b1 = b2 = 0. lfilter expects:
        #   numerator   b = [a, 0, 0]
        #   denominator a = [1, -b, -c]
        # zi is in 'direct form II transposed'; convert (z1, z2) to that form.
        b_coef = np.asarray([self.a, 0.0, 0.0], dtype=np.float64)
        a_coef = np.asarray([1.0, -self.b, -self.c], dtype=np.float64)
        # Initial transposed-DFII state from our (z1, z2) which were stored as
        # filter outputs. For b = [a,0,0], the equivalence is:
        #   zi[0] = b * z1 + c * z2   (becomes y[n-1] contribution)
        #   zi[1] = c * z1            (becomes y[n-2] contribution)
        zi = np.asarray([self.b * self.z1 + self.c * self.z2, self.c * self.z1], dtype=np.float64)
        y, _zf = lfilter(b_coef, a_coef, x, zi=zi)
        # Update (z1, z2) from the last two output samples; this is simpler
        # than inverting the transposed-DFII state.
        n = y.size
        if n >= _STATE_HISTORY:
            self.z1 = float(y[-1])
            self.z2 = float(y[-2])
        elif n == 1:
            self.z2 = self.z1
            self.z1 = float(y[-1])
        return np.asarray(y, dtype=np.float64)
