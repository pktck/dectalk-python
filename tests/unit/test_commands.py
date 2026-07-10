"""Tests for the inline ``[:cmd value]`` command parser."""

from __future__ import annotations

import math

from dectalk.cmd import SpeechState, parse
from dectalk.cmd.cmd_states import PHONEME_ASCKY, PHONEME_OFF, PHONEME_SPEAK

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
    # ``[:phoneme ...]`` mutates the C ``pKsd_t->phoneme_mode`` bitfield
    # (default ``PHONEME_OFF | PHONEME_SPEAK``); it never turns a segment
    # body into phonemes. ``[:phoneme on]`` clears PHONEME_OFF; ``off``
    # sets it again (issue #248; ``cmd/cm_copt.c`` ``cm_cmd_phoneme``).
    segs = parse("hello [:phoneme on] HH AH L OW [:phoneme off] world")
    assert len(segs) == 3
    assert segs[0].body.strip() == "hello"
    assert segs[0].state.phoneme_mode == PHONEME_OFF | PHONEME_SPEAK  # default
    assert segs[1].state.phoneme_mode == PHONEME_SPEAK  # PHONEME_OFF cleared
    assert "HH AH L OW" in segs[1].body  # body stays plain text, not consumed
    assert segs[2].state.phoneme_mode == PHONEME_OFF | PHONEME_SPEAK  # off re-sets


def test_phoneme_submatrix_bitfield() -> None:
    """Every ``[:phoneme <kw>]`` maps to the exact bit op in cm_copt.c:238-260."""

    def mode_after(cmd: str) -> int:
        return parse(f"[:phoneme {cmd}] x")[0].state.phoneme_mode

    default = PHONEME_OFF | PHONEME_SPEAK
    assert mode_after("on") == PHONEME_SPEAK  # clear OFF
    assert mode_after("off") == default  # set OFF (already set) -> no change
    assert mode_after("asky") == default | PHONEME_ASCKY  # set ASCKY
    assert mode_after("arpabet") == default  # clear ASCKY (already clear)
    assert mode_after("silent") == PHONEME_OFF  # clear SPEAK
    assert mode_after("speak") == default  # set SPEAK (already set)
    # Multiple keywords accumulate left-to-right, like the C for-loop.
    assert mode_after("arpabet on") == PHONEME_SPEAK  # arpabet no-op, on clears OFF
    assert mode_after("asky on") == PHONEME_SPEAK | PHONEME_ASCKY


def test_phoneme_unknown_keyword_stops_like_c() -> None:
    # C's cm_cmd_phoneme returns CMD_bad_string on an unknown keyword and
    # stops, keeping bits applied by earlier keywords (cm_copt.c:234-236).
    # ``dectalk`` is NOT a valid keyword -- the DECtalk-alphabet keyword is
    # ``asky`` (the empirical oracle even speaks a "command error" message
    # for ``[:phoneme dectalk on]``, which we don't model).
    assert parse("[:phoneme dectalk on] x")[0].state.phoneme_mode == PHONEME_OFF | PHONEME_SPEAK
    # A valid keyword before the bad one is kept; the bad one halts the rest.
    assert parse("[:phoneme silent bogus speak] x")[0].state.phoneme_mode == PHONEME_OFF


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


def test_comma_pause_recorded_unclamped() -> None:
    """``[:comma N]`` records the raw ms value (issue #249).

    The C ``cm_cmd_comma`` (cm_copt.c lines 2486-2502) forwards the
    value unclamped; the PH consumer applies its own deadstop. The
    two-letter ``cp`` alias maps to the same handler (c_us_cde.h
    line 418).
    """
    segs = parse("[:comma 1000] a, b")
    assert segs[0].state.comma_pause == 1000
    segs = parse("[:cp -500] a, b")
    assert segs[0].state.comma_pause == -500
    # Out-of-range values are NOT clamped at the command layer --
    # they wrap through the 16-bit LTS pipe on the way to PH.
    segs = parse("[:comma 45000] a, b")
    assert segs[0].state.comma_pause == 45000


def test_period_pause_clamped_at_command_layer() -> None:
    """``[:period N]`` clamps to [-420, 30000] (issue #249).

    Mirrors ``cm_cmd_period`` (cm_copt.c lines 2526-2530, the
    BTS#10100 fix): the clamp happens at the command layer, before
    the 16-bit pipe. The ``pp`` alias maps to the same handler.
    """
    segs = parse("[:period 2000] a. b")
    assert segs[0].state.period_pause == 2000
    segs = parse("[:pp 90000] a. b")
    assert segs[0].state.period_pause == 30000
    segs = parse("[:period -1000] a. b")
    assert segs[0].state.period_pause == -420


def test_pause_commands_persist_and_ignore_bad_args() -> None:
    """Pause state persists across segments; bad args leave it unset."""
    segs = parse("[:comma 700] a, b [:dv harry] c, d")
    assert all(s.state.comma_pause == 700 for s in segs)
    for bad in ("[:comma] x", "[:comma abc] x", "[:period] x", "[:period xyz] x"):
        segs = parse(bad)
        assert segs[0].state.comma_pause is None
        assert segs[0].state.period_pause is None
