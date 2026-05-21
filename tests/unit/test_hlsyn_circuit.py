"""Unit tests for :mod:`dectalk.hlsyn.circuit` (SpeechCircuit port).

Exercises :func:`speech_circuit` — the aerodynamic equivalent-circuit
solver translated from ``src/dapi/src/hlsyn/circuit.c``.

Test strategy
-------------
- **Idle / silent frame**: ag = 0, ps = 0.  All flows must be zero and
  mouth pressure must not grow.
- **Typical voiced frame**: a plausible mid-vowel configuration with a
  reasonable subglottal pressure; asserts physical sign conventions and
  the consistency relation ``Ug - Uacx - Un - ue == Uw``.
- **Negative ag clamp**: when the raw ag + f(Pm)*Cg*Lg would be
  negative, ``agx`` must be clamped to 0.
- **Negative an clamp**: negative nasal area must be treated as 0 so
  Un stays non-negative.
- **Cg / Cw dc-scaling**: state.Cg and state.Cw are updated from
  speaker.Cgm / Cwm and the dc field of the current frame.
- **agf = agx + ap** structural check.
- **SpeechCircuit alias** is importable and is the same callable.
"""

from __future__ import annotations

import math

import dectalk.hlsyn.circuit as circuit_mod
from dectalk.hlsyn.circuit import SpeechCircuit, speech_circuit
from dectalk.ph.hl_speaker import HLSpeaker
from dectalk.ph.hlsyn_structs import HLFrame, HLState

# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _make_speaker() -> HLSpeaker:
    """Return a minimal HLSpeaker with the fields SpeechCircuit touches."""
    spk = HLSpeaker()
    # Wall / glottal compliance baselines (typical US-Paul values).
    spk.Cwm = 2.0e-5  # cm^3 / dyne
    spk.KCw = 0.0  # no dc-dependence for simplicity
    spk.Cgm = 1.0e-6  # cm^3 / dyne
    spk.KCg = 0.0
    spk.Rw = 100.0  # dyne s / cm^5
    spk.Lg = 0.3  # cm (glottal duct length)
    # UpdateInterval: one HL frame = 5 ms = 0.005 s (typical).
    spk.UpdateInterval = 0.005
    return spk


def _make_frames_silent() -> tuple[HLFrame, HLFrame]:
    """Old and new frames for a fully silent (closed-glottis) configuration."""
    old = HLFrame()
    new = HLFrame()
    # Everything at zero: ag=0, ps=0, an=0, ap=0, ue=0, dc=0.
    return old, new


def _make_state_zero() -> HLState:
    """Initial HLState with all quantities at zero."""
    return HLState()


def _make_typical_voiced() -> tuple[HLFrame, HLFrame, HLState, HLState]:
    """Frames and states for a mid-vowel voiced configuration."""
    old_frame = HLFrame(ag=30.0, an=0.0, ap=5.0, ue=20.0, ps=8.0, dc=0.0)
    new_frame = HLFrame(ag=35.0, an=0.0, ap=5.0, ue=22.0, ps=8.2, dc=0.0)
    old_state = HLState(
        Pm=1500.0,
        Pcw=1200.0,
        Uw=50.0,
        acx=50.0,  # mm^2 — wide-open oral tract
        Cw=2.0e-5,
        Cg=1.0e-6,
    )
    new_state = HLState(
        acx=55.0,  # updated constriction area (set by caller before SpeechCircuit)
        Cw=2.0e-5,
        Cg=1.0e-6,
    )
    return old_frame, new_frame, old_state, new_state


# ---------------------------------------------------------------------------
# Tests.
# ---------------------------------------------------------------------------


def test_speech_circuit_importable() -> None:
    """speech_circuit and SpeechCircuit alias are both importable callables."""
    assert callable(speech_circuit)
    assert callable(SpeechCircuit)
    assert SpeechCircuit is speech_circuit


def test_speech_circuit_alias_same_object() -> None:
    """``SpeechCircuit`` must be the identical function object, not a copy."""
    assert circuit_mod.SpeechCircuit is circuit_mod.speech_circuit


def test_speech_circuit_silent_frame_pm_stays_near_zero() -> None:
    """Silent frame (ag=0, ps=0) → mouth pressure stays close to zero."""
    spk = _make_speaker()
    old_frame, new_frame = _make_frames_silent()
    old_state = _make_state_zero()
    new_state = _make_state_zero()

    speech_circuit(new_frame, old_frame, spk, new_state, old_state)

    # With no source pressure and no glottal area, Pm should not build up.
    assert abs(new_state.Pm) < 10.0, f"Expected Pm ≈ 0, got {new_state.Pm}"


def test_speech_circuit_silent_frame_flows_near_zero() -> None:
    """Silent frame → all flows (Ug, Uacx, Un, Uw) should be near zero."""
    spk = _make_speaker()
    old_frame, new_frame = _make_frames_silent()
    old_state = _make_state_zero()
    new_state = _make_state_zero()

    speech_circuit(new_frame, old_frame, spk, new_state, old_state)

    for name, val in [
        ("Ug", new_state.Ug),
        ("Uacx", new_state.Uacx),
        ("Un", new_state.Un),
        ("Uw", new_state.Uw),
    ]:
        assert abs(val) < 1.0, f"Expected {name} ≈ 0 for silent frame, got {val}"


def test_speech_circuit_updates_cg_cw_from_dc() -> None:
    """state.Cg and state.Cw reflect speaker.Cgm/Cwm and the dc field."""
    spk = _make_speaker()
    # Non-zero KCg / KCw so dc matters.
    spk.KCg = 1.0
    spk.KCw = 1.0
    spk.Cgm = 1.0e-6
    spk.Cwm = 2.0e-5
    dc_val = 50.0  # 50 %

    old_frame = HLFrame(dc=0.0)
    new_frame = HLFrame(dc=dc_val)
    old_state = _make_state_zero()
    new_state = _make_state_zero()

    speech_circuit(new_frame, old_frame, spk, new_state, old_state)

    expected_cg = spk.Cgm + spk.KCg * 0.01 * dc_val * spk.Cgm
    expected_cw = spk.Cwm + spk.KCw * 0.01 * dc_val * spk.Cwm
    assert math.isclose(new_state.Cg, expected_cg, rel_tol=1e-6), (
        f"state.Cg: expected {expected_cg}, got {new_state.Cg}"
    )
    assert math.isclose(new_state.Cw, expected_cw, rel_tol=1e-6), (
        f"state.Cw: expected {expected_cw}, got {new_state.Cw}"
    )


def test_speech_circuit_agf_equals_agx_plus_ap() -> None:
    """state.agf == state.agx + ap (when ap >= 0) after the call."""
    spk = _make_speaker()
    old_frame, new_frame, old_state, new_state = _make_typical_voiced()

    speech_circuit(new_frame, old_frame, spk, new_state, old_state)

    ap_safe = max(0.0, new_frame.ap)
    expected_agf = new_state.agx + ap_safe
    assert math.isclose(new_state.agf, expected_agf, rel_tol=1e-9), (
        f"agf {new_state.agf} != agx+ap {expected_agf}"
    )


def test_speech_circuit_negative_ag_clamps_agx_to_zero() -> None:
    """When the raw ag + Pm*Cg*Lg would go negative, agx is clamped to 0."""
    spk = _make_speaker()
    # Very negative ag, zero Cg → agx0 = ag < 0 always.
    old_frame = HLFrame(ag=-100.0, ps=8.0, dc=0.0)
    new_frame = HLFrame(ag=-100.0, ps=8.0, dc=0.0)
    old_state = _make_state_zero()
    new_state = _make_state_zero()

    speech_circuit(new_frame, old_frame, spk, new_state, old_state)

    assert new_state.agx >= 0.0, f"agx must be >= 0, got {new_state.agx}"


def test_speech_circuit_negative_an_yields_zero_un() -> None:
    """Negative nasal area is treated as 0, so Un >= 0."""
    spk = _make_speaker()
    old_frame = HLFrame(ag=30.0, an=-5.0, ps=8.0, dc=0.0)
    new_frame = HLFrame(ag=30.0, an=-5.0, ps=8.0, dc=0.0)
    old_state = HLState(Pm=1000.0, Pcw=800.0, acx=30.0, Cw=2.0e-5, Cg=1.0e-6)
    new_state = HLState(acx=30.0)

    speech_circuit(new_frame, old_frame, spk, new_state, old_state)

    assert new_state.Un >= 0.0, f"Un must be >= 0 for negative an, got {new_state.Un}"


def test_speech_circuit_typical_pm_in_plausible_range() -> None:
    """Typical voiced frame → Pm stays within [0, 8000] dynes/cm^2."""
    spk = _make_speaker()
    old_frame, new_frame, old_state, new_state = _make_typical_voiced()

    speech_circuit(new_frame, old_frame, spk, new_state, old_state)

    assert 0.0 <= new_state.Pm <= 8000.0, f"Pm={new_state.Pm} out of plausible [0, 8000] range"


def test_speech_circuit_uw_consistency() -> None:
    """``Uw = Ug - Uacx - Un - ue`` must hold (circuit.c line 323)."""
    spk = _make_speaker()
    old_frame, new_frame, old_state, new_state = _make_typical_voiced()

    speech_circuit(new_frame, old_frame, spk, new_state, old_state)

    expected_uw = new_state.Ug - new_state.Uacx - new_state.Un - new_frame.ue
    assert math.isclose(new_state.Uw, expected_uw, rel_tol=1e-9, abs_tol=1e-12), (
        f"Uw consistency: got {new_state.Uw}, expected {expected_uw}"
    )


def test_speech_circuit_pcw_is_finite() -> None:
    """After the call ``Pcw`` and ``Pm`` are finite (not NaN / Inf)."""
    spk = _make_speaker()
    old_frame, new_frame, old_state, new_state = _make_typical_voiced()

    speech_circuit(new_frame, old_frame, spk, new_state, old_state)

    assert math.isfinite(new_state.Pcw), f"Pcw is not finite: {new_state.Pcw}"
    assert math.isfinite(new_state.Pm), f"Pm is not finite: {new_state.Pm}"


def test_speech_circuit_ug_non_negative_for_positive_ps() -> None:
    """For ps > Pm, the glottal flow Ug must be non-negative."""
    spk = _make_speaker()
    old_frame, new_frame, old_state, new_state = _make_typical_voiced()

    speech_circuit(new_frame, old_frame, spk, new_state, old_state)

    # If Pm < ps_cgs = 8.2 * 980 = 8036 dynes/cm^2, Ug >= 0.
    ps_cgs = new_frame.ps * 980.0
    if new_state.Pm < ps_cgs:
        assert new_state.Ug >= 0.0, f"Ug={new_state.Ug} < 0 when Pm < ps"


def test_speech_circuit_num_interp_threshold_high_pm() -> None:
    """With oldstate.Pm > 4000, the solver uses 4 sub-interpolations (no crash)."""
    spk = _make_speaker()
    old_frame = HLFrame(ag=30.0, an=0.0, ap=5.0, ps=8.0, dc=0.0)
    new_frame = HLFrame(ag=35.0, an=0.0, ap=5.0, ps=8.0, dc=0.0)
    # High initial Pm triggers the 4-interpolation branch.
    old_state = HLState(Pm=5000.0, Pcw=4000.0, Uw=80.0, acx=50.0, Cw=2.0e-5, Cg=1.0e-6)
    new_state = HLState(acx=50.0)

    # Must not raise.
    speech_circuit(new_frame, old_frame, spk, new_state, old_state)

    assert math.isfinite(new_state.Pm)
    assert math.isfinite(new_state.Ug)


def test_speech_circuit_module_exports() -> None:
    """The module exports ``SpeechCircuit`` and ``speech_circuit`` in ``__all__``."""
    assert "speech_circuit" in circuit_mod.__all__
    assert "SpeechCircuit" in circuit_mod.__all__
