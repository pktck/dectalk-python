"""C-source parity test for ``par_copy_string_data`` against par_pars1.c.

Re-parses the C function body and asserts the byte ``memcpy``
plus parallel ``par_copy_index_list`` invocation pattern matches
the Python port.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_copy_string_data import par_copy_string_data
from dectalk.cmd.par_structs import IndexData, ReturnValue

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_pars1.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_par_pars1_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_par_pars1_c()
    # Anchor on the definition (not the forward declaration earlier in the file).
    match = re.search(
        r"void\s+par_copy_string_data\s*\(\s*unsigned\s+char\s*\*\s*input_array\s*,"
        r"\s*pindex_data_t\s+input_indexes\s*,\s*unsigned\s+char\s*\*\s*output_array"
        r"\s*,\s*pindex_data_t\s+output_indexes\s*,\s*int\s+num_chars\s*,"
        r"\s*preturn_value_t\s+ret_value\s*\)\s*\n\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "par_copy_string_data definition not found"
    return match.group(1)


def test_memcpy_uses_output_pos_plus_offset() -> None:
    """The C ``memcpy`` writes at ``output_array[ret_value->output_pos + output_offset]``."""
    body = _extract_body()
    assert re.search(
        r"memcpy\s*\(\s*&\s*output_array\s*\[\s*ret_value\s*->\s*output_pos"
        r"\s*\+\s*ret_value\s*->\s*output_offset\s*\]\s*,",
        body,
    )


def test_memcpy_reads_input_pos_plus_offset() -> None:
    """The C ``memcpy`` reads ``input_array[ret_value->input_pos + input_offset]``."""
    body = _extract_body()
    assert re.search(
        r"&\s*input_array\s*\[\s*ret_value\s*->\s*input_pos\s*\+"
        r"\s*ret_value\s*->\s*input_offset\s*\]",
        body,
    )


def test_calls_par_copy_index_list() -> None:
    """The body delegates the parallel index-copy to par_copy_index_list."""
    body = _extract_body()
    assert "par_copy_index_list" in body


def test_python_copies_bytes() -> None:
    """A 3-byte copy at offset 0 lands in the output at offset 0."""
    src = bytearray(b"hello world")
    dst = bytearray(b"\x00" * 11)
    ret = ReturnValue(input_pos=0, input_offset=0, output_pos=0, output_offset=0)
    par_copy_string_data(
        src, [IndexData() for _ in range(11)], dst, [IndexData() for _ in range(11)], 5, ret
    )
    assert dst[:5] == b"hello"
    assert dst[5:] == b"\x00" * 6


def test_python_respects_offsets() -> None:
    """Offsets shift both source and destination cursors."""
    src = bytearray(b"abcdefghij")
    dst = bytearray(b"\x00" * 10)
    ret = ReturnValue(input_pos=2, input_offset=1, output_pos=4, output_offset=0)
    par_copy_string_data(
        src, [IndexData() for _ in range(10)], dst, [IndexData() for _ in range(10)], 3, ret
    )
    # Reads at src[2 + 1 = 3] for 3 bytes -> "def"; writes at dst[4 + 0 = 4].
    assert dst[4:7] == b"def"
    assert dst[:4] == b"\x00" * 4
    assert dst[7:] == b"\x00" * 3


def test_python_copies_zero_chars_is_noop() -> None:
    """num_chars == 0 leaves both arrays unchanged."""
    src = bytearray(b"abc")
    dst = bytearray(b"xyz")
    ret = ReturnValue(input_pos=0, input_offset=0, output_pos=0, output_offset=0)
    par_copy_string_data(
        src, [IndexData() for _ in range(3)], dst, [IndexData() for _ in range(3)], 0, ret
    )
    assert dst == b"xyz"


def test_python_copies_index_entries_parallel() -> None:
    """``par_copy_index_list`` is invoked with the same offsets / count."""
    src = bytearray(b"abc")
    dst = bytearray(b"\x00" * 3)
    src_idx = [IndexData(index=[i * 10, i * 10 + 1, i * 10 + 2]) for i in range(3)]
    dst_idx = [IndexData() for _ in range(3)]
    ret = ReturnValue(input_pos=0, input_offset=0, output_pos=0, output_offset=0)
    par_copy_string_data(src, src_idx, dst, dst_idx, 3, ret)
    # Indexes were copied; the index field should be carried over.
    assert dst_idx[0].index == [0, 1, 2]
    assert dst_idx[1].index == [10, 11, 12]
    assert dst_idx[2].index == [20, 21, 22]
