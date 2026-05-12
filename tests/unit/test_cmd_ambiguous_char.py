"""Verify the ambiguous_char 15x20 table matches par_ambi.tab.

Re-parses the C ``char ambiguous_char[15][20]`` initialiser at test
time and asserts every cell matches our Python literal.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd import ambiguous_char as ac

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / (
    "src/dapi/src/cmd/par_ambi.tab"
)

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_ambiguous_char() -> tuple[tuple[int, ...], ...]:
    """Parse ``char ambiguous_char[15][20] = {{...},{...},...};``."""
    text = _C_FILE.read_text(encoding="latin-1")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*", "", text)
    m = re.search(
        r"char\s+ambiguous_char\[15\]\[20\]\s*=\s*\{(.+?)\}\s*;",
        text,
        re.DOTALL,
    )
    assert m is not None
    body = m.group(1)
    rows: list[tuple[int, ...]] = []
    for rec in re.finditer(r"\{([^{}]+)\}", body):
        vals = tuple(int(v.strip()) for v in rec.group(1).split(",") if v.strip())
        assert len(vals) == 20, f"row has {len(vals)} cells, expected 20"
        rows.append(vals)
    return tuple(rows)


def test_ambiguous_char_matches_c() -> None:
    """The 15x20 matrix matches the C source byte-for-byte."""
    assert ac.ambiguous_char == _parse_ambiguous_char()


def test_dimensions() -> None:
    """15 rows x 20 columns matches the C declaration."""
    expected_rows = 15
    expected_cols = 20
    assert len(ac.ambiguous_char) == expected_rows
    for row in ac.ambiguous_char:
        assert len(row) == expected_cols


def test_most_diagonal_entries_are_9() -> None:
    """Most self-transitions (row N, column N) yield code 9.

    Exception: row 4 (ANY_CHAR_CHAR_TYPE) maps to itself as 1 — the
    "any" type is a pass-through with no break.
    """
    expected_diagonal_value = 9
    any_char_row = 4
    any_char_diagonal = 1
    for i in range(15):
        if i == any_char_row:
            assert ac.ambiguous_char[i][i] == any_char_diagonal
        else:
            assert ac.ambiguous_char[i][i] == expected_diagonal_value


def test_column_15_always_zero() -> None:
    """Column 15 is always 0 (terminator/N/A column per the C layout)."""
    for row in ac.ambiguous_char:
        column_15_idx = 15
        assert row[column_15_idx] == 0


def test_value_codomain_is_small() -> None:
    """All values are in {0, 1, 3, 5, 9, 11, 13, 14, 15}."""
    expected = {0, 1, 3, 5, 9, 11, 13, 14, 15}
    seen = {v for row in ac.ambiguous_char for v in row}
    assert seen <= expected
