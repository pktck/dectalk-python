"""Tests for the inline ``[:cmd value]`` command parser."""

from __future__ import annotations

import math

from dectalk.cmd import SpeechState, parse

# Generous epsilon for the float multiplier comparisons -- the values
# being compared are exact ratios of small ints so 1e-9 is plenty
# without inviting subnormal flakiness. Manual epsilon (avoiding
# pytest.approx for pyright strict mode, matching the project
# convention used in test_hlsyn_*_parity.py etc.).
_RATE_EPS = 1e-9


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


def test_voice_name_shortcuts() -> None:
    """``[:nX]`` shortcuts select the C command-table voices.

    Mirrors ``c_us_cde.h`` lines 403-415 (``DCS_NAME_*`` escapes ->
    ``usevoice`` speaker numbers). ``[:nw]`` is Whispery Willy — the
    public ``willy`` preset name mapping to the ``wendy`` SPDEF row
    (issue #302 cluster 3: these prompts previously fell through the
    unknown-command path and rendered as Paul).
    """
    expected = {
        "np": "paul",
        "nb": "betty",
        "nh": "harry",
        "nf": "frank",
        "nd": "dennis",
        "nk": "kit",
        "nu": "ursula",
        "nr": "rita",
        "nw": "willy",
    }
    for cmd, voice in expected.items():
        segs = parse(f"[:{cmd}] hello")
        assert segs[0].state.voice == voice, cmd


def test_voice_shortcut_mid_stream_switches_segment_voice() -> None:
    segs = parse("plain [:nr] rough part")
    assert len(segs) == 2
    assert segs[0].state.voice is None
    assert segs[1].state.voice == "rita"


def test_dv_parameter_form_does_not_set_voice() -> None:
    """``[:dv XX YY]`` design-voice params must not be read as a preset name.

    Regression for issue #241: ``[:dv ap 200]`` stored ``"ap"`` as the
    active voice, which later crashed the renderer at ``get_preset``. The
    parameter form (leading option keyword from
    :data:`dectalk.cmd.option_tables.define_options`) must leave the voice
    unchanged, while the ``[:dv NAME]`` preset form still selects a voice.
    """
    for body in ("[:dv ap 200] hi", "[:dv hs 120] hi", "[:dv sx 1] hi"):
        segs = parse(body)
        assert segs[0].state.voice is None, body
    # The preset-name form is unaffected.
    assert parse("[:dv harry] hi")[0].state.voice == "harry"


def test_rate_is_absolute_wpm() -> None:
    """``[:rate N]`` is absolute WPM (matching the C binary), not a percentage.

    Before issue #70, the parser treated N as a percentage of nominal
    (100 = nominal, 200 = half speed). The C binary instead treats N
    as absolute words-per-minute (default 180 WPM, range [75, 600]).

    The parser now translates the absolute WPM into the equivalent
    ``rate`` multiplier on :class:`SpeechState` using
    ``rate = DEFAULT_WPM / N``. With the documented DECtalk default
    of 180 WPM this gives:

    - ``[:rate 180] -> 1.0`` (nominal, identical to no directive)
    - ``[:rate 90]  -> 2.0`` (half-speed)
    - ``[:rate 360] -> 0.5`` (double-speed)
    """
    # Nominal: 180 WPM == default == multiplier 1.0
    segs = parse("[:rate 180] hello")
    assert math.isclose(segs[0].state.rate, 1.0, abs_tol=_RATE_EPS)

    # Half-speed: 90 WPM → multiplier 2.0 (each phoneme stretched 2x).
    segs = parse("[:rate 90] hello")
    assert math.isclose(segs[0].state.rate, 2.0, abs_tol=_RATE_EPS)

    # Double-speed: 360 WPM → multiplier 0.5 (each phoneme halved).
    segs = parse("[:rate 360] hello")
    assert math.isclose(segs[0].state.rate, 0.5, abs_tol=_RATE_EPS)

    # The headline case from issue #70: 250 WPM is ~28% faster than
    # default. ``rate = 180/250 = 0.72``.
    segs = parse("[:rate 250] testing one two three")
    assert math.isclose(segs[0].state.rate, 180.0 / 250.0, abs_tol=_RATE_EPS)


def test_rate_clamps_out_of_range_to_legal_wpm() -> None:
    """Out-of-range WPM is clamped to [75, 600] before conversion.

    Matches the C binary's MIN_SPEAKING_RATE / MAX_SPEAKING_RATE
    behaviour (see :mod:`dectalk.cmd.cmd_states`).
    """
    # Below 75 WPM → clamped to 75 → multiplier 180/75 = 2.4
    segs = parse("[:rate 10] hello")
    assert math.isclose(segs[0].state.rate, 180.0 / 75.0, abs_tol=_RATE_EPS)

    # Above 600 WPM → clamped to 600 → multiplier 180/600 = 0.3
    segs = parse("[:rate 1000] hello")
    assert math.isclose(segs[0].state.rate, 180.0 / 600.0, abs_tol=_RATE_EPS)


def test_rate_composes_multiplicatively_with_initial_state() -> None:
    """An inline ``[:rate N]`` multiplies any caller-supplied rate.

    The caller may pass ``initial_state`` with a non-1.0 rate (e.g.
    the public API's ``speak(rate=...)`` arg threads through this).
    The inline directive should compose multiplicatively rather than
    overwrite, so a ``rate=0.5`` caller passing
    ``[:rate 360] hello`` ends up with multiplier 0.25 (4x speed).
    """
    initial = SpeechState(rate=0.5)
    segs = parse("[:rate 360] hello", initial_state=initial)
    # 360 WPM → 180/360 = 0.5, composed with the 0.5 initial = 0.25.
    assert math.isclose(segs[0].state.rate, 0.25, abs_tol=_RATE_EPS)


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
    # 90 WPM is half the default 180 → multiplier 2.0 (twice as slow).
    segs = parse("[:dv harry][:rate 90] hello")
    assert len(segs) == 1
    assert segs[0].state.voice == "harry"
    assert math.isclose(segs[0].state.rate, 2.0, abs_tol=_RATE_EPS)


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
