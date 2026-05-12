"""Verify ``ls_proc_do_part_number`` parity with l_us_pr1.c."""

from __future__ import annotations

from dectalk.include.phoneme_codes import WBOUND
from dectalk.lts.emitter import LtsEmitter
from dectalk.lts.part_number_emit import ls_proc_do_part_number


def test_pure_2_digit_run() -> None:
    """``42`` reads as a 2-digit number."""
    e = LtsEmitter()
    ls_proc_do_part_number(e, b"42")
    assert len(e.phones) > 0


def test_pure_3_digit_run() -> None:
    """``123`` reads as a 3-digit number."""
    e = LtsEmitter()
    ls_proc_do_part_number(e, b"123")
    assert len(e.phones) > 0


def test_pure_4_digit_run() -> None:
    """``1984`` reads as a 4-digit number (year-style or thousands)."""
    e = LtsEmitter()
    ls_proc_do_part_number(e, b"1984")
    assert len(e.phones) > 0


def test_dash_separator_emits_wbound() -> None:
    """``123-456`` has a WBOUND between the two number runs."""
    e = LtsEmitter()
    ls_proc_do_part_number(e, b"123-456")
    # Each run ends with WBOUND if followed by more.
    assert WBOUND in e.phones


def test_separator_callback_invoked() -> None:
    """A custom ``spell_separator`` callback is called for each ``-``."""
    captured: list[int] = []

    def cb(emitter: LtsEmitter, c: int) -> None:
        captured.append(c)
        # Don't emit anything

    e = LtsEmitter()
    ls_proc_do_part_number(e, b"A-B/C", spell_separator=cb)
    assert captured == [ord("-"), ord("/")]


def test_letter_run_callback_invoked() -> None:
    """A custom ``speak_letters`` callback is called for letter runs."""
    captured: list[bytes] = []

    def cb(emitter: LtsEmitter, run: bytes) -> None:
        captured.append(run)

    e = LtsEmitter()
    ls_proc_do_part_number(e, b"AB12CD", speak_letters=cb)
    # Two letter runs: AB and CD.
    assert captured == [b"AB", b"CD"]


def test_empty_input() -> None:
    """Empty input emits nothing."""
    e = LtsEmitter()
    ls_proc_do_part_number(e, b"")
    assert e.phones == []


def test_separator_only() -> None:
    """``---`` emits two WBOUNDs but no phonemes (no spell callback)."""
    e = LtsEmitter()
    ls_proc_do_part_number(e, b"---")
    # Two WBOUNDs between three separators.
    assert e.phones == [WBOUND, WBOUND]


def test_full_wrapper_spells_letters() -> None:
    """``ls_proc_do_part_number_full`` spells letter runs via ls_spel_spell."""
    from dectalk.lts.part_number_emit import ls_proc_do_part_number_full  # noqa: PLC0415

    e = LtsEmitter()
    ls_proc_do_part_number_full(e, b"X1")
    # The letter X is spelled out; digit 1 is read as 'one'. Both
    # emit phonemes — assert non-empty.
    assert len(e.phones) > 0


def test_full_emits_wbound_after_short_alpha_run() -> None:
    """``X`` is a 1-char (FAST) run — emits WBOUND after spelling X."""
    from dectalk.include.phoneme_codes import WBOUND  # noqa: PLC0415
    from dectalk.lts.part_number_emit import ls_proc_do_part_number_full  # noqa: PLC0415

    e = LtsEmitter()
    ls_proc_do_part_number_full(e, b"X")
    assert e.phones[-1] == WBOUND


def test_full_emits_comma_after_slow_alpha_run() -> None:
    """``HELLO`` is 5 letters → SLOW; emits COMMA after spelling."""
    from dectalk.include.phoneme_codes import COMMA  # noqa: PLC0415
    from dectalk.lts.part_number_emit import ls_proc_do_part_number_full  # noqa: PLC0415

    e = LtsEmitter()
    ls_proc_do_part_number_full(e, b"HELLO")
    assert e.phones[-1] == COMMA


def test_full_at_t_emits_wbound() -> None:
    """``AT&T`` is the 4-char-with-1-ampersand special case → FAST → WBOUND."""
    from dectalk.include.phoneme_codes import WBOUND  # noqa: PLC0415
    from dectalk.lts.part_number_emit import ls_proc_do_part_number_full  # noqa: PLC0415

    e = LtsEmitter()
    ls_proc_do_part_number_full(e, b"AT&T")
    assert e.phones[-1] == WBOUND
