"""Asynchronous-action bit flags from kernel.h.

Translated from ``src/dapi/src/include/kernel.h``. The kernel
maintains an ``async_flags`` field bitmask that signals which
voice / rate / pause attributes have changed asynchronously and
need to be applied before the next clause is synthesised.

Five bit flags, one per attribute:

  ASYNC_voice      = 0x0001
  ASYNC_rate       = 0x0002
  ASYNC_period     = 0x0004
  ASYNC_comma      = 0x0008
  ASYNC_rate_delta = 0x0010
"""

from __future__ import annotations

from typing import Final

ASYNC_voice: Final[int] = 0x0001
"""Async change: voice (speaker) was switched."""

ASYNC_rate: Final[int] = 0x0002
"""Async change: speaking rate (``[:rate]``) was set."""

ASYNC_period: Final[int] = 0x0004
"""Async change: period-pause duration (``[:period]``) was set."""

ASYNC_comma: Final[int] = 0x0008
"""Async change: comma-pause duration (``[:comma]``) was set."""

ASYNC_rate_delta: Final[int] = 0x0010
"""Async change: rate delta (``[:rate +N]`` / ``[:rate -N]``) was applied."""


__all__ = [
    "ASYNC_comma",
    "ASYNC_period",
    "ASYNC_rate",
    "ASYNC_rate_delta",
    "ASYNC_voice",
]
