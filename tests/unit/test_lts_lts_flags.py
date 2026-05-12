"""Verify LTS flag / dict-hit / homograph constants from ls_data.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.lts import lts_flags as lf

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/lts/ls_data.h")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> <int-or-hex>``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+(0[xX][0-9A-Fa-f]+|\d+)\b"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            value = match.group(1)
            return int(value, 16) if value.lower().startswith("0x") else int(value)
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("MAIN_DICT_HIT", "MAIN_DICT_HIT", 1),
        ("USER_DICT_HIT", "USER_DICT_HIT", 2),
        ("FOREIGH_DICT_HIT", "FOREIGH_DICT_HIT", 3),
        ("WORD_IS_HOMOGRAPH", "WORD_IS_HOMOGRAPH", 0x01),
        ("HOMO_PRIMARY", "HOMO_PRIMARY", 0x02),
        ("HOMO_SECONDARY", "HOMO_SECONDARY", 0x04),
        ("LTS_FLAG_DONE", "LTS_FLAG_DONE", 0x00000001),
        ("LTS_FLAG_HOMOGRAPH", "LTS_FLAG_HOMOGRAPH", 0x00000006),
        ("LTS_FLAG_IS_PHONES", "LTS_FLAG_IS_PHONES", 0x00000008),
        ("LTS_FLAG_DICT_HIT_TYPE", "LTS_FLAG_DICT_HIT_TYPE", 0x00000030),
        ("MAX_WORDS", "MAX_WORDS", 500),
    ],
)
def test_lts_constant(py_attr: str, c_name: str, expected: int) -> None:
    """Each constant matches ls_data.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert c_value == expected
    assert getattr(lf, py_attr) == expected


def test_dict_hit_codes_distinct() -> None:
    """The three dict-hit codes (MAIN / USER / FOREIGH) are 1/2/3."""
    codes = {lf.MAIN_DICT_HIT, lf.USER_DICT_HIT, lf.FOREIGH_DICT_HIT}
    assert codes == {1, 2, 3}


def test_homograph_flags() -> None:
    """``HOMO_PRIMARY | HOMO_SECONDARY`` matches the bits in LTS_FLAG_HOMOGRAPH."""
    homo_mask = lf.HOMO_PRIMARY | lf.HOMO_SECONDARY
    assert homo_mask == 0x06
    assert homo_mask == lf.LTS_FLAG_HOMOGRAPH
