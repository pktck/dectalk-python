"""C-source parity test for ``par_match_set`` against par_pars1.c.

Re-parses the C function body and asserts the per-section loop +
``par_match_string`` invocation pattern matches the Python port.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_bin_codes import BIN_EXACT, BIN_OPERATION_MASK
from dectalk.cmd.par_match_set import par_match_set
from dectalk.cmd.par_structs import MatchArrays, RangeValue, ReturnValue
from dectalk.cmd.rule_states import FAIL, SUCCESS

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
            r"^int\s+par_match_set\s*\([^;{]+?\)\s*\n\{",
            text,
            re.MULTILINE,
        )
    )
    assert matches, "par_match_set definition not found"
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


def test_uses_par_match_string() -> None:
    """The C body calls par_match_string for each section's inner type."""
    body = _extract_body()
    assert "par_match_string(" in body


def test_uses_bin_operation_mask() -> None:
    """The inner dispatch ANDs ``current_rule[new_ret.rule]`` with ``BIN_OPERATION_MASK``."""
    body = _extract_body()
    assert re.search(r"BIN_OPERATION_MASK", body) is not None


def test_tracks_range_value_state() -> None:
    """The body mutates ``range_value->range_set`` and ``range_value->start``."""
    body = _extract_body()
    assert "range_value->range_set" in body
    assert "range_value->start" in body


def test_uses_par_copy_return_value() -> None:
    """The body uses ``par_copy_return_value`` to snapshot+restore state."""
    body = _extract_body()
    assert "par_copy_return_value(" in body


def _build_single_section_rule() -> tuple[bytes, int, int]:
    """Build a minimal one-section ``{'a'}`` set rule.

    Returns ``(rule_bytes, rule_p, sect_p)`` -- ``rule_p`` is the
    section-count byte and ``sect_p`` is the start of section 0.

    Layout:

    .. code-block:: text

        +0  num_sections (=1)
        +1  end-offset of section 0
        +2  BIN_EXACT
        +3  length (=1)
        +4  'a'
    """
    section_body_start = 2
    # End-offset is the *inclusive* last byte index of the section, per
    # the C source's `end_of_all_types = current_rule[...] + 1` pattern.
    section_body_end = 4
    rule = bytes(
        [
            1,  # num_sections
            section_body_end,  # end-offset of section 0
            BIN_EXACT,
            1,
            ord("a"),
        ]
    )
    return rule, 0, section_body_start


def test_python_match_single_section_hit() -> None:
    """One-section ``{'a'}`` set matches input 'a'."""
    rule, rule_p, sect_p = _build_single_section_rule()
    inp = b"a"
    ma = MatchArrays()
    rv = ReturnValue(value=SUCCESS)
    rng = RangeValue()
    length = par_match_set(rule, inp, rule_p, sect_p, 0, ma, rng, rv, 0)
    assert length == 1
    # On a successful match the C source leaves ret_value->value untouched.
    assert rv.value == SUCCESS


def test_python_match_single_section_miss() -> None:
    """One-section ``{'a'}`` set fails on input 'b'."""
    rule, rule_p, sect_p = _build_single_section_rule()
    inp = b"b"
    ma = MatchArrays()
    rv = ReturnValue(value=SUCCESS)
    rng = RangeValue()
    length = par_match_set(rule, inp, rule_p, sect_p, 0, ma, rng, rv, 0)
    assert length == 0
    assert rv.value == FAIL


def test_python_match_sets_range_value() -> None:
    """A successful match clears ``range_value.range_set`` to 2 on first hit."""
    rule, rule_p, sect_p = _build_single_section_rule()
    inp = b"a"
    ma = MatchArrays()
    rv = ReturnValue()
    rng = RangeValue()  # range_set initially 0
    par_match_set(rule, inp, rule_p, sect_p, 0, ma, rng, rv, 0)
    # First hit: range_set goes from 0 -> 2.
    assert rng.range_set == 2
    assert rng.start == 0


def test_python_match_two_section_picks_second() -> None:
    """Two-section ``{'a','b'}`` set matches 'b' via second section."""
    # Layout:
    # +0  num_sections (=2)
    # +1  end-offset of section 0
    # +2  end-offset of section 1
    # +3..+5 section 0: [BIN_EXACT, 1, 'a']
    # +6..+8 section 1: [BIN_EXACT, 1, 'b']
    rule = bytes(
        [
            2,
            5,  # end of section 0 (inclusive last byte index)
            8,  # end of section 1 (inclusive last byte index)
            BIN_EXACT,
            1,
            ord("a"),
            BIN_EXACT,
            1,
            ord("b"),
        ]
    )
    rule_p = 0
    sect_p = 3
    inp = b"b"
    ma = MatchArrays()
    rv = ReturnValue()
    rng = RangeValue()
    length = par_match_set(rule, inp, rule_p, sect_p, 0, ma, rng, rv, 0)
    assert length == 1


def test_python_uses_bin_operation_mask_constant() -> None:
    """The ``BIN_OPERATION_MASK`` constant is 0x1F (low 5 bits)."""
    assert BIN_OPERATION_MASK == 0x1F
