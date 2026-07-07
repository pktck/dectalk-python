"""Field-level parity test for SpdChip US-Paul defaults vs the C source.

Re-parses ``${DECTALK_SRC}/src/dapi/src/ph/p_us_vdf_dectalk43.c`` at test
time, extracts the literal initialisers of the non-``_8`` ``paul[SPDEF]``
row (the DECtalk 4.3 speaker definition loaded at 11025 Hz per
``ph_vset.c:449-459``), and asserts that
:func:`dectalk.vtm.spd_chip.default_us_paul_spd` returns a
:class:`~dectalk.vtm.spd_chip.SpdChip` whose chip-format fields match
the corresponding SPDEF slot values from the C source.

Skips cleanly when ``DECTALK_SRC`` is not set, matching the other
parity tests in this tree (see ``tests/unit/test_ph_make_dip_parity.py``
for the canonical pattern).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.vtm.spd_chip import default_us_paul_spd

# SPDEF slot names in C array order (cmd.h SPD_* indices 0..37). The 4.3
# ``paul`` row fills 38 of the 39 SPDEF slots; slot 38 (SPD_NM, the
# speaker number) is written at load time, not in the table.
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
    "AGVO",
    "AGUO",
    "UNVOW",
    "CHINK",
    "OQ",
    "OS",
)

# Symbolic constants used in the 4.3 voice initialisers. Paul's row uses
# ``MALE``; the ZAP* magic formant values appear in the female rows but
# are resolved here too for completeness.
_C_CONSTS: dict[str, int] = {"MALE": 1, "FEMALE": 0, "ZAPF": 6000, "ZAPB": 6000}


def _dectalk_src() -> Path | None:
    """Return ``$DECTALK_SRC`` as a :class:`Path` if set, else None."""
    raw = os.environ.get("DECTALK_SRC")
    if not raw:
        return None
    return Path(raw)


def _extract_paul_spdef_values() -> dict[str, int]:
    """Parse the non-``_8`` ``paul[SPDEF]`` row out of ``p_us_vdf_dectalk43.c``.

    The parser strips C/C++ comments, resolves the ``MALE`` / ``FEMALE``
    / ``ZAPF`` / ``ZAPB`` symbolic constants, and zips the resulting
    integer literals against :data:`_SPDEF_SLOT_NAMES`. The
    ``paul\\s*\\[`` anchor only matches ``paul[`` (never ``paul_8[``), so
    the non-``_8`` row is selected even though it follows ``paul_8`` in
    the file.

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

    decl = re.search(r"const\s+short\s+paul\s*\[\s*SPDEF\s*\]\s*=\s*\{", text)
    assert decl is not None, "non-_8 paul[SPDEF] declaration not found"

    body_start = decl.end()
    depth = 1
    i = body_start
    while i < len(text) and depth > 0:
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    body = text[body_start : i - 1]

    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//[^\n]*", "", body)
    for name, value in _C_CONSTS.items():
        body = re.sub(rf"\b{name}\b", str(value), body)

    raw_values: list[int] = [int(m.group(0)) for m in re.finditer(r"-?\d+", body)]

    assert len(raw_values) == len(_SPDEF_SLOT_NAMES), (
        f"paul had {len(raw_values)} integer literals, expected {len(_SPDEF_SLOT_NAMES)}"
    )
    return dict(zip(_SPDEF_SLOT_NAMES, raw_values, strict=True))


@pytest.fixture(scope="module")
def paul_c_values() -> dict[str, int]:
    """Cached parse of the non-_8 paul SPDEF literals from p_us_vdf_dectalk43.c."""
    return _extract_paul_spdef_values()


class TestSpdChipFieldParity:
    """Each SPD_CHIP field is compared to the SPDEF slot it maps from."""

    def test_r4cb_eq_b4(self, paul_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r4cb == paul_c_values["B4"]

    def test_r4cc_eq_f4_chip_scaled(self, paul_c_values: dict[str, int]) -> None:
        # setspdef pre-scales F4 by fnscale before streaming it to the
        # chip: r4cb_chip = (F4 * fnscale) >> 12 (ph_vset.c:648). The
        # Python SpdChip stores the frequency in .r4cc (swapped field
        # convention -- see spd_chip.py docstring).
        fnscale = (200 - paul_c_values["HS"]) * 41
        assert default_us_paul_spd().r4cc == (paul_c_values["F4"] * fnscale) >> 12

    def test_r5cb_eq_b5(self, paul_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r5cb == paul_c_values["B5"]

    def test_r5cc_eq_f5_chip_scaled(self, paul_c_values: dict[str, int]) -> None:
        # r5cb_chip = (F5 * fnscale) >> 12 (ph_vset.c:670).
        fnscale = (200 - paul_c_values["HS"]) * 41
        assert default_us_paul_spd().r5cc == (paul_c_values["F5"] * fnscale) >> 12

    def test_r4pb_eq_f7(self, paul_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r4pb == paul_c_values["F7"]

    def test_r5pb_eq_f8(self, paul_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r5pb == paul_c_values["F8"]

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

    def test_sex_eq_spdef_sex(self, paul_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().sex == paul_c_values["SEX"]

    def test_osgain_eq_spdef_os(self, paul_c_values: dict[str, int]) -> None:
        # ph_vset.c:789 copies curspdef[SPD_OS] into osgain; the 4.3 paul
        # row and the all-zero paul_tune both carry 0 there.
        assert paul_c_values["OS"] == 0, "test assumes 4.3 paul SPD_OS=0"
        assert default_us_paul_spd().osgain == paul_c_values["OS"] == 0

    def test_t0jit_eq_la_shifted(self, paul_c_values: dict[str, int]) -> None:
        # t0jit = LA << 3 (ph_vset.c:701); Paul LA=0.
        assert default_us_paul_spd().t0jit == paul_c_values["LA"] << 3

    def test_nopen1_setspdef_derivation(self, paul_c_values: dict[str, int]) -> None:
        # nopen1 = 4000 + 160*(100 - RI) (ph_vset.c:717); Paul RI=70
        # gives 8800 -- the K1 of the glottal open phase (issue #284).
        assert default_us_paul_spd().nopen1 == 4000 + 160 * (100 - paul_c_values["RI"])

    def test_nopen2_setspdef_derivation(self, paul_c_values: dict[str, int]) -> None:
        # nopen2 = NF * 4 (ph_vset.c:718); Paul NF=0.
        assert default_us_paul_spd().nopen2 == paul_c_values["NF"] * 4

    def test_aturb_setspdef_derivation(self, paul_c_values: dict[str, int]) -> None:
        # aturb = BR + 9 (ph_vset.c:722, non-HLSYN branch); Paul BR=0.
        assert default_us_paul_spd().aturb == paul_c_values["BR"] + 9

    def test_notused_zero(self) -> None:
        assert default_us_paul_spd().notused == 0

    def test_fnscale_setspdef_derivation(
        self,
        paul_c_values: dict[str, int],
    ) -> None:
        # fnscale = (200 - HS) * 41 (ph_vset.c:638): 4100 for HS=100,
        # not Q12-unity 4096 (issue #284).
        assert default_us_paul_spd().fnscale == (200 - paul_c_values["HS"]) * 41

    def test_speaker_index_zero(self) -> None:
        assert default_us_paul_spd().speaker == 0


class TestSpdefParseSanity:
    """Defensive checks on the SPDEF reparse, independent of SpdChip."""

    def test_all_38_spdef_slots_present(
        self,
        paul_c_values: dict[str, int],
    ) -> None:
        assert set(paul_c_values.keys()) == set(_SPDEF_SLOT_NAMES)

    def test_paul_is_male(self, paul_c_values: dict[str, int]) -> None:
        assert paul_c_values["SEX"] == 1

    def test_paul_head_size_nominal(
        self,
        paul_c_values: dict[str, int],
    ) -> None:
        assert paul_c_values["HS"] == 100

    def test_paul_glottal_areas_zero(
        self,
        paul_c_values: dict[str, int],
    ) -> None:
        # Unlike the 8 kHz HLSYN paul_8 row (AGO=700/AGVO=800/AGUO=1800/
        # UNVOW=700/OQ=60), the active non-_8 4.3 paul row zeros the whole
        # AGO..OS tail.
        assert paul_c_values["AGO"] == 0
        assert paul_c_values["AGVO"] == 0
        assert paul_c_values["AGUO"] == 0
        assert paul_c_values["UNVOW"] == 0
        assert paul_c_values["CHINK"] == 0
        assert paul_c_values["OQ"] == 0
        assert paul_c_values["OS"] == 0
