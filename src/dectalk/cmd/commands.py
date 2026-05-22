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
- ``[:phoneme on]`` / ``[:phoneme off]`` — switch between text and direct
  ARPABET phoneme input.
- ``[:say TYPE]`` — segmentation hint (currently parsed and ignored).

Unrecognised commands are passed through silently rather than aborting,
matching the documented DECtalk behaviour.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from typing import Final

_Handler = Callable[["SpeechState", list[str]], "SpeechState"]

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


@dataclass(frozen=True, slots=True)
class SpeechState:
    """Running state mutated by ``[:cmd]`` directives.

    Attributes:
        voice: Active voice short name, or None for the default preset.
        rate: Speaking-rate multiplier (1.0 = nominal).
        phoneme_mode: When True, the body is interpreted as ARPABET
            phonemes rather than text.
    """

    voice: str | None = None
    rate: float = 1.0
    phoneme_mode: bool = False


@dataclass(frozen=True, slots=True)
class Segment:
    """One chunk of text or phonemes paired with the state to render it under.

    Attributes:
        body: The text (or phoneme string when ``state.phoneme_mode``).
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
    """Handle ``[:dv NAME]`` / ``[:name NAME]``."""
    if not args:
        return state
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


def _cmd_phoneme(state: SpeechState, args: list[str]) -> SpeechState:
    """Handle ``[:phoneme on/off]``."""
    if not args:
        return state
    flag = args[0].lower()
    if flag == "on":
        return replace(state, phoneme_mode=True)
    if flag == "off":
        return replace(state, phoneme_mode=False)
    return state


def _cmd_noop(state: SpeechState, args: list[str]) -> SpeechState:
    """Recognise but ignore commands we don't simulate yet."""
    del args
    return state


_HANDLERS: Final[dict[str, _Handler]] = {
    "dv": _cmd_dv,
    "name": _cmd_dv,
    "rate": _cmd_rate,
    "phoneme": _cmd_phoneme,
    "say": _cmd_noop,
    "ap": _cmd_noop,  # average pitch — future: drive preset.f0_x10 directly
    "pr": _cmd_noop,  # pitch range
    "hs": _cmd_noop,  # head size (head_scale on the preset)
    "sm": _cmd_noop,  # smoothness
    "emph": _cmd_noop,  # emphasis
}


def iter_phoneme_segments(source: str) -> Iterator[Segment]:
    """Yield segments from :func:`parse` lazily."""
    yield from parse(source)
