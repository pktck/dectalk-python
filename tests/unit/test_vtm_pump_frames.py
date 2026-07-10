"""Smoke + parity-precondition tests for the vtm1 default synth path.

Covers :mod:`dectalk.vtm.pump_frames` (the default full-pipeline
synth-path bridge wired in :func:`dectalk.api.speak._speak_via_python_full`,
issue #272) and :mod:`dectalk.vtm.seed_speaker_state` (the
per-utterance bring-up that mirrors
``vtm1.c::read_speaker_definition`` + ``SetSampleRate``).

The full bit-parity test against the C oracle's PCM output is gated
on Phase E (the PH stage matching the C kernel sample-for-sample);
until that lands, this file establishes:

- The seeder populates :class:`SynthState` with the same well-known
  constants the C source uses (verified by re-parsing ``vtm1.c``
  for those constants).
- A deterministic parstochip frame sequence runs end-to-end through
  ``pump_frames_via_vtm1`` and produces int16 PCM of the right shape.
- The wiring in ``_speak_via_python_full`` routes through
  ``pump_frames_via_vtm1`` by default (``DECTALK_USE_VTM1`` unset or
  ``=1``) and falls back to the legacy hlsyn render only under the
  ``DECTALK_USE_VTM1=0`` escape hatch. The audio output is not
  bit-compared to the C oracle here (that test ships in Phase E).
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
    def test_8khz_path_sets_51_samples_per_frame(self) -> None:
        """MULAW_SAMPLE_RATE (8000 Hz) → 51 samples/frame (vtm1.c line 2061)."""
        state = SynthState()
        seed_speaker_state(state, default_us_paul_spd(), sample_rate=8000)
        assert state.uiNumberOfSamplesPerFrame == 51
        assert state.bEightKHz is True
        assert state.rate_scale == 26214
        assert state.inv_rate_scale == 20480
        # noiseb takes the SAMPLE_RATE_DECREASE branch (-1873).
        assert state.noiseb == -1873

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
        # Paul: azgain=65 (GV), apgain=70 (GH), afgain=70 (GF) from the
        # non-_8 paul row in p_us_vdf_dectalk43.c.
        assert state.avgain == amptable[65]
        assert state.APgain == amptable[70]
        assert state.AFgain == amptable[70]

    def test_seeds_paul_fnscale(self) -> None:
        """Paul's HS=100 → fnscale = (200-HS)*41 = 4100 (ph_vset.c:638)."""
        state = SynthState()
        seed_speaker_state(state, default_us_paul_spd())
        assert state.fnscal == 4100

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

    def test_8khz_path_produces_51_samples_per_frame(self) -> None:
        """MULAW_SAMPLE_RATE (8000 Hz) → 51 samples/frame; pump should drive
        the SAMPLE_RATE_DECREASE branch of speech_waveform_generator end
        to end without errors.
        """
        out = pump_frames_via_vtm1(
            [_make_parstochip_frame(av_db=55) for _ in range(3)],
            sample_rate=8000,
        )
        assert out.shape == (3 * 51,)
        assert out.dtype == np.int16

    def test_output_within_int16_range(self) -> None:
        frames = [_make_parstochip_frame(av_db=65) for _ in range(10)]
        out = pump_frames_via_vtm1(frames)
        assert out.min() >= -32768
        assert out.max() <= 32767


# -------------------------------------------------------------------------
# vol_att Q15 post-scale (vtm3.c line 1642, ported per issue #279 so the
# capability survives the legacy hlsyn-render retirement).
# -------------------------------------------------------------------------


class TestPumpFramesVolAtt:
    """``vol_att`` post-scale on the vtm1 pump (issue #279).

    ``vtm2.c``/``vtm3.c`` apply ``out = frac1mul(out, vol_att)`` with
    ``vol_att = int_volume_table[pKsd_t->vol_att]`` per synthesised
    sample; ``vtm1.c`` has no volume stage, so the pump carries the
    hook the future ``[:volume N]`` port needs. The default index
    (100, the C kernel's reset value) must be a bit-exact no-op so the
    byte-parity path is unaffected.
    """

    def _voiced_frames(self, n: int = 20) -> list[list[int]]:
        return [_make_parstochip_frame(av_db=65, ph_value=1) for _ in range(n)]

    def test_default_vol_att_100_is_bit_exact_noop(self) -> None:
        """``vol_att=100`` (and omitted) return the raw vtm1 output.

        ``int_volume_table[100] = 32767`` is ~Q15 unity; the pump must
        skip the multiply entirely so the default-volume parity path
        stays byte-identical.
        """
        frames = self._voiced_frames()
        base = pump_frames_via_vtm1(list(frames))
        at_default = pump_frames_via_vtm1(list(frames), vol_att=100)
        assert np.any(base != 0), "voiced frames produced silence; test is vacuous"
        np.testing.assert_array_equal(base, at_default)

    def test_vol_att_zero_mutes_output(self) -> None:
        """``vol_att=0`` mutes (``int_volume_table[0] = 0``)."""
        frames = self._voiced_frames()
        base = pump_frames_via_vtm1(list(frames))
        out = pump_frames_via_vtm1(list(frames), vol_att=0)
        assert np.any(base != 0), "voiced frames produced silence; test is vacuous"
        assert int(np.max(np.abs(out.astype(np.int32)))) == 0

    def test_vol_att_below_unity_attenuates_q15_exact(self) -> None:
        """``vol_att=50`` scales each sample by ``(x * 5826) >> 15`` exactly."""
        from dectalk.vtm.volume_table import int_volume_table  # noqa: PLC0415

        frames = self._voiced_frames()
        base = pump_frames_via_vtm1(list(frames))
        out = pump_frames_via_vtm1(list(frames), vol_att=50)
        vol_mul = int_volume_table[50]
        expected = ((base.astype(np.int32) * vol_mul) >> 15).astype(np.int16)
        np.testing.assert_array_equal(out, expected)

    def test_vol_att_above_unity_amplifies_with_clip(self) -> None:
        """``vol_att=140`` (+12 dB) scales by ``(x * 131071) >> 15`` with int16 clip."""
        from dectalk.vtm.volume_table import int_volume_table  # noqa: PLC0415

        frames = self._voiced_frames()
        base = pump_frames_via_vtm1(list(frames))
        out = pump_frames_via_vtm1(list(frames), vol_att=140)
        vol_mul = int_volume_table[140]
        scaled = (base.astype(np.int32) * vol_mul) >> 15
        expected = np.clip(scaled, -32768, 32767).astype(np.int16)
        np.testing.assert_array_equal(out, expected)

    def test_vol_att_clamps_out_of_range_indices(self) -> None:
        """Indices outside [0, 140] clamp to the table range (vtm3.c 515-518)."""
        frames = self._voiced_frames(8)
        neg = pump_frames_via_vtm1(list(frames), vol_att=-99)
        zero = pump_frames_via_vtm1(list(frames), vol_att=0)
        np.testing.assert_array_equal(neg, zero)

        huge = pump_frames_via_vtm1(list(frames), vol_att=999)
        max_idx = pump_frames_via_vtm1(list(frames), vol_att=140)
        np.testing.assert_array_equal(huge, max_idx)

    def test_render_clause_full_threads_ksd_vol_att(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The driver passes ``KsdT.vol_att`` (default 100) to the pump.

        Pins the ``pKsd_t->vol_att`` read from ``vtm3.c`` line 514 —
        the seam a future ``[:volume N]`` port will drive.
        """
        monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
        monkeypatch.setenv("DECTALK_FULL_PIPELINE", "1")

        import dectalk.vtm.pump_frames as pump_frames_mod  # noqa: PLC0415
        from dectalk.api.speak import _speak_via_python_full  # noqa: PLC0415

        seen: list[object] = []
        real_pump = pump_frames_mod.pump_frames_via_vtm1

        def _spy(
            frames: list[list[int]],
            preset: object = None,
            **kwargs: object,
        ) -> np.ndarray:
            seen.append(kwargs.get("vol_att"))
            return real_pump(frames, preset, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(pump_frames_mod, "pump_frames_via_vtm1", _spy)

        _speak_via_python_full("hi", 1.0, None, "us", True)
        assert seen, "vtm1 pump never invoked"
        assert seen == [100], f"expected KsdT default vol_att=100 threaded, got {seen}"


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
    """Smoke-test the render-path dispatch in _speak_via_python_full.

    The full-pipeline runs are multi-second and pull in the whole PH
    stack, so each test drives a tiny utterance.
    ``test_pump_frames_via_vtm1_importable`` verifies static wiring;
    the rest pin the issue #272 dispatch contract: vtm1 renders by
    default (env var unset or ``=1``), and ``DECTALK_USE_VTM1=0`` is
    the explicit escape hatch back to the legacy hlsyn render.
    """

    def test_pump_frames_via_vtm1_importable(self) -> None:
        from dectalk.vtm.pump_frames import pump_frames_via_vtm1  # noqa: PLC0415

        assert callable(pump_frames_via_vtm1)

    def test_full_pipeline_runs_under_vtm1_flag(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """End-to-end: DECTALK_FULL_PIPELINE+DECTALK_USE_VTM1=1 produces audio.

        Walks the full PH pipeline (kernel/cmd/lts/dic/ph) into the
        vtm1 synth path. Asserts:

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

    def test_full_pipeline_defaults_to_vtm1(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With DECTALK_USE_VTM1 unset, the vtm1 render path is used (#272).

        ``DECTALK_FULL_PIPELINE=1`` alone must imply the vtm1 render --
        the byte-exact-capable parity path -- so measurements taken
        without the (former) opt-in flag can no longer land on the
        over-running legacy path (the #254 misdiagnosis footgun).
        """
        monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
        monkeypatch.setenv("DECTALK_FULL_PIPELINE", "1")
        monkeypatch.delenv("DECTALK_USE_VTM1", raising=False)

        import dectalk.vtm.pump_frames as pump_frames_mod  # noqa: PLC0415
        from dectalk.api.speak import _speak_via_python_full  # noqa: PLC0415

        calls: list[int] = []
        real_pump = pump_frames_mod.pump_frames_via_vtm1

        def _spy(
            frames: list[list[int]],
            preset: object = None,
            **kwargs: object,
        ) -> np.ndarray:
            calls.append(len(frames))
            return real_pump(frames, preset, **kwargs)  # type: ignore[arg-type]

        # _render_clause_full imports the symbol lazily at call time, so
        # patching the module attribute intercepts the dispatch.
        monkeypatch.setattr(pump_frames_mod, "pump_frames_via_vtm1", _spy)

        samples = _speak_via_python_full("hi", 1.0, None, "us", True)
        assert calls, "default full-pipeline render did not route through vtm1"
        assert samples.dtype == np.int16
        assert samples.size > 0
        assert np.any(samples != 0), "vtm1 default path produced all-zero output"

    def test_driver_feeds_send_pars_delaypars_packets(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The vtm1 pump receives post-send_pars packets, not raw parstochip.

        Pins the issue #275 wiring invariant: for every emitted frame
        the driver hands the pump exactly ``send_pars_delaypars(cur,
        prev)`` where ``(cur, prev)`` is the raw current/previous
        parstochip pair the ``send_pars_delaypars`` capture seam sees
        — formant side one frame delayed, ``OUT_TLT`` LUT-mapped,
        ``OUT_AV``/``OUT_T0`` current, and the discarded first driver
        frame surfacing as packet 0's delayed half. Also re-pins the
        #279 precondition that the capture seam keeps seeing raw
        (un-mixed) parstochip pairs.
        """
        monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
        monkeypatch.setenv("DECTALK_FULL_PIPELINE", "1")

        import dectalk.vtm.pump_frames as pump_frames_mod  # noqa: PLC0415
        from dectalk.api.speak import _speak_via_python_full  # noqa: PLC0415
        from dectalk.ph import parstochip_to_frames as ptf_mod  # noqa: PLC0415

        pump_inputs: list[list[int]] = []
        real_pump = pump_frames_mod.pump_frames_via_vtm1

        def _pump_spy(
            frames: list[list[int]],
            preset: object = None,
            **kwargs: object,
        ) -> np.ndarray:
            pump_inputs.extend(list(f) for f in frames)
            return real_pump(frames, preset, **kwargs)  # type: ignore[arg-type]

        seam_pairs: list[tuple[list[int], list[int]]] = []
        real_seam = ptf_mod.send_pars_delaypars

        def _seam_spy(
            parstochip: list[int],
            previous_parstochip: list[int],
        ) -> list[int]:
            # The driver never emits before the first frame seeded the
            # delay buffer, so the seam must keep seeing a real pair.
            assert previous_parstochip is not None
            seam_pairs.append((list(parstochip), list(previous_parstochip)))
            return real_seam(parstochip, previous_parstochip)

        # Both call sites import lazily at call time, so patching the
        # module attributes intercepts the dispatch.
        monkeypatch.setattr(pump_frames_mod, "pump_frames_via_vtm1", _pump_spy)
        monkeypatch.setattr(ptf_mod, "send_pars_delaypars", _seam_spy)

        _speak_via_python_full("hi", 1.0, None, "us", True)

        assert pump_inputs, "vtm1 pump never invoked"
        assert len(pump_inputs) == len(seam_pairs)
        expected = [real_seam(cur, prev) for cur, prev in seam_pairs]
        assert pump_inputs == expected

    def test_escape_hatch_zero_selects_legacy_hlsyn(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """DECTALK_USE_VTM1=0 restores the legacy hlsyn render path.

        The escape hatch must bypass ``pump_frames_via_vtm1`` entirely
        and still produce audio through the SenSyn 2.2 cascade-parallel
        synthesiser (``_pump_frames_to_samples``).
        """
        monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
        monkeypatch.setenv("DECTALK_FULL_PIPELINE", "1")
        monkeypatch.setenv("DECTALK_USE_VTM1", "0")

        import dectalk.vtm.pump_frames as pump_frames_mod  # noqa: PLC0415
        from dectalk.api.speak import _speak_via_python_full  # noqa: PLC0415

        def _fail(*args: object, **kwargs: object) -> np.ndarray:
            raise AssertionError("DECTALK_USE_VTM1=0 must not route through vtm1")

        monkeypatch.setattr(pump_frames_mod, "pump_frames_via_vtm1", _fail)

        samples = _speak_via_python_full("hi", 1.0, None, "us", True)
        assert samples.dtype == np.int16
        assert samples.size > 0
        assert np.any(samples != 0), "legacy hlsyn path produced all-zero output"
