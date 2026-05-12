"""Signal-processing-chip (SPC) packet struct from kernel.h.

Translated from ``src/dapi/src/include/kernel.h``. ``spc_packet`` is
the linked-list node the kernel queues to send audio / control data
to the original DECtalk signal-processing chip. The Linux/HLSYN
build still uses these as the internal pipeline format between the
PH and VTM modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from dectalk.kernel.spc_codes import MAX_SPC_DATA, MAX_SPC_PACKETS

SPC_DATA_OFFSET: Final[int] = 12
"""Byte offset of the ``data`` array inside an :class:`SpcPacket`."""

SPC_PACKET_POOL: Final[int] = MAX_SPC_PACKETS // 16 + 1
"""Pool size for the SPC packet allocator (matches kernel.h's
``(sizeof(struct spc_packet) * (MAX_SPC_PACKETS/16)) + 1`` expressed
in packet count rather than bytes)."""


def _default_data() -> list[int]:
    """Factory: 32-entry zero-filled SPC packet data array."""
    return [0] * MAX_SPC_DATA


@dataclass(slots=True)
class SpcPacket:
    """One SPC packet — linked-list node carrying audio or control data.

    Faithful translation of:

    .. code-block:: c

        struct spc_packet {
            struct spc_packet far *link;
            unsigned int  high_addr;
            unsigned int  low_addr;
            unsigned int  length;
            unsigned int  type;
            unsigned int  data[MAX_SPC_DATA];
        };

    The C source's ``link`` is a forward pointer; Python uses
    ``SpcPacket | None`` so packets form a one-way linked list the
    kernel walks during flush.

    The ``high_addr`` / ``low_addr`` fields originally held the
    physical-address split for the SPC's 24-bit address bus.
    Modern builds carry pointers / opaque handles in the same slot.

    Attributes:
        link: Next packet in the queue, or None at the tail.
        high_addr: High 16 bits of physical-address (legacy).
        low_addr: Low 16 bits of physical-address (legacy).
        length: Number of meaningful entries in ``data``.
        type: Packet type code (one of the :data:`SPC_type_*`
            constants in :mod:`dectalk.kernel.spc_codes`).
        data: 32-entry payload array.
    """

    link: SpcPacket | None = None
    high_addr: int = 0
    low_addr: int = 0
    length: int = 0
    type: int = 0
    data: list[int] = field(default_factory=_default_data)


__all__ = ["SPC_DATA_OFFSET", "SPC_PACKET_POOL", "SpcPacket"]
