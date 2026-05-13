"""Verify par_copy_index / par_is_index_set match par_pars.c."""

from __future__ import annotations

from dectalk.cmd.par_index import par_copy_index, par_is_index_set
from dectalk.cmd.par_structs import IndexData


def test_par_copy_index_copies_three_values() -> None:
    """``par_copy_index`` copies all 3 ints from src to dest."""
    src = [IndexData(index=[1, 2, 3]), IndexData(index=[10, 20, 30])]
    dest = [IndexData(), IndexData()]
    par_copy_index(dest, 0, src, 1)
    assert dest[0].index == [10, 20, 30]


def test_par_copy_index_does_not_share_storage() -> None:
    """Copy is a snapshot — mutating ``src`` later doesn't affect ``dest``."""
    src = [IndexData(index=[7, 8, 9])]
    dest = [IndexData()]
    par_copy_index(dest, 0, src, 0)
    src[0].index[0] = 100
    assert dest[0].index == [7, 8, 9]


def test_par_is_index_set_zero() -> None:
    """Default IndexData (all-zero) returns False."""
    indexes = [IndexData()]
    assert par_is_index_set(indexes, 0) is False


def test_par_is_index_set_first_entry_only() -> None:
    """A non-zero first entry returns True."""
    indexes = [IndexData(index=[1, 0, 0])]
    assert par_is_index_set(indexes, 0) is True


def test_par_is_index_set_middle_entry_only() -> None:
    """A non-zero middle entry returns True."""
    indexes = [IndexData(index=[0, 5, 0])]
    assert par_is_index_set(indexes, 0) is True


def test_par_is_index_set_last_entry_only() -> None:
    """A non-zero last entry returns True."""
    indexes = [IndexData(index=[0, 0, 9])]
    assert par_is_index_set(indexes, 0) is True


def test_par_is_index_set_position_selects_record() -> None:
    """``pos`` selects which index record to probe."""
    indexes = [IndexData(), IndexData(index=[1, 0, 0]), IndexData()]
    assert par_is_index_set(indexes, 0) is False
    assert par_is_index_set(indexes, 1) is True
    assert par_is_index_set(indexes, 2) is False
