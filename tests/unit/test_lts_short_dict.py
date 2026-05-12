"""Verify ``sdic`` and ``whdic`` match l_us_con.c byte-for-byte.

Re-parses the C initialisers (resolving ``US_*`` phoneme constants,
``SPECIALWORD``, ``PPSTART``, ``EOS``, ``SIL``) and asserts each
byte string matches our Python literal.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.phoneme_codes import (
    PPSTART,
    SPECIALWORD,
    USPhoneme,
)
from dectalk.lts import short_dict as sd

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/lts/l_us_con.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


_NAMES: dict[str, int] = {
    **{f"US_{m.name}": int(m) for m in USPhoneme},
    "US_OR": int(USPhoneme.OR_),
    "SIL": 0,
    "EOS": 0,
    "SPECIALWORD": SPECIALWORD,
    "PPSTART": PPSTART,
}


def _parse_byte_array(name: str) -> bytes:
    """Parse ``const unsigned char NAME[] = { ... };`` from l_us_con.c."""
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(
        rf"const\s+unsigned\s+char\s+{re.escape(name)}\[\]\s*=\s*\{{(.*?)\}};",
        text,
        re.DOTALL,
    )
    assert m is not None, f"could not find {name} in l_us_con.c"
    body = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    out: list[int] = []
    for raw in body.split(","):
        tok = raw.strip()
        if not tok:
            continue
        v = 0
        for part in re.split(r"\s*\+\s*", tok):
            p = part.strip()
            if p.startswith("'") and p.endswith("'"):
                v += ord(p[1:-1])
            elif re.fullmatch(r"\d+", p):
                v += int(p)
            elif p in _NAMES:
                v += _NAMES[p]
            else:
                raise ValueError(f"{name}: unknown token {p!r}")
        out.append(v)
    return bytes(out)


def test_sdic_matches_c_source() -> None:
    """``sdic`` matches the C source initialiser byte-for-byte."""
    assert sd.sdic == _parse_byte_array("sdic")


def test_whdic_matches_c_source() -> None:
    """``whdic`` matches the C source initialiser byte-for-byte."""
    assert sd.whdic == _parse_byte_array("whdic")


def test_sdic_records_walk_to_terminator() -> None:
    """Walking sdic by ``1 + size`` lands on the final 0 terminator."""
    pos = 0
    while pos < len(sd.sdic) and sd.sdic[pos] != 0:
        pos += 1 + sd.sdic[pos]
    assert pos == len(sd.sdic) - 1


def test_sdic_first_record_is_for() -> None:
    """First sdic record should be ``9, 'f','o','r', EOS, SPECIALWORD, PPSTART, …``."""
    assert sd.sdic[0] == 9
    assert bytes(sd.sdic[1:4]) == b"for"
    assert sd.sdic[4] == 0  # EOS
    assert sd.sdic[5] == SPECIALWORD
    assert sd.sdic[6] == PPSTART


def test_whdic_records_walk_to_terminator() -> None:
    """Walking whdic by ``1 + size`` lands on the final 0 terminator."""
    pos = 0
    while pos < len(sd.whdic) and sd.whdic[pos] != 0:
        pos += 1 + sd.whdic[pos]
    assert pos == len(sd.whdic) - 1


def test_whdic_first_record_is_what() -> None:
    """First whdic record is ``6, 'w','h','a','t', EOS, SIL``."""
    assert sd.whdic[0] == 6
    assert bytes(sd.whdic[1:5]) == b"what"
    assert sd.whdic[5] == 0  # EOS
    assert sd.whdic[6] == 0  # SIL


def test_whdic_contains_canonical_wh_words() -> None:
    """All nine wh-words (what/when/where/why/who/how/which/whose/whom) appear."""
    blob = bytes(sd.whdic)
    for word in (b"what", b"when", b"where", b"why", b"who", b"how", b"which", b"whose", b"whom"):
        assert word in blob, f"missing {word!r}"
