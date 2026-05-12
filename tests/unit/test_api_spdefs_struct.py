"""Verify the Spdefs dataclass models ttsapi.h's SPDEFS struct."""

from __future__ import annotations

from dectalk.api.spdefs_struct import Spdefs


def test_default_construction() -> None:
    """All 39 fields default to zero."""
    s = Spdefs()
    assert s.sex == 0
    assert s.smoothness == 0
    assert s.junk == 0
    assert s.junk1 == 0


def test_field_count_matches_c_struct() -> None:
    """The 39 fields match the C ``SPDEFS_TAG`` struct."""
    fields = Spdefs.__dataclass_fields__
    expected = {
        "sex",
        "smoothness",
        "assertiveness",
        "average_pitch",
        "pitch_range",
        "breathiness",
        "richness",
        "num_fixed_samp_og",
        "laryngealization",
        "head_size",
        "formant4_res_freq",
        "formant4_bandwidth",
        "formant5_res_freq",
        "formant5_bandwidth",
        "parallel4_freq",
        "parallel5_freq",
        "gain_frication",
        "gain_aspiration",
        "gain_voicing",
        "gain_nasalization",
        "gain_cfr1",
        "gain_cfr2",
        "gain_cfr3",
        "gain_cfr4",
        "loudness",
        "spectral_tilt",
        "baseline_fall",
        "lax_breathiness",
        "quickness",
        "hat_rise",
        "stress_rise",
        "avg_glot_open",
        "avg_glot_voicd_open",
        "avg_glot_unv_open",
        "area_chink",
        "open_quo",
        "output_gain_mult",
        "junk",
        "junk1",
    }
    assert set(fields.keys()) == expected
    assert len(fields) == 39


def test_paul_kwargs() -> None:
    """Paul-like construction (male, average pitch 122 Hz)."""
    s = Spdefs(sex=1, average_pitch=122, pitch_range=100, head_size=100)
    assert s.sex == 1
    assert s.average_pitch == 122
    assert s.pitch_range == 100
    assert s.head_size == 100


def test_uses_slots() -> None:
    """Spdefs uses slots=True."""
    s = Spdefs()
    assert not hasattr(s, "__dict__")
