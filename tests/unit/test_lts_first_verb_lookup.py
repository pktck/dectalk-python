"""Verify ``ls_task_lookup_first_verbs`` parity with ls_task.c."""

from __future__ import annotations

import pytest

from dectalk.lts.first_verb_lookup import ls_task_lookup_first_verbs
from dectalk.lts.phone_list import EOS
from dectalk.lts.structs import Letter


def _word(text: str) -> list[Letter]:
    """Build an EOS-terminated LETTER list."""
    return [Letter(l_ch=ord(c)) for c in text] + [Letter(l_ch=EOS)]


@pytest.mark.parametrize("verb", ["are", "had", "is", "was", "were", "will"])
def test_known_verbs_match(verb: str) -> None:
    """Each of the 6 first-verbs matches its exact lowercase form."""
    result = ls_task_lookup_first_verbs(_word(verb))
    assert result is not None
    assert result.word == verb


def test_case_insensitive_match() -> None:
    """``ls_lower`` folds upper-case input before comparing."""
    result = ls_task_lookup_first_verbs(_word("ARE"))
    assert result is not None
    assert result.word == "are"


def test_no_match_returns_none() -> None:
    """A word not in the verb list returns None."""
    assert ls_task_lookup_first_verbs(_word("hello")) is None


def test_prefix_does_not_match() -> None:
    """A prefix of a verb (e.g. 'wa') does NOT match 'was'."""
    assert ls_task_lookup_first_verbs(_word("wa")) is None


def test_extension_does_not_match() -> None:
    """An extension of a verb (e.g. 'arent') does NOT match 'are'."""
    assert ls_task_lookup_first_verbs(_word("arent")) is None


def test_empty_word_returns_none() -> None:
    """An empty word (just EOS) returns None."""
    assert ls_task_lookup_first_verbs([Letter(l_ch=EOS)]) is None
