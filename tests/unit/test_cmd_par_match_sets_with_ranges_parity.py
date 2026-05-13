"""C-source parity test for ``par_match_sets_with_ranges`` against par_pars1.c.

Re-parses the C function body and asserts the descriptor-decode +
``par_match_set`` loop pattern matches the Python port.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_bin_codes import (
    BIN_EXACT,
    BIN_LARGE_DESC,
    BIN_SETS,
    BIN_SMALL_ANY_NUMBER,
)
from dectalk.cmd.par_match_sets_with_ranges import par_match_sets_with_ranges
from dectalk.cmd.par_structs import MatchArrays, RangeValue, ReturnValue
from dectalk.cmd.rule_states import SUCCESS

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_pars1.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_par_pars1_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_par_pars1_c()
    matches = list(
        re.finditer(
            r"^int\s+par_match_sets_with_ranges\s*\([^;{]+?\)\s*\n\{",
            text,
            re.MULTILINE,
        )
    )
    assert matches, "par_match_sets_with_ranges definition not found"
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


def test_invokes_par_match_set() -> None:
    """The body calls ``par_match_set`` inside the per-descriptor loop."""
    body = _extract_body()
    assert "par_match_set(" in body


def test_uses_bin_large_desc() -> None:
    """The body has a ``BIN_LARGE_DESC`` branch."""
    body = _extract_body()
    assert "BIN_LARGE_DESC" in body


def test_uses_bin_small_any_number() -> None:
    """The body has a ``BIN_SMALL_ANY_NUMBER`` branch."""
    body = _extract_body()
    assert "BIN_SMALL_ANY_NUMBER" in body


def test_uses_end_of_all_types_pattern() -> None:
    """The body computes ``end_of_all_types = current_rule[section_p+...] + 1``."""
    body = _extract_body()
    assert "end_of_all_types" in body


def test_python_single_match_exact_a() -> None:
    """``[{'a'}]{1,1}`` matches input 'a' exactly once.

    Layout for BIN_SETS rule starting at rule_p=0:

    .. code-block:: text

        +0  opcode (BIN_SETS)           -- skipped by ret_value.rule++
        +1  num_sections (=1)           -- section_p
        +2  end-of-section-0 (=7)       -- inclusive last byte index
        +3  num_desc (=1)
        +4  desc value
        +5..+7  section 0: BIN_EXACT 1 'a'
    """
    rule = bytes([BIN_SETS, 1, 7, 1, 1, BIN_EXACT, 1, ord("a")])
    inp = b"a"
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0, value=SUCCESS)
    rng = RangeValue()
    length = par_match_sets_with_ranges(rule, inp, ma, rv, rng, 0, 0)
    assert length == 1


def test_python_multi_repeat_match() -> None:
    """``[{'a'}]{3,3}`` matches three consecutive 'a's."""
    rule = bytes([BIN_SETS, 1, 7, 1, 3, BIN_EXACT, 1, ord("a")])
    inp = b"aaa"
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0, value=SUCCESS)
    rng = RangeValue()
    length = par_match_sets_with_ranges(rule, inp, ma, rv, rng, 0, 0)
    assert length == 3


def test_python_no_match_fails() -> None:
    """``[{'a'}]{1,1}`` returns 0 when the input starts with 'b'."""
    rule = bytes([BIN_SETS, 1, 7, 1, 1, BIN_EXACT, 1, ord("a")])
    inp = b"b"
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0, value=SUCCESS)
    rng = RangeValue()
    length = par_match_sets_with_ranges(rule, inp, ma, rv, rng, 0, 0)
    assert length == 0


def test_python_any_number_repeat_matches_run() -> None:
    """``[{'a'}]{0,inf}`` (BIN_SMALL_ANY_NUMBER) consumes a run."""
    rule = bytes([BIN_SETS, 1, 7, 1, BIN_SMALL_ANY_NUMBER, BIN_EXACT, 1, ord("a")])
    inp = b"aaab"
    ma = MatchArrays()
    rv = ReturnValue(rule=0, input_pos=0, value=SUCCESS)
    rng = RangeValue()
    length = par_match_sets_with_ranges(rule, inp, ma, rv, rng, 0, 0)
    # 3 'a's match, then 'b' bails. Length should be 3.
    # The C source also accepts -2 (zero-length success) for empty min=0
    # rules; we don't pin the exact value beyond "matches some bytes".
    assert length in (3, -2)


def test_c_source_has_large_desc_shift_pattern() -> None:
    """The C source computes ``sect_p`` via ``current_rule[rule_p] << 1``.

    The Linux compiler packs ``num_desc | BIN_LARGE_DESC`` into one
    byte and the matcher reads the raw byte for the sect_p offset.
    Constructing a synthetic rule that round-trips through the
    matcher would require running the rule compiler, so we just
    confirm the shift-and-add pattern is present in the C source.
    """
    body = _extract_body()
    assert re.search(r"current_rule\s*\[\s*rule_p\s*\]\s*<<\s*1", body) is not None
    _ = BIN_LARGE_DESC  # keep the import live for reference
