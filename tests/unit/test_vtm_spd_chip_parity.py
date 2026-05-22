"""Field-level parity test for SpdChip US-Paul defaults vs the C source.

Re-parses ``${DECTALK_SRC}/src/dapi/src/ph/p_us_vdf1.c`` at test time,
extracts the literal initialisers of ``paul_8[SPDEF]`` (the HLSYN 8 kHz
speaker definition), and asserts that
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
)


def _dectalk_src() -> Path | None:
    """Return ``$DECTALK_SRC`` as a :class:`Path` if set, else None."""
    raw = os.environ.get("DECTALK_SRC")
    if not raw:
        return None
    return Path(raw)


def _extract_paul_8_spdef_values() -> dict[str, int]:
    """Parse ``paul_8[SPDEF]`` out of ``p_us_vdf1.c`` and return a dict.

    The parser strips C/C++ comments, drops the optional ``FP_VTM``
    trailing entry (gated by ``#ifdef FP_VTM`` which the linux build
    does not enable), and zips the remaining integer literals against
    :data:`_SPDEF_SLOT_NAMES`.

    Returns:
        Mapping from SPDEF slot name to integer literal value.
    """
    src = _dectalk_src()
    if src is None:
        pytest.skip("DECTALK_SRC not set; cannot reparse paul_8 from C source")

    vdf_path = src / "src" / "dapi" / "src" / "ph" / "p_us_vdf1.c"
    if not vdf_path.is_file():
        pytest.skip(f"{vdf_path} missing from oracle tree")

    text = vdf_path.read_text(encoding="utf-8", errors="replace")

    decl = re.search(
        r"const\s+short\s+paul_8\s*\[\s*SPDEF\s*\]\s*=\s*\{",
        text,
    )
    assert decl is not None, "paul_8[SPDEF] declaration not found"

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

    body = re.sub(
        r"#ifdef\s+FP_VTM.*?#endif",
        "",
        body,
        flags=re.DOTALL,
    )

    raw_values: list[int] = [int(m.group(0)) for m in re.finditer(r"-?\d+", body)]

    assert len(raw_values) == len(_SPDEF_SLOT_NAMES), (
        f"paul_8 had {len(raw_values)} integer literals, expected "
        f"{len(_SPDEF_SLOT_NAMES)}"
    )
    return dict(zip(_SPDEF_SLOT_NAMES, raw_values, strict=True))


@pytest.fixture(scope="module")
def paul_8_c_values() -> dict[str, int]:
    """Cached parse of paul_8 SPDEF literals from p_us_vdf1.c."""
    return _extract_paul_8_spdef_values()


class TestSpdChipFieldParity:
    """Each SPD_CHIP field is compared to the SPDEF slot it maps from."""

    def test_r4cb_eq_b4(self, paul_8_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r4cb == paul_8_c_values["B4"]

    def test_r4cc_eq_f4(self, paul_8_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r4cc == paul_8_c_values["F4"]

    def test_r5cb_eq_b5(self, paul_8_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r5cb == paul_8_c_values["B5"]

    def test_r5cc_eq_f5(self, paul_8_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r5cc == paul_8_c_values["F5"]

    def test_r4pb_eq_f7(self, paul_8_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r4pb == paul_8_c_values["F7"]

    def test_r5pb_eq_f8(self, paul_8_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r5pb == paul_8_c_values["F8"]

    def test_r5ca_eq_g1(self, paul_8_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r5ca == paul_8_c_values["G1"]

    def test_r4ca_eq_g2(self, paul_8_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r4ca == paul_8_c_values["G2"]

    def test_r3ca_eq_g3(self, paul_8_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r3ca == paul_8_c_values["G3"]

    def test_r2ca_eq_g4(self, paul_8_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r2ca == paul_8_c_values["G4"]

    def test_r1ca_eq_lo(self, paul_8_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().r1ca == paul_8_c_values["LO"]

    def test_afgain_eq_gf(self, paul_8_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().afgain == paul_8_c_values["GF"]

    def test_apgain_eq_gh(self, paul_8_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().apgain == paul_8_c_values["GH"]

    def test_azgain_eq_gv(self, paul_8_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().azgain == paul_8_c_values["GV"]

    def test_rnpgain_eq_gn(self, paul_8_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().rnpgain == paul_8_c_values["GN"]

    def test_sex_eq_spdef_sex(self, paul_8_c_values: dict[str, int]) -> None:
        assert default_us_paul_spd().sex == paul_8_c_values["SEX"]

    def test_t0jit_zero(self) -> None:
        assert default_us_paul_spd().t0jit == 0

    def test_nopen1_zero(self) -> None:
        assert default_us_paul_spd().nopen1 == 0

    def test_nopen2_zero(self) -> None:
        assert default_us_paul_spd().nopen2 == 0

    def test_aturb_zero(self) -> None:
        assert default_us_paul_spd().aturb == 0

    def test_notused_zero(self) -> None:
        assert default_us_paul_spd().notused == 0

    def test_fnscale_q12_unity_for_hs_100(
        self,
        paul_8_c_values: dict[str, int],
    ) -> None:
        assert paul_8_c_values["HS"] == 100, "test assumes nominal HS=100"
        assert default_us_paul_spd().fnscale == 4096

    def test_speaker_index_zero(self) -> None:
        assert default_us_paul_spd().speaker == 0

    def test_osgain_auto(self) -> None:
        assert default_us_paul_spd().osgain == -1


class TestSpdefParseSanity:
    """Defensive checks on the SPDEF reparse, independent of SpdChip."""

    def test_all_37_spdef_slots_present(
        self,
        paul_8_c_values: dict[str, int],
    ) -> None:
        assert set(paul_8_c_values.keys()) == set(_SPDEF_SLOT_NAMES)

    def test_paul_is_male(self, paul_8_c_values: dict[str, int]) -> None:
        assert paul_8_c_values["SEX"] == 1

    def test_paul_head_size_nominal(
        self,
        paul_8_c_values: dict[str, int],
    ) -> None:
        assert paul_8_c_values["HS"] == 100

    def test_paul_glottal_areas_hlsyn(
        self,
        paul_8_c_values: dict[str, int],
    ) -> None:
        assert paul_8_c_values["AGO"] == 700
        assert paul_8_c_values["agvo"] == 800
        assert paul_8_c_values["aguo"] == 1800
        assert paul_8_c_values["unvow"] == 700
        assert paul_8_c_values["open_quo"] == 60
