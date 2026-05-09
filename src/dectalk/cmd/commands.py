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
- ``[:rate N]`` — speaking rate as a percentage of nominal (100 = normal,
  200 = half speed, 50 = double speed). DECtalk historically used
  words-per-minute; we normalise to a multiplier here.
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

    DECtalk's ``rate`` is words-per-minute (default ~180). We accept a
    percentage where 100 = nominal speed; smaller is faster. Numeric
    parse failures leave the state unchanged.
    """
    if not args:
        return state
    try:
        pct = float(args[0])
    except ValueError:
        return state
    if pct <= 0:
        return state
    # Convert wpm-style percentage into a "rate multiplier" where bigger
    # values stretch each phoneme. 100 -> 1.0; 200 -> 2.0 (slower);
    # 50 -> 0.5 (faster).
    return replace(state, rate=pct / 100.0)


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
