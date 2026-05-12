"""Verify SpcPacket dataclass and SPC packet constants."""

from __future__ import annotations

from dectalk.kernel.spc_codes import MAX_SPC_DATA, MAX_SPC_PACKETS
from dectalk.kernel.spc_packet import SPC_DATA_OFFSET, SPC_PACKET_POOL, SpcPacket


def test_default_construction() -> None:
    """SpcPacket defaults to all-zero / empty / None."""
    p = SpcPacket()
    assert p.link is None
    assert p.high_addr == 0
    assert p.low_addr == 0
    assert p.length == 0
    assert p.type == 0
    assert p.data == [0] * MAX_SPC_DATA


def test_data_buffer_size() -> None:
    """data array length matches MAX_SPC_DATA (32)."""
    p = SpcPacket()
    assert len(p.data) == 32
    assert len(p.data) == MAX_SPC_DATA


def test_linked_list() -> None:
    """``link`` lets packets form a forward-linked list."""
    tail = SpcPacket(type=1, length=5)
    head = SpcPacket(type=0, length=3, link=tail)
    assert head.link is tail
    assert head.link is not None
    assert head.link.length == 5


def test_independent_data_arrays() -> None:
    """Each packet has its own data array (no sharing)."""
    p1 = SpcPacket()
    p2 = SpcPacket()
    p1.data[0] = 0xAB
    assert p2.data[0] == 0


def test_spc_data_offset() -> None:
    """``SPC_DATA_OFFSET`` (12) — header byte count before data[]."""
    assert SPC_DATA_OFFSET == 12


def test_spc_packet_pool_size() -> None:
    """``SPC_PACKET_POOL`` matches ``MAX_SPC_PACKETS / 16 + 1``."""
    assert SPC_PACKET_POOL == MAX_SPC_PACKETS // 16 + 1


def test_uses_slots() -> None:
    """SpcPacket uses slots=True."""
    p = SpcPacket()
    assert not hasattr(p, "__dict__")
