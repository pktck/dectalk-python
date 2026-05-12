"""Verify the par_def.h rule-engine constants in cmd.rule_states."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.cmd import rule_states as rs

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/cmd/par_def.h")


def _parse_define(name: str) -> str | None:
    """Return the RHS of a single ``#define <name> <value>`` in par_def.h."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+(.+?)\s*(?:/\*.*|//.*)?$"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            return match.group(1).strip()
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("FAIL", "FAIL", 0),
        ("SUCCESS", "SUCCESS", 1),
        ("OPT_FAIL", "OPT_FAIL", 2),
        ("END_OF_STRING", "END_OF_STRING", 3),
        ("FATAL_FAIL", "FATAL_FAIL", 4),
        ("STOP", "STOP", 5),
    ],
)
def test_rule_return_codes_match_c_source(
    py_attr: str,
    c_name: str,
    expected: int,
) -> None:
    """FAIL / SUCCESS / OPT_FAIL / END_OF_STRING / FATAL_FAIL / STOP."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert int(c_value) == expected
    assert getattr(rs, py_attr) == expected


def test_end_is_slash_paren_null() -> None:
    """End-of-section markers match par_def.h."""
    assert rs.End_Is_Slash == ord("/")
    assert rs.End_Is_Paren == ord(")")
    assert rs.End_Is_Null == 0


def test_return_codes_form_dense_set() -> None:
    """Six return codes 0..5 — dense, no gaps."""
    codes = {
        rs.FAIL,
        rs.SUCCESS,
        rs.OPT_FAIL,
        rs.END_OF_STRING,
        rs.FATAL_FAIL,
        rs.STOP,
    }
    assert codes == {0, 1, 2, 3, 4, 5}


# -- Extended par_def.h constants -----------------------------------------


@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("NORMAL_TAG_VALUE", "NORMAL_TAG_VALUE", 0),
        ("STOP_TAG_VALUE", "STOP_TAG_VALUE", 1),
        ("RETURN_TAG_VALUE", "RETURN_TAG_VALUE", 2),
        ("GOTO_TAG_VALUE", "GOTO_TAG_VALUE", 3),
        ("GORET_TAG_VALUE", "GORET_TAG_VALUE", 4),
        ("DICT_HIT_VALUE", "DICT_HIT_VALUE", 1),
        ("DICT_MISS_VALUE", "DICT_MISS_VALUE", 0),
        ("UNSET_PARAM", "UNSET_PARAM", -1),
        ("NORMAL_TO_NORMAL", "NORMAL_TO_NORMAL", 0x01),
        ("NORMAL_TO_REVERSE", "NORMAL_TO_REVERSE", 0x02),
        ("REVERSE_TO_NORMAL", "REVERSE_TO_NORMAL", 0x04),
        ("REVERSE_TO_REVERSE", "REVERSE_TO_REVERSE", 0x08),
        ("PAR_OUTPUT_CHARS", "PAR_OUTPUT_CHARS", 1),
        ("PAR_OUTPUT_PHONES", "PAR_OUTPUT_PHONES", 2),
        ("PAR_PHONES_ON_D", "PAR_PHONES_ON_D", 0x81),
        ("PAR_PHONES_OFF_D", "PAR_PHONES_OFF_D", 0x82),
        ("PAR_INDEX_DUMMY_CHAR", "PAR_INDEX_DUMMY_CHAR", 0x83),
    ],
)
def test_extended_par_def_constants(
    py_attr: str,
    c_name: str,
    expected: int,
) -> None:
    """Each extended constant matches par_def.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    parsed = int(c_value, 16) if c_value.lower().startswith("0x") else int(c_value)
    assert parsed == expected
    assert getattr(rs, py_attr) == expected


def test_tag_values_form_dense_set() -> None:
    """The 5 special-tag values are dense 0..4."""
    tags = {
        rs.NORMAL_TAG_VALUE,
        rs.STOP_TAG_VALUE,
        rs.RETURN_TAG_VALUE,
        rs.GOTO_TAG_VALUE,
        rs.GORET_TAG_VALUE,
    }
    assert tags == {0, 1, 2, 3, 4}


def test_dict_value_pair() -> None:
    """DICT_HIT_VALUE / DICT_MISS_VALUE are complementary booleans."""
    assert rs.DICT_HIT_VALUE != rs.DICT_MISS_VALUE
    assert rs.DICT_HIT_VALUE == 1
    assert rs.DICT_MISS_VALUE == 0


def test_orientation_flags_are_distinct_bits() -> None:
    """The 4 orientation flags are single-bit and distinct."""
    flags = (
        rs.NORMAL_TO_NORMAL,
        rs.NORMAL_TO_REVERSE,
        rs.REVERSE_TO_NORMAL,
        rs.REVERSE_TO_REVERSE,
    )
    for flag in flags:
        assert flag > 0
        assert flag & (flag - 1) == 0
    assert len(set(flags)) == 4


def test_all_to_all_covers_all_four() -> None:
    """``ALL_TO_ALL`` is the OR of all four orientation flags."""
    assert rs.ALL_TO_ALL == (
        rs.NORMAL_TO_NORMAL | rs.NORMAL_TO_REVERSE | rs.REVERSE_TO_NORMAL | rs.REVERSE_TO_REVERSE
    )


def test_all_to_normal_omits_reverse_targets() -> None:
    """``ALL_TO_NORMAL`` covers only NORMAL_TO_NORMAL + REVERSE_TO_NORMAL."""
    assert rs.ALL_TO_NORMAL == (rs.NORMAL_TO_NORMAL | rs.REVERSE_TO_NORMAL)


def test_save_state_pair() -> None:
    """START_SAVE_STATE ``(`` and END_SAVE_STATE ``)`` mirror each other."""
    assert ord("(") == rs.START_SAVE_STATE
    assert ord(")") == rs.END_SAVE_STATE


def test_dictionary_aliases() -> None:
    """``DICTIONARY_HIT`` aliases ``HIT_NUMBER_DELIM`` and likewise for MISS."""
    assert rs.DICTIONARY_HIT == rs.HIT_NUMBER_DELIM
    assert rs.DICTIONARY_MISS == rs.MISS_NUMBER_DELIM
