"""Inline DECtalk command parser for ``[:cmd value]`` syntax.

DECtalk's text input may interleave control commands with the text to be
spoken. Commands change synthesizer state — the active voice, speaking
rate, average pitch, phoneme-direct mode, etc. — and persist until
overridden.

Supported commands (subset of the full DECtalk command vocabulary):

- ``[:dv NAME]`` — design voice. ``NAME`` is one of the canonical voice
  short names (``paul``, ``betty``, ``harry``, ``frank``, ``dennis``,
  ``kit``, ``ursula``, ``rita``, ``willy``).
- ``[:name NAME]`` — alias for ``[:dv]`` accepted by older DECtalk versions.
- ``[:rate N]`` — speaking rate in absolute words-per-minute, matching
  the DECtalk binary's semantics (default 180 WPM; legal range
  [75, 600], clamped). Translated into the equivalent multiplicative
  ``rate`` on :class:`SpeechState` so downstream renderers can combine
  it with any public-API ``rate=`` multiplier.
- ``[:comma N]`` / ``[:cp N]`` — extra comma-boundary pause in
  milliseconds (issue #249). Recorded on :class:`SpeechState`; the
  full-pipeline renderer threads it into ``DphT.compause`` exactly as
  the C ``CPAUSE`` control word does (``ph_task.c`` line 785).
- ``[:period N]`` / ``[:pp N]`` — extra period-boundary pause in
  milliseconds, clamped to [-420, 30000] at the command layer
  (``cm_copt.c`` lines 2526-2530, the BTS#10100 fix) like the C
  ``cm_cmd_period``; threaded into ``DphT.perpause``.
- ``[:phoneme on|off|asky|arpabet|speak|silent]`` — mutate the phoneme-mode
  bitfield that governs how ``[...]`` bracket blocks are read (see
  :func:`_cmd_phoneme`). Plain text outside brackets is always spoken via
  LTS regardless, so ``[:phoneme on] hello`` still says the word "hello".
- ``[:say TYPE]`` — segmentation hint (currently parsed and ignored).

Unrecognised commands are passed through silently rather than aborting,
matching the documented DECtalk behaviour.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from typing import Final

from dectalk.cmd.cmd_states import (
    MAX_PERIOD_PAUSE,
    MIN_PERIOD_PAUSE,
    PHONEME_ASCKY,
    PHONEME_OFF,
    PHONEME_SPEAK,
)
from dectalk.cmd.option_tables import define_options

_Handler = Callable[["SpeechState", list[str]], "SpeechState"]

# Design-voice parameter keywords. ``[:dv XX YY ...]`` (a.k.a. the
# ``[:define <field> <value>]`` form) assigns speaker-definition
# parameters (``ap`` = average pitch, ``hs`` = head size, ...) rather than
# selecting a preset; see :data:`dectalk.cmd.option_tables.define_options`.
_DV_PARAM_KEYWORDS: Final[frozenset[str]] = frozenset(define_options)

# Default words-per-minute used as the reference point for
# ``[:rate N]``. Matches DECtalk's documented default
# (``idh_ref_2_speaking_rate.htm``: "The default speaking rate is 180
# words per minute"). Keep in sync with
# :data:`dectalk.api.speak._DEFAULT_WPM`.
_DEFAULT_WPM: Final[int] = 180

# Inclusive WPM clamps applied to ``[:rate N]`` before converting to a
# multiplier. The C binary clamps to the same [75, 600] range
# (verified empirically; matches ``MIN_SPEAKING_RATE`` /
# ``MAX_SPEAKING_RATE`` in :mod:`dectalk.cmd.cmd_states`).
_MIN_WPM: Final[int] = 75
_MAX_WPM: Final[int] = 600

# ``[:phoneme ...]`` mode bitfield (mirrors the C ``pKsd_t->phoneme_mode``
# 3-bit field). The DECtalk front-end initialises it to
# ``PHONEME_OFF | PHONEME_SPEAK`` (``cmd/cmd_init.c:87``). Only the
# ``PHONEME_OFF``-cleared state enables phonemic interpretation of ``[...]``
# bracket blocks (``cmd/cm_pars.c:361`` / ``:1454``); plain text outside
# brackets is ALWAYS run through LTS regardless of the bits.
_DEFAULT_PHONEME_MODE: Final[int] = PHONEME_OFF | PHONEME_SPEAK

# ``[:phoneme <kw>]`` keyword -> (bitmask, set?) — one row per ``switch``
# case in the C handler ``cm_cmd_phoneme`` (``cmd/cm_copt.c:238-260``).
# Keyword order matches :data:`dectalk.cmd.option_tables.phoneme_modes`.
_PHONEME_MODE_OPS: Final[dict[str, tuple[int, bool]]] = {
    "asky": (PHONEME_ASCKY, True),  # case 0: |= PHONEME_ASCKY
    "arpabet": (PHONEME_ASCKY, False),  # case 1: &= ~PHONEME_ASCKY
    "speak": (PHONEME_SPEAK, True),  # case 2: |= PHONEME_SPEAK
    "silent": (PHONEME_SPEAK, False),  # case 3: &= ~PHONEME_SPEAK
    "off": (PHONEME_OFF, True),  # case 4: |= PHONEME_OFF
    "on": (PHONEME_OFF, False),  # case 5: &= ~PHONEME_OFF
}


@dataclass(frozen=True, slots=True)
class SpeechState:
    """Running state mutated by ``[:cmd]`` directives.

    Attributes:
        voice: Active voice short name, or None for the default preset.
        rate: Speaking-rate multiplier (1.0 = nominal).
        phoneme_mode: The DECtalk ``[:phoneme ...]`` mode bitfield
            (``PHONEME_OFF`` / ``PHONEME_ASCKY`` / ``PHONEME_SPEAK``),
            mirroring the C ``pKsd_t->phoneme_mode``. It only selects how
            ``[...]`` bracket blocks are read; it never turns a plain
            segment body into phonemes.
        comma_pause: ``[:comma N]`` / ``[:cp N]`` extra comma-boundary
            pause in milliseconds, or None when unset (issue #249).
            Raw command value — the C ``cm_cmd_comma`` sends it
            unclamped; the PH consumer applies the [-280, 30000]
            deadstop (``ph_task.c`` line 785).
        period_pause: ``[:period N]`` / ``[:pp N]`` extra
            period-boundary pause in milliseconds, or None when unset.
            Already clamped to [-420, 30000] at the command layer like
            the C ``cm_cmd_period`` (``cm_copt.c`` lines 2526-2530).
    """

    voice: str | None = None
    rate: float = 1.0
    phoneme_mode: int = _DEFAULT_PHONEME_MODE
    comma_pause: int | None = None
    period_pause: int | None = None


@dataclass(frozen=True, slots=True)
class Segment:
    """One chunk of text or phonemes paired with the state to render it under.

    Attributes:
        body: The text to speak (always plain text; the
            ``[:phoneme ...]`` modes never turn a body into phonemes).
        state: The :class:`SpeechState` active for this segment.
    """

    body: str
    state: SpeechState = field(default_factory=SpeechState)


_COMMAND_RE: Final[re.Pattern[str]] = re.compile(r"\[:\s*([^\]]*?)\s*\]")


def parse(source: str, *, initial_state: SpeechState | None = None) -> list[Segment]:
    """Split ``source`` into command-affected segments.

    Args:
        source: Input text possibly containing ``[:cmd value]`` directives.
        initial_state: Starting state. Defaults to a fresh
            :class:`SpeechState`.

    Returns:
        Ordered list of :class:`Segment` instances. Empty bodies are
        suppressed; consecutive commands collapse into a single state
        transition with no preceding segment.
    """
    state = initial_state if initial_state is not None else SpeechState()
    out: list[Segment] = []
    last_end = 0
    for m in _COMMAND_RE.finditer(source):
        body = source[last_end : m.start()]
        if body.strip():
            out.append(Segment(body=body, state=state))
        state = _apply_command(state, m.group(1))
        last_end = m.end()
    tail = source[last_end:]
    if tail.strip():
        out.append(Segment(body=tail, state=state))
    return out


def _apply_command(state: SpeechState, body: str) -> SpeechState:
    """Apply one command body (the text between ``[:`` and ``]``) to ``state``."""
    parts = body.split()
    if not parts:
        return state
    cmd = parts[0].lower()
    args = parts[1:]
    handler = _HANDLERS.get(cmd)
    if handler is None:
        return state
    return handler(state, args)


def _cmd_dv(state: SpeechState, args: list[str]) -> SpeechState:
    """Handle ``[:dv ...]`` / ``[:name NAME]``.

    Two forms share the ``dv`` keyword:

    - ``[:dv NAME]`` — select a built-in voice preset (``paul``..``willy``).
    - ``[:dv XX YY ...]`` — *design voice*: assign speaker-definition
      parameters (``ap`` = average pitch, ``hs`` = head size, ...; see
      :data:`dectalk.cmd.option_tables.define_options`).

    The parameter form must not be mistaken for a preset name: doing so
    stored e.g. ``"ap"`` as the active voice and crashed the renderer at
    ``get_preset`` (issue #241). Recognise the parameter form by its
    leading option keyword and leave the voice unchanged. The individual
    parameters are not yet applied to the speaker definition — that is a
    follow-on; the important behaviour here is not crashing.
    """
    if not args:
        return state
    if args[0].lower() in _DV_PARAM_KEYWORDS:
        # Parameter (design-voice) form: ``<field> <value>`` pairs, not a
        # preset. Not yet simulated — leave state unchanged.
        return state
    # Preset-name form: select a built-in voice.
    return replace(state, voice=args[0].lower())


def _cmd_rate(state: SpeechState, args: list[str]) -> SpeechState:
    """Handle ``[:rate N]``.

    DECtalk's ``[:rate N]`` directive sets the speaking rate to ``N``
    words per minute (absolute, not a percentage). The default is
    180 WPM; legal range is [75, 600] and out-of-range values are
    clamped to the nearest endpoint (matching the C binary's behaviour
    documented in ``idh_ref_2_speaking_rate.htm``).

    We translate the absolute WPM into the equivalent
    :attr:`SpeechState.rate` multiplier so the rest of the pipeline
    keeps its single-knob interface:

    ``rate_multiplier = DEFAULT_WPM / N``

    With ``DEFAULT_WPM = 180`` this gives ``[:rate 180] -> 1.0``
    (nominal, identical to no directive), ``[:rate 90] -> 2.0``
    (half-speed), and ``[:rate 360] -> 0.5`` (double-speed). The
    formula is the exact inverse of
    :func:`dectalk.api.speak._rate_multiplier_to_wpm`, so a
    ``[:rate N]`` directive round-trips back to WPM=N when the
    downstream renderer recovers it.

    The multiplier is composed with any pre-existing
    :attr:`SpeechState.rate` on the state so a caller-supplied
    ``rate=`` and an inline ``[:rate N]`` combine multiplicatively
    (matching the legacy approximate path's behaviour).

    Numeric parse failures and non-positive values leave the state
    unchanged.
    """
    if not args:
        return state
    try:
        wpm = float(args[0])
    except ValueError:
        return state
    if wpm <= 0:
        return state
    # Clamp to DECtalk's legal WPM range before computing the
    # multiplier so the resulting rate maps deterministically back to
    # a clamped WPM downstream (avoids float drift in the round-trip).
    wpm = max(_MIN_WPM, min(_MAX_WPM, wpm))
    return replace(state, rate=state.rate * (_DEFAULT_WPM / wpm))


def _cmd_comma(state: SpeechState, args: list[str]) -> SpeechState:
    """Handle ``[:comma N]`` / ``[:cp N]`` — comma-pause milliseconds.

    The C command table (``c_us_cde.h`` lines 417-418) parses one
    decimal argument and ``cm_cmd_comma`` (``cm_copt.c`` lines
    2486-2502) forwards it down the LTS pipe **unclamped** as the
    ``CPAUSE`` control word; the PH consumer applies the
    [-280, 30000] ms deadstop (``ph_task.c`` line 785), mirrored where
    :func:`dectalk.api.speak._render_clause_full` seeds
    ``DphT.compause``. Missing / non-numeric arguments leave the
    state unchanged (the BATS#628 no-argument guard).
    """
    if not args:
        return state
    try:
        pause_ms = int(args[0], 10)
    except ValueError:
        return state
    return replace(state, comma_pause=pause_ms)


def _cmd_period(state: SpeechState, args: list[str]) -> SpeechState:
    """Handle ``[:period N]`` / ``[:pp N]`` — period-pause milliseconds.

    ``cm_cmd_period`` (``cm_copt.c`` lines 2517-2541) clamps the
    decimal argument to [``MIN_PERIOD_PAUSE``, ``MAX_PERIOD_PAUSE``]
    = [-420, 30000] at the command layer (the BTS#10100 fix) before
    sending the ``PPAUSE`` control word. The PH consumer re-applies
    the same deadstop (``ph_task.c`` lines 786-788), so clamping here
    is byte-equivalent to the C double-clamp.
    """
    if not args:
        return state
    try:
        pause_ms = int(args[0], 10)
    except ValueError:
        return state
    pause_ms = max(MIN_PERIOD_PAUSE, min(MAX_PERIOD_PAUSE, pause_ms))
    return replace(state, period_pause=pause_ms)


def _cmd_phoneme(state: SpeechState, args: list[str]) -> SpeechState:
    """Handle ``[:phoneme <kw> ...]`` by mutating the phoneme-mode bitfield.

    Faithful to the C handler ``cm_cmd_phoneme`` (``cmd/cm_copt.c:226``):
    each space-separated keyword sets or clears one bit of
    ``pKsd_t->phoneme_mode`` via the ``switch (value)`` at
    ``cm_copt.c:238-260``. ``on``/``off`` toggle ``PHONEME_OFF``,
    ``asky``/``arpabet`` select the bracket alphabet (``PHONEME_ASCKY``),
    and ``speak``/``silent`` toggle ``PHONEME_SPEAK``.

    An unrecognised keyword makes the C handler return ``CMD_bad_string``
    and stop, keeping the bits applied by any earlier keywords
    (``cm_copt.c:234-236``); we mirror that by breaking out of the loop.

    Crucially the bitfield only governs whether ``[...]`` bracket blocks
    are read as phonemes (``cm_pars.c:361`` / ``:1454``). Plain text
    outside brackets is always spoken via LTS, so this handler never
    causes a segment body to be re-interpreted as a raw phoneme stream
    (issue #248: ``[:phoneme on] hello`` speaks the word "hello", stream
    ``hxaxll' ow``, exactly like bare ``hello``).
    """
    mode = state.phoneme_mode
    for keyword in args:
        op = _PHONEME_MODE_OPS.get(keyword.lower())
        if op is None:
            break  # C: NO_STRING_MATCH -> CMD_bad_string (stops; prior bits kept)
        mask, set_bit = op
        mode = mode | mask if set_bit else mode & ~mask
    if mode == state.phoneme_mode:
        return state
    return replace(state, phoneme_mode=mode)


def _cmd_noop(state: SpeechState, args: list[str]) -> SpeechState:
    """Recognise but ignore commands we don't simulate yet."""
    del args
    return state


def _make_name_shortcut(name: str) -> _Handler:
    """Build a handler for a ``[:nX]`` voice-name shortcut.

    The C command table (``c_us_cde.h`` lines 403-415) maps each
    two-letter ``nX`` command to a ``DCS_NAME_*`` escape whose low bits
    are the speaker number fed to ``usevoice`` (``cm_copt.c``
    ``cm_cmd_name``): ``np``=paul(0), ``nb``=betty(1), ``nh``=harry(2),
    ``nf``=frank(3), ``nd``=dennis(4), ``nk``=kit(5), ``nu``=ursula(6),
    ``nr``=rita(7), ``nw``=wendy(8, public preset name ``willy``). The
    light parser realises the same switch as a per-segment voice-name
    assignment (issue #302 — non-Paul voice prompts like ``[:nr] rita
    rough`` previously fell through the unknown-command path and
    rendered as Paul).
    """

    def _handler(state: SpeechState, args: list[str]) -> SpeechState:
        del args
        return replace(state, voice=name)

    return _handler


_HANDLERS: Final[dict[str, _Handler]] = {
    "dv": _cmd_dv,
    "name": _cmd_dv,
    "rate": _cmd_rate,
    # Comma / period boundary-pause commands and their two-letter
    # aliases (C command table ``c_us_cde.h`` lines 417-420).
    "comma": _cmd_comma,
    "cp": _cmd_comma,
    "period": _cmd_period,
    "pp": _cmd_period,
    "phoneme": _cmd_phoneme,
    "say": _cmd_noop,
    "ap": _cmd_noop,  # average pitch — future: drive preset.f0_x10 directly
    "pr": _cmd_noop,  # pitch range
    "hs": _cmd_noop,  # head size (head_scale on the preset)
    "sm": _cmd_noop,  # smoothness
    "emph": _cmd_noop,  # emphasis
    # Voice-name shortcuts (C ``DCS_NAME_*`` escapes; the speaker rows
    # live in ``dectalk.ph.voice_definitions``). ``nv`` (Variable Val,
    # speaker 9 = the saved var_val row) is not modelled — left to the
    # unknown-command fallthrough like before.
    "np": _make_name_shortcut("paul"),
    "nb": _make_name_shortcut("betty"),
    "nh": _make_name_shortcut("harry"),
    "nf": _make_name_shortcut("frank"),
    "nd": _make_name_shortcut("dennis"),
    "nk": _make_name_shortcut("kit"),
    "nu": _make_name_shortcut("ursula"),
    "nr": _make_name_shortcut("rita"),
    "nw": _make_name_shortcut("willy"),
}


def iter_phoneme_segments(source: str) -> Iterator[Segment]:
    """Yield segments from :func:`parse` lazily."""
    yield from parse(source)
