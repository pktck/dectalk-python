"""C-source parity test for the ``perform_action_funcs`` dispatch table.

Re-parses the static table definition in par_pars1.c (lines 651-704)
at test time and asserts the Python dispatch table maps each opcode
to the corresponding action function (or to a stub for ERROR slots).

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_perform_action_funcs import (
    PERFORM_ACTION_FUNCS,
    PERFORM_ACTION_FUNCS_GCN,
)

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_pars1.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_dispatch_table() -> tuple[dict[int, str], dict[int, str]]:
    """Parse the perform_action_funcs initialiser into opcode -> name maps.

    Returns ``(non_gcn, gcn)`` where each map covers all 0x20 opcodes.
    """
    text = _C_FILE.read_text(encoding="latin-1").replace("\r\n", "\n")

    # Locate the perform_action_funcs definition body (between the
    # opening "= {" and the closing "};").
    start = text.find("perform_action_funcs[0x20]")
    assert start >= 0, "perform_action_funcs definition not found"
    brace_open = text.find("= {", start)
    assert brace_open >= 0, "perform_action_funcs initialiser not found"
    body_start = brace_open + len("= {")
    # The body ends at "};" that closes the initialiser.
    body_end = text.find("};", body_start)
    assert body_end >= 0, "perform_action_funcs end brace not found"
    body = text[body_start:body_end]

    # Build a context-aware scanner that tracks `#ifndef GERMAN_COMPOUND_NOUNS`
    # vs the `#else` branch.
    non_gcn: dict[int, str] = {}
    gcn: dict[int, str] = {}
    branch = "both"  # before any preproc directive both maps see the entry

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line.startswith("#ifndef GERMAN_COMPOUND_NOUNS"):
            branch = "non_gcn"
            continue
        if line.startswith("#else"):
            branch = "gcn"
            continue
        if line.startswith("#endif"):
            branch = "both"
            continue
        # Match the comment-prefixed entry: /* 0xNN */  func_name,
        m = re.match(r"/\*\s*0x([0-9A-Fa-f]+)\s*\*/\s*([A-Za-z_][A-Za-z_0-9]*)\s*,?", line)
        if not m:
            continue
        opcode = int(m.group(1), 16)
        name = m.group(2)
        if branch in ("both", "non_gcn"):
            non_gcn[opcode] = name
        if branch in ("both", "gcn"):
            gcn[opcode] = name

    return non_gcn, gcn


# Maps from C function name to the matching Python adapter function name
# (each adapter wraps the corresponding port to the uniform dispatch
# signature). ERROR_func1 / ERROR_func2 map to the local stubs.
_NAME_TO_PY_NAME: dict[str, str] = {
    "ERROR_func1": "_ERROR_func1",
    "ERROR_func2": "_ERROR_func2",
    "par_delete_string": "_adapt_delete_string",
    "par_save_string": "_adapt_save_string",
    "par_replace_string": "_adapt_replace_string",
    "par_insert_string": "_adapt_insert_string",
    "par_insert_string_after": "_adapt_insert_string_after",
    "par_insert_string_before": "_adapt_insert_string_before",
    "par_compound_break": "_adapt_compound_break",
    "par_dom_dict_search": "_adapt_dom_dict_search",
    "par_status_string": "_adapt_status_string",
    "par_check_word_string": "_adapt_check_word_string",
}


def test_dispatch_table_has_32_entries() -> None:
    """The dispatch table has 0x20 entries -- one per 5-bit opcode."""
    non_gcn, gcn = _parse_dispatch_table()
    assert len(non_gcn) == 0x20
    assert len(gcn) == 0x20
    assert len(PERFORM_ACTION_FUNCS) == 0x20
    assert len(PERFORM_ACTION_FUNCS_GCN) == 0x20


def test_dispatch_table_non_gcn_matches_c() -> None:
    """The non-GERMAN_COMPOUND_NOUNS dispatch table matches the C source."""
    non_gcn, _ = _parse_dispatch_table()
    for opcode, c_name in non_gcn.items():
        expected_py_name = _NAME_TO_PY_NAME.get(c_name)
        assert expected_py_name is not None, f"no Python adapter for {c_name}"
        actual = PERFORM_ACTION_FUNCS[opcode]
        assert actual.__name__ == expected_py_name, (
            f"opcode 0x{opcode:02X}: expected {expected_py_name} "
            f"(C: {c_name}), got {actual.__name__}"
        )


def test_dispatch_table_gcn_matches_c() -> None:
    """The GERMAN_COMPOUND_NOUNS dispatch table matches the C source."""
    _, gcn = _parse_dispatch_table()
    for opcode, c_name in gcn.items():
        expected_py_name = _NAME_TO_PY_NAME.get(c_name)
        assert expected_py_name is not None, f"no Python adapter for {c_name}"
        actual = PERFORM_ACTION_FUNCS_GCN[opcode]
        assert actual.__name__ == expected_py_name, (
            f"GCN opcode 0x{opcode:02X}: expected {expected_py_name} "
            f"(C: {c_name}), got {actual.__name__}"
        )


def test_dispatch_tables_differ_only_at_0x1b_and_0x1c() -> None:
    """GCN diverges from non-GCN at 0x1B (compound_break) and 0x1C (error)."""
    for i in range(0x20):
        if i in (0x1B, 0x1C):
            continue
        assert PERFORM_ACTION_FUNCS[i] is PERFORM_ACTION_FUNCS_GCN[i], (
            f"opcode 0x{i:02X} should match between GCN and non-GCN"
        )
    # 0x1B and 0x1C must differ.
    assert PERFORM_ACTION_FUNCS[0x1B] is not PERFORM_ACTION_FUNCS_GCN[0x1B]
    assert PERFORM_ACTION_FUNCS[0x1C] is not PERFORM_ACTION_FUNCS_GCN[0x1C]
