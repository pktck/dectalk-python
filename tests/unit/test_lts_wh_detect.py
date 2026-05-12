"""Verify ``is_wh_word`` parity with ls_task.c wh-word branch."""

from __future__ import annotations

import pytest

from dectalk.lts.phone_list import EOS
from dectalk.lts.structs import Letter
from dectalk.lts.wh_detect import is_wh_word


def _word(text: str) -> list[Letter]:
    """Build an EOS-terminated LETTER list."""
    return [Letter(l_ch=ord(c)) for c in text] + [Letter(l_ch=EOS)]


@pytest.mark.parametrize(
    "wh",
    ["what", "when", "where", "why", "who", "how", "which", "whose", "whom"],
)
def test_known_wh_words_match(wh: str) -> None:
    """Each canonical wh-word matches."""
    assert is_wh_word(_word(wh)) is True


def test_case_insensitive() -> None:
    """Upper-case wh-words match via ls_lower folding."""
    assert is_wh_word(_word("WHAT")) is True
    assert is_wh_word(_word("Who")) is True


def test_non_wh_words_reject() -> None:
    """Non-wh words don't match."""
    assert is_wh_word(_word("hello")) is False
    assert is_wh_word(_word("the")) is False
    assert is_wh_word(_word("is")) is False


def test_empty_word_rejects() -> None:
    """An empty word returns False."""
    assert is_wh_word([Letter(l_ch=EOS)]) is False


def test_skip_offset() -> None:
    """``skip`` offset starts the lookup later in the LETTER list."""
    # Simulate the C source's leading-LS skip: e.g. an opening quote.
    cword = _word('"what')
    # Without skip, "what doesn't match (starts with '"').
    assert is_wh_word(cword) is False
    # With skip=1, "what" inside the buffer matches.
    assert is_wh_word(cword, skip=1) is True


def test_partial_wh_no_match() -> None:
    """A prefix of a wh-word doesn't match (wlookup needs an EOS match)."""
    # "wha" is a prefix of "what" but doesn't fully match.
    assert is_wh_word(_word("wha")) is False
