"""Unit tests for the ``setspdef`` port (:mod:`dectalk.ph.setspdef`).

Pins the ``ph_vset.c`` lines 541-831 derivations against hand-computed
values from the active ``p_us_vdf_dectalk43.c`` voice rows (issue #302
cluster 3 — the non-Paul voice byte-parity fix). The end-to-end
arbiter is the byte-identical suite in
``tests/parity/test_vtm1_pcm_parity.py`` (``[:nr]`` / ``[:nw]`` /
``[:nk]`` prompts render byte-exact); these tests keep the individual
scalar derivations self-documenting and regression-named.
"""

from __future__ import annotations

from dataclasses import asdict

from dectalk.ph.dph_t import DphT
from dectalk.ph.setspdef import C_SPEAKER_INDEX, seed_dph_scalars, spd_chip_from_row
from dectalk.ph.voice_definitions import (
    voice_kit,
    voice_paul,
    voice_rita,
    voice_wendy,
)
from dectalk.vtm.spd_chip import default_us_paul_spd


def test_paul_chip_matches_oracle_verified_factory() -> None:
    """The derived Paul chip equals the oracle-packet-verified factory.

    ``default_us_paul_spd()`` was byte-verified against the oracle's
    ``SPC_type_speaker`` packet (issue #284); the generic derivation
    must reproduce it exactly (including fnscale=4100, nopen1=8800,
    aturb=9 — the non-obvious ``ph_vset.c`` scalings).
    """
    derived = spd_chip_from_row(voice_paul, speaker=C_SPEAKER_INDEX["paul"])
    assert asdict(derived) == asdict(default_us_paul_spd())


def test_paul_dph_scalars_match_previous_hardcoded_seeds() -> None:
    """Paul's DphT scalars equal the values speak.py used to hard-code."""
    p = DphT()
    seed_dph_scalars(p, voice_paul)
    assert p.malfem == 1
    assert p.fnscale == 4100  # (200 - 100) * 41
    assert p.f0_lp_filter == 1500 + 15 * 40  # QU = 40
    assert p.f0minimum == 1220  # AP = 122, non-HLSYN AP * 10 (issue #259)
    assert p.f0scalefac == 4100  # PR = 100
    assert p.size_hat_rise == 180  # HR = 18, * 10 (issue #261)
    assert p.scale_str_rise == 32  # SR = 32, bare copy
    assert p.f0basefall == 180  # BF = 18, * 10 (issue #261)
    assert p.assertiveness == 4100  # AS = 100, * 41
    assert p.f0_dep_tilt == 75  # FT = 75 (issue #289)
    assert p.spdeftltoff == 0  # (SM=3 * 25) // 100
    assert p.spdefb1off == 4096  # BR = 0 -> Q12 unity
    assert p.spdeflaxprcnt == 0  # LX = 0
    assert p.last_lang == 0  # forces gettar table reload


def test_rita_derivations() -> None:
    """Rough Rita: SEX=0 SM=24 BR=46 RI=20 LA=4 HS=95 FT=0 (4.3 row)."""
    p = DphT()
    seed_dph_scalars(p, voice_rita)
    assert p.malfem == 0  # FEMALE -> gettar selects the femtar tables
    assert p.fnscale == (200 - 95) * 41 == 4305
    assert p.f0_dep_tilt == 0  # FT = 0
    assert p.spdeftltoff == (24 * 25) // 100 == 6
    assert p.spdefb1off == ((46 * 46) >> 1) + 4096 == 5154
    assert p.f0minimum == 1060  # AP = 106

    chip = spd_chip_from_row(voice_rita, speaker=C_SPEAKER_INDEX["rita"])
    assert chip.speaker == 7
    assert chip.sex == 0
    assert chip.t0jit == 4 << 3 == 32  # LA = 4 -> the "rough" T0 jitter
    assert chip.r4cc == (4000 * 4305) >> 12 == 4204  # F4 chip word
    assert chip.r4cb == 250  # B4
    assert chip.r5cc == 6000  # F5 = ZAPF passes through
    assert chip.r5cb == 6000  # B5 zapped to ZAPB with it
    assert chip.nopen1 == 4000 + 160 * (100 - 20) == 16800  # RI = 20
    assert chip.aturb == 46 + 9 == 55  # BR + 9 (non-HLSYN)


def test_wendy_derivations() -> None:
    """Whispery Wendy: SM=100 BR=55 RI=0 NF=10 LX=80 GV=51 (4.3 row)."""
    p = DphT()
    seed_dph_scalars(p, voice_wendy)
    assert p.malfem == 0
    assert p.fnscale == 4100  # HS = 100
    assert p.f0_dep_tilt == 100  # FT = 100
    assert p.spdeftltoff == 25  # SM = 100
    assert p.spdefb1off == ((55 * 55) >> 1) + 4096 == 5608
    assert p.spdeflaxprcnt == 80 * 41 == 3280  # LX drives the breathy-AH AP

    chip = spd_chip_from_row(voice_wendy, speaker=C_SPEAKER_INDEX["willy"])
    assert chip.speaker == 8  # public "willy" preset = wendy row/slot
    assert chip.r4cc == (4500 * 4100) >> 12 == 4504
    assert chip.r4cb == 400
    assert chip.nopen1 == 20000  # RI = 0
    assert chip.nopen2 == 40  # NF = 10, * 4
    assert chip.aturb == 64  # BR = 55
    assert chip.azgain == 51  # GV — the whispery low voicing gain


def test_kit_derivations() -> None:
    """Kit the Kid: HS=80 (child head) BR=47 RI=40 F4=ZAPF (4.3 row)."""
    p = DphT()
    seed_dph_scalars(p, voice_kit)
    assert p.malfem == 0
    assert p.fnscale == (200 - 80) * 41 == 4920  # small head scales formants up
    assert p.spdeftltoff == (5 * 25) // 100 == 1
    assert p.spdefb1off == ((47 * 47) >> 1) + 4096 == 5200
    assert p.spdeflaxprcnt == 75 * 41 == 3075
    assert p.f0minimum == 3060  # AP = 306

    chip = spd_chip_from_row(voice_kit, speaker=C_SPEAKER_INDEX["kit"])
    assert chip.speaker == 5
    assert chip.r4cc == 6000  # F4 = ZAPF: no fnscale pre-scale
    assert chip.r4cb == 6000  # B4 = ZAPB
    assert chip.nopen1 == 4000 + 160 * 60 == 13600  # RI = 40
    assert chip.aturb == 56  # BR = 47


def test_zap_threshold_applies_after_fnscale() -> None:
    """A scaled F4 above 4950 zaps both the frequency and the bandwidth.

    ``ph_vset.c`` lines 652-660: the 11025 Hz build zaps chip
    frequencies above 4950 *after* the fnscale multiply. Construct a
    synthetic row (F4=4500 at kit's HS=80 head size -> 5404 > 4950).
    """
    row = list(voice_kit)
    row[10] = 4500  # SPD_F4
    row[11] = 260  # SPD_B4
    chip = spd_chip_from_row(tuple(row))
    assert (4500 * 4920) >> 12 == 5405  # would exceed the threshold
    assert chip.r4cc == 6000  # ZAPF
    assert chip.r4cb == 6000  # ZAPB — bandwidth zapped alongside
