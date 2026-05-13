"""Verify SPC packet pool helpers mirror services.c."""

from __future__ import annotations

from dectalk.kernel.spc_packet import SpcPacket
from dectalk.kernel.spc_packet_pool import free_spc_packet, get_spc_packet


def test_get_returns_global_slot() -> None:
    """``get_spc_packet`` returns the singleton global slot when free."""
    pkt = get_spc_packet()
    assert pkt is not None
    assert isinstance(pkt, SpcPacket)


def test_free_accepts_global_slot() -> None:
    """``free_spc_packet`` on the global slot returns it to the pool."""
    pkt = get_spc_packet()
    assert pkt is not None
    free_spc_packet(pkt)
    # Next get returns the same slot again.
    pkt2 = get_spc_packet()
    assert pkt2 is pkt


def test_free_ignores_foreign_packet() -> None:
    """``free_spc_packet`` ignores a packet not from the global pool."""
    foreign = SpcPacket()
    # No-op — no exception raised.
    free_spc_packet(foreign)


def test_free_ignores_none() -> None:
    """``free_spc_packet(None)`` is a safe no-op."""
    free_spc_packet(None)


def test_returned_slot_is_singleton() -> None:
    """Every call returns the same SpcPacket instance (single global slot)."""
    a = get_spc_packet()
    b = get_spc_packet()
    assert a is b
