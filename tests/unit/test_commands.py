"""Tests for the inline ``[:cmd value]`` command parser."""

from __future__ import annotations

from dectalk.cmd import SpeechState, parse


def test_no_commands_returns_single_segment() -> None:
    segs = parse("hello world")
    assert len(segs) == 1
    assert segs[0].body == "hello world"
    assert segs[0].state == SpeechState()


def test_dv_changes_voice() -> None:
    segs = parse("[:dv harry] hello")
    assert len(segs) == 1
    assert segs[0].state.voice == "harry"


def test_name_alias_for_dv() -> None:
    segs = parse("[:name betty] hi")
    assert segs[0].state.voice == "betty"


def test_rate_percentage_to_multiplier() -> None:
    segs = parse("[:rate 200] hello")
    assert segs[0].state.rate == 2.0
    segs = parse("[:rate 50] hello")
    assert segs[0].state.rate == 0.5


def test_invalid_rate_value_is_ignored() -> None:
    segs = parse("[:rate notnumeric] hi")
    assert segs[0].state.rate == 1.0  # unchanged from default


def test_phoneme_mode_toggle() -> None:
    segs = parse("hello [:phoneme on] HH AH L OW [:phoneme off] world")
    # Three segments: text "hello", phoneme stream, text "world"
    assert len(segs) == 3
    assert segs[0].body.strip() == "hello"
    assert not segs[0].state.phoneme_mode
    assert segs[1].state.phoneme_mode
    assert "HH AH L OW" in segs[1].body
    assert not segs[2].state.phoneme_mode


def test_back_to_back_commands_collapse() -> None:
    """Consecutive [:cmd] directives shouldn't generate empty segments."""
    segs = parse("[:dv harry][:rate 200] hello")
    assert len(segs) == 1
    assert segs[0].state.voice == "harry"
    assert segs[0].state.rate == 2.0


def test_initial_state_seeds_first_segment() -> None:
    initial = SpeechState(voice="betty", rate=0.5)
    segs = parse("hello world", initial_state=initial)
    assert segs[0].state == initial


def test_unknown_command_passes_through() -> None:
    """Unrecognised commands should be silently dropped, not crash."""
    segs = parse("[:bogus xxx] hello")
    assert len(segs) == 1
    assert segs[0].body.strip() == "hello"
    assert segs[0].state == SpeechState()  # state unchanged


def test_empty_input() -> None:
    assert parse("") == []
    assert parse("[:dv harry]") == []  # only a command -> no body segment
