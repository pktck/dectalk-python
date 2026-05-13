"""ASCII / ISO-8859 control-code constants from esc.h.

Translated from ``src/dapi/src/include/esc.h`` lines 62-92.

The DECtalk command parser walks raw bytes; control characters
need named constants both for the parser (recognising start-of-text,
escape, etc.) and for the index/reply pipeline (which uses ``DCS``,
``CSI`` and friends to frame its packets).

Two groups:

- Lower control-code block (``NUL`` 0x00 - ``DEL`` 0x7F): standard
  C0 set the parser tokenises before letting text characters through.
- Upper control-code block (``SS2`` 0x8E - ``RDEL`` 0xFF): C1 codes
  the DCS/CSI framer recognises when it sees an 8-bit escape.

``LS0`` / ``LS1`` and ``SO`` / ``SI`` are aliases — the ISO names
(``LSn``) and the historical TTY names (``SO``/``SI``) share their
single-byte code.
"""

from __future__ import annotations

from typing import Final

# -- C0 control codes (0x00..0x1F + DEL) -----------------------------------

NUL: Final[int] = 0x00
"""Null."""

SOH: Final[int] = 0x01
"""Start of heading."""

STX: Final[int] = 0x02
"""Start of text."""

ETX: Final[int] = 0x03
"""End of text."""

ENQ: Final[int] = 0x05
"""Enquiry."""

BEL: Final[int] = 0x07
"""Bell."""

BS: Final[int] = 0x08
"""Backspace."""

HT: Final[int] = 0x09
"""Horizontal tab."""

LF: Final[int] = 0x0A
"""Line feed."""

VT: Final[int] = 0x0B
"""Vertical tab."""

FF: Final[int] = 0x0C
"""Form feed."""

CR: Final[int] = 0x0D
"""Carriage return."""

LS1: Final[int] = 0x0E
"""ISO 2022 locking-shift G1 (alias of ``SO``)."""

LS0: Final[int] = 0x0F
"""ISO 2022 locking-shift G0 (alias of ``SI``)."""

SO: Final[int] = 0x0E
"""Shift out — historical synonym of :data:`LS1`."""

SI: Final[int] = 0x0F
"""Shift in — historical synonym of :data:`LS0`."""

DLE: Final[int] = 0x10
"""Data-link escape."""

XON: Final[int] = 0x11
"""DC1 — software-flow resume."""

XOFF: Final[int] = 0x13
"""DC3 — software-flow pause."""

NAK: Final[int] = 0x15
"""Negative acknowledge (^U)."""

CAN: Final[int] = 0x18
"""Cancel (^X)."""

SUB: Final[int] = 0x1A
"""Substitute."""

ESC: Final[int] = 0x1B
"""Escape — introducer for 7-bit escape sequences."""

DEL: Final[int] = 0x7F
"""Delete."""

# -- C1 control codes (0x80..0x9F + RDEL 0xFF) -----------------------------

SS2: Final[int] = 0x8E
"""Single shift G2."""

SS3: Final[int] = 0x8F
"""Single shift G3."""

DCS: Final[int] = 0x90
"""Device-control sequence — DECtalk's primary command framing."""

OLDID: Final[int] = 0x9A
"""Historical 8-bit ``ESC Z`` collapse — single-byte identifier."""

CSI: Final[int] = 0x9B
"""Control-sequence introducer."""

ST: Final[int] = 0x9C
"""String terminator."""

OSC: Final[int] = 0x9D
"""Operating-system command."""

PM: Final[int] = 0x9E
"""Privacy message."""

APC: Final[int] = 0x9F
"""Application-program control."""

RDEL: Final[int] = 0xFF
"""Right-side delete (DECtalk extension)."""


__all__ = [
    "APC",
    "BEL",
    "BS",
    "CAN",
    "CR",
    "CSI",
    "DCS",
    "DEL",
    "DLE",
    "ENQ",
    "ESC",
    "ETX",
    "FF",
    "HT",
    "LF",
    "LS0",
    "LS1",
    "NAK",
    "NUL",
    "OLDID",
    "OSC",
    "PM",
    "RDEL",
    "SI",
    "SO",
    "SOH",
    "SS2",
    "SS3",
    "ST",
    "STX",
    "SUB",
    "VT",
    "XOFF",
    "XON",
]
