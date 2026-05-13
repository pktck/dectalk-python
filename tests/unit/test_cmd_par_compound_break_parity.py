"""C-source parity test for ``par_compound_break`` against par_pars1.c.

Asserts the early-return path (gated by
``noun_num_character_in_mapping == 0``) is preserved.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_compound_break import par_compound_break
from dectalk.cmd.par_structs import IndexData, MatchArrays, RangeValue, ReturnValue

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_pars1.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_par_pars1_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_par_pars1_c()
    match = re.search(
        r"void\s+par_compound_break\s*\([^)]*\)\s*\n\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "par_compound_break body not found"
    return match.group(1)


def test_early_return_when_no_mapping_loaded() -> None:
    """``if (noun_num_character_in_mapping == 0) return;``."""
    body = _extract_body()
    assert re.search(
        r"if\s*\(\s*noun_num_character_in_mapping\s*==\s*0\s*\)",
        body,
    )


def test_calls_par_break_down_word_after_setup() -> None:
    """Once the mapping is loaded the splitter delegates to par_break_down_word."""
    body = _extract_body()
    assert "par_break_down_word" in body


def test_python_no_op_on_us_build() -> None:
    """The US build's permanent state has the mapping empty -> no-op."""
    src = bytearray(b"abc")
    dst = bytearray(b"xyz")
    ret = ReturnValue(input_pos=0, input_offset=3, output_pos=0, output_offset=3)
    par_compound_break(
        b"",
        src,
        dst,
        [IndexData() for _ in range(3)],
        [IndexData() for _ in range(3)],
        MatchArrays(),
        ret,
        RangeValue(),
        0,
        0,
        0,
        0,
    )
    # No mutation since the early-return fires.
    assert dst == b"xyz"
    assert ret.value == 0
