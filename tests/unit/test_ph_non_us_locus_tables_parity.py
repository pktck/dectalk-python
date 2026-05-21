"""C-source parity tests for non-US locus tables (UK/GR/LA/SP/FR).

Re-parses ``const short {lang}_{male,fem}loc[]`` and ``const short
{lang}_plocu[]`` from the corresponding ``p_{lang}_rom.c`` files and
asserts that the Python literal tables are byte-identical.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import importlib
import os
import re
from pathlib import Path

import pytest

from dectalk.include.cmd_codes import PSFONT
from dectalk.include.phoneme_codes import PFFR, PFGR, PFLA, PFSP, PFUK, PFUSA
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.fr_locus_tables import fr_femloc, fr_maleloc, fr_plocu
from dectalk.ph.gr_locus_tables import gr_femloc, gr_maleloc, gr_plocu
from dectalk.ph.la_locus_tables import la_femloc, la_maleloc, la_plocu
from dectalk.ph.numeric_constants import F1
from dectalk.ph.rom_tables import us_plocu
from dectalk.ph.setloc import setloc
from dectalk.ph.sp_locus_tables import sp_femloc, sp_maleloc, sp_plocu
from dectalk.ph.timing import plocu
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.uk_locus_tables import uk_femloc, uk_maleloc, uk_plocu
from dectalk.ph.utterance_constants import GEN_SIL

_C_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph"

pytestmark = pytest.mark.skipif(
    not (_C_ROOT / "p_uk_rom.c").is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_c_table(c_file: Path, table_name: str) -> tuple[int, ...]:
    """Parse ``const short NAME[] = { ... };`` from a C source file."""
    text = c_file.read_bytes().replace(b"\r", b"").decode("latin-1")
    # Strip block comments.
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    # Strip line comments.
    text = re.sub(r"//.*", "", text)
    m = re.search(
        rf"const\s+short\s+{re.escape(table_name)}\s*\[\d*\]\s*=\s*\{{(.+?)\}}\s*;",
        text,
        re.DOTALL,
    )
    if m is None:
        pytest.skip(f"table {table_name} not found in {c_file.name}")
    return tuple(int(v) for v in re.findall(r"-?\d+", m.group(1)))


# ---------------------------------------------------------------------------
# Per-language parametrisation
# ---------------------------------------------------------------------------

_LANG_FILES = [
    ("uk", "p_uk_rom.c", ["uk_plocu", "uk_maleloc", "uk_femloc"]),
    ("gr", "p_gr_rom.c", ["gr_plocu", "gr_maleloc", "gr_femloc"]),
    ("la", "p_la_rom.c", ["la_plocu", "la_maleloc", "la_femloc"]),
    ("sp", "p_sp_rom.c", ["sp_plocu", "sp_maleloc", "sp_femloc"]),
    ("fr", "p_fr_rom.c", ["fr_plocu", "fr_maleloc", "fr_femloc"]),
]

# Flatten into (c_file_basename, table_name) pairs for parametrize.
_TABLE_PARAMS: list[tuple[str, str]] = [
    (c_file, tname) for (_lang, c_file, tnames) in _LANG_FILES for tname in tnames
]


def _get_python_table(table_name: str) -> tuple[int, ...]:
    """Import and return the Python table matching ``table_name``."""
    lang = table_name.split("_", maxsplit=1)[0]  # e.g. "uk" from "uk_maleloc"
    module_name = f"dectalk.ph.{lang}_locus_tables"
    mod = importlib.import_module(module_name)
    return getattr(mod, table_name)  # type: ignore[no-any-return]


@pytest.mark.parametrize("c_file,table_name", _TABLE_PARAMS)
def test_locus_table_matches_c(c_file: str, table_name: str) -> None:
    """Each non-US locus/plocu table matches the C source initialiser."""
    expected = _parse_c_table(_C_ROOT / c_file, table_name)
    actual = _get_python_table(table_name)
    assert actual == expected, (
        f"{table_name}: Python table ({len(actual)} entries) does not match "
        f"C source ({len(expected)} entries)"
    )


def test_locus_tables_are_valid_int16() -> None:
    """All values in every non-US locus table fit in signed int16."""
    int16_min = -32768
    int16_max = 32767
    for _lang, _c_file, tnames in _LANG_FILES:
        for tname in tnames:
            table = _get_python_table(tname)
            for i, v in enumerate(table):
                assert int16_min <= v <= int16_max, f"{tname}[{i}] = {v} out of int16 range"


# ---------------------------------------------------------------------------
# Smoke: setloc no longer raises for non-US fonts
# ---------------------------------------------------------------------------


def _make_setloc_handle(font_code: int) -> TtsHandle:
    """Build a handle using a phone encoded with the given font."""
    phone = (font_code << PSFONT) | (GEN_SIL & 0xFF)
    p_dph_t = DphT()
    p_dph_t.allophons = [phone] * 6
    p_dph_t.allofeats = [0] * 6
    p_dph_t.allodurs = [0] * 6
    p_dph_t.nallotot = 6
    p_dph_t.nphone = 1
    p_dph_t.last_lang = 0
    settar = DphSettarSt()
    settar.np = F1
    p_dph_t.pSTphsettar = settar
    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    handle.p_kernel_share_data = KsdT()
    return handle


@pytest.mark.parametrize(
    "font_name,font_code",
    [
        ("UK", PFUK),
        ("GR", PFGR),
        ("LA", PFLA),
        ("SP", PFSP),
        ("FR", PFFR),
    ],
)
def test_setloc_does_not_raise_for_non_us_fonts(font_name: str, font_code: int) -> None:
    """setloc returns 0 (filter rejects silence) for every non-US font.

    Previously each non-US branch raised ``NotImplementedError``.  With
    the locus tables ported, the function must reach at least the
    filter check and return 0 for a silence-only phone array (rather
    than raising).
    """
    handle = _make_setloc_handle(font_code)
    # Must not raise; must return 0 (filter rejects a silence phone).
    result = setloc(handle, 0, 1, "i", 2, 0)
    assert result == 0, f"setloc returned {result!r} for {font_name} font; expected 0"


@pytest.mark.parametrize(
    "font_code,table,label",
    [
        (PFUSA, us_plocu, "US"),
        (PFUK, uk_plocu, "UK"),
        (PFGR, gr_plocu, "GR"),
        (PFSP, sp_plocu, "SP"),
        (PFLA, la_plocu, "LA"),
        (PFFR, fr_plocu, "FR"),
    ],
)
def test_plocu_dispatches_by_font(font_code: int, table: tuple[int, ...], label: str) -> None:
    """``plocu()`` routes to the correct per-language table for each font."""
    # Index 0 of each table: confirm plocu() returns the same value as direct lookup.
    index = (font_code << 8) | 0  # code 0 in the given font
    expected = table[0] if len(table) > 0 else 0
    actual = plocu(index)
    assert actual == expected, f"plocu dispatch for {label} font: got {actual}, expected {expected}"


# Unused imports kept as reference for completeness checks.
_ = (
    fr_femloc,
    fr_maleloc,
    gr_femloc,
    gr_maleloc,
    la_femloc,
    la_maleloc,
    sp_femloc,
    sp_maleloc,
    uk_femloc,
    uk_maleloc,
)
