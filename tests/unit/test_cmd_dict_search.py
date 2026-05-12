"""Verify ``par_dict_where_to_look`` parity with par_dict.c.

The C function is a 3-way comparator wrapped to return one of two
codes — LOOK_HIGHER (target ≥ entry) or LOOK_LOWER (target < entry).
We replay the same algorithm against handcrafted test cases.
"""

from __future__ import annotations

import pytest

from dectalk.cmd import dict_search as ds


def test_constants() -> None:
    """LOOK_HIGHER / LOOK_LOWER match the C source #defines."""
    expected_higher = 0xFFFF
    expected_lower = 0xFFFE
    assert expected_higher == ds.LOOK_HIGHER
    assert expected_lower == ds.LOOK_LOWER


def test_exact_match_returns_higher() -> None:
    """Both strings ended at the same length → LOOK_HIGHER (search terminates)."""
    assert ds.par_dict_where_to_look(b"hello", b"hello") == ds.LOOK_HIGHER


def test_case_insensitive_match() -> None:
    """The comparator folds both inputs to upper-case before comparing."""
    assert ds.par_dict_where_to_look(b"HELLO", b"hello") == ds.LOOK_HIGHER
    assert ds.par_dict_where_to_look(b"hello", b"HELLO") == ds.LOOK_HIGHER
    assert ds.par_dict_where_to_look(b"HeLLo", b"hEllO") == ds.LOOK_HIGHER


def test_word_greater_than_entry() -> None:
    """If the word sorts greater (case-insensitive), return LOOK_HIGHER."""
    assert ds.par_dict_where_to_look(b"apple", b"banana") == ds.LOOK_HIGHER
    assert ds.par_dict_where_to_look(b"ant", b"and") == ds.LOOK_LOWER  # 't' < (no upper match)
    # 'apple' < 'banana' alphabetically; word='banana' > entry='apple' → HIGHER.


def test_word_less_than_entry() -> None:
    """If the word sorts less, return LOOK_LOWER."""
    assert ds.par_dict_where_to_look(b"banana", b"apple") == ds.LOOK_LOWER


def test_prefix_matches() -> None:
    """The C source treats 'word ends first' as 'word < entry' → LOOK_LOWER."""
    # word='hel' ends at 3; entry='hello' still has 'lo' — word ended,
    # entry didn't → pivot_char = 'L' from entry, word_byte = 0 → 0 < 'L' → LOOK_LOWER.
    assert ds.par_dict_where_to_look(b"hello", b"hel") == ds.LOOK_LOWER


def test_entry_is_prefix_of_word() -> None:
    """Entry ends first, word has more — word > entry → LOOK_HIGHER."""
    # entry='hel', word='hello' — pivot_char becomes 0 when entry runs out
    # at i=3; word[3]='l' → 'L' > 0 → LOOK_HIGHER.
    assert ds.par_dict_where_to_look(b"hel", b"hello") == ds.LOOK_HIGHER


@pytest.mark.parametrize(
    ("entry", "word", "expected"),
    [
        (b"banana", b"apple", "LOWER"),
        (b"apple", b"banana", "HIGHER"),
        (b"cat", b"cat", "HIGHER"),  # exact match
        (b"cat", b"car", "LOWER"),  # 't' > 'r' but word='car' < 'cat'
        (b"car", b"cat", "HIGHER"),
        (b"zebra", b"aardvark", "LOWER"),
    ],
)
def test_alphabetical_comparison(entry: bytes, word: bytes, expected: str) -> None:
    """The comparator implements case-insensitive alphabetical order."""
    code = ds.par_dict_where_to_look(entry, word)
    if expected == "HIGHER":
        assert code == ds.LOOK_HIGHER
    else:
        assert code == ds.LOOK_LOWER
