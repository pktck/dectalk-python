"""C-source parity tests for ``adjust_allo`` / ``set_index_allo``.

Re-parses both functions from ``kernel/services.c`` and asserts the
Python ports preserve:

- ``adjust_allo``: predicate ``data[5] >= which`` and mutation
  ``data[5] += direction``.
- ``set_index_allo``: predicate ``data[4] == nphone`` and mutation
  ``data[5] = nallo``.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.kernel.adjust_allo import adjust_allo, set_index_allo
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


def _extract_body(func: str) -> str:
    """Return the body of the C function ``func``."""
    text = _read_services_c()
    match = re.search(
        rf"void\s+{re.escape(func)}\s*\([^)]*\)\s*\{{(.+?)^\}}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, f"{func}() not found in services.c"
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    return body


# ---------------------------------------------------------------------------
# adjust_allo
# ---------------------------------------------------------------------------


def test_adjust_allo_predicate_is_data5_ge_which() -> None:
    """The C source's adjustment trigger is ``data[5] >= which``."""
    body = _extract_body("adjust_allo")
    assert re.search(
        r"if\s*\(\s*\(?\s*spc_pkt->data\[\s*5\s*\]\s*>=\s*which\s*\)?\s*\)",
        body,
    ), "expected `if (spc_pkt->data[5] >= which)` predicate"


def test_adjust_allo_mutation_is_data5_plus_direction() -> None:
    """The C source mutates ``data[5] += direction`` (only data[5])."""
    body = _extract_body("adjust_allo")
    data5_pat = (
        r"spc_pkt->data\[\s*5\s*\]\s*=\s*\(unsigned int\)\s*\(\s*\(int\)\s*"
        r"\(?\s*spc_pkt->data\[\s*5\s*\]\s*\)?\s*\+\s*direction\s*\)\s*;"
    )
    assert re.search(data5_pat, body), "expected `data[5] = (int)data[5] + direction` mutation"

    assigns = re.findall(
        r"spc_pkt->data\[\s*(\d+)\s*\]\s*=",
        body,
    )
    # Only data[5] should be mutated.
    assert set(assigns) == {"5"}


def test_adjust_allo_walks_via_link() -> None:
    """``adjust_allo`` walks ``spc_pkt = spc_pkt->link`` in a while loop."""
    body = _extract_body("adjust_allo")
    assert re.search(
        r"while\s*\(\s*spc_pkt\s*!=\s*NULL_SPC_PACKET\s*\)",
        body,
    )
    assert re.search(
        r"spc_pkt\s*=\s*spc_pkt->link\s*;",
        body,
    )


def test_adjust_allo_python_predicate_matches_c() -> None:
    """Python's predicate matches the C ``data[5] >= which`` rule."""
    cases = [
        # (data5, which) -> should_match
        (5, 5, True),  # equal
        (6, 5, True),
        (4, 5, False),
        (0, 0, True),
        (-1, 0, False),
    ]
    for data5, which, should_match in cases:
        pkt = SpcPacket()
        while len(pkt.data) < 6:
            pkt.data.append(0)
        pkt.data[5] = data5
        original = data5
        adjust_allo(pkt, which=which, direction=10)
        if should_match:
            assert pkt.data[5] == original + 10, f"data5={data5} which={which}: expected match"
        else:
            assert pkt.data[5] == original, f"data5={data5} which={which}: expected NO match"


def test_adjust_allo_python_signature_matches_c() -> None:
    """C signature: ``adjust_allo(PKSD_T, unsigned int which, int direction)``."""
    text = _read_services_c()
    sig = re.search(
        r"void\s+adjust_allo\s*\(\s*PKSD_T\s+\w+\s*,\s*"
        r"unsigned\s+int\s+which\s*,\s*"
        r"int\s+direction\s*\)",
        text,
    )
    assert sig is not None


# ---------------------------------------------------------------------------
# set_index_allo
# ---------------------------------------------------------------------------


def test_set_index_allo_predicate_is_data4_eq_nphone() -> None:
    """The C source's predicate is ``data[4] == nphone``."""
    body = _extract_body("set_index_allo")
    assert re.search(
        r"if\s*\(\s*spc_pkt->data\[\s*4\s*\]\s*==\s*nphone\s*\)",
        body,
    ), "expected `if (spc_pkt->data[4] == nphone)`"


def test_set_index_allo_mutation_is_data5_eq_nallo() -> None:
    """The C source mutates ``data[5] = nallo`` (verbatim, no arithmetic)."""
    body = _extract_body("set_index_allo")
    assert re.search(
        r"spc_pkt->data\[\s*5\s*\]\s*=\s*nallo\s*;",
        body,
    ), "expected `data[5] = nallo` mutation"
    # Only data[5] is the LHS of an assignment (exclude == predicates).
    assigns = re.findall(
        r"spc_pkt->data\[\s*(\d+)\s*\]\s*=(?!=)",
        body,
    )
    assert set(assigns) == {"5"}


def test_set_index_allo_walks_via_link() -> None:
    """``set_index_allo`` walks the chain via ``spc_pkt = spc_pkt->link``."""
    body = _extract_body("set_index_allo")
    assert re.search(
        r"while\s*\(\s*spc_pkt\s*!=\s*NULL_SPC_PACKET\s*\)",
        body,
    )
    assert re.search(
        r"spc_pkt\s*=\s*spc_pkt->link\s*;",
        body,
    )


def test_set_index_allo_python_predicate_matches_c() -> None:
    """Python's predicate matches ``data[4] == nphone`` exactly (no ordering)."""
    cases = [
        # (data4, nphone) -> should_match
        (3, 3, True),
        (4, 3, False),
        (2, 3, False),
        (0, 0, True),
        (-1, -1, True),  # equality on negatives works in Python
    ]
    for data4, nphone, should_match in cases:
        pkt = SpcPacket()
        while len(pkt.data) < 6:
            pkt.data.append(0)
        pkt.data[4] = data4
        pkt.data[5] = 999  # sentinel
        set_index_allo(pkt, nphone=nphone, nallo=42)
        if should_match:
            assert pkt.data[5] == 42, f"data4={data4} nphone={nphone}: expected match"
        else:
            assert pkt.data[5] == 999, f"data4={data4} nphone={nphone}: expected NO match"


def test_set_index_allo_python_signature_matches_c() -> None:
    """C signature: ``set_index_allo(PKSD_T, unsigned int nphone, unsigned int nallo)``."""
    text = _read_services_c()
    sig = re.search(
        r"void\s+set_index_allo\s*\(\s*PKSD_T\s+\w+\s*,\s*"
        r"unsigned\s+int\s+nphone\s*,\s*"
        r"unsigned\s+int\s+nallo\s*\)",
        text,
    )
    assert sig is not None
