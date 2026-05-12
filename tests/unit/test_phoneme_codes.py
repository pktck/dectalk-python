"""Verify Python phoneme-code constants match the C ``#define``s.

The C front end uses numeric codes for phonemes and prosody markers
throughout its pipeline; per-module parity tests compare byte-equal
output, so the Python translations must use the same numeric values.
This test parses the C headers and asserts every constant we translate
matches.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include import phoneme_codes as pc

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_L_COM_PH = _SRC_ROOT / "src/dapi/src/include/l_com_ph.h"
_L_ALL_PH = _SRC_ROOT / "src/dapi/src/include/l_all_ph.h"

pytestmark = pytest.mark.skipif(
    not _L_COM_PH.is_file() or not _L_ALL_PH.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_define(text: str, name: str) -> int | None:
    """Parse a single ``#define NAME EXPR`` line; ``EXPR`` is ``int(<expr>)``."""
    m = re.search(rf"^#define\s+{re.escape(name)}\s+(.+?)\s*(?:/\*.*)?$", text, re.MULTILINE)
    if not m:
        return None
    expr = m.group(1).strip()
    # Direct hex literal.
    hex_match = re.fullmatch(r"0x[0-9a-fA-F]+", expr)
    if hex_match:
        return int(expr, 16)
    # Decimal arithmetic (parentheses allowed): e.g. ``(100+ 1)``.
    if re.fullmatch(r"[\d+\-*/() ]+", expr):
        return int(eval(expr))
    return None


def _l_com_ph_text() -> str:
    return _L_COM_PH.read_text(encoding="latin-1")


def _l_all_ph_text() -> str:
    return _L_ALL_PH.read_text(encoding="latin-1")


# ----- l_com_ph.h prosody/boundary constants --------------------------------


@pytest.mark.parametrize(
    ("py_name", "c_name"),
    [
        ("BLOCK_RULES", "BLOCK_RULES"),
        ("S3", "S3"),
        ("S2", "S2"),
        ("S1", "S1"),
        ("SEMPH", "SEMPH"),
        ("HAT_RISE", "HAT_RISE"),
        ("HAT_FALL", "HAT_FALL"),
        ("HAT_RF", "HAT_RF"),
        ("SBOUND", "SBOUND"),
        ("MBOUND", "MBOUND"),
        ("HYPHEN", "HYPHEN"),
        ("WBOUND", "WBOUND"),
        ("PPSTART", "PPSTART"),
        ("VPSTART", "VPSTART"),
        ("RELSTART", "RELSTART"),
        ("COMMA", "COMMA"),
        ("PERIOD", "PERIOD"),
        ("QUEST", "QUEST"),
        ("EXCLAIM", "EXCLAIM"),
        ("NEW_PARAGRAPH", "NEW_PARAGRAPH"),
        ("SPECIALWORD", "SPECIALWORD"),
        ("LINKRWORD", "LINKRWORD"),
        ("DOUBLCONS", "DOUBLCONS"),
        ("MAXI_PHONES", "MAXI_PHONES"),
        ("PHO_SYM_TOT", "PHO_SYM_TOT"),
    ],
)
def test_l_com_ph_matches(py_name: str, c_name: str) -> None:
    """Each ``l_com_ph.h`` ``#define`` matches our Python constant."""
    c_value = _parse_define(_l_com_ph_text(), c_name)
    assert c_value is not None, f"could not parse #define {c_name} in l_com_ph.h"
    py_value = getattr(pc, py_name)
    assert py_value == c_value, f"{py_name}={py_value} but C says {c_name}={c_value}"


# ----- l_all_ph.h US phoneme codes -----------------------------------------


@pytest.mark.parametrize(
    "phoneme",
    [m for m in pc.USPhoneme if m is not pc.USPhoneme.SIL],  # SIL is the sentinel
)
def test_us_phoneme_matches(phoneme: pc.USPhoneme) -> None:
    """Each ``USPhoneme`` enumerator matches its ``US_*`` C constant.

    ``USPhoneme.OR_`` maps to ``US_OR`` (Python keyword collision in the
    enum name only; the integer value is the source of truth).
    """
    c_name = "US_OR" if phoneme.name == "OR_" else f"US_{phoneme.name}"
    c_value = _parse_define(_l_all_ph_text(), c_name)
    assert c_value is not None, f"could not parse #define {c_name} in l_all_ph.h"
    assert phoneme.value == c_value, (
        f"USPhoneme.{phoneme.name}={phoneme.value} but C says {c_name}={c_value}"
    )


def test_us_phoneme_total_count() -> None:
    """``US_TOT_ALLOPHONES`` matches our enum size (71)."""
    expected_count = 71
    assert expected_count == pc.US_TOT_ALLOPHONES
    assert len(pc.USPhoneme) == expected_count
    # And the codes are dense 0..70:
    values = sorted(m.value for m in pc.USPhoneme)
    assert values == list(range(expected_count))


def test_pfusa_matches() -> None:
    """``PFUSA`` font code matches ``l_all_ph.h``."""
    c_value = _parse_define(_l_all_ph_text(), "PFUSA")
    assert c_value is not None
    assert c_value == pc.PFUSA


@pytest.mark.parametrize(
    ("py_attr", "c_name"),
    [
        ("PFUK", "PFUK"),
        ("PFGR", "PFGR"),
        ("PFSP", "PFSP"),
        ("PFLA", "PFLA"),
        ("PFFR", "PFFR"),
    ],
)
def test_other_language_font_codes_match(py_attr: str, c_name: str) -> None:
    """``PFUK`` / ``PFGR`` / ``PFSP`` / ``PFLA`` / ``PFFR`` match p_all_ph.h."""
    src_path = Path("/tmp/dectalk-src/src/dapi/src/ph/p_all_ph.h")
    if not src_path.exists():
        pytest.skip("C source not available")
    text = src_path.read_bytes().replace(b"\r", b"").decode("latin-1")
    c_value = _parse_define(text, c_name)
    assert c_value is not None
    assert c_value == getattr(pc, py_attr)


def test_font_codes_descend_from_us() -> None:
    """``PFUSA > PFUK > PFGR > PFSP > PFLA > PFFR``: each one byte lower."""
    fonts = [pc.PFUSA, pc.PFUK, pc.PFGR, pc.PFSP, pc.PFLA, pc.PFFR]
    for i in range(len(fonts) - 1):
        assert fonts[i] == fonts[i + 1] + 1, (
            f"font ladder break at index {i}: {fonts[i]:#x} vs {fonts[i + 1]:#x}"
        )
