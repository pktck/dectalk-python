"""Parser buffer-size limits from par_def.h.

Translated from ``src/dapi/src/cmd/par_def.h`` lines 55-73 —
the size constants the inline-command rule engine uses to bound
its input / output / temporary buffers.

The C source uses different values for the Win32 vs non-Win32
builds:

- Win32:        ``PAR_MAX_INPUT_ARRAY`` / ``PAR_MAX_OUTPUT_ARRAY``
                are 500; ``PAR_MAX_RULE_LENGTH`` /
                ``PAR_ROLLING_STOP_VALUE`` are 300.
- non-Win32:    ``PAR_MAX_INPUT_ARRAY`` / ``PAR_MAX_OUTPUT_ARRAY``
                are 300; ``PAR_MAX_RULE_LENGTH`` /
                ``PAR_ROLLING_STOP_VALUE`` are 200.

The Python port uses the **Win32** numbers to match the existing
:data:`dectalk.cmd.rule_struct.PAR_MAX_RULE_LENGTH` = 300. The
non-Win32 values are documented in each constant's docstring.
"""

from __future__ import annotations

from typing import Final

PAR_MAX_INPUT_ARRAY: Final[int] = 500
"""Maximum input-buffer length the rule engine reads from (300 on
non-Win32 builds)."""

PAR_MAX_OUTPUT_ARRAY: Final[int] = 500
"""Maximum output-buffer length the rule engine writes to (300 on
non-Win32 builds)."""

PAR_ROLLING_STOP_VALUE: Final[int] = 300
"""Threshold at which the rule engine stops accumulating and flushes
its rolling buffer (200 on non-Win32 builds)."""

PAR_MAX_RETURN_LEVEL: Final[int] = 10
"""Maximum recursion depth for rule lookahead (GORET return stack)."""

PAR_MIN_INPUT_SIZE: Final[int] = 5
"""Minimum input length the parser requires before attempting a rule."""


__all__ = [
    "PAR_MAX_INPUT_ARRAY",
    "PAR_MAX_OUTPUT_ARRAY",
    "PAR_MAX_RETURN_LEVEL",
    "PAR_MIN_INPUT_SIZE",
    "PAR_ROLLING_STOP_VALUE",
]
