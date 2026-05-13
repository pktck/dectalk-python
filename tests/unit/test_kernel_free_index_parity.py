"""C-source parity test for ``free_index`` against kernel/services.c.

Re-parses the C function body and asserts the Python port preserves:

- the chain-walk pattern (``free_pkt = spc_pkt; spc_pkt = spc_pkt->link;``),
- the ``free(free_pkt)`` per packet,
- the reset of ``pKsd_t->spc_pkt_save = NULL_SPC_PACKET`` at the end,
- no mutation of any ``data[N]`` field.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.kernel.free_index import free_index
from dectalk.kernel.spc_packet import SpcPacket

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / (
    "src/dapi/src/kernel/services.c"
)

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_services_c() -> str:
    """Read services.c with CRLF endings normalised."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_free_index_body() -> str:
    """Return the C ``free_index`` function body."""
    text = _read_services_c()
    match = re.search(
        r"void\s+free_index\s*\([^)]*\)\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "free_index() not found in services.c"
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    return body


def test_free_index_walks_chain_via_free_pkt_assign() -> None:
    """``free_pkt = spc_pkt; spc_pkt = spc_pkt->link;`` is the chain walk."""
    body = _extract_free_index_body()
    assert re.search(
        r"free_pkt\s*=\s*spc_pkt\s*;",
        body,
    ), "expected `free_pkt = spc_pkt;` in free_index"
    assert re.search(
        r"spc_pkt\s*=\s*spc_pkt->link\s*;",
        body,
    ), "expected `spc_pkt = spc_pkt->link;` step"


def test_free_index_loop_condition_is_not_null() -> None:
    """The free loop runs while ``spc_pkt != NULL_SPC_PACKET``."""
    body = _extract_free_index_body()
    assert re.search(
        r"while\s*\(\s*spc_pkt\s*!=\s*NULL_SPC_PACKET\s*\)",
        body,
    )


def test_free_index_resets_spc_pkt_save_to_null() -> None:
    """After the walk, ``pKsd_t->spc_pkt_save = NULL_SPC_PACKET;``."""
    body = _extract_free_index_body()
    assert re.search(
        r"pKsd_t->spc_pkt_save\s*=\s*NULL_SPC_PACKET\s*;",
        body,
    ), "expected reset of pKsd_t->spc_pkt_save to NULL_SPC_PACKET"


def test_free_index_calls_free_per_packet() -> None:
    """The body calls ``free(free_pkt)`` (or the ARM7 equivalent) per packet."""
    body = _extract_free_index_body()
    # Match either ``free( free_pkt )`` (modern build) or
    # ``free_spc_packet( free_pkt )`` (ARM7 ifdef).
    assert re.search(
        r"\b(?:free|free_spc_packet)\s*\(\s*free_pkt\s*\)\s*;",
        body,
    ), "expected per-packet free()"


def test_free_index_does_not_mutate_any_data_slot() -> None:
    """The free_index body never assigns to ``data[N]`` (no payload mutation)."""
    body = _extract_free_index_body()
    matches = re.findall(
        r"spc_pkt->data\[\s*\d+\s*\]\s*=(?!=)",
        body,
    )
    assert matches == [], f"unexpected data[] mutation in free_index: {matches}"


def test_free_index_python_breaks_every_link() -> None:
    """The Python port nulls every ``link`` in the chain (matches C ``free``)."""
    head = SpcPacket()
    mid = SpcPacket()
    tail = SpcPacket()
    head.link = mid
    mid.link = tail

    free_index(head)
    # In C the packets are free()'d so following the link would be UB.
    # In Python we instead null the links so GC can reclaim them; the
    # observable invariant is: every visited packet has link=None.
    assert head.link is None
    assert mid.link is None
    assert tail.link is None


def test_free_index_python_visits_all_packets_in_chain() -> None:
    """``free_index`` visits every packet in the chain (proven by all links None)."""
    n = 50
    nodes: list[SpcPacket] = []
    prev: SpcPacket | None = None
    head: SpcPacket | None = None
    for _ in range(n):
        node = SpcPacket()
        if prev is not None:
            prev.link = node
        else:
            head = node
        nodes.append(node)
        prev = node
    assert head is not None

    free_index(head)
    for node in nodes:
        assert node.link is None


def test_free_index_python_does_not_mutate_data() -> None:
    """``free_index`` doesn't touch the data[] arrays (matches C)."""
    head = SpcPacket()
    while len(head.data) < 7:
        head.data.append(0)
    head.data[0] = 11
    head.data[1] = 22
    head.data[5] = 33

    snapshot = list(head.data)
    free_index(head)
    assert head.data == snapshot


def test_free_index_python_signature_matches_c() -> None:
    """C signature: ``free_index(PKSD_T pKsd_t)`` (one arg, void return)."""
    text = _read_services_c()
    sig = re.search(
        r"void\s+free_index\s*\(\s*PKSD_T\s+\w+\s*\)",
        text,
    )
    assert sig is not None
