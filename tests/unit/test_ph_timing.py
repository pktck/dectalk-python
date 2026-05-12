"""Verify ``min_timing`` / ``inh_timing`` parity with ph_timng.c."""

from __future__ import annotations

import pytest

from dectalk.include.cmd_codes import PSFONT
from dectalk.include.phoneme_codes import PFUSA
from dectalk.ph import timing as t
from dectalk.ph.rom_tables import us_featb, us_inhdr, us_mindur


def _us_phone(code: int) -> int:
    """Return a font-encoded US phoneme code (``(PFUSA << 8) | code``)."""
    return (PFUSA << PSFONT) | code


@pytest.mark.parametrize("code", [0, 1, 5, 10, 20, 50, 60, 70])
def test_min_timing_us(code: int) -> None:
    """For US-font phones with code < 100, ``min_timing`` returns ``us_mindur[code]``."""
    assert t.min_timing(_us_phone(code)) == us_mindur[code]


@pytest.mark.parametrize("code", [0, 1, 5, 10, 20, 50, 60, 70])
def test_inh_timing_us(code: int) -> None:
    """For US-font phones with code < 100, ``inh_timing`` returns ``us_inhdr[code]``."""
    assert t.inh_timing(_us_phone(code)) == us_inhdr[code]


@pytest.mark.parametrize("code", [100, 101, 150, 200, 255])
def test_min_timing_high_value_returns_zero(code: int) -> None:
    """Phones with code ≥ 100 are control codes — min duration is 0."""
    assert t.min_timing(_us_phone(code)) == 0


@pytest.mark.parametrize("code", [100, 101, 150, 200, 255])
def test_inh_timing_high_value_returns_zero(code: int) -> None:
    """Phones with code ≥ 100 are control codes — inh duration is 0."""
    assert t.inh_timing(_us_phone(code)) == 0


def test_min_timing_unknown_font_falls_back_to_us() -> None:
    """The C default branch returns ``us_mindur[code]`` for unknown fonts."""
    # Font 0x0F is not a recognised language — C falls back to us_mindur.
    fake_phone = (0x0F << PSFONT) | 5
    assert t.min_timing(fake_phone) == us_mindur[5]


def test_inh_timing_unknown_font_falls_back_to_us() -> None:
    """The C default branch returns ``us_inhdr[code]`` for unknown fonts."""
    fake_phone = (0x0F << PSFONT) | 5
    assert t.inh_timing(fake_phone) == us_inhdr[5]


def test_other_language_fonts_fall_back_to_us_until_tables_landed() -> None:
    """UK/GR/SP/LA/FR fonts return ``us_*`` until those tables ship."""
    for font in (0x1D, 0x1C, 0x1B, 0x1A, 0x19):
        phone = (font << PSFONT) | 3
        assert t.min_timing(phone) == us_mindur[3]
        assert t.inh_timing(phone) == us_inhdr[3]


# ---- phone_feature ----


def test_phone_feature_us_font() -> None:
    """For US-font phones, ``phone_feature`` returns ``us_featb[code]``."""
    for code in (0, 1, 5, 10, 20, 50):
        assert t.phone_feature(_us_phone(code)) == us_featb[code]


def test_phone_feature_unknown_font_falls_back_to_us() -> None:
    """Unknown fonts fall back to us_featb (Python keeps it defined)."""
    fake_phone = (0x0F << PSFONT) | 5
    assert t.phone_feature(fake_phone) == us_featb[5]
