"""Core DECtalk constants, voice IDs, and shared parser structs.

Translated from `src/dapi/src/include/dectalk.h` in the DECtalk 4.2CD source.
This module exposes the universal symbols used by every other module: ANSI
sequence buffer sizes, voice index constants, debug flags, and the `Seq` /
`Pparse` dataclasses that carry pre-parsed control sequences and phoneme
parser state through the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, IntFlag
from typing import Final

# -- Sequence parser sizes --------------------------------------------------
EOS: Final[int] = 0
"""End-of-string sentinel."""

NINTER: Final[int] = 10
"""Maximum intermediates in an ANSI sequence."""

NPARAM: Final[int] = 10
"""Maximum parameters in an ANSI sequence."""

NSTRING: Final[int] = 254
"""Maximum control-string length (must stay under 256)."""

NUDPHON: Final[int] = 100
"""Maximum user-defined phonemes (must stay under 128 to fit a byte)."""

NLPIPE: Final[int] = 250
"""Word capacity of the LTS-to-PH pipe."""

NKPIPE: Final[int] = 250
"""Word capacity of the PH-to-Klatt-synth pipe."""

MSHZ: Final[int] = 10
"""Basic clock period in milliseconds (100 Hz frame tick)."""

FWREV: Final[int] = 13
"""Firmware revision number (legacy, kept for parity with the original)."""


# -- Voice IDs --------------------------------------------------------------
class Voice(IntEnum):
    """Index into the voice parameter tables.

    The numeric values match the C `#define`s in `dectalk.h` so binary
    artifacts (saved presets, dictionary overrides) remain compatible.
    """

    PERFECT_PAUL = 0
    BEAUTIFUL_BETTY = 1
    HUGE_HARRY = 2
    FRAIL_FRANK = 3
    DOCTOR_DENNIS = 4
    KIT_THE_KID = 5
    UPPITY_URSULA = 6
    ROUGH_RITA = 7
    WHISPERY_WILLY = 8
    CRAFTY_CHRIS = 9
    VARIABLE_VAL = 10


# -- Language pipe codes ----------------------------------------------------
LTS_PIPE: Final[int] = 0x00
"""Pipe-connection code for letter-to-sound output (supports 32 languages)."""

PH_PIPE: Final[int] = 0x20
"""Pipe-connection code for phoneme output."""


# -- Debug flags ------------------------------------------------------------
class DebugSection(IntFlag):
    """Top-nibble bits of the debug switch identifying which module to trace."""

    CMD = 0x8000
    LTS = 0x4000
    PH = 0x2000
    VTM = 0x1000


# -- ANSI sequence struct ---------------------------------------------------
@dataclass(slots=True)
class Seq:
    """Pre-parsed ANSI control sequence handed between DECtalk modules.

    Mirrors the C `SEQ` struct. Default-ness of each parameter is tracked in
    `s_dflag` (1 means "the caller did not supply a value").

    Attributes:
        s_type: Numeric type code identifying the sequence family.
        s_badf: True when the parser rejected the sequence as malformed.
        s_pintro: Non-zero when the sequence used a private introducer.
        s_nparam: Number of populated entries in `s_param`.
        s_ninter: Number of populated entries in `s_inter`.
        s_param: Numeric parameter values, indexed `[0, NPARAM)`.
        s_dflag: Per-parameter default flags, indexed `[0, NPARAM)`.
        s_inter: Intermediate bytes, indexed `[0, NINTER)`.
        s_final: Final byte that terminated the sequence.
    """

    s_type: int = 0
    s_badf: bool = False
    s_pintro: int = 0
    s_nparam: int = 0
    s_ninter: int = 0
    s_param: list[int] = field(default_factory=lambda: [0] * NPARAM)
    s_dflag: list[bool] = field(default_factory=lambda: [True] * NPARAM)
    s_inter: list[int] = field(default_factory=lambda: [0] * NINTER)
    s_final: int = 0


@dataclass(slots=True)
class Pparse:
    """Inpure area for the finite-state phoneme parser (was `PPARSE`).

    Attributes:
        p_state: Current state of the parser FSM.
        p_nbuf: Number of populated entries in `p_buf`.
        p_buf: Lookahead buffer; sized for the longest token (`dhx<1,2>`).
    """

    p_state: int = 0
    p_nbuf: int = 0
    p_buf: list[int] = field(default_factory=lambda: [0] * 4)
