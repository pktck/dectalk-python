"""``INPUT_SEQ`` ANSI-escape struct from cm_data.h.

Translated from ``src/dapi/src/cmd/cm_data.h``. ``INPUT_SEQ`` is
the pre-parsed ANSI control-sequence record the inline-command
parser uses internally when ``ESCAPE_SEQ`` mode is enabled — it
captures the type, badness flag, private-intro byte, parameter
array, default-flag mask, intermediates, and final byte of an
``ESC[<params><inter><final>`` sequence.

The struct is mostly inert in the modern Linux build (the
ESCAPE_SEQ code path is ``#ifdef``-disabled), but the Python
mirror is needed for symbol parity with the LPTTS_HANDLE_T thread
state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from dectalk.cmd.cmd_states import NUM_INTER, NUM_PARAM


@dataclass(slots=True)
class InputSeq:
    """ANSI control-sequence parse buffer (matches C ``INPUT_SEQ``).

    Faithful translation of:

    .. code-block:: c

        typedef struct input_esc_struct {
            short type;
            char  badf;
            char  pintro;
            short nparam;
            short ninter;
            short param[NUM_PARAM];
            char  dflag[NUM_PARAM];
            char  inter[NUM_INTER];
            char  final;
        } INPUT_SEQ;

    Attributes:
        type: Sequence type code (CSI / DCS / OSC etc.).
        badf: Truthy if the sequence is malformed.
        pintro: Private-intro byte (zero if none).
        nparam: Number of parameters captured in :attr:`param`.
        ninter: Number of intermediate bytes captured in :attr:`inter`.
        param: Numeric parameter list (length :data:`NUM_PARAM`).
        dflag: Per-parameter "this slot is default" mask (length
            :data:`NUM_PARAM`).
        inter: Intermediate-byte buffer (length :data:`NUM_INTER`).
        final: Final byte that terminated the sequence.
    """

    type: int = 0
    badf: int = 0
    pintro: int = 0
    nparam: int = 0
    ninter: int = 0
    param: list[int] = field(default_factory=lambda: [0] * NUM_PARAM)
    dflag: list[int] = field(default_factory=lambda: [0] * NUM_PARAM)
    inter: list[int] = field(default_factory=lambda: [0] * NUM_INTER)
    final: int = 0


INPUT_SEQ_PARAM_LEN: Final[int] = NUM_PARAM
"""Length of :attr:`InputSeq.param` and :attr:`InputSeq.dflag` (matches C)."""

INPUT_SEQ_INTER_LEN: Final[int] = NUM_INTER
"""Length of :attr:`InputSeq.inter` (matches C)."""


__all__ = [
    "INPUT_SEQ_INTER_LEN",
    "INPUT_SEQ_PARAM_LEN",
    "InputSeq",
]
