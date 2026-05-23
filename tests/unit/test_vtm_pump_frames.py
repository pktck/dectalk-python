"""Smoke + parity-precondition tests for the vtm1 alternative synth path.

Covers :mod:`dectalk.vtm.pump_frames` (the ``DECTALK_USE_VTM1=1``
synth-path bridge wired in :func:`dectalk.api.speak._speak_via_python_full`)
and :mod:`dectalk.vtm.seed_speaker_state` (the per-utterance bring-up
that mirrors ``vtm1.c::read_speaker_definition`` + ``SetSampleRate``).

The full bit-parity test against the C oracle's PCM output is gated
on Phase E (the PH stage matching the C kernel sample-for-sample);
until that lands, this file establishes:

- The seeder populates :class:`SynthState` with the same well-known
  constants the C source uses (verified by re-parsing ``vtm1.c``
  for those constants).
- A deterministic parstochip frame sequence runs end-to-end through
  ``pump_frames_via_vtm1`` and produces int16 PCM of the right shape.
- The wiring in ``_speak_via_python_full`` actually routes through
  ``pump_frames_via_vtm1`` when ``DECTALK_USE_VTM1=1`` is set --
  the function-import path is exercised but the audio output is not
  bit-compared to the C oracle (that test ships in Phase E).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np
import pytest

from dectalk.ph.param_indices import (
    OUT_AV,
    OUT_F1,
    OUT_F2,
    OUT_F3,
    OUT_FZ,
    OUT_PH,
    OUT_T0,
    OUT_TLT,
)
from dectalk.vtm.pump_frames import pump_frames_via_vtm1
from dectalk.vtm.seed_speaker_state import seed_speaker_state
from dectalk.vtm.spd_chip import default_us_paul_spd
from dectalk.vtm.synth_state import SynthState

_DECTALK_SRC = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_VTM1_C = _DECTALK_SRC / "src/dapi/src/vtm/vtm1.c"


def _make_parstochip_frame(av_db: int = 65, ph_value: int = 1) -> list[int]:
    """Build a single 40-cell parstochip array with reasonable voicing defaults."""
    chip = [0] * 40
    chip[OUT_T0] = 100
    chip[OUT_F1] = 500
    chip[OUT_F2] = 1500
    chip[OUT_F3] = 2500
    chip[OUT_FZ] = 290
    chip[OUT_TLT] = 18
    chip[OUT_AV] = av_db
    chip[OUT_PH] = ph_value  # non-zero -> rampdown gating off
    # Bandwidths at non-zero defaults so the parstochip slots PH-stage
    # would have written into are populated.
    for i in (14, 15, 16):  # OUT_B1, OUT_B2, OUT_B3
        chip[i] = max(60, 60 + i * 30)
    return chip


# -------------------------------------------------------------------------
# seed_speaker_state: SynthState population
# -------------------------------------------------------------------------


class TestSeedSpeakerState:
    def test_sample_rate_other_than_11025_raises(self) -> None:
        state = SynthState()
        chip = default_us_paul_spd()
        with pytest.raises(NotImplementedError, match="11025"):
            seed_speaker_state(state, chip, sample_rate=8000)

    def test_11k_path_sets_71_samples_per_frame(self) -> None:
        state = SynthState()
        seed_speaker_state(state, default_us_paul_spd())
        assert state.uiNumberOfSamplesPerFrame == 71  # ((11025*64)+5000)/10000

    def test_11k_path_sets_rate_scalers(self) -> None:
        state = SynthState()
        seed_speaker_state(state, default_us_paul_spd())
        # The Q14/Q15 rate-scale constants from vtm1.c::SetSampleRate.
        assert state.rate_scale == 18063
        assert state.inv_rate_scale == 29722

    def test_loads_ldspdef_flag(self) -> None:
        """``ldspdef = 1`` is the just-loaded-speaker-def gate (vtm1.c line 1503)."""
        state = SynthState()
        seed_speaker_state(state, default_us_paul_spd())
        assert state.ldspdef == 1

    def test_seeds_r6pb_r6pc_at_11k(self) -> None:
        """r6pb / r6pc constants at 11 kHz from vtm1.c lines 1759-1760."""
        state = SynthState()
        seed_speaker_state(state, default_us_paul_spd())
        assert state.r6pb == -5702
        assert state.r6pc == -1995

    def test_seeds_noiseb_for_rate_increase(self) -> None:
        """noiseb = -2913 in the SAMPLE_RATE_INCREASE branch (line 1582)."""
        state = SynthState()
        seed_speaker_state(state, default_us_paul_spd())
        assert state.noiseb == -2913

    def test_seeds_paul_gains(self) -> None:
        """avgain / APgain / AFgain come from amptable[] lookups."""
        from dectalk.vtm.amp_table import amptable  # noqa: PLC0415

        state = SynthState()
        seed_speaker_state(state, default_us_paul_spd())
        # Paul: azgain=60, apgain=55, afgain=55 (from p_us_vdf1.c).
        assert state.avgain == amptable[60]
        assert state.APgain == amptable[55]
        assert state.AFgain == amptable[55]

    def test_seeds_paul_fnscale_unity(self) -> None:
        """Paul's HS=100 → fnscale=4096 (Q12 unity)."""
        state = SynthState()
        seed_speaker_state(state, default_us_paul_spd())
        assert state.fnscal == 4096

    def test_idempotent_seed_resets_delays(self) -> None:
        """Re-seeding clears the filter delays — speaker switches start fresh."""
        state = SynthState()
        seed_speaker_state(state, default_us_paul_spd())
        # Pretend we ran some frames and accumulated state.
        state.r1cd1 = 9999
        state.rampdown = 4096
        state.avlind = 12345
        seed_speaker_state(state, default_us_paul_spd())
        assert state.r1cd1 == 0
        assert state.rampdown == 0
        assert state.avlind == 0


# -------------------------------------------------------------------------
# pump_frames_via_vtm1: end-to-end smoke
# -------------------------------------------------------------------------


class TestPumpFramesViaVtm1:
    def test_empty_input_returns_empty_array(self) -> None:
        out = pump_frames_via_vtm1([])
        assert isinstance(out, np.ndarray)
        assert out.dtype == np.int16
        assert out.size == 0

    def test_silence_frame_produces_71_samples(self) -> None:
        out = pump_frames_via_vtm1([_make_parstochip_frame(av_db=0, ph_value=1)])
        assert out.shape == (71,)
        assert out.dtype == np.int16

    def test_voiced_frame_produces_nontrivial_output(self) -> None:
        # 20 voiced frames; let the resonators charge.
        frames = [_make_parstochip_frame(av_db=65, ph_value=1) for _ in range(20)]
        out = pump_frames_via_vtm1(frames)
        assert out.shape == (20 * 71,)
        # By 20 frames the cascade should be ringing — at least one
        # sample non-zero.
        assert np.any(out != 0)

    def test_deterministic(self) -> None:
        """Two back-to-back calls must produce identical output."""
        frames = [_make_parstochip_frame(av_db=55) for _ in range(5)]
        a = pump_frames_via_vtm1(list(frames))
        b = pump_frames_via_vtm1(list(frames))
        np.testing.assert_array_equal(a, b)

    def test_unsupported_sample_rate_raises(self) -> None:
        with pytest.raises(NotImplementedError):
            pump_frames_via_vtm1(
                [_make_parstochip_frame()],
                sample_rate=8000,
            )

    def test_output_within_int16_range(self) -> None:
        frames = [_make_parstochip_frame(av_db=65) for _ in range(10)]
        out = pump_frames_via_vtm1(frames)
        assert out.min() >= -32768
        assert out.max() <= 32767


# -------------------------------------------------------------------------
# C-source parity preconditions: re-parse vtm1.c and assert the constants
# our Python port depends on still hold.
# -------------------------------------------------------------------------


pytestmark_c_source = pytest.mark.skipif(
    not _VTM1_C.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_c_source() -> str:
    return _VTM1_C.read_bytes().replace(b"\r", b"").decode("latin-1")


@pytestmark_c_source
class TestSeederConstantsFromCSource:
    """Verify the constants seed_speaker_state hard-codes still match vtm1.c."""

    def test_set_sample_rate_71_at_11k(self) -> None:
        """``((samplerate*64)+5000)/10000`` is the C formula (line 2044)."""
        text = _read_c_source()
        assert re.search(
            r"uiNumberOfSamplesPerFrame\s*=\s*\(\s*\(\s*pKsd_t->uiSampleRate\s*\*\s*64\s*\)\s*"
            r"\+\s*5000\s*\)\s*/\s*10000\s*;",
            text,
        ), "Expected ((uiSampleRate*64)+5000)/10000 formula in vtm1.c"

    def test_noiseb_minus_2913_in_increase_branch(self) -> None:
        text = _read_c_source()
        assert re.search(r"pVtm_t->noiseb\s*=\s*-\s*2913\s*;", text), (
            "Expected `pVtm_t->noiseb = -2913;` in vtm1.c"
        )

    def test_r6pb_r6pc_at_11k(self) -> None:
        text = _read_c_source()
        assert re.search(r"pVtm_t->r6pb\s*=\s*-\s*5702\s*;", text)
        assert re.search(r"pVtm_t->r6pc\s*=\s*-\s*1995\s*;", text)

    def test_nasal_pole_fnp_290_bnp_70(self) -> None:
        """``fnp = 290; bnp = 70;`` in read_speaker_definition (lines 1635-1637)."""
        text = _read_c_source()
        assert re.search(r"fnp\s*=\s*290\s*;", text)
        assert re.search(r"bnp\s*=\s*70\s*;", text)

    def test_lowpass_flp_blp_at_11k(self) -> None:
        """``flp = 948; blp = 615;`` at PC_SAMPLE_RATE == 11025 (lines 1674-1675)."""
        text = _read_c_source()
        assert re.search(r"flp\s*=\s*948\s*;.*?860\s*\*\s*1\.1025", text, re.DOTALL)
        assert re.search(r"blp\s*=\s*615\s*;.*?558\s*\*\s*1\.1025", text, re.DOTALL)

    def test_lowpass_rlpg_2400(self) -> None:
        text = _read_c_source()
        assert re.search(r"rlpg\s*=\s*2400\s*;", text)

    def test_parallel_b4p_400_b5p_500(self) -> None:
        """Lines 1725 (b4p = 400) and 1734 (b5p = 500)."""
        text = _read_c_source()
        assert re.search(r"b4p\s*=\s*400\s*;", text)
        assert re.search(r"b5p\s*=\s*500\s*;", text)

    def test_ldspdef_set_to_1_on_speaker_load(self) -> None:
        """``ldspdef=1;`` flag-write (line 1503)."""
        text = _read_c_source()
        assert re.search(r"pVtm_t->ldspdef\s*=\s*1\s*;", text)


# -------------------------------------------------------------------------
# End-to-end wiring smoke (the DECTALK_USE_VTM1 env-flag branch in speak.py).
# -------------------------------------------------------------------------


class TestSpeakViaPythonFullVtm1Dispatch:
    """Smoke-test the import-path in _speak_via_python_full.

    The full DECTALK_FULL_PIPELINE+DECTALK_USE_VTM1 combination is
    multi-second and pulls in the whole PH stack. The
    ``test_pump_frames_via_vtm1_importable`` test verifies static
    wiring; ``test_full_pipeline_runs_under_vtm1_flag`` actually drives
    the end-to-end path under the env flag with a tiny utterance.
    """

    def test_pump_frames_via_vtm1_importable(self) -> None:
        from dectalk.vtm.pump_frames import pump_frames_via_vtm1  # noqa: PLC0415

        assert callable(pump_frames_via_vtm1)

    def test_full_pipeline_runs_under_vtm1_flag(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """End-to-end: DECTALK_FULL_PIPELINE+DECTALK_USE_VTM1 produces audio.

        Walks the full PH pipeline (kernel/cmd/lts/dic/ph) into the
        new vtm1 synth path. Asserts:

        * The call completes without raising.
        * Output is a non-empty int16 array.
        * Output is non-trivial (at least one non-zero sample).
        """
        monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
        monkeypatch.setenv("DECTALK_FULL_PIPELINE", "1")
        monkeypatch.setenv("DECTALK_USE_VTM1", "1")

        from dectalk.api.speak import _speak_via_python_full  # noqa: PLC0415

        samples = _speak_via_python_full("hi", 1.0, None, "us", True)
        assert samples.dtype == np.int16
        assert samples.size > 0
        assert np.any(samples != 0), "vtm1 path produced all-zero output"
