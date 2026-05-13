"""C-source parity test for ``adjust_index`` against kernel/services.c.

Re-parses the C function body, extracts:

- the chain-walk predicate ``data[5] >= which + data[6]``,
- the two adjustments ``data[4] += direction`` and ``data[6] += del``,
- the lack of any other mutation,

and asserts the Python port behaves identically over a representative
table of packet states.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.kernel.adjust_index import adjust_index
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


def _extract_adjust_index_body() -> str:
    """Return the C ``adjust_index`` function body."""
    text = _read_services_c()
    match = re.search(
        r"void\s+adjust_index\s*\([^)]*\)\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "adjust_index() not found in services.c"
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    return body


def test_adjust_index_predicate_is_data5_ge_which_plus_data6() -> None:
    """The C source's adjustment trigger is ``data[5] >= which + data[6]``."""
    body = _extract_adjust_index_body()
    assert re.search(
        r"if\s*\(\s*spc_pkt->data\[\s*5\s*\]\s*>=\s*which\s*\+\s*\(int\)\s*spc_pkt->data\[\s*6\s*\]\s*\)",
        body,
    ), "expected `if ( spc_pkt->data[5] >= which+(int)spc_pkt->data[6] )` predicate"


def test_adjust_index_mutations_are_data4_direction_and_data6_del() -> None:
    """The C source mutates ``data[4] += direction`` and ``data[6] += del`` (no others)."""
    body = _extract_adjust_index_body()
    # data[4] gets += direction
    data4_pat = (
        r"spc_pkt->data\[\s*4\s*\]\s*=\s*\(unsigned int\)\s*\(\s*\(int\)\s*"
        r"\(?\s*spc_pkt->data\[\s*4\s*\]\s*\)?\s*\+\s*direction\s*\)\s*;"
    )
    assert re.search(data4_pat, body), "expected `data[4] = (int)data[4] + direction` mutation"
    # data[6] gets += del
    data6_pat = (
        r"spc_pkt->data\[\s*6\s*\]\s*=\s*\(unsigned int\)\s*\(\s*\(int\)\s*"
        r"\(?\s*spc_pkt->data\[\s*6\s*\]\s*\)?\s*\+\s*del\s*\)\s*;"
    )
    assert re.search(data6_pat, body), "expected `data[6] = (int)data[6] + del` mutation"

    # Confirm there are no other ``data[N] =`` assignments inside the
    # adjust_index body (no spillover into data[5], etc.).
    other_assigns = re.findall(
        r"spc_pkt->data\[\s*(\d+)\s*\]\s*=",
        body,
    )
    # Convert to set: only 4 and 6 should be mutated.
    assert set(other_assigns) == {"4", "6"}


def test_adjust_index_walks_via_link() -> None:
    """The C source walks via ``spc_pkt = spc_pkt->link;`` (full chain)."""
    body = _extract_adjust_index_body()
    assert re.search(
        r"spc_pkt\s*=\s*spc_pkt->link\s*;",
        body,
    )
    # The loop is ``while (spc_pkt != NULL_SPC_PACKET)`` (every packet visited).
    assert re.search(
        r"while\s*\(\s*spc_pkt\s*!=\s*NULL_SPC_PACKET\s*\)",
        body,
    )


def test_adjust_index_python_predicate_matches_c() -> None:
    """For every representative (data[5], data[6], which) the Python port matches."""
    cases = [
        # (data5, data6, which) — expected_match?
        (10, 0, 5, True),  # 10 >= 5+0
        (10, 0, 10, True),  # 10 >= 10+0 (==)
        (10, 0, 11, False),  # 10 < 11+0
        (10, 5, 5, True),  # 10 >= 5+5
        (10, 5, 6, False),  # 10 < 6+5
        (10, -3, 13, True),  # 10 >= 13+(-3)
        (10, -3, 14, False),  # 10 < 14+(-3)
    ]
    for data5, data6, which, should_match in cases:
        pkt = SpcPacket()
        while len(pkt.data) < 7:
            pkt.data.append(0)
        pkt.data[4] = 100
        pkt.data[5] = data5
        pkt.data[6] = data6

        adjust_index(pkt, which=which, direction=1, delete=2)
        if should_match:
            assert pkt.data[4] == 101, f"data5={data5} data6={data6} which={which}: expected match"
            assert pkt.data[6] == data6 + 2
        else:
            assert pkt.data[4] == 100, (
                f"data5={data5} data6={data6} which={which}: expected NO match"
            )
            assert pkt.data[6] == data6


def test_adjust_index_python_chain_walk_visits_every_packet() -> None:
    """Every packet on the chain is visited regardless of position."""
    head = SpcPacket()
    mid = SpcPacket()
    tail = SpcPacket()
    head.link = mid
    mid.link = tail
    for pkt in (head, mid, tail):
        while len(pkt.data) < 7:
            pkt.data.append(0)
        pkt.data[4] = 0
        pkt.data[5] = 100  # all match
        pkt.data[6] = 0

    adjust_index(head, which=10, direction=7, delete=0)
    assert head.data[4] == 7
    assert mid.data[4] == 7
    assert tail.data[4] == 7


def test_adjust_index_python_only_mutates_data4_and_data6() -> None:
    """Mutations are limited to ``data[4]`` and ``data[6]`` per the C source."""
    pkt = SpcPacket()
    while len(pkt.data) < 7:
        pkt.data.append(0)
    pkt.data[0] = 11
    pkt.data[1] = 22
    pkt.data[2] = 33
    pkt.data[3] = 44
    pkt.data[4] = 55
    pkt.data[5] = 100  # match
    pkt.data[6] = 5

    adjust_index(pkt, which=10, direction=1, delete=1)
    assert pkt.data[0] == 11  # untouched
    assert pkt.data[1] == 22
    assert pkt.data[2] == 33
    assert pkt.data[3] == 44
    assert pkt.data[4] == 56
    assert pkt.data[5] == 100  # data[5] is NOT mutated by adjust_index
    assert pkt.data[6] == 6


def test_adjust_index_python_signature_matches_c() -> None:
    """The C signature is ``adjust_index(PKSD_T, unsigned int which, int direction, int del)``."""
    text = _read_services_c()
    sig = re.search(
        r"void\s+adjust_index\s*\(\s*PKSD_T\s+\w+\s*,\s*"
        r"unsigned\s+int\s+which\s*,\s*"
        r"int\s+direction\s*,\s*"
        r"int\s+del\s*\)",
        text,
    )
    assert sig is not None
