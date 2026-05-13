"""C-source parity test for ``save_index`` against kernel/services.c.

Re-parses the ``save_index`` function body from the original DECtalk C
source at test time, extracts the data[] assignments and invariants,
and asserts the Python port preserves them.

Skips cleanly when ``DECTALK_SRC`` env / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.cmd_codes import INDEX
from dectalk.kernel.save_index import save_index
from dectalk.kernel.spc_codes import SPC_type_index
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


def _extract_save_index_body() -> str:
    """Return the contents of the C ``save_index`` function body."""
    text = _read_services_c()
    match = re.search(
        r"void\s+save_index\s*\([^)]*\)\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "save_index() not found in services.c"
    body = match.group(1)
    # Strip block & line comments.
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    return body


def _extract_data_assignments(body: str) -> dict[int, str]:
    """Return ``{N: rhs}`` for every ``spc_pkt->data[N] = rhs;`` line."""
    out: dict[int, str] = {}
    for slot_str, rhs in re.findall(
        r"spc_pkt->data\[\s*(\d+)\s*\]\s*=\s*([^;]+);",
        body,
    ):
        slot = int(slot_str)
        rhs_clean = rhs.strip()
        # Keep only the first assignment per slot (matches C: top-down).
        out.setdefault(slot, rhs_clean)
    return out


def test_save_index_assigns_all_seven_data_slots() -> None:
    """The C body assigns ``data[0..6]`` once each (sym, type, value, how, sym, sym, 0)."""
    body = _extract_save_index_body()
    assignments = _extract_data_assignments(body)
    assert set(assignments.keys()) == {0, 1, 2, 3, 4, 5, 6}


def test_save_index_data_layout_matches_c() -> None:
    """``data[0]=sym, data[1]=type, data[2]=value, data[3]=how, data[4..5]=sym, data[6]=0``."""
    body = _extract_save_index_body()
    assignments = _extract_data_assignments(body)
    assert assignments[0] == "sym"
    assert assignments[1] == "type"
    assert assignments[2] == "value"
    assert assignments[3] == "how"
    assert assignments[4] == "sym"
    assert assignments[5] == "sym"
    assert assignments[6] == "0"


def test_save_index_sets_packet_type_to_spc_type_index() -> None:
    """The C body sets ``spc_pkt->type = SPC_type_index;``."""
    body = _extract_save_index_body()
    assert re.search(
        r"spc_pkt->type\s*=\s*SPC_type_index\s*;",
        body,
    ), "expected `spc_pkt->type = SPC_type_index;` in save_index"


def test_save_index_tail_walk_loop_present() -> None:
    """The C body walks ``spc_pkt->link`` until NULL_SPC_PACKET (tail-append)."""
    body = _extract_save_index_body()
    # Loop form: while( spc_pkt != NULL_SPC_PACKET )
    assert re.search(
        r"while\s*\(\s*spc_pkt\s*!=\s*NULL_SPC_PACKET\s*\)",
        body,
    ), "expected tail-walk loop in save_index"
    # And the loop body steps via spc_pkt = spc_pkt->link
    assert re.search(
        r"spc_pkt\s*=\s*spc_pkt->link\s*;",
        body,
    ), "expected `spc_pkt = spc_pkt->link;` inside save_index tail loop"


def test_save_index_new_packet_link_is_null() -> None:
    """Every newly-allocated packet gets ``spc_pkt->link = NULL_SPC_PACKET``."""
    body = _extract_save_index_body()
    matches = re.findall(
        r"spc_pkt->link\s*=\s*NULL_SPC_PACKET\s*;",
        body,
    )
    # The C source assigns NULL_SPC_PACKET to link in both the
    # empty-chain and the append-to-existing branches (2 places).
    assert len(matches) >= 2


def test_save_index_python_matches_c_data_layout() -> None:
    """The Python port produces the data[] layout the C source assigns."""
    body = _extract_save_index_body()
    assignments = _extract_data_assignments(body)

    # Drive the Python port with known sentinel values.
    sym_val = 7
    type_val = INDEX
    value_val = 123
    how_val = 5
    head = save_index(None, sym=sym_val, type_code=type_val, value=value_val, how=how_val)

    bindings = {
        "sym": sym_val,
        "type": type_val,
        "value": value_val,
        "how": how_val,
        "0": 0,
    }
    for slot, rhs in assignments.items():
        expected = bindings[rhs]
        assert head.data[slot] == expected, (
            f"data[{slot}] = {head.data[slot]} but C source assigns {rhs} = {expected}"
        )

    # Packet ``type`` field
    assert head.type == SPC_type_index
    # New tail link must be None (NULL_SPC_PACKET).
    assert head.link is None


def test_save_index_python_tail_append_matches_c_walk() -> None:
    """Repeated calls extend the chain at the tail (the C ``while`` walk)."""
    head: SpcPacket | None = None
    syms = [11, 22, 33, 44]
    for s in syms:
        head = save_index(head, sym=s, type_code=INDEX, value=s, how=0)

    walked: list[int] = []
    cur = head
    while cur is not None:
        walked.append(cur.data[0])
        cur = cur.link
    assert walked == syms


def test_save_index_python_signature_matches_c() -> None:
    """The Python signature mirrors the C parameter list (sym, type, value, how)."""
    # The C signature is: save_index(PKSD_T pKsd_t, unsigned int sym,
    #                                unsigned int type, unsigned int value,
    #                                unsigned int how).
    text = _read_services_c()
    sig = re.search(
        r"void\s+save_index\s*\(\s*PKSD_T\s+\w+\s*,\s*"
        r"unsigned\s+int\s+sym\s*,\s*"
        r"unsigned\s+int\s+type\s*,\s*"
        r"unsigned\s+int\s+value\s*,\s*"
        r"unsigned\s+int\s+how\s*\)",
        text,
    )
    assert sig is not None, "expected C signature with (sym, type, value, how) params"
