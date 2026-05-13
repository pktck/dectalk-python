"""C-source parity test for ``par_search_for_word`` against par_pars1.c.

Asserts the binary-search loop body and the structural use of
``dict_point[]`` / ``dict_index_table[]`` / ``dict_data_table[]``
are preserved, plus the Python stub returns ``0`` (no match) and
does not mutate its output buffer.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_search_for_word import par_search_for_word

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_pars1.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_par_pars1_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_par_pars1_c()
    # The C source has both a prototype near line 543 and a definition near
    # line 3677. The definition has the body; the prototype is one-line.
    matches = list(
        re.finditer(
            r"int\s+par_search_for_word\s*\([^;{]+?\)\s*\n\{",
            text,
            re.MULTILINE,
        )
    )
    assert matches, "par_search_for_word definition not found"
    start = matches[-1].start()
    body_start = text.index("{", start)
    depth = 1
    i = body_start + 1
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    return text[start:i]


def test_uses_dict_point_for_bounds() -> None:
    """The C body bisects between ``dict_point[dict_number].start`` and ``.end``."""
    body = _extract_body()
    assert re.search(r"dict_point\s*\[\s*dict_number\s*\]\s*\.\s*start", body)
    assert re.search(r"dict_point\s*\[\s*dict_number\s*\]\s*\.\s*end", body)


def test_uses_dict_index_table_in_comparator() -> None:
    """The bisection comparator pokes through ``dict_index_table[pos]``."""
    body = _extract_body()
    assert re.search(r"dict_data_table\s*\+\s*dict_index_table\s*\[\s*pos\s*\]", body)


def test_subtracts_one_from_dict_num() -> None:
    """The first body statement is ``dict_number = dict_num - 1``."""
    body = _extract_body()
    assert re.search(r"dict_number\s*=\s*dict_num\s*-\s*1\s*;", body)


def test_uses_midpoint_bisection() -> None:
    """The body computes ``pos = (rev_same + for_same) >> 1`` each step."""
    body = _extract_body()
    assert re.search(
        r"pos\s*=\s*\(\s*\(\s*rev_same\s*\+\s*for_same\s*\)\s*>>\s*1\s*\)",
        body,
    )


def test_short_circuit_on_dict_state_flag() -> None:
    """``if (dict_state_flag)`` short-circuits to ``return(1)`` on first hit."""
    body = _extract_body()
    assert re.search(r"if\s*\(\s*dict_state_flag\s*\)", body)


def test_returns_zero_on_no_match() -> None:
    """The body has a ``return(0)`` exit path."""
    body = _extract_body()
    assert re.search(r"return\s*\(\s*0\s*\)\s*;", body)


def test_python_returns_zero_on_stub() -> None:
    """The Python stub always reports no match."""
    output = bytearray(64)
    assert par_search_for_word(b"hello", 5, output, 1, 0) == 0


def test_python_stub_does_not_mutate_output() -> None:
    """The stub leaves the output buffer untouched."""
    output = bytearray(b"\x01" * 32)
    par_search_for_word(b"hello", 5, output, 1, 0)
    assert output == bytearray(b"\x01" * 32)


def test_python_stub_handles_short_search_flag() -> None:
    """The stub still returns 0 with ``dict_state_flag == 1``."""
    output = bytearray(16)
    assert par_search_for_word(b"foo", 3, output, 2, 1) == 0


def test_dict_point_is_loaded_on_linux() -> None:
    """``par_rule2.h`` (linked on Linux) populates ``dict_point[27]``."""
    par_rule2 = (
        Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_rule2.h"
    )
    if not par_rule2.is_file():
        pytest.skip("par_rule2.h not available")
    text = par_rule2.read_bytes().replace(b"\r", b"").decode("latin-1")
    # Header has the const definition; this fact is what the deferred
    # docstring promises will eventually unblock a real implementation.
    assert "const dict_pointers_t dict_point[27]" in text
    assert "const unsigned char dict_data_table" in text
    assert "const int dict_index_table" in text
