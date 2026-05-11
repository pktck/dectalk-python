"""Verify the LTS suffix tables match ``l_us_suf.c`` byte-for-byte.

Re-parses ``suffix_index`` (27 U32 entries) and ``suffix_table``
(5988 bytes of opaque suffix-rule records) from the C source at
test time and asserts every value matches our Python literal.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.lts import suffix_data as sd

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/lts/l_us_suf.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_suffix_index() -> tuple[int, ...]:
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(r"const\s+U32\s+suffix_index\[\]\s*=\s*\{(.*?)\};", text, re.DOTALL)
    assert m is not None
    return tuple(int(x, 16) for x in re.findall(r"0x[0-9a-fA-F]+", m.group(1)))


def _parse_suffix_table() -> bytes:
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(
        r"const\s+unsigned\s+char\s+suffix_table\[\]\s*=\s*\{(.*?)\};",
        text,
        re.DOTALL,
    )
    assert m is not None
    return bytes(int(x, 16) for x in re.findall(r"0x[0-9a-fA-F]+", m.group(1)))


def test_suffix_index_matches_c_source() -> None:
    """Every entry in suffix_index matches the C ``const U32`` declaration."""
    expected = _parse_suffix_index()
    assert sd.suffix_index == expected


def test_suffix_index_has_27_entries() -> None:
    """The C source declares 27 entries (26 letters + 1 trailing slot)."""
    expected_count = 27
    assert len(sd.suffix_index) == expected_count


def test_suffix_table_matches_c_source() -> None:
    """All 5988 bytes of suffix_table match the C source exactly."""
    expected = _parse_suffix_table()
    assert sd.suffix_table == expected


def test_suffix_table_size_documented() -> None:
    """The C source declares 5988 bytes (encoded in the module assertion)."""
    expected_size = 5988
    assert len(sd.suffix_table) == expected_size


def test_suffix_index_offsets_are_in_range() -> None:
    """Every non-FFFF offset points within the table (sanity for downstream
    consumers — a malformed offset would walk past the table end)."""
    sentinel = 0xFFFF
    for letter_idx, offset in enumerate(sd.suffix_index):
        if offset == sentinel:
            continue
        assert offset < len(sd.suffix_table), (
            f"suffix_index[{letter_idx}]={offset:#x} exceeds table size {len(sd.suffix_table)}"
        )
