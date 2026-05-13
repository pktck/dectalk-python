"""Verify save_index matches kernel/services.c."""

from __future__ import annotations

from dectalk.include.cmd_codes import INDEX
from dectalk.kernel.save_index import save_index
from dectalk.kernel.spc_codes import SPC_type_index
from dectalk.kernel.spc_packet import SpcPacket


def test_append_to_empty_chain() -> None:
    """First save creates a new chain head."""
    head = save_index(None, sym=5, type_code=INDEX, value=42, how=1)
    assert isinstance(head, SpcPacket)
    assert head.link is None
    assert head.type == SPC_type_index
    assert head.data[0] == 5
    assert head.data[1] == INDEX
    assert head.data[2] == 42
    assert head.data[3] == 1
    assert head.data[4] == 5
    assert head.data[5] == 5
    assert head.data[6] == 0


def test_append_to_single_packet_chain() -> None:
    """Second save appends after existing head."""
    head = save_index(None, sym=1, type_code=INDEX, value=10, how=0)
    new_head = save_index(head, sym=2, type_code=INDEX, value=20, how=0)
    assert new_head is head  # Head unchanged.
    assert head.link is not None
    assert head.link.data[0] == 2
    assert head.link.data[2] == 20
    assert head.link.link is None


def test_append_to_long_chain_finds_tail() -> None:
    """Save walks to the tail of an N-packet chain before appending."""
    head: SpcPacket | None = None
    for sym in (1, 2, 3, 4, 5):
        head = save_index(head, sym=sym, type_code=INDEX, value=sym * 10, how=0)

    # Walk the chain and check order.
    seen: list[int] = []
    cur = head
    while cur is not None:
        seen.append(cur.data[0])
        cur = cur.link
    assert seen == [1, 2, 3, 4, 5]


def test_data4_data5_both_sym() -> None:
    """``data[4]`` and ``data[5]`` are both seeded to ``sym``."""
    head = save_index(None, sym=42, type_code=INDEX, value=0, how=0)
    assert head.data[4] == 42
    assert head.data[5] == 42


def test_data6_zero_init() -> None:
    """``data[6]`` is explicitly initialised to 0 (BATS sync-bug fix)."""
    head = save_index(None, sym=99, type_code=INDEX, value=0, how=0)
    assert head.data[6] == 0


def test_type_is_spc_type_index() -> None:
    """The packet's ``type`` field is set to :data:`SPC_type_index`."""
    head = save_index(None, sym=0, type_code=INDEX, value=0, how=0)
    assert head.type == SPC_type_index
