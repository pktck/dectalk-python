"""Verify ``min_timing`` / ``inh_timing`` parity with ph_timng.c."""

from __future__ import annotations

import pytest

from dectalk.include.cmd_codes import PSFONT
from dectalk.include.phoneme_codes import PFUSA
from dectalk.ph import timing as t
from dectalk.ph.rom_tables import (
    us_begtyp,
    us_burdr,
    us_endtyp,
    us_featb,
    us_inhdr,
    us_mindur,
    us_ptram,
)


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


# ---- begtyp / endtyp / ptram / burdr ----


@pytest.mark.parametrize("code", [0, 1, 5, 10, 20, 50, 60])
def test_begtyp_us(code: int) -> None:
    """For US-font phones, ``begtyp`` returns ``us_begtyp[code]``."""
    assert t.begtyp(_us_phone(code)) == us_begtyp[code]


@pytest.mark.parametrize("code", [0, 1, 5, 10, 20, 50, 60])
def test_endtyp_us(code: int) -> None:
    """For US-font phones, ``endtyp`` returns ``us_endtyp[code]``."""
    assert t.endtyp(_us_phone(code)) == us_endtyp[code]


@pytest.mark.parametrize("code", [0, 1, 5, 10, 20, 50, 60])
def test_ptram_us(code: int) -> None:
    """For US-font phones, ``ptram`` returns ``us_ptram[code]``."""
    assert t.ptram(_us_phone(code)) == us_ptram[code]


@pytest.mark.parametrize("code", [0, 1, 5, 10, 20, 50, 60])
def test_burdr_us(code: int) -> None:
    """For US-font phones, ``burdr`` returns ``us_burdr[code]``."""
    assert t.burdr(_us_phone(code)) == us_burdr[code]


def test_begtyp_lookup_uses_low_byte() -> None:
    """``begtyp(phone)`` only reads the low byte — font bits are masked."""
    # Same low byte (=5) under different fonts should give the same result.
    assert t.begtyp(_us_phone(5)) == t.begtyp((0x1D << PSFONT) | 5)
    assert t.endtyp(_us_phone(5)) == t.endtyp((0x1C << PSFONT) | 5)
    assert t.ptram(_us_phone(5)) == t.ptram((0x1B << PSFONT) | 5)
    assert t.burdr(_us_phone(5)) == t.burdr((0x1A << PSFONT) | 5)
