"""Verify ``nabtab`` and ``nwdtab`` match l_us_con.c byte-for-byte.

Re-parses the C initialisers (resolving the symbolic ``US_*`` /
``S1`` / ``EOS`` / ``SIL`` / ``MBOUND`` constants to numbers) and
asserts the byte string matches our Python literal exactly.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.phoneme_codes import (
    BLOCK_RULES,
    COMMA,
    EXCLAIM,
    HAT_FALL,
    HAT_RF,
    HAT_RISE,
    HYPHEN,
    MBOUND,
    NEW_PARAGRAPH,
    PERIOD,
    PPSTART,
    QUEST,
    RELSTART,
    S1,
    S2,
    SBOUND,
    SEMPH,
    SPECIALWORD,
    VPSTART,
    WBOUND,
    USPhoneme,
)
from dectalk.lts import number_tables as nt

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/lts/l_us_con.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


_NAMES: dict[str, int] = {
    **{f"US_{m.name}": int(m) for m in USPhoneme},
    "US_OR": int(USPhoneme.OR_),
    "S1": S1, "S2": S2, "SEMPH": SEMPH, "SIL": 0, "EOS": 0,
    "BLOCK_RULES": BLOCK_RULES, "HAT_RISE": HAT_RISE,
    "HAT_FALL": HAT_FALL, "HAT_RF": HAT_RF,
    "SBOUND": SBOUND, "MBOUND": MBOUND, "HYPHEN": HYPHEN, "WBOUND": WBOUND,
    "PPSTART": PPSTART, "VPSTART": VPSTART, "RELSTART": RELSTART,
    "COMMA": COMMA, "PERIOD": PERIOD, "QUEST": QUEST, "EXCLAIM": EXCLAIM,
    "NEW_PARAGRAPH": NEW_PARAGRAPH, "SPECIALWORD": SPECIALWORD,
}  # fmt: skip


def _parse_byte_array(name: str) -> bytes:
    """Parse ``const unsigned char NAME[] = { ... };`` from l_us_con.c."""
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(
        rf"const\s+unsigned\s+char\s+{re.escape(name)}\s*\[\]\s*=\s*\{{(.*?)\}};",
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


def test_nabtab_matches_c_source() -> None:
    """Every byte of ``nabtab`` matches the C source initialiser."""
    assert nt.nabtab == _parse_byte_array("nabtab")


def test_nwdtab_matches_c_source() -> None:
    """Every byte of ``nwdtab`` matches the C source initialiser."""
    assert nt.nwdtab == _parse_byte_array("nwdtab")


def test_nabtab_terminator_is_zero() -> None:
    """The C scanner stops at the final 0 byte."""
    assert nt.nabtab[-1] == 0


def test_nwdtab_terminator_is_zero() -> None:
    """Same: 0-byte terminator at end of records."""
    assert nt.nwdtab[-1] == 0


def test_nabtab_first_record_is_cm() -> None:
    """The first record should be ``28, 'c', 'm', EOS, …``."""
    # First byte = total record length (28). Then 'c'=0x63, 'm'=0x6D, EOS=0.
    assert nt.nabtab[0] == 28
    assert nt.nabtab[1] == ord("c")
    assert nt.nabtab[2] == ord("m")
    assert nt.nabtab[3] == 0


def test_nwdtab_first_record_is_hundred() -> None:
    """The first record should be ``17, 'h', 'u', 'n', 'd', 'r', 'e', 'd', EOS, …``."""
    # Total length 17, then "hundred", then EOS.
    assert nt.nwdtab[0] == 17
    assert bytes(nt.nwdtab[1:8]) == b"hundred"
    assert nt.nwdtab[8] == 0


def test_nabtab_record_sizes_walk_table() -> None:
    """Walking nabtab by ``1 + size`` should reach the final terminator.

    The C convention: the size byte counts the *payload* (name + EOS +
    singular-phonemes + SIL + plural-phonemes + SIL) but not itself, so
    the stride between successive size bytes is ``1 + size``.
    """
    pos = 0
    while pos < len(nt.nabtab) and nt.nabtab[pos] != 0:
        pos += 1 + nt.nabtab[pos]
    # We must land exactly on the 0 terminator.
    assert pos == len(nt.nabtab) - 1
    assert nt.nabtab[pos] == 0


def test_nwdtab_record_sizes_walk_table() -> None:
    """Walking nwdtab by ``1 + size`` should reach the final terminator."""
    pos = 0
    while pos < len(nt.nwdtab) and nt.nwdtab[pos] != 0:
        pos += 1 + nt.nwdtab[pos]
    assert pos == len(nt.nwdtab) - 1
    assert nt.nwdtab[pos] == 0
