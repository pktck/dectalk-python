"""Verify proverbs.h verb-pair and conjunction tables."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.lts import proverbs as pv

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/lts/proverbs.h")


def _parse_array_1d(text: str, name: str, count: int, hex_radix: bool) -> tuple[int, ...]:
    """Parse a 1-D ``const ... <name>[<count>] = { ... };`` literal."""
    match = re.search(
        rf"{re.escape(name)}\s*\[\s*{count}\s*\]\s*=\s*\{{(.*?)\}};",
        text,
        re.DOTALL,
    )
    assert match is not None
    body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    if hex_radix:
        return tuple(int(v, 16) for v in re.findall(r"0x[0-9A-Fa-f]+", body))
    return tuple(int(v) for v in re.findall(r"-?\d+", body))


def _parse_array_2d(text: str, name: str, rows: int, cols: int) -> tuple[tuple[int, ...], ...]:
    """Parse a 2-D ``const ... <name>[<rows>][<cols>] = { ... };`` literal."""
    match = re.search(
        rf"{re.escape(name)}\s*\[\s*{rows}\s*\]\s*\[\s*{cols}\s*\]\s*=\s*\{{(.*?)\}};",
        text,
        re.DOTALL,
    )
    assert match is not None
    body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    flat = [int(v) for v in re.findall(r"-?\d+", body)]
    assert len(flat) == rows * cols
    return tuple(tuple(flat[i : i + cols]) for i in range(0, len(flat), cols))


@pytest.fixture
def header_text() -> str:
    """De-CRLFed contents of proverbs.h."""
    if not _C_HEADER.exists():
        pytest.skip("C source not available")
    return _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")


def test_verb_pairs_index_matches_c(header_text: str) -> None:
    """All 175 hex offsets match the C source."""
    expected = _parse_array_1d(header_text, "verb_pairs_index", 175, hex_radix=True)
    assert pv.verb_pairs_index == expected


def test_verb_pairs_words_matches_c(header_text: str) -> None:
    """All 963 word bytes match the C source byte-for-byte."""
    expected = _parse_array_1d(header_text, "verb_pairs_words", 963, hex_radix=True)
    assert pv.verb_pairs_words == expected


def test_verb_pairs_cont2_matches_c(header_text: str) -> None:
    """76 cont2 rows match."""
    expected = _parse_array_2d(header_text, "verb_pairs_cont2", 76, 2)
    assert pv.verb_pairs_cont2 == expected


def test_verb_pairs_disc2_matches_c(header_text: str) -> None:
    """7 disc2 rows match."""
    expected = _parse_array_2d(header_text, "verb_pairs_disc2", 7, 2)
    assert pv.verb_pairs_disc2 == expected


def test_verb_pairs_cont3_matches_c(header_text: str) -> None:
    """7 cont3 triples match."""
    expected = _parse_array_2d(header_text, "verb_pairs_cont3", 7, 3)
    assert pv.verb_pairs_cont3 == expected


def test_verb_pairs_either_matches_c(header_text: str) -> None:
    """125 either rows match."""
    expected = _parse_array_2d(header_text, "verb_pairs_either", 125, 2)
    assert pv.verb_pairs_either == expected


def test_conj_words_matches_c(header_text: str) -> None:
    """34 conjunction 4-tuples match."""
    expected = _parse_array_2d(header_text, "conj_words", 34, 4)
    assert pv.conj_words == expected


def test_table_lengths() -> None:
    """Each table has the documented length."""
    assert len(pv.verb_pairs_index) == 175
    assert len(pv.verb_pairs_words) == 963
    assert len(pv.verb_pairs_cont2) == 76
    assert len(pv.verb_pairs_disc2) == 7
    assert len(pv.verb_pairs_cont3) == 7
    assert len(pv.verb_pairs_either) == 125
    assert len(pv.conj_words) == 34


def test_first_word_index_points_at_a() -> None:
    """``verb_pairs_index[1] = 1`` because the first word is ``"\\0a\\0"``.

    The packed buffer starts with NUL ``0x00`` then ``"a"`` ``0x61`` then
    NUL. So the index for word #1 (the article ``"a"``) is offset 1.
    """
    assert pv.verb_pairs_index[0] == 0
    assert pv.verb_pairs_words[0] == 0
    assert pv.verb_pairs_words[1] == ord("a")
    assert pv.verb_pairs_words[2] == 0
    assert pv.verb_pairs_index[1] == 1


def test_word_buffer_is_ascii() -> None:
    """All non-NUL bytes are lowercase ASCII letters."""
    for byte in pv.verb_pairs_words:
        if byte == 0:
            continue
        assert ord("a") <= byte <= ord("z"), f"non-letter byte: {byte:#x}"


def test_decoded_word_about() -> None:
    """The word starting at offset 3 spells ``"about"``."""
    start = pv.verb_pairs_index[2]
    assert start == 3
    chars: list[str] = []
    for byte in pv.verb_pairs_words[start:]:
        if byte == 0:
            break
        chars.append(chr(byte))
    assert "".join(chars) == "about"


def test_conj_words_short_rows_zero_padded() -> None:
    """Conjunction rows shorter than 4 words are padded with zero."""
    short_rows = [row for row in pv.conj_words if row[2] == 0]
    assert len(short_rows) > 0
    for row in short_rows:
        assert row[3] == 0
