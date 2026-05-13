"""C-source parity test for ``cm_cmd_loadv`` against cm_copt.c.

Re-parses the body of ``cm_cmd_loadv`` (lines 1435-1480 in
``src/dapi/src/cmd/cm_copt.c``) using brace-depth tracking and
asserts the load-bearing structural invariants:

- The 60-byte temporary buffer ``unsigned char temp[60]`` is preserved.
- The ``params[0] < 0 || params[0] > 9`` slot-range check is preserved.
- The ``insertflag`` early-return (``loadv can't be called from setv``)
  is preserved.
- The terminator check ``temp[j] == ']'`` is preserved.

Plus behavioural tests of the Python architectural shim.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.cm_cmd_loadv import LoadvResult, cm_cmd_loadv
from dectalk.cmd.cmd_states import CMD_bad_param, CMD_bad_value, CMD_success

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/cm_copt.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_cm_copt_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Locate the ``cm_cmd_loadv`` body in cm_copt.c via brace tracking."""
    text = _read_cm_copt_c()
    decl = re.search(r"\bint\s+cm_cmd_loadv\s*\(", text)
    assert decl is not None, "cm_cmd_loadv declaration not found in cm_copt.c"
    brace_start = text.index("{", decl.end())
    depth = 1
    i = brace_start + 1
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    assert depth == 0, "Unbalanced braces while extracting cm_cmd_loadv body"
    return text[brace_start + 1 : i - 1]


# -- Structural assertions on the C body -----------------------------------


def test_c_body_declares_temp_buffer_of_60_bytes() -> None:
    """The C body still declares ``unsigned char temp[60]``."""
    body = _extract_body()
    assert re.search(r"unsigned\s+char\s+temp\s*\[\s*60\s*\]\s*;", body), (
        "expected ``unsigned char temp[60];`` in cm_cmd_loadv body"
    )


def test_c_body_validates_slot_range() -> None:
    """The C body still checks ``params[0] < 0 || params[0] > 9``."""
    body = _extract_body()
    pattern = (
        r"\(\s*pCmd_t\s*->\s*params\s*\[\s*0\s*\]\s*\)\s*<\s*0"
        r"\s*\|\|\s*pCmd_t\s*->\s*params\s*\[\s*0\s*\]\s*>\s*9"
    )
    assert re.search(pattern, body), "expected slot-range check params[0]<0 || params[0]>9"


def test_c_body_guards_on_insertflag() -> None:
    """The C body still has the ``insertflag`` early-return."""
    body = _extract_body()
    # The C source does ``if (pCmd_t->insertflag) { return CMD_bad_param; }``.
    pattern = r"if\s*\(\s*pCmd_t\s*->\s*insertflag\s*\)\s*\{[^}]*return\s*\(?\s*CMD_bad_param"
    assert re.search(pattern, body, re.DOTALL), (
        "expected ``if (pCmd_t->insertflag) { return CMD_bad_param; }``"
    )


def test_c_body_checks_close_bracket_terminator() -> None:
    """The C body still terminates on the ``]`` byte."""
    body = _extract_body()
    assert re.search(r"temp\s*\[\s*j\s*\]\s*==\s*'\]'", body), (
        "expected ``temp[j] == ']'`` terminator check"
    )


# -- Behavioural tests of the Python shim ----------------------------------


def test_python_returns_dataclass_result() -> None:
    """The Python port returns a :class:`LoadvResult`."""
    result = cm_cmd_loadv(0, b"hello]", insert_flag=False)
    assert isinstance(result, LoadvResult)


def test_python_slot_zero_succeeds() -> None:
    """Slot 0 is the lowest valid voice slot."""
    result = cm_cmd_loadv(0, b"abc]", insert_flag=False)
    assert result.status == CMD_success
    assert result.voice_slot == 0
    # Trailing ']' is stripped on success.
    assert result.body == b"abc"


def test_python_slot_nine_succeeds() -> None:
    """Slot 9 is the highest valid voice slot."""
    result = cm_cmd_loadv(9, b"x]", insert_flag=False)
    assert result.status == CMD_success
    assert result.voice_slot == 9
    assert result.body == b"x"


def test_python_each_slot_zero_through_nine_succeeds() -> None:
    """Every slot in 0..9 returns CMD_success."""
    for slot in range(10):
        result = cm_cmd_loadv(slot, b"v]", insert_flag=False)
        assert result.status == CMD_success
        assert result.voice_slot == slot


def test_python_negative_slot_returns_bad_value() -> None:
    """Slot -1 is out of range -- CMD_bad_value."""
    result = cm_cmd_loadv(-1, b"abc]", insert_flag=False)
    assert result.status == CMD_bad_value
    assert result.body == b""


def test_python_slot_ten_returns_bad_value() -> None:
    """Slot 10 is out of range -- CMD_bad_value."""
    result = cm_cmd_loadv(10, b"abc]", insert_flag=False)
    assert result.status == CMD_bad_value
    assert result.body == b""


def test_python_insert_flag_returns_bad_param() -> None:
    """``insert_flag`` truthy returns CMD_bad_param (loadv can't run from setv)."""
    result = cm_cmd_loadv(3, b"abc]", insert_flag=True)
    assert result.status == CMD_bad_param
    assert result.body == b""


def test_python_insert_flag_takes_priority_over_slot_check() -> None:
    """``insert_flag`` short-circuits before the slot-range check, like C."""
    # Even with an out-of-range slot, the C body's first check is
    # ``if (pCmd_t->insertflag) return CMD_bad_param;``. Python mirrors that.
    result = cm_cmd_loadv(99, b"abc]", insert_flag=True)
    assert result.status == CMD_bad_param


def test_python_body_at_max_length_succeeds() -> None:
    """A 59-byte body (the C ``sizeof(temp) - 1`` limit) succeeds."""
    body = b"a" * 58 + b"]"  # 59 bytes total, terminator included.
    result = cm_cmd_loadv(0, body, insert_flag=False)
    assert result.status == CMD_success
    assert result.body == b"a" * 58


def test_python_body_over_max_length_returns_bad_param() -> None:
    """A 60+ byte body trips the C ``j >= sizeof(temp) - 1`` guard."""
    body = b"a" * 60 + b"]"  # 61 bytes -- well past 59.
    result = cm_cmd_loadv(0, body, insert_flag=False)
    assert result.status == CMD_bad_param
    assert result.body == b""


def test_python_body_exactly_sixty_bytes_returns_bad_param() -> None:
    """A 60-byte body (one over the 59-byte limit) fails."""
    body = b"a" * 59 + b"]"  # 60 bytes total.
    result = cm_cmd_loadv(0, body, insert_flag=False)
    assert result.status == CMD_bad_param


def test_python_body_without_terminator_is_kept_verbatim() -> None:
    """A body that doesn't end in ``]`` is returned unchanged on success."""
    # The C source always terminates on ']' because the parser feeds
    # the loop until it sees one; this test exercises the Python shim's
    # defensive ``endswith`` strip so non-bracketed input is preserved.
    result = cm_cmd_loadv(0, b"hello", insert_flag=False)
    assert result.status == CMD_success
    assert result.body == b"hello"


def test_python_empty_body_succeeds() -> None:
    """An empty body is valid -- the C loop just terminates immediately."""
    result = cm_cmd_loadv(0, b"]", insert_flag=False)
    assert result.status == CMD_success
    assert result.body == b""
