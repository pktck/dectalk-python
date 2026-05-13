"""C-source parity test for ``par_find_word_in_dict`` against par_pars1.c.

Asserts the recursive trie-walk body is preserved -- the dispatch
on ``NOUN_UNUSED_ENTRY`` / ``head == 0`` / ``word_ending`` flags
and the two tail recursions -- plus the Python port returns
``0`` (no match) on the US-English build because the German
compound dictionary is never populated.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_find_word_in_dict import par_find_word_in_dict

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_pars1.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_par_pars1_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_par_pars1_c()
    match = re.search(
        r"int\s+par_find_word_in_dict\s*\([^;{]+?\)\s*\n\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "par_find_word_in_dict body not found"
    return match.group(1)


def test_checks_noun_unused_entry_sentinel() -> None:
    """The C body's first dispatch is ``if (head == NOUN_UNUSED_ENTRY)``."""
    body = _extract_body()
    assert re.search(r"if\s*\(\s*head\s*==\s*NOUN_UNUSED_ENTRY\s*\)", body)


def test_checks_head_equals_zero_terminal() -> None:
    """The C body has the terminal ``if (head == 0)`` branch."""
    body = _extract_body()
    assert re.search(r"if\s*\(\s*head\s*==\s*0\s*\)", body)


def test_uses_word_ending_mask() -> None:
    """The C body branches on ``cur->word_ending & 1``, ``& 2`` and ``& 4``."""
    body = _extract_body()
    assert re.search(r"cur\s*->\s*word_ending\s*&\s*1", body)
    assert re.search(r"cur\s*->\s*word_ending\s*&\s*2", body)
    assert re.search(r"cur\s*->\s*word_ending\s*&\s*4", body)


def test_recurses_on_self() -> None:
    """The C body has at least two recursive ``par_find_word_in_dict`` calls."""
    body = _extract_body()
    assert len(re.findall(r"par_find_word_in_dict\s*\(", body)) >= 2


def test_indexes_noun_character_mapping_table() -> None:
    """The dispatch uses ``noun_character_mapping_table[word[0]]``."""
    body = _extract_body()
    assert re.search(
        r"noun_character_mapping_table\s*\[\s*word\s*\[\s*0\s*\]\s*\]",
        body,
    )


def test_us_build_compound_dict_dummy_has_unused_entries() -> None:
    """``comp_dum.h`` (linked on US English) sets every mapping to -1."""
    comp_dum = (
        Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/comp_dum.h"
    )
    if not comp_dum.is_file():
        pytest.skip("comp_dum.h not available")
    text = comp_dum.read_bytes().replace(b"\r", b"").decode("latin-1")
    # Every line of the mapping table is just ``-1,``.
    assert "noun_num_character_in_mapping = 0" in text
    # The mapping table itself: count of -1 entries should match the
    # 256-entry array (give or take comments).
    assert text.count("-1,") >= 255


def test_python_returns_zero_on_us_build() -> None:
    """The Python stub returns 0 because the compound dict is empty."""
    positions: list[int] = [0] * 10
    num_pos = [0]
    assert par_find_word_in_dict(1, b"compound", positions, 0, num_pos) == 0


def test_python_does_not_mutate_positions() -> None:
    """The stub does not write into ``positions`` or ``num_pos``."""
    positions: list[int] = [0] * 10
    num_pos = [0]
    par_find_word_in_dict(1, b"hello", positions, 0, num_pos)
    assert positions == [0] * 10
    assert num_pos == [0]
