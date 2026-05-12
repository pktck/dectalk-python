"""Verify ``preftab`` matches l_us_con.c byte-for-byte.

Re-parses the C ``const unsigned char preftab[]`` initialiser
(resolving ``US_*`` phoneme constants and the PCONT/P2SYL/PRCON
feature flags) and asserts the byte string matches our Python literal.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.phoneme_codes import USPhoneme
from dectalk.lts import preftab as pt

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/lts/l_us_con.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


_NAMES: dict[str, int] = {
    **{f"US_{m.name}": int(m) for m in USPhoneme},
    "US_OR": int(USPhoneme.OR_),
    "PCONT": pt.PCONT,
    "P2SYL": pt.P2SYL,
    "PRCON": pt.PRCON,
}


def _parse_byte_array(name: str) -> bytes:
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
            if re.fullmatch(r"\d+", p):
                v += int(p)
            elif p in _NAMES:
                v += _NAMES[p]
            else:
                raise ValueError(f"{name}: unknown token {p!r}")
        out.append(v)
    return bytes(out)


def test_preftab_matches_c_source() -> None:
    """Every byte of ``preftab`` matches the C source initialiser."""
    assert pt.preftab == _parse_byte_array("preftab")


def test_preftab_terminator_is_zero() -> None:
    """The C scanner stops at the final 0 byte."""
    assert pt.preftab[-1] == 0


def test_preftab_first_record_is_ab() -> None:
    """First record: ``2, US_AA, US_B`` — the AB- prefix."""
    aa = int(USPhoneme.AA)
    b = int(USPhoneme.B)
    assert pt.preftab[0] == 2  # phoneme count, no flags
    assert pt.preftab[1] == aa
    assert pt.preftab[2] == b


def test_preftab_record_sizes_walk_table() -> None:
    """Walking preftab by ``(size byte low nibble) + 1`` lands on the terminator."""
    pos = 0
    size_mask = 0x0F
    while pos < len(pt.preftab) and pt.preftab[pos] != 0:
        # The C scanner reads one byte = phoneme count (low nibble) + flags
        # (high nibble). The next ``count`` bytes are phonemes.
        count = pt.preftab[pos] & size_mask
        pos += 1 + count
    assert pos == len(pt.preftab) - 1


def test_preftab_flag_constants_are_correct() -> None:
    """Prefix flag values match ls_defs.h."""
    assert pt.PCONT == 0x10
    assert pt.PRCON == 0x20
    assert pt.P2SYL == 0x80
