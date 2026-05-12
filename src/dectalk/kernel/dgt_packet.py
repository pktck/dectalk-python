"""Digitized-audio packet struct from kernel.h.

Translated from ``src/dapi/src/include/kernel.h``. ``dgt_packet`` is
the linked-list node carrying pre-recorded digitised audio frames
through the kernel pipeline — distinct from :class:`SpcPacket` which
carries synthesised audio / control data.

Each digitised packet holds up to 8 frames of 65 short words each
(8 * 65 = 520 samples of pre-recorded audio).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

MAX_DGT_PACKETS: Final[int] = 16
"""Maximum number of digitised packets in flight at once."""

DGT_WORDS_PER_FRAME: Final[int] = 65
"""Short words (16-bit samples) per audio frame."""

DGT_BYTES_PER_FRAME: Final[int] = 130
"""Bytes per audio frame (``DGT_WORDS_PER_FRAME * 2``)."""

MAX_DGT_FRAMES: Final[int] = 8
"""Maximum audio frames carried by one digitised packet."""

MAX_DGT_DATA: Final[int] = DGT_WORDS_PER_FRAME * MAX_DGT_FRAMES
"""``MAX_DGT_DATA = 520`` — total words in one packet's ``data[]`` array."""

DGT_DATA_OFFSET: Final[int] = 12
"""Byte offset of ``data[]`` array inside a :class:`DgtPacket`."""

DGT_PACKET_POOL: Final[int] = MAX_DGT_PACKETS // 16 + 1
"""Pool size for the DGT packet allocator (matches kernel.h)."""


def _default_data() -> list[int]:
    """Factory: 520-entry zero-filled DGT packet data array."""
    return [0] * MAX_DGT_DATA


@dataclass(slots=True)
class DgtPacket:
    """Digitised audio packet — linked-list node carrying recorded samples.

    Faithful translation of:

    .. code-block:: c

        struct dgt_packet {
            struct dgt_packet far *link;
            unsigned int  high_addr;
            unsigned int  low_addr;
            unsigned int  length;
            unsigned int  data[MAX_DGT_DATA];
        };

    Unlike :class:`SpcPacket`, no ``type`` field — every DGT packet
    carries the same digitised-audio payload.

    Attributes:
        link: Next packet, or None at tail.
        high_addr: Legacy physical-address high word.
        low_addr: Legacy physical-address low word.
        length: Meaningful entries in ``data``.
        data: 520-entry sample array.
    """

    link: DgtPacket | None = None
    high_addr: int = 0
    low_addr: int = 0
    length: int = 0
    data: list[int] = field(default_factory=_default_data)


__all__ = [
    "DGT_BYTES_PER_FRAME",
    "DGT_DATA_OFFSET",
    "DGT_PACKET_POOL",
    "DGT_WORDS_PER_FRAME",
    "MAX_DGT_DATA",
    "MAX_DGT_FRAMES",
    "MAX_DGT_PACKETS",
    "DgtPacket",
]
