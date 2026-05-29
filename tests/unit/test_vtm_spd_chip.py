"""Unit tests for vtm.spd_chip and vtm.vtm_t.

Covers:
- default_us_paul_spd() field values (sourced from the active non-_8
  paul row in p_us_vdf_dectalk43.c)
- SpdChip re-export from vtm.spd_chip
- VtmT NOM_* defaults (sourced from p_us_vdf1.c / vtminst.h)
- Cross-consistency between SpdChip and VtmT
"""

from __future__ import annotations

from dectalk.ph.spdef_chip import SpdChip as SpdChipFromPh
from dectalk.vtm.spd_chip import SpdChip, default_us_paul_spd
from dectalk.vtm.vtm_t import VtmT, default_us_paul_vtm_t


class TestDefaultUsPaulSpd:
    """Verify US-Paul SpdChip field values against p_us_vdf_dectalk43.c paul."""

    # Resonator 4 cascade (F4=3300, B4=260)
    def test_r4cc_f4(self) -> None:
        assert default_us_paul_spd().r4cc == 3300, "F4 centre frequency"

    def test_r4cb_b4(self) -> None:
        assert default_us_paul_spd().r4cb == 260, "B4 bandwidth"

    # Resonator 5 cascade (F5=3650, B5=330)
    def test_r5cc_f5(self) -> None:
        assert default_us_paul_spd().r5cc == 3650, "F5 centre frequency"

    def test_r5cb_b5(self) -> None:
        assert default_us_paul_spd().r5cb == 330, "B5 bandwidth"

    # Parallel resonator proxies (F7=3350, F8=3850)
    def test_r4pb_f7(self) -> None:
        assert default_us_paul_spd().r4pb == 3350, "F7 (resonator-4 parallel proxy)"

    def test_r5pb_f8(self) -> None:
        assert default_us_paul_spd().r5pb == 3850, "F8 (resonator-5 parallel proxy)"

    # Cascade amplitudes (G1-G4, LO)
    def test_r5ca_g1(self) -> None:
        assert default_us_paul_spd().r5ca == 68, "G1 (cascade amp resonator 5)"

    def test_r4ca_g2(self) -> None:
        assert default_us_paul_spd().r4ca == 60, "G2 (cascade amp resonator 4)"

    def test_r3ca_g3(self) -> None:
        assert default_us_paul_spd().r3ca == 48, "G3 (cascade amp resonator 3)"

    def test_r2ca_g4(self) -> None:
        assert default_us_paul_spd().r2ca == 64, "G4 (cascade amp resonator 2)"

    def test_r1ca_lo(self) -> None:
        assert default_us_paul_spd().r1ca == 86, "LO (output level)"

    # Gain fields
    def test_afgain_gf(self) -> None:
        assert default_us_paul_spd().afgain == 70, "GF (frication gain)"

    def test_apgain_gh(self) -> None:
        assert default_us_paul_spd().apgain == 70, "GH (aspiration gain)"

    def test_azgain_gv(self) -> None:
        assert default_us_paul_spd().azgain == 65, "GV (voicing/glottal gain)"

    def test_rnpgain_gn(self) -> None:
        assert default_us_paul_spd().rnpgain == 74, "GN (nasal-pole gain)"

    # fnscale: 4096 = Q12 unity (HS=100, nominal head size for Paul)
    def test_fnscale_q12_unity(self) -> None:
        assert default_us_paul_spd().fnscale == 4096, "fnscale must be Q12 unity (4096) for HS=100"

    # Integer-cascade build leaves these chip slots zero
    def test_nopen1_zero(self) -> None:
        assert default_us_paul_spd().nopen1 == 0, "nopen1 unused in integer cascade build"

    def test_nopen2_zero(self) -> None:
        assert default_us_paul_spd().nopen2 == 0, "nopen2 unused in integer cascade build"

    def test_aturb_zero(self) -> None:
        assert default_us_paul_spd().aturb == 0, "aturb unused in integer cascade build"

    def test_t0jit_zero(self) -> None:
        assert default_us_paul_spd().t0jit == 0

    # Sex / speaker
    def test_sex_male(self) -> None:
        assert default_us_paul_spd().sex == 1, "Paul is MALE (sex=1)"

    def test_speaker_paul(self) -> None:
        assert default_us_paul_spd().speaker == 0, "Paul is speaker index 0"

    def test_osgain_zero(self) -> None:
        assert default_us_paul_spd().osgain == 0, (
            "osgain=0: paul[SPD_OS]=0 and paul_tune=0 -> no output-stage dB delta"
        )


class TestSpdChipReexport:
    """Verify that vtm.spd_chip re-exports the canonical SpdChip."""

    def test_reexport_is_same_class(self) -> None:
        assert SpdChip is SpdChipFromPh, (
            "vtm.spd_chip.SpdChip must be the same object as ph.spdef_chip.SpdChip"
        )

    def test_spdchip_has_slots(self) -> None:
        spd = default_us_paul_spd()
        assert isinstance(spd, SpdChip)
        # Slots classes don't have __dict__ on instances.
        assert not hasattr(spd, "__dict__")

    def test_factory_returns_spdchip(self) -> None:
        spd = default_us_paul_spd()
        assert isinstance(spd, SpdChip)

    def test_each_call_returns_fresh_instance(self) -> None:
        a = default_us_paul_spd()
        b = default_us_paul_spd()
        assert a is not b


class TestVtmTDefaults:
    """Verify VtmT NOM_* fields match p_us_vdf1.c paul_8 SPDEF values."""

    # Values from paul_8 SPDEF in p_us_vdf1.c
    def test_nom_unstressed_vowel(self) -> None:
        assert default_us_paul_vtm_t().NOM_UNSTRESSED_VOWEL == 700, "paul_8.AGO=700"

    def test_nom_voic_glot_area(self) -> None:
        assert default_us_paul_vtm_t().NOM_VOIC_GLOT_AREA == 700, "paul_8.unvow=700"

    def test_nom_unvoiced_son(self) -> None:
        assert default_us_paul_vtm_t().NOM_UNVOICED_SON == 1800, "paul_8.AGUO=1800"

    def test_nom_voiced_obstruent(self) -> None:
        assert default_us_paul_vtm_t().NOM_VOICED_OBSTRUENT == 800, "paul_8.AGVO=800"

    def test_nom_area_chink(self) -> None:
        assert default_us_paul_vtm_t().NOM_Area_Chink == 0, "paul_8.chink=0"

    def test_nom_open_quo(self) -> None:
        assert default_us_paul_vtm_t().NOM_Open_Quo == 60, "paul_8.open_quo=60"

    def test_nom_fricative_opening(self) -> None:
        # Must agree with _NOM_FRICATIVE_OPENING constant used in phdraw.py
        assert default_us_paul_vtm_t().NOM_Fricative_Opening == 100

    def test_vtmt_has_slots(self) -> None:
        assert not hasattr(default_us_paul_vtm_t(), "__dict__")

    def test_factory_returns_vtmt(self) -> None:
        assert isinstance(default_us_paul_vtm_t(), VtmT)


class TestSpdChipVtmTConsistency:
    """Cross-consistency checks between SpdChip and VtmT."""

    def test_fnscale_is_q12_integer(self) -> None:
        """fnscale must be a positive integer (Q12 fixed-point)."""
        spd = default_us_paul_spd()
        assert isinstance(spd.fnscale, int)
        assert spd.fnscale > 0

    def test_nom_fricative_opening_matches_phdraw_constant(self) -> None:
        """VtmT.NOM_Fricative_Opening must match phdraw's hardcoded value."""
        vtm = default_us_paul_vtm_t()
        # phdraw.py has _NOM_FRICATIVE_OPENING = 100
        assert vtm.NOM_Fricative_Opening == 100

    def test_sex_consistent_with_nom_voic_glot_area(self) -> None:
        """Male voice (sex=1) should have lower glottal-area nominal than female."""
        spd = default_us_paul_spd()
        vtm = default_us_paul_vtm_t()
        # Paul is MALE; male voices have NOM_VOIC_GLOT_AREA around 700 (smaller
        # than female ~900). Check that the sex field is consistent.
        assert spd.sex == 1  # MALE
        assert vtm.NOM_VOIC_GLOT_AREA <= 800  # male typical range


class TestSpdChipMutability:
    """SpdChip instances are mutable (dataclass without frozen=True)."""

    def test_can_modify_fnscale(self) -> None:
        spd = default_us_paul_spd()
        spd.fnscale = 3686  # HS=90 hypothetical
        assert spd.fnscale == 3686

    def test_can_modify_sex(self) -> None:
        spd = default_us_paul_spd()
        spd.sex = 0  # female
        assert spd.sex == 0


class TestVtmTMutability:
    """VtmT instances are mutable (dataclass without frozen=True)."""

    def test_can_modify_nom_fricative_opening(self) -> None:
        vtm = default_us_paul_vtm_t()
        vtm.NOM_Fricative_Opening = 150
        assert vtm.NOM_Fricative_Opening == 150

    def test_can_set_all_nom_fields(self) -> None:
        vtm = VtmT(
            NOM_UNSTRESSED_VOWEL=800,
            NOM_VOIC_GLOT_AREA=800,
            NOM_UNVOICED_SON=2000,
            NOM_VOICED_OBSTRUENT=900,
            STRESS_STEP=120,
            UNSTRESS_PRESSURE=450,
            STRESS_PRESSURE=750,
            NOM_Sub_Pressure=650,
            NOM_Open_Glottis=3200,
            NOM_Area_Chink=50,
            NOM_Open_Quo=55,
            NOM_Fricative_Opening=110,
            NOM_Glot_Stop_Area=5,
            VOT_speed=110,
            EndOfPhrase_Spread=60,
            Tiltm=80,
        )
        assert vtm.NOM_UNSTRESSED_VOWEL == 800
        assert vtm.NOM_Area_Chink == 50
        assert vtm.Tiltm == 80
