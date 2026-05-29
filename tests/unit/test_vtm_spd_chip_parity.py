"""Field-level parity test for SpdChip US-Paul gains vs the active C source.

Re-parses the *active* ``paul`` row from
``${DECTALK_SRC}/src/dapi/src/ph/p_us_vdf_dectalk43.c`` at test time and
asserts that :func:`dectalk.vtm.spd_chip.default_us_paul_spd` returns a
:class:`~dectalk.vtm.spd_chip.SpdChip` whose gain fields match the
corresponding SPDEF slot values run through the plain-build
``setspdef()`` (``ph/ph_vset.c`` lines 703-790 -- all verbatim copies
when ``HLSYN`` / ``CHANGES_AFTER_V43`` / ``LOWCOMPUTE`` /
``LOW_COST_VERSION`` are undefined, which is the shipped x86_64 build).

The active build links ``p_us_vdf_dectalk43.c`` (confirmed by
``ph_vdefi.d``) and selects the non-``_8`` rows at the 11025 Hz US
sample rate (``ph_vset.c:454-457``). ``paul_tune`` in
``p_us_vdf_oldtune.c`` is all zeros, so ``curspdef`` == the raw row.

The retired HLSYN file ``p_us_vdf1.c`` ``paul_8`` (GF=55 GH=55 GV=60 ...)
that this test previously checked is *not* the live path.

Skips cleanly when ``DECTALK_SRC`` is not set, matching the other
parity tests in this tree.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.vtm.spd_chip import default_us_paul_spd

# SPDEF slot order in p_us_vdf_dectalk43.c (38 filled slots: SEX..SR,
# then AGO/agvo/aguo/unvow/chink/open_quo/OutputGainMult).
_SPDEF_SLOT_NAMES: tuple[str, ...] = (
    "SEX",
    "SM",
    "AS",
    "AP",
    "PR",
    "BR",
    "RI",
    "NF",
    "LA",
    "HS",
    "F4",
    "B4",
    "F5",
    "B5",
    "F7",
    "F8",
    "GF",
    "GH",
    "GV",
    "GN",
    "G1",
    "G2",
    "G3",
    "G4",
    "LO",
    "FT",
    "BF",
    "LX",
    "QU",
    "HR",
    "SR",
    "AGO",
    "agvo",
    "aguo",
    "unvow",
    "chink",
    "open_quo",
    "OS",
)

# Symbolic constants in the C initialisers (11025 Hz branch).
_C_CONSTS: dict[str, int] = {"MALE": 1, "FEMALE": 0, "ZAPF": 6000, "ZAPB": 6000}


def _dectalk_src() -> Path | None:
    """Return ``$DECTALK_SRC`` as a :class:`Path` if set, else None."""
    raw = os.environ.get("DECTALK_SRC")
    if not raw:
        return None
    return Path(raw)


def _extract_paul_spdef_values() -> dict[str, int]:
    """Parse the active non-``_8`` ``paul`` row out of p_us_vdf_dectalk43.c.

    Returns:
        Mapping from SPDEF slot name to integer literal value.
    """
    src = _dectalk_src()
    if src is None:
        pytest.skip("DECTALK_SRC not set; cannot reparse paul from C source")

    vdf_path = src / "src" / "dapi" / "src" / "ph" / "p_us_vdf_dectalk43.c"
    if not vdf_path.is_file():
        pytest.skip(f"{vdf_path} missing from oracle tree")

    text = vdf_path.read_text(encoding="latin-1")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)

    # Match the non-``_8`` ``paul`` row exactly (not ``paul_8``).
    m = re.search(
        r"const\s+short\s+paul\[\s*SPDEF\s*\]\s*=\s*\{([^}]+)\}\s*;",
        text,
        re.DOTALL,
    )
    assert m is not None, "non-_8 paul[SPDEF] declaration not found"

    raw_values: list[int] = []
    for raw_field in m.group(1).split(","):
        field = raw_field.strip()
        if not field:
            continue
        for name, value in _C_CONSTS.items():
            field = re.sub(r"\b" + name + r"\b", str(value), field)
        raw_values.append(int(field))

    assert len(raw_values) == len(_SPDEF_SLOT_NAMES), (
        f"paul had {len(raw_values)} integer literals, expected {len(_SPDEF_SLOT_NAMES)}"
    )
    return dict(zip(_SPDEF_SLOT_NAMES, raw_values, strict=True))


@pytest.fixture(scope="module")
def paul_c_values() -> dict[str, int]:
    """Cached parse of the active paul SPDEF literals from p_us_vdf_dectalk43.c."""
    return _extract_paul_spdef_values()


class TestSpdChipGainParity:
    """Each SPD_CHIP gain field is the verbatim setspdef copy of its SPDEF slot."""

    def test_r5ca_eq_g1(self, paul_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r5ca == paul_c_values["G1"]

    def test_r4ca_eq_g2(self, paul_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r4ca == paul_c_values["G2"]

    def test_r3ca_eq_g3(self, paul_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r3ca == paul_c_values["G3"]

    def test_r2ca_eq_g4(self, paul_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r2ca == paul_c_values["G4"]

    def test_r1ca_eq_lo(self, paul_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r1ca == paul_c_values["LO"]

    def test_afgain_eq_gf(self, paul_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().afgain == paul_c_values["GF"]

    def test_apgain_eq_gh(self, paul_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().apgain == paul_c_values["GH"]

    def test_azgain_eq_gv(self, paul_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().azgain == paul_c_values["GV"]

    def test_rnpgain_eq_gn(self, paul_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().rnpgain == paul_c_values["GN"]

    def test_osgain_eq_spd_os(self, paul_c_values: dict[str, int]) -> None:
        # setspdef: osgain <- SPD_OS; dectalk43 paul OS = 0.
        assert default_us_paul_spd().osgain == paul_c_values["OS"]
        assert default_us_paul_spd().osgain == 0


class TestSpdChipStructuralFields:
    """Non-gain chip fields.

    The formant frequencies / bandwidths (``r4cc``/``r5cc``/``r4cb``/
    ``r5cb``/``r4pb``/``r5pb``), ``nopen1``/``nopen2``/``aturb`` and
    ``fnscale`` are *not* re-sourced by this gain lever -- they are
    deliberately left at their previous values (see the ``spd_chip.py``
    module note: Python's r4cc/r4cb convention is the inverse of the C
    chip layout, and the ``setspdef`` derivations for nopen/aturb/fnscale
    are formant/glottal/breathiness concerns). Only ``sex`` and
    ``speaker`` are checked against the C row here.
    """

    def test_sex_eq_spdef_sex(self, paul_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().sex == paul_c_values["SEX"]

    def test_t0jit_zero(self) -> None:
        assert default_us_paul_spd().t0jit == 0

    def test_nopen1_zero(self) -> None:
        # setspdef derivation (4000 + 160*(100-RI)) deferred; not a gain.
        assert default_us_paul_spd().nopen1 == 0

    def test_nopen2_zero(self) -> None:
        assert default_us_paul_spd().nopen2 == 0

    def test_aturb_zero(self) -> None:
        # setspdef derivation (BR + 9) deferred; breathiness, not a gain.
        assert default_us_paul_spd().aturb == 0

    def test_notused_zero(self) -> None:
        assert default_us_paul_spd().notused == 0

    def test_fnscale_q12_unity(self, paul_c_values: dict[str, int]) -> None:
        # setspdef computes (200-HS)*41 = 4100 for HS=100, but the
        # pure-Python formant path keys on Q12 unity (4096); reconciling
        # the two is formant-parity work outside this gain lever.
        assert paul_c_values["HS"] == 100, "test assumes nominal HS=100"
        assert default_us_paul_spd().fnscale == 4096

    def test_speaker_index_zero(self) -> None:
        assert default_us_paul_spd().speaker == 0


class TestSpdefParseSanity:
    """Defensive checks on the SPDEF reparse, independent of SpdChip."""

    def test_all_spdef_slots_present(self, paul_c_values: dict[str, int]) -> None:
        assert set(paul_c_values.keys()) == set(_SPDEF_SLOT_NAMES)

    def test_paul_is_male(self, paul_c_values: dict[str, int]) -> None:
        assert paul_c_values["SEX"] == 1

    def test_paul_head_size_nominal(self, paul_c_values: dict[str, int]) -> None:
        assert paul_c_values["HS"] == 100

    def test_paul_active_gains(self, paul_c_values: dict[str, int]) -> None:
        """The active dectalk43 paul gains differ from the retired paul_8."""
        assert paul_c_values["GF"] == 70
        assert paul_c_values["GH"] == 70
        assert paul_c_values["GV"] == 65
        assert paul_c_values["GN"] == 74
        assert paul_c_values["G1"] == 68
        assert paul_c_values["LO"] == 86
        assert paul_c_values["OS"] == 0
