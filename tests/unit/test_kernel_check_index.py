"""Verify check_index matches kernel/services.c."""

from __future__ import annotations

from dectalk.include.cmd_codes import (
    INDEX,
    INDEX_BOOKMARK,
    INDEX_WORDPOS,
)
from dectalk.kernel.check_index import check_index
from dectalk.kernel.spc_codes import (
    SPC_subtype_bookmark,
    SPC_subtype_wordpos,
    SPC_type_index,
)
from dectalk.kernel.spc_packet import SpcPacket


def _make_index_packet(index_type: int, data2: int, data3: int, data5: int) -> SpcPacket:
    """Build an SPC index packet with the C-source's data[] layout."""
    pkt = SpcPacket()
    while len(pkt.data) < 6:
        pkt.data.append(0)
    pkt.data[1] = index_type
    pkt.data[2] = data2
    pkt.data[3] = data3
    pkt.data[5] = data5
    return pkt


def test_empty_chain_returns_none() -> None:
    """Empty chain returns None head and no emit calls."""
    calls: list[tuple[int, int, int]] = []
    new_head = check_index(None, which_phone=10, emit=calls.append)
    assert new_head is None
    assert calls == []


def test_packet_at_threshold_flushed() -> None:
    """A packet with data[5] <= which_phone is flushed."""
    pkt = _make_index_packet(INDEX, data2=42, data3=99, data5=5)
    calls: list[tuple[int, int, int]] = []
    new_head = check_index(pkt, which_phone=10, emit=calls.append)
    assert new_head is None  # Only packet flushed.
    assert calls == [(SPC_type_index, 42, 99)]


def test_packet_past_threshold_not_flushed() -> None:
    """A packet with data[5] > which_phone stops the walk."""
    pkt = _make_index_packet(INDEX, data2=1, data3=2, data5=20)
    calls: list[tuple[int, int, int]] = []
    new_head = check_index(pkt, which_phone=10, emit=calls.append)
    assert new_head is pkt
    assert calls == []


def test_index_bookmark_subtype_or() -> None:
    """``INDEX_BOOKMARK`` ORs the bookmark subtype bits into buf[0]."""
    pkt = _make_index_packet(INDEX_BOOKMARK, data2=0, data3=0, data5=0)
    calls: list[tuple[int, int, int]] = []
    check_index(pkt, which_phone=0, emit=calls.append)
    assert len(calls) == 1
    assert calls[0][0] == (SPC_type_index | SPC_subtype_bookmark)


def test_chain_flushes_prefix_only() -> None:
    """A mixed chain only flushes the prefix at-or-before which_phone."""
    a = _make_index_packet(INDEX, data2=1, data3=2, data5=2)
    b = _make_index_packet(INDEX_WORDPOS, data2=3, data3=4, data5=5)
    c = _make_index_packet(INDEX, data2=5, data3=6, data5=20)
    a.link = b
    b.link = c
    calls: list[tuple[int, int, int]] = []
    new_head = check_index(a, which_phone=10, emit=calls.append)
    assert new_head is c
    assert calls == [
        (SPC_type_index, 1, 2),
        (SPC_type_index | SPC_subtype_wordpos, 3, 4),
    ]


def test_chain_links_cleared_for_flushed_packets() -> None:
    """Flushed packets have ``link`` cleared so GC can reach them."""
    a = _make_index_packet(INDEX, data2=0, data3=0, data5=0)
    b = _make_index_packet(INDEX, data2=0, data3=0, data5=0)
    a.link = b
    check_index(a, which_phone=10, emit=lambda _buf: None)
    assert a.link is None
    assert b.link is None


def test_unknown_index_type_defaults_to_no_subtype() -> None:
    """An unknown data[1] code emits the base SPC_type_index."""
    pkt = _make_index_packet(0xDEAD, data2=1, data3=2, data5=0)
    calls: list[tuple[int, int, int]] = []
    check_index(pkt, which_phone=10, emit=calls.append)
    assert calls[0][0] == SPC_type_index
