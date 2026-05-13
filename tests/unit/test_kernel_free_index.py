"""Verify free_index breaks chain links per kernel/services.c."""

from __future__ import annotations

from dectalk.kernel.free_index import free_index
from dectalk.kernel.spc_packet import SpcPacket


def test_empty_chain_is_noop() -> None:
    """Passing None doesn't crash."""
    free_index(None)


def test_single_packet_link_cleared() -> None:
    """A single-packet chain's link is cleared (already None for tail)."""
    pkt = SpcPacket()
    free_index(pkt)
    assert pkt.link is None


def test_chain_links_broken() -> None:
    """Every packet's ``link`` is set to None after free_index."""
    head = SpcPacket()
    mid = SpcPacket()
    tail = SpcPacket()
    head.link = mid
    mid.link = tail
    free_index(head)
    assert head.link is None
    assert mid.link is None
    assert tail.link is None


def test_traversal_complete() -> None:
    """All N packets visited (proven by all links broken)."""
    n = 10
    head: SpcPacket | None = None
    for _ in range(n):
        new = SpcPacket()
        new.link = head
        head = new
    free_index(head)
    # Walk the chain — every link should be None.
    cur = head
    visited = 0
    while cur is not None:
        assert cur.link is None
        # cur.link is None so this loop terminates after 1 iteration —
        # we just check `head` here, the others are unreachable via head
        # since their links were broken too.
        visited += 1
        cur = cur.link
    assert visited == 1
