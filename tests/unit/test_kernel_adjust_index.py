"""Verify adjust_index matches kernel/services.c."""

from __future__ import annotations

from dectalk.kernel.adjust_index import adjust_index
from dectalk.kernel.spc_packet import SpcPacket


def _make_packet(data4: int, data5: int, data6: int) -> SpcPacket:
    """Build an SPC packet with given data[4..6] values."""
    pkt = SpcPacket()
    while len(pkt.data) < 7:
        pkt.data.append(0)
    pkt.data[4] = data4
    pkt.data[5] = data5
    pkt.data[6] = data6
    return pkt


def test_empty_chain_is_noop() -> None:
    """Passing None doesn't crash."""
    adjust_index(None, which=5, direction=1, delete=0)


def test_packet_matches_adjusts_data4_and_data6() -> None:
    """A packet where data[5] >= which + data[6] gets data[4] and data[6] adjusted."""
    pkt = _make_packet(data4=10, data5=20, data6=3)
    # which=15, data[5]=20, data[6]=3 => 20 >= 15+3 (=18) => matches.
    adjust_index(pkt, which=15, direction=1, delete=-1)
    assert pkt.data[4] == 11
    assert pkt.data[6] == 2


def test_packet_below_threshold_not_adjusted() -> None:
    """A packet where data[5] < which + data[6] is left alone."""
    pkt = _make_packet(data4=10, data5=5, data6=3)
    # which=15, data[5]=5, data[6]=3 => 5 < 15+3 => no match.
    adjust_index(pkt, which=15, direction=1, delete=-1)
    assert pkt.data[4] == 10
    assert pkt.data[6] == 3


def test_chain_traversed_fully() -> None:
    """All packets in the chain are visited."""
    head = _make_packet(data4=10, data5=20, data6=0)
    mid = _make_packet(data4=20, data5=20, data6=0)
    tail = _make_packet(data4=30, data5=20, data6=0)
    head.link = mid
    mid.link = tail
    adjust_index(head, which=10, direction=5, delete=0)
    assert head.data[4] == 15
    assert mid.data[4] == 25
    assert tail.data[4] == 35


def test_chain_mixed_match_no_match() -> None:
    """Only matching packets are adjusted."""
    matching = _make_packet(data4=0, data5=20, data6=0)  # 20 >= 10
    skipped = _make_packet(data4=0, data5=5, data6=0)  # 5 < 10
    matching.link = skipped
    adjust_index(matching, which=10, direction=1, delete=0)
    assert matching.data[4] == 1
    assert skipped.data[4] == 0


def test_negative_direction() -> None:
    """``direction`` can be negative — applied verbatim."""
    pkt = _make_packet(data4=10, data5=20, data6=0)
    adjust_index(pkt, which=10, direction=-3, delete=0)
    assert pkt.data[4] == 7
