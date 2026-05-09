"""Tests for the optional user-supplied lexicon (CMUDict integration)."""

from __future__ import annotations

from pathlib import Path

from dectalk.api import speak
from dectalk.dic import (
    clear_extra_lexicon,
    lookup,
    set_extra_lexicon,
)


def test_set_extra_lexicon_via_dict_takes_precedence() -> None:
    try:
        # Override "HELLO" with a different pronunciation
        set_extra_lexicon({"HELLO": ["X", "Y", "Z"]})
        assert lookup("hello") == ["X", "Y", "Z"]
    finally:
        clear_extra_lexicon()


def test_set_extra_lexicon_via_path(tmp_path: Path) -> None:
    p = tmp_path / "extra.txt"
    p.write_text("FOO F UW1\n", encoding="utf-8")
    try:
        set_extra_lexicon(p)
        assert lookup("foo") == ["F", "UW1"]
    finally:
        clear_extra_lexicon()


def test_clear_extra_lexicon_restores_bundled() -> None:
    try:
        set_extra_lexicon({"HELLO": ["Z"]})
        assert lookup("hello") == ["Z"]
        clear_extra_lexicon()
        # bundled HELLO should be back
        bundled = lookup("hello")
        assert bundled is not None
        assert bundled != ["Z"]
    finally:
        clear_extra_lexicon()


def test_extra_lexicon_does_not_break_lts_fallback() -> None:
    try:
        set_extra_lexicon({"HELLO": ["HH", "AH0", "L", "OW1"]})
        # Word still missing from any lexicon -> LTS fallback should fire.
        samples = speak("xyzzyfication")
        assert samples.size > 0
    finally:
        clear_extra_lexicon()
