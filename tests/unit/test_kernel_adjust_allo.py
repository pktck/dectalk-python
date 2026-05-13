"""Verify adjust_allo / set_index_allo match kernel/services.c."""

from __future__ import annotations

from dectalk.kernel.adjust_allo import adjust_allo, set_index_allo
from dectalk.kernel.spc_packet import SpcPacket


def _make_packet(data4: int, data5: int) -> SpcPacket:
    """Build an SPC packet with given data[4]/data[5]."""
    pkt = SpcPacket()
    while len(pkt.data) < 6:
        pkt.data.append(0)
    pkt.data[4] = data4
    pkt.data[5] = data5
    return pkt


def test_adjust_allo_empty_chain_is_noop() -> None:
    """Passing None doesn't crash."""
    adjust_allo(None, which=5, direction=1)


def test_adjust_allo_above_threshold_adjusts() -> None:
    """A packet with data[5] >= which has direction added."""
    pkt = _make_packet(data4=0, data5=10)
    adjust_allo(pkt, which=5, direction=3)
    assert pkt.data[5] == 13


def test_adjust_allo_below_threshold_unchanged() -> None:
    """A packet with data[5] < which is left alone."""
    pkt = _make_packet(data4=0, data5=3)
    adjust_allo(pkt, which=5, direction=10)
    assert pkt.data[5] == 3


def test_adjust_allo_chain_traversal() -> None:
    """All packets in the chain are visited."""
    head = _make_packet(0, 5)
    mid = _make_packet(0, 10)
    tail = _make_packet(0, 15)
    head.link = mid
    mid.link = tail
    adjust_allo(head, which=5, direction=1)
    assert head.data[5] == 6
    assert mid.data[5] == 11
    assert tail.data[5] == 16


def test_set_index_allo_empty_chain_is_noop() -> None:
    """Passing None doesn't crash."""
    set_index_allo(None, nphone=3, nallo=42)


def test_set_index_allo_matching_packet_updates_data5() -> None:
    """A packet with data[4] == nphone has data[5] set to nallo."""
    pkt = _make_packet(data4=3, data5=99)
    set_index_allo(pkt, nphone=3, nallo=42)
    assert pkt.data[5] == 42


def test_set_index_allo_non_matching_unchanged() -> None:
    """A packet with data[4] != nphone is left alone."""
    pkt = _make_packet(data4=2, data5=99)
    set_index_allo(pkt, nphone=3, nallo=42)
    assert pkt.data[5] == 99


def test_set_index_allo_chain_mixed() -> None:
    """Only matching packets have data[5] updated."""
    matching = _make_packet(data4=7, data5=10)
    skipped = _make_packet(data4=8, data5=20)
    matching.link = skipped
    set_index_allo(matching, nphone=7, nallo=100)
    assert matching.data[5] == 100
    assert skipped.data[5] == 20
