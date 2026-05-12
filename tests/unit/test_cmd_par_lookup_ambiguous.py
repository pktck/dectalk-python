"""Verify ``par_lookup_ambiguous`` parity with par_pars.c.

Independent of the par_ambi.tab C source — only exercises the
already-translated :data:`ambiguous_char` table plus the bit-shift
logic from par_pars.c::par_lookup_ambiguous.
"""

from __future__ import annotations

import pytest

from dectalk.cmd import ambiguous_char as ac


def test_par_lookup_ambiguous_bit_encoding() -> None:
    """Each (from_reverse, to_reverse) combination tests a distinct bit.

    The C source's shift logic encodes:

    * (1, 1) → bit 0 (0x01)
    * (1, 0) → bit 1 (0x02)
    * (0, 1) → bit 2 (0x04)
    * (0, 0) → bit 3 (0x08)

    For an entry value of 15 (= 0x0F = all 4 low bits set), all four
    combos should return their bit unchanged.
    """
    target = 15
    for r, row in enumerate(ac.ambiguous_char):
        for c, val in enumerate(row):
            if val == target:
                assert ac.par_lookup_ambiguous(r, 1, c, 1) == 0x01
                assert ac.par_lookup_ambiguous(r, 1, c, 0) == 0x02
                assert ac.par_lookup_ambiguous(r, 0, c, 1) == 0x04
                assert ac.par_lookup_ambiguous(r, 0, c, 0) == 0x08
                return
    pytest.fail("No value-15 cell found in ambiguous_char")  # pragma: no cover


def test_par_lookup_ambiguous_zero_cell() -> None:
    """A cell with value 0 returns 0 for every direction."""
    # Cell (0,15) is 0 (terminator column per the table layout).
    for from_rev in (0, 1):
        for to_rev in (0, 1):
            assert ac.par_lookup_ambiguous(0, from_rev, 15, to_rev) == 0


def test_par_lookup_ambiguous_value_5() -> None:
    """Value 5 = 0x05 = bits 0 and 2 set → only the matching combos return >0."""
    five = 5
    assert ac.ambiguous_char[0][4] == five
    # (from=1, to=1) tests bit 0 (0x01) — present in 5 → 0x01
    assert ac.par_lookup_ambiguous(0, 1, 4, 1) == 0x01
    # (from=0, to=1) tests bit 2 (0x04) — present in 5 → 0x04
    assert ac.par_lookup_ambiguous(0, 0, 4, 1) == 0x04
    # (from=1, to=0) tests bit 1 (0x02) — NOT present in 5 → 0
    assert ac.par_lookup_ambiguous(0, 1, 4, 0) == 0
    # (from=0, to=0) tests bit 3 (0x08) — NOT present in 5 → 0
    assert ac.par_lookup_ambiguous(0, 0, 4, 0) == 0


def test_par_lookup_ambiguous_diagonal_value_9() -> None:
    """The diagonal values are 9 = 0x09 = bits 0 and 3 set."""
    nine = 9
    assert ac.ambiguous_char[0][0] == nine
    # (1,1) bit 0 → 0x01 present
    assert ac.par_lookup_ambiguous(0, 1, 0, 1) == 0x01
    # (0,0) bit 3 → 0x08 present
    assert ac.par_lookup_ambiguous(0, 0, 0, 0) == 0x08
    # (1,0) bit 1 → 0x02 NOT present
    assert ac.par_lookup_ambiguous(0, 1, 0, 0) == 0
    # (0,1) bit 2 → 0x04 NOT present
    assert ac.par_lookup_ambiguous(0, 0, 0, 1) == 0


@pytest.mark.parametrize(
    ("from_rev", "to_rev", "expected_bit"),
    [
        (1, 1, 0x01),
        (1, 0, 0x02),
        (0, 1, 0x04),
        (0, 0, 0x08),
    ],
)
def test_bit_shifts_isolate_one_bit_each(
    from_rev: int,
    to_rev: int,
    expected_bit: int,
) -> None:
    """Each direction-combo isolates exactly one of the four low bits."""
    # Synthesise a "saturated" lookup against value-15 cell.
    # Find any value-15 cell.
    target_value = 15
    for r, row in enumerate(ac.ambiguous_char):
        for c, val in enumerate(row):
            if val == target_value:
                assert ac.par_lookup_ambiguous(r, from_rev, c, to_rev) == expected_bit
                return
    pytest.fail("No value-15 cell found in ambiguous_char")  # pragma: no cover
