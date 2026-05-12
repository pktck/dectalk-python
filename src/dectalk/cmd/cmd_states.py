"""Command-parser state codes and error codes from cm_defs.h.

Translated from ``src/dapi/src/cmd/cm_defs.h``:

- :data:`STATE_NORMAL` .. :data:`STATE_KEEP` — values of
  ``pCmd_t->state``, the inline-command parser state machine.
- :data:`CMD_success` .. :data:`CMD_flushing` — error / status codes
  returned by command callbacks and the parser dispatcher.
- :data:`CMD_flush_toss` / :data:`CMD_flush_sync` / :data:`CMD_flush_done`
  — flush-stage codes used by ``cm_util_flush_init``.
- :data:`CMD_sync_char` / :data:`CMD_sync_out` — sync-byte markers
  used to align the parser stream with downstream pipes.
- :data:`MIN_SPEAKING_RATE` / :data:`MAX_SPEAKING_RATE` — bounds on
  the ``[:rate <wpm>]`` parameter.
- :data:`MIN_PERIOD_PAUSE` / :data:`MAX_PERIOD_PAUSE` — bounds on
  the ``[:period <ms>]`` parameter.
"""

from __future__ import annotations

from typing import Final

# -- pCmd_t->state values ---------------------------------------------------

STATE_NORMAL: Final[int] = 0
"""Passing characters through unchanged (no escape in progress)."""

STATE_BRACKET: Final[int] = 1
"""Saw ``[``; deciding whether this is a command or phonemic block."""

STATE_COMMAND: Final[int] = 2
"""Saw ``[:`` — parsing the command name."""

STATE_PHONEME: Final[int] = 3
"""Saw ``[`` without ``:`` — collecting phonemic input."""

STATE_PARAM: Final[int] = 4
"""Matched a command name — parsing its parameter list."""

STATE_TOSS: Final[int] = 5
"""Bad ``[:`` — drop characters until matching ``]``."""

STATE_KEEP: Final[int] = 6
"""Hold the parse buffer so the next clause sees the same context."""

# -- Command-callback / dispatcher result codes -----------------------------

CMD_success: Final[int] = 0
"""Command parsed and executed successfully."""

CMD_bad_string: Final[int] = 1
"""Bad string parameter."""

CMD_bad_value: Final[int] = 2
"""Numeric parameter out of range."""

CMD_bad_command: Final[int] = 3
"""Unknown command name."""

CMD_bad_param: Final[int] = 4
"""Wrong number/kind of parameters."""

CMD_bad_phoneme: Final[int] = 5
"""Bad phoneme symbol inside a ``[<…>]`` phonemic block."""

CMD_out_of_memory: Final[int] = 6
"""Allocation failed."""

CMD_unable_to_open_file: Final[int] = 7
"""``[:filename …]`` couldn't open the file."""

CMD_bad_wave_file_format: Final[int] = 8
"""Wave file failed format check."""

CMD_unsupported_wave_file_format: Final[int] = 9
"""Wave file format recognised but not playable."""

CMD_unsupported_audio_format: Final[int] = 10
"""Audio format not supported by the engine."""

CMD_flushing: Final[int] = 11
"""Stream is mid-flush — the command was suppressed."""

# -- cm_util_flush_init stage codes -----------------------------------------

CMD_flush_toss: Final[int] = 1
"""Throwing away buffered characters during a flush."""

CMD_flush_sync: Final[int] = 2
"""Waiting for the next sync byte on the input stream."""

CMD_flush_done: Final[int] = 3
"""Flush complete — resume normal parsing."""

# -- Sync byte markers ------------------------------------------------------

CMD_sync_char: Final[int] = 0xFF
"""Sync byte injected into the input by ``cm_util_flush_init``."""

CMD_sync_out: Final[int] = 0xFE
"""Sync byte forwarded to downstream pipes after parsing completes."""

# -- Parameter bounds -------------------------------------------------------

MIN_SPEAKING_RATE: Final[int] = 75
"""Lower bound of the ``[:rate <wpm>]`` parameter (Kurzweil-build raises to 50)."""

MAX_SPEAKING_RATE: Final[int] = 600
"""Upper bound of the ``[:rate <wpm>]`` parameter (was 350 in DECtalk 3.x)."""

MIN_PERIOD_PAUSE: Final[int] = -420
"""Lower bound of the ``[:period <ms>]`` parameter (negative shortens pauses)."""

MAX_PERIOD_PAUSE: Final[int] = 30000
"""Upper bound of the ``[:period <ms>]`` parameter."""

MIN_RATE: Final[int] = 100
"""Lower bound for the ``[:rate]`` parameter (cm_defs.h variant)."""

MAX_RATE: Final[int] = 550
"""Upper bound for the ``[:rate]`` parameter (cm_defs.h variant)."""

MAX_VOICES: Final[int] = 11
"""Number of voice slots in the voice table (Paul…Wendy + Variable Val)."""

# -- Skip mode flags --------------------------------------------------------

SKIP_email: Final[int] = 1
"""Skip-mode: email-addressing — split words on ``@`` / ``.`` boundaries."""

SKIP_punct: Final[int] = 2
"""Skip-mode: punctuation — read aloud most punctuation marks."""

SKIP_rule: Final[int] = 3
"""Skip-mode: rule-based — let the LTS engine decide."""

SKIP_all: Final[int] = 4
"""Skip-mode: silent — skip everything, useful for testing."""

SKIP_cpg: Final[int] = 5
"""Skip-mode: ``[:cpg]`` (custom phoneme group) mode."""

__all__ = [
    "MAX_PERIOD_PAUSE",
    "MAX_RATE",
    "MAX_SPEAKING_RATE",
    "MAX_VOICES",
    "MIN_PERIOD_PAUSE",
    "MIN_RATE",
    "MIN_SPEAKING_RATE",
    "STATE_BRACKET",
    "STATE_COMMAND",
    "STATE_KEEP",
    "STATE_NORMAL",
    "STATE_PARAM",
    "STATE_PHONEME",
    "STATE_TOSS",
    "CMD_bad_command",
    "CMD_bad_param",
    "CMD_bad_phoneme",
    "CMD_bad_string",
    "CMD_bad_value",
    "CMD_bad_wave_file_format",
    "CMD_flush_done",
    "CMD_flush_sync",
    "CMD_flush_toss",
    "CMD_flushing",
    "CMD_out_of_memory",
    "CMD_success",
    "CMD_sync_char",
    "CMD_sync_out",
    "CMD_unable_to_open_file",
    "CMD_unsupported_audio_format",
    "CMD_unsupported_wave_file_format",
    "SKIP_all",
    "SKIP_cpg",
    "SKIP_email",
    "SKIP_punct",
    "SKIP_rule",
]
