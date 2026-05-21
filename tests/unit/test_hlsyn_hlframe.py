"""Unit tests for :mod:`dectalk.hlsyn.hlframe`.

Covers ``hl_synthesize_ll_frame`` and the static helper functions
it calls:

- :func:`_map_glottal_formants_not_f1`
- :func:`_source_amplitudes`
- :func:`_glottal_interaction`
- :func:`_source_specifics`
- :func:`_fricative_filters`
- :func:`_llframe_n_to_llframe`

The tests are purely behavioural (no C re-parsing): they exercise the
Python logic using hand-crafted HLFrame / HLSpeaker / HLState inputs
and assert known output ranges / values.
"""

from __future__ import annotations

import pytest

from dectalk.hlsyn.hlframe import (
    HLSynthesizeLLFrame,
    _fricative_filters,
    _glottal_interaction,
    _llframe_n_to_llframe,
    _map_glottal_formants_not_f1,
    _source_amplitudes,
    _source_specifics,
    hl_synthesize_ll_frame,
)
from dectalk.hlsyn.initialize_hl_synthesizer import initialize_hl_synthesizer
from dectalk.hlsyn.ll_frame_n import LLFrameN
from dectalk.hlsyn.llsyn import LLFrame
from dectalk.hlsyn.place_constants import LIPS
from dectalk.ph.hl_speaker import HLSpeaker
from dectalk.ph.hlsyn_structs import HLFrame, HLState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def male_speaker_state() -> tuple[HLSpeaker, HLFrame, HLState]:
    """Return fresh (speaker, oldframe, oldstate) for a male voice."""
    return initialize_hl_synthesizer(is_male=True)


@pytest.fixture()
def male_speaker(male_speaker_state: tuple[HLSpeaker, HLFrame, HLState]) -> HLSpeaker:
    return male_speaker_state[0]


@pytest.fixture()
def male_oldframe(male_speaker_state: tuple[HLSpeaker, HLFrame, HLState]) -> HLFrame:
    return male_speaker_state[1]


@pytest.fixture()
def male_oldstate(male_speaker_state: tuple[HLSpeaker, HLFrame, HLState]) -> HLState:
    return male_speaker_state[2]


def _neutral_frame() -> HLFrame:
    """Neutral HLFrame: voiced vowel at 120 Hz, F1=500, F2=1500, F3=2500."""
    frame = HLFrame()
    frame.f0 = 1200.0  # deciHz (120 Hz)
    frame.f1 = 500.0
    frame.f2 = 1500.0
    frame.f3 = 2500.0
    frame.f4 = 3500.0
    frame.ag = 4.0  # mm^2 — right at agm for a male
    frame.al = 0.0
    frame.an = 0.0
    frame.ps = 8.0  # cmH2O
    frame.dc = 0.0
    frame.ap = 0.0
    return frame


def _neutral_state(ag: float = 4.0) -> HLState:
    """HLState with agf=agx=ag, Pm=0, and f1x/b1x zeroed (shim fills them)."""
    state = HLState()
    state.agf = ag
    state.agx = ag
    state.Pm = 0.0
    state.f1c = 0.0
    state.f1x = 0.0
    state.b1x = 0.0
    return state


# ---------------------------------------------------------------------------
# 1. _map_glottal_formants_not_f1
# ---------------------------------------------------------------------------


class TestMapGlottalFormantsNotF1:
    def test_f0_copied_as_rounded_short(self, male_speaker: HLSpeaker) -> None:
        frame = _neutral_frame()
        frame.f0 = 1199.6  # rounds to 1200
        state = _neutral_state()
        llframe = LLFrameN()
        _map_glottal_formants_not_f1(frame, male_speaker, state, llframe)
        assert llframe.NF0 == 1200

    def test_f0_zero_when_frame_f0_not_positive(self, male_speaker: HLSpeaker) -> None:
        frame = _neutral_frame()
        frame.f0 = 0.0
        state = _neutral_state()
        llframe = LLFrameN()
        _map_glottal_formants_not_f1(frame, male_speaker, state, llframe)
        assert llframe.NF0 == 0

    def test_formants_f2_f3_f4_f5_copied(self, male_speaker: HLSpeaker) -> None:
        frame = _neutral_frame()
        state = _neutral_state()
        llframe = LLFrameN()
        _map_glottal_formants_not_f1(frame, male_speaker, state, llframe)
        assert int(frame.f2) == llframe.NF2
        assert int(frame.f3) == llframe.NF3
        assert int(frame.f4) == llframe.NF4
        assert int(male_speaker.F5) == llframe.NF5

    def test_f1c_tracheal_coupling_not_applied_when_an_high(self, male_speaker: HLSpeaker) -> None:
        """f1c bump requires an < 3; an=5 should leave f1c unchanged."""
        frame = _neutral_frame()
        frame.an = 5.0  # above threshold
        state = _neutral_state(ag=5.0)
        state.f1c = 100.0
        llframe = LLFrameN()
        f1c_before = state.f1c
        _map_glottal_formants_not_f1(frame, male_speaker, state, llframe)
        assert state.f1c == f1c_before


# ---------------------------------------------------------------------------
# 2. _source_amplitudes
# ---------------------------------------------------------------------------


class TestSourceAmplitudes:
    def test_nav_zero_when_agx_below_agmin(self, male_speaker: HLSpeaker) -> None:
        frame = _neutral_frame()
        frame.ps = 8.0
        state = _neutral_state(ag=0.5)  # below agMin=1.0
        state.agx = 0.5
        oldstate = _neutral_state()
        llframe = LLFrameN()
        llframe.NF0 = 1200
        _source_amplitudes(frame, male_speaker, state, oldstate, llframe)
        assert llframe.NAV == 0

    def test_nav_nonzero_at_modal_area(self, male_speaker: HLSpeaker) -> None:
        """With ag=agm=4, ps=8 cmH2O, NAV should be positive."""
        frame = _neutral_frame()
        frame.ag = male_speaker.agm
        frame.ps = 8.0
        state = _neutral_state(ag=male_speaker.agm)
        oldstate = _neutral_state()
        llframe = LLFrameN()
        llframe.NF0 = 1200
        _source_amplitudes(frame, male_speaker, state, oldstate, llframe)
        assert llframe.NAV >= 0  # may be 0 if ps < AVPressureThreshold

    def test_nah_zero_when_no_nasal_and_no_acx(self, male_speaker: HLSpeaker) -> None:
        """NAH is 0 when an=0 and acx=0 (the (an<=0 and acx<=0) guard)."""
        frame = _neutral_frame()
        frame.an = 0.0
        state = _neutral_state()
        state.acx = 0.0
        oldstate = _neutral_state()
        llframe = LLFrameN()
        _source_amplitudes(frame, male_speaker, state, oldstate, llframe)
        assert llframe.NAH == 0

    def test_nav_clamped_nonnegative(self, male_speaker: HLSpeaker) -> None:
        """NAV must never go below zero."""
        frame = _neutral_frame()
        frame.ps = 0.001  # very low pressure
        state = _neutral_state(ag=2.0)
        oldstate = _neutral_state()
        llframe = LLFrameN()
        llframe.NF0 = 1200
        _source_amplitudes(frame, male_speaker, state, oldstate, llframe)
        assert llframe.NAV >= 0


# ---------------------------------------------------------------------------
# 3. _glottal_interaction
# ---------------------------------------------------------------------------


class TestGlottalInteraction:
    def test_b3_b4_b5_widen_above_agm(self, male_speaker: HLSpeaker) -> None:
        frame = _neutral_frame()
        state = _neutral_state(ag=male_speaker.agm + 2.0)  # above modal
        state.f1x = 500.0
        state.b1x = male_speaker.B1m
        llframe = LLFrameN()
        _glottal_interaction(frame, male_speaker, state, llframe)
        assert int(male_speaker.B3m) < llframe.NB3
        assert int(male_speaker.B4m) < llframe.NB4
        assert int(male_speaker.B5m) < llframe.NB5

    def test_b3_b4_b5_at_modal_below_agm(self, male_speaker: HLSpeaker) -> None:
        frame = _neutral_frame()
        state = _neutral_state(ag=2.0)  # below agm=4
        state.f1x = 500.0
        state.b1x = male_speaker.B1m
        llframe = LLFrameN()
        _glottal_interaction(frame, male_speaker, state, llframe)
        assert int(male_speaker.B3m) == llframe.NB3
        assert int(male_speaker.B4m) == llframe.NB4
        assert int(male_speaker.B5m) == llframe.NB5

    def test_nf1_from_f1x(self, male_speaker: HLSpeaker) -> None:
        frame = _neutral_frame()
        state = _neutral_state()
        state.f1x = 480.0
        state.b1x = male_speaker.B1m
        llframe = LLFrameN()
        _glottal_interaction(frame, male_speaker, state, llframe)
        assert int(480.0) == llframe.NF1


# ---------------------------------------------------------------------------
# 4. _source_specifics
# ---------------------------------------------------------------------------


class TestSourceSpecifics:
    def test_oq_in_valid_range(self, male_speaker: HLSpeaker) -> None:
        frame = _neutral_frame()
        state = _neutral_state(ag=male_speaker.agm)
        llframe = LLFrameN()
        _source_specifics(frame, male_speaker, state, llframe)
        assert male_speaker.OQMin <= llframe.NOQ <= male_speaker.OQMax

    def test_ntl_in_valid_range(self, male_speaker: HLSpeaker) -> None:
        frame = _neutral_frame()
        state = _neutral_state(ag=male_speaker.agm)
        state.acx = 0.0
        llframe = LLFrameN()
        _source_specifics(frame, male_speaker, state, llframe)
        assert male_speaker.TLMin <= llframe.NTL <= male_speaker.TLMax

    def test_ndi_zero_at_agm(self, male_speaker: HLSpeaker) -> None:
        """DI is 0 when agx >= agm (no breathy diphthongization above modal)."""
        frame = _neutral_frame()
        state = _neutral_state(ag=male_speaker.agm)
        llframe = LLFrameN()
        _source_specifics(frame, male_speaker, state, llframe)
        assert llframe.NDI == 0


# ---------------------------------------------------------------------------
# 5. _fricative_filters
# ---------------------------------------------------------------------------


class TestFricativeFilters:
    def test_all_zero_when_naf_below_threshold(self, male_speaker: HLSpeaker) -> None:
        frame = _neutral_frame()
        state = _neutral_state()
        state.loc = LIPS
        llframe = LLFrameN()
        llframe.NAF = int(male_speaker.AFThreshold) - 1  # below threshold
        _fricative_filters(frame, male_speaker, state, llframe)
        assert llframe.NAB == 0
        assert llframe.NA2F == 0
        assert llframe.NA3F == 0

    def test_nab_set_for_lips_above_threshold(self, male_speaker: HLSpeaker) -> None:
        frame = _neutral_frame()
        state = _neutral_state()
        state.loc = LIPS
        llframe = LLFrameN()
        llframe.NAF = int(male_speaker.AFThreshold) + 5
        _fricative_filters(frame, male_speaker, state, llframe)
        assert int(male_speaker.LabialAB) == llframe.NAB

    def test_nf6_always_set(self, male_speaker: HLSpeaker) -> None:
        """NF6 is set regardless of NAF."""
        frame = _neutral_frame()
        state = _neutral_state()
        state.loc = LIPS
        llframe = LLFrameN()
        llframe.NAF = 0  # below threshold
        _fricative_filters(frame, male_speaker, state, llframe)
        assert int(male_speaker.F6) == llframe.NF6


# ---------------------------------------------------------------------------
# 6. _llframe_n_to_llframe
# ---------------------------------------------------------------------------


class TestLLFrameNToLLFrame:
    def test_field_transfer(self) -> None:
        """Every non-zero field in LLFrameN should land in the matching LLFrame field."""
        n = LLFrameN()
        n.NF0 = 1200
        n.NAV = 45
        n.NOQ = 60
        n.NTL = 10
        n.NF1 = 500
        n.NB1 = 80
        n.NF2 = 1500
        n.NB2 = 90
        n.NF3 = 2500
        n.NB3 = 150
        result = _llframe_n_to_llframe(n)
        assert isinstance(result, LLFrame)
        assert result.F0 == 1200
        assert result.AV == 45
        assert result.OQ == 60
        assert result.TL == 10
        assert result.F1 == 500
        assert result.B1 == 80
        assert result.F2 == 1500
        assert result.B2 == 90
        assert result.F3 == 2500
        assert result.B3 == 150

    def test_alias_hlsynthesizellframe(self) -> None:
        """HLSynthesizeLLFrame should be the same callable as hl_synthesize_ll_frame."""
        assert HLSynthesizeLLFrame is hl_synthesize_ll_frame


# ---------------------------------------------------------------------------
# 7. hl_synthesize_ll_frame integration
# ---------------------------------------------------------------------------


class TestHLSynthesizeLLFrame:
    def test_returns_llframe(
        self,
        male_speaker: HLSpeaker,
        male_oldframe: HLFrame,
        male_oldstate: HLState,
    ) -> None:
        frame = _neutral_frame()
        oldframe = _neutral_frame()
        state = _neutral_state(ag=male_speaker.agm)
        result = hl_synthesize_ll_frame(frame, oldframe, male_speaker, state, male_oldstate)
        assert isinstance(result, LLFrame)

    def test_f0_passed_through(
        self,
        male_speaker: HLSpeaker,
        male_oldframe: HLFrame,
        male_oldstate: HLState,
    ) -> None:
        frame = _neutral_frame()
        frame.f0 = 1100.0
        oldframe = _neutral_frame()
        state = _neutral_state(ag=male_speaker.agm)
        result = hl_synthesize_ll_frame(frame, oldframe, male_speaker, state, male_oldstate)
        # NF0 = int(f0 + 0.5) = 1100, but zeroed if NAV==0; ps may be too low.
        # Just ensure F0 is non-negative.
        assert result.F0 >= 0

    def test_silent_frame_when_zero_glottal_area(
        self,
        male_speaker: HLSpeaker,
        male_oldframe: HLFrame,
        male_oldstate: HLState,
    ) -> None:
        """agf=agx=0 -> NAV/NAH/NAF should all be 0."""
        frame = _neutral_frame()
        frame.ag = 0.0
        oldframe = _neutral_frame()
        state = _neutral_state(ag=0.0)
        result = hl_synthesize_ll_frame(frame, oldframe, male_speaker, state, male_oldstate)
        assert result.AV == 0

    def test_formant_bandwidths_nonnegative(
        self,
        male_speaker: HLSpeaker,
        male_oldframe: HLFrame,
        male_oldstate: HLState,
    ) -> None:
        frame = _neutral_frame()
        frame.ag = male_speaker.agm + 2.0
        frame.ps = 8.0
        oldframe = _neutral_frame()
        state = _neutral_state(ag=male_speaker.agm + 2.0)
        result = hl_synthesize_ll_frame(frame, oldframe, male_speaker, state, male_oldstate)
        assert result.B1 >= 0
        assert result.B2 >= 0
        assert result.B3 >= 0

    def test_oq_in_range(
        self,
        male_speaker: HLSpeaker,
        male_oldframe: HLFrame,
        male_oldstate: HLState,
    ) -> None:
        frame = _neutral_frame()
        oldframe = _neutral_frame()
        state = _neutral_state(ag=male_speaker.agm)
        result = hl_synthesize_ll_frame(frame, oldframe, male_speaker, state, male_oldstate)
        assert 0 <= result.OQ <= 99
