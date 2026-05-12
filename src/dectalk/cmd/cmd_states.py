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

# -- Phoneme-parser mode bits (kernel.h) ------------------------------------

PHONEME_OFF: Final[int] = 0x1
"""Phoneme-mode bit: parser is currently NOT in phonemic mode."""

PHONEME_ASCKY: Final[int] = 0x2
"""Phoneme-mode bit: input phonemes are ASCKY (vs ARPABET)."""

PHONEME_SPEAK: Final[int] = 0x4
"""Phoneme-mode bit: phonemic words should still be spoken."""

# -- Error-handling modes (cm_defs.h) ---------------------------------------

ERROR_ignore: Final[int] = 0
"""Error mode: ignore the bad input silently."""

ERROR_text: Final[int] = 1
"""Error mode: print the bad input as text."""

ERROR_escape: Final[int] = 2
"""Error mode: emit an escape sequence pointing at the bad input."""

ERROR_speak: Final[int] = 3
"""Error mode: speak the bad input verbatim (DECtalk's default)."""

ERROR_tone: Final[int] = 4
"""Error mode: play an error tone."""

# -- Punctuation modes (cm_defs.h) ------------------------------------------

PUNCT_none: Final[int] = 0
"""Punctuation mode: don't speak any punctuation."""

PUNCT_some: Final[int] = 1
"""Punctuation mode: speak some punctuation (clause-internal pauses,
question/exclamation marks)."""

PUNCT_all: Final[int] = 2
"""Punctuation mode: speak every punctuation mark."""

PUNCT_pass: Final[int] = 3
"""Punctuation mode: pass punctuation through unprocessed (let LTS decide)."""

# -- Skip mode flags --------------------------------------------------------

SKIP_none: Final[int] = 0
"""Skip-mode: no special skip handling — process the input verbatim."""

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

# -- Misc cm_defs.h constants -----------------------------------------------

MAXRULES: Final[int] = 500
"""Rule-engine state-table size (matches ``MAXRULES`` in cm_defs.h)."""

NUM_INTER: Final[int] = 20
"""Maximum intermediate bytes in an ANSI escape sequence."""

NUM_PARAM: Final[int] = 20
"""Maximum parameter bytes in an ANSI escape sequence."""

STRING_MAX: Final[int] = 0x200
"""Capacity of the parser's string-parameter buffer (must be a power of two)."""

STRING_MASK: Final[int] = 0x1FF
"""Wrap mask for :data:`STRING_MAX` (= ``STRING_MAX - 1``)."""

# -- DTMF tone timings (cm_defs.h) ------------------------------------------

DTMF_OFF: Final[int] = 600
"""DTMF off-time in samples (≈60 ms at 10 kHz / 54 ms at 11.025 kHz)."""

DTMF_ON: Final[int] = 1600
"""DTMF on-time in samples (≈160 ms at 10 kHz; DTPC2 build right-shifts by 4)."""

NWDTMF: Final[int] = 10
"""Number of DTMF tones supported (0-9)."""

__all__ = [
    "DTMF_OFF",
    "DTMF_ON",
    "MAXRULES",
    "MAX_PERIOD_PAUSE",
    "MAX_RATE",
    "MAX_SPEAKING_RATE",
    "MAX_VOICES",
    "MIN_PERIOD_PAUSE",
    "MIN_RATE",
    "MIN_SPEAKING_RATE",
    "NUM_INTER",
    "NUM_PARAM",
    "NWDTMF",
    "PHONEME_ASCKY",
    "PHONEME_OFF",
    "PHONEME_SPEAK",
    "STATE_BRACKET",
    "STATE_COMMAND",
    "STATE_KEEP",
    "STATE_NORMAL",
    "STATE_PARAM",
    "STATE_PHONEME",
    "STATE_TOSS",
    "STRING_MASK",
    "STRING_MAX",
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
    "ERROR_escape",
    "ERROR_ignore",
    "ERROR_speak",
    "ERROR_text",
    "ERROR_tone",
    "PUNCT_all",
    "PUNCT_none",
    "PUNCT_pass",
    "PUNCT_some",
    "SKIP_all",
    "SKIP_cpg",
    "SKIP_email",
    "SKIP_none",
    "SKIP_punct",
    "SKIP_rule",
]
