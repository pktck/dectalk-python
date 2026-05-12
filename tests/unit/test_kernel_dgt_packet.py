"""Verify DgtPacket dataclass and digitised-packet constants."""

from __future__ import annotations

from dectalk.kernel.dgt_packet import (
    DGT_BYTES_PER_FRAME,
    DGT_DATA_OFFSET,
    DGT_PACKET_POOL,
    DGT_WORDS_PER_FRAME,
    MAX_DGT_DATA,
    MAX_DGT_FRAMES,
    MAX_DGT_PACKETS,
    DgtPacket,
)


def test_max_constants() -> None:
    """All four MAX_DGT_* constants match kernel.h."""
    assert MAX_DGT_PACKETS == 16
    assert DGT_WORDS_PER_FRAME == 65
    assert DGT_BYTES_PER_FRAME == 130
    assert MAX_DGT_FRAMES == 8


def test_max_dgt_data_derived() -> None:
    """MAX_DGT_DATA = WORDS_PER_FRAME * MAX_FRAMES = 520."""
    assert MAX_DGT_DATA == 520
    assert MAX_DGT_DATA == DGT_WORDS_PER_FRAME * MAX_DGT_FRAMES


def test_bytes_per_frame_doubled_word_count() -> None:
    """DGT_BYTES_PER_FRAME = 2 * DGT_WORDS_PER_FRAME (16-bit samples)."""
    assert DGT_BYTES_PER_FRAME == 2 * DGT_WORDS_PER_FRAME


def test_default_construction() -> None:
    """DgtPacket defaults to all-zero / empty."""
    p = DgtPacket()
    assert p.link is None
    assert p.high_addr == 0
    assert p.low_addr == 0
    assert p.length == 0
    assert p.data == [0] * MAX_DGT_DATA


def test_data_buffer_size() -> None:
    """``data`` array length matches MAX_DGT_DATA (520)."""
    p = DgtPacket()
    assert len(p.data) == MAX_DGT_DATA


def test_linked_list() -> None:
    """``link`` lets packets form a forward-linked list."""
    tail = DgtPacket(length=10)
    head = DgtPacket(length=5, link=tail)
    assert head.link is tail
    assert head.link is not None
    assert head.link.length == 10


def test_dgt_data_offset_and_pool() -> None:
    """``DGT_DATA_OFFSET`` (12) and ``DGT_PACKET_POOL`` (2)."""
    assert DGT_DATA_OFFSET == 12
    assert DGT_PACKET_POOL == 2  # MAX_DGT_PACKETS / 16 + 1 = 1 + 1


def test_uses_slots() -> None:
    """DgtPacket uses slots=True."""
    p = DgtPacket()
    assert not hasattr(p, "__dict__")
