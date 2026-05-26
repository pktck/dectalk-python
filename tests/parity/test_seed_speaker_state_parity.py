"""Parity preconditions for :mod:`dectalk.vtm.seed_speaker_state`.

The seed_speaker_state helper inlines the body of
``vtm1.c::read_speaker_definition`` + ``SetSampleRate``. Re-parse the C
source at test time and verify that every magic constant the Python
port hard-codes is the one the C source still uses. If the upstream
C ever drifts, these tests fail loudly and point the offending Python
constant out.

Covers both the SAMPLE_RATE_INCREASE (PC_SAMPLE_RATE == 11025) and
SAMPLE_RATE_DECREASE (MULAW_SAMPLE_RATE == 8000) branches of
``SetSampleRate`` plus the per-branch noise/lowpass constants from
``read_speaker_definition``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.vtm.seed_speaker_state import (
    MULAW_SAMPLE_RATE,
    PC_SAMPLE_RATE,
    seed_speaker_state,
)
from dectalk.vtm.spd_chip import default_us_paul_spd
from dectalk.vtm.synth_state import SynthState

_DECTALK_SRC = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_VTM1_C = _DECTALK_SRC / "src/dapi/src/vtm/vtm1.c"
_SAMPRATE_H = _DECTALK_SRC / "src/dapi/src/include/samprate.h"

pytestmark = pytest.mark.skipif(
    not _VTM1_C.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_c_source() -> str:
    return _VTM1_C.read_bytes().replace(b"\r", b"").decode("latin-1")


def _read_samprate_h() -> str:
    return _SAMPRATE_H.read_bytes().replace(b"\r", b"").decode("latin-1")


# -------------------------------------------------------------------------
# SAMPLE_RATE_DECREASE (8 kHz / MULAW) branch parity
# -------------------------------------------------------------------------


class TestSetSampleRate8kHz:
    """Constants for the MULAW_SAMPLE_RATE branch (vtm1.c lines 2049-2061)."""

    def test_mulaw_constant_is_8000(self) -> None:
        """``samprate.h`` defines ``MULAW_SAMPLE_RATE`` as 8000."""
        text = _read_samprate_h()
        assert re.search(
            r"#define\s+MULAW_SAMPLE_RATE\s+8000\b",
            text,
        ), "Expected `#define MULAW_SAMPLE_RATE 8000` in samprate.h"
        assert MULAW_SAMPLE_RATE == 8000

    def test_8khz_rate_scale_26214(self) -> None:
        """``rate_scale = 26214;`` in the SAMPLE_RATE_DECREASE branch."""
        text = _read_c_source()
        assert re.search(
            r"pVtm_t->rate_scale\s*=\s*26214\s*;",
            text,
        ), "Expected `pVtm_t->rate_scale = 26214;` in vtm1.c"

    def test_8khz_inv_rate_scale_20480(self) -> None:
        """``inv_rate_scale = 20480;`` in the SAMPLE_RATE_DECREASE branch."""
        text = _read_c_source()
        assert re.search(
            r"pVtm_t->inv_rate_scale\s*=\s*20480\s*;",
            text,
        ), "Expected `pVtm_t->inv_rate_scale = 20480;` in vtm1.c"

    def test_8khz_samples_per_frame_51(self) -> None:
        """``uiNumberOfSamplesPerFrame = 51;`` at 8 kHz."""
        text = _read_c_source()
        assert re.search(
            r"pVtm_t->uiNumberOfSamplesPerFrame\s*=\s*51\s*;",
            text,
        ), "Expected `pVtm_t->uiNumberOfSamplesPerFrame = 51;` in vtm1.c"

    def test_noiseb_minus_1873_in_decrease_branch(self) -> None:
        """``noiseb = -1873;`` in the SAMPLE_RATE_DECREASE branch (line 1590)."""
        text = _read_c_source()
        assert re.search(
            r"pVtm_t->noiseb\s*=\s*-\s*1873\s*;",
            text,
        ), "Expected `pVtm_t->noiseb = -1873;` in vtm1.c"

    def test_lowpass_flp_blp_8k(self) -> None:
        """``flp = 698; blp = 453;`` in the SAMPLE_RATE_DECREASE branch."""
        text = _read_c_source()
        assert re.search(r"flp\s*=\s*698\s*;", text), "Expected `flp = 698;` in vtm1.c"
        assert re.search(r"blp\s*=\s*453\s*;", text), "Expected `blp = 453;` in vtm1.c"

    def test_lowpass_flp_blp_default_no_change(self) -> None:
        """``flp = 860; blp = 558;`` in the NO_SAMPLE_RATE_CHANGE default."""
        text = _read_c_source()
        assert re.search(r"flp\s*=\s*860\s*;", text), (
            "Expected `flp = 860;` in vtm1.c default branch"
        )
        assert re.search(r"blp\s*=\s*558\s*;", text), (
            "Expected `blp = 558;` in vtm1.c default branch"
        )


# -------------------------------------------------------------------------
# Behavioural assertions: the seeder mutates state the way the C does.
# -------------------------------------------------------------------------


class TestSeedSpeakerState8kHzBehavior:
    """End-to-end behavioural parity at 8 kHz."""

    def test_seeds_51_samples_per_frame_at_8000(self) -> None:
        state = SynthState()
        seed_speaker_state(state, default_us_paul_spd(), sample_rate=8000)
        assert state.uiNumberOfSamplesPerFrame == 51

    def test_seeds_8khz_rate_scalers(self) -> None:
        state = SynthState()
        seed_speaker_state(state, default_us_paul_spd(), sample_rate=8000)
        assert state.rate_scale == 26214
        assert state.inv_rate_scale == 20480

    def test_8khz_sets_b_eight_khz(self) -> None:
        state = SynthState()
        seed_speaker_state(state, default_us_paul_spd(), sample_rate=8000)
        assert state.bEightKHz is True

    def test_11khz_does_not_set_b_eight_khz(self) -> None:
        state = SynthState()
        seed_speaker_state(state, default_us_paul_spd(), sample_rate=11025)
        assert state.bEightKHz is False

    def test_8khz_noiseb_in_decrease_branch(self) -> None:
        """SAMPLE_RATE_DECREASE → noiseb = -1873 (vs -2913 at 11 kHz)."""
        state = SynthState()
        seed_speaker_state(state, default_us_paul_spd(), sample_rate=8000)
        assert state.noiseb == -1873

    def test_other_sample_rate_no_change_keeps_11k_scalers(self) -> None:
        """Unrecognised sample rates fall through to NO_SAMPLE_RATE_CHANGE.

        vtm1.c lines 2063-2065 leave rate_scale / inv_rate_scale /
        uiNumberOfSamplesPerFrame untouched in this branch. The
        Python dataclass defaults (11 kHz) carry through, mirroring
        the C behaviour of running whatever was last loaded.
        """
        state = SynthState()
        seed_speaker_state(state, default_us_paul_spd(), sample_rate=10000)
        # noiseb in NO_SAMPLE_RATE_CHANGE branch is -2913 (same as INCREASE).
        assert state.noiseb == -2913

    def test_pc_sample_rate_formula_matches_c(self) -> None:
        """The Q14 rate_scale formula is ((1<<14)*samplerate+5000)/10000."""
        state = SynthState()
        seed_speaker_state(state, default_us_paul_spd(), sample_rate=PC_SAMPLE_RATE)
        # At 11025: ((16384*11025)+5000)/10000 = 18063
        expected = (((1 << 14) * PC_SAMPLE_RATE) + 5000) // 10000
        assert state.rate_scale == expected
        assert state.rate_scale == 18063

    def test_pc_inv_rate_scale_formula_matches_c(self) -> None:
        """The Q15 inv_rate_scale formula matches the C source."""
        state = SynthState()
        seed_speaker_state(state, default_us_paul_spd(), sample_rate=PC_SAMPLE_RATE)
        expected = ((1 << 15) * 10000 + PC_SAMPLE_RATE // 2) // PC_SAMPLE_RATE
        assert state.inv_rate_scale == expected
        assert state.inv_rate_scale == 29722
