"""Verify ``InputSeq`` ANSI escape struct mirrors cm_data.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.cmd.cmd_states import NUM_INTER, NUM_PARAM
from dectalk.cmd.input_seq import (
    INPUT_SEQ_INTER_LEN,
    INPUT_SEQ_PARAM_LEN,
    InputSeq,
)

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/cmd/cm_data.h")


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_input_seq_struct_fields_match_c() -> None:
    """Each field of the C ``INPUT_SEQ`` struct has a Python counterpart."""
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(
        r"typedef\s+struct\s+input_esc_struct\s*\{(.*?)\}\s*INPUT_SEQ\s*;",
        text,
        re.DOTALL,
    )
    assert match is not None
    body = match.group(1)
    c_fields = {
        name.strip().rstrip(";")
        for name in re.findall(
            r"^\s*(?:short|char|unsigned\s+char|int|S16|U16)\s+(\w+)",
            body,
            re.MULTILINE,
        )
    }
    py_fields = {f for f in InputSeq.__slots__ if not f.startswith("_")}
    assert c_fields == py_fields


def test_default_construction() -> None:
    """All fields default to zero / empty buffers."""
    seq = InputSeq()
    assert seq.type == 0
    assert seq.badf == 0
    assert seq.pintro == 0
    assert seq.nparam == 0
    assert seq.ninter == 0
    assert seq.final == 0
    assert seq.param == [0] * NUM_PARAM
    assert seq.dflag == [0] * NUM_PARAM
    assert seq.inter == [0] * NUM_INTER


def test_buffer_lengths_match_c_constants() -> None:
    """Buffer lengths match :data:`NUM_PARAM` / :data:`NUM_INTER`."""
    assert INPUT_SEQ_PARAM_LEN == 20
    assert INPUT_SEQ_INTER_LEN == 20
    seq = InputSeq()
    assert len(seq.param) == NUM_PARAM
    assert len(seq.dflag) == NUM_PARAM
    assert len(seq.inter) == NUM_INTER


def test_distinct_default_buffers() -> None:
    """Each instance gets its own buffers (no shared mutable default)."""
    s1 = InputSeq()
    s2 = InputSeq()
    s1.param[0] = 99
    assert s2.param[0] == 0


def test_input_seq_uses_slots() -> None:
    """``InputSeq`` is a slots dataclass — no __dict__."""
    seq = InputSeq()
    assert not hasattr(seq, "__dict__")


def test_field_assignment() -> None:
    """Field assignment works for all named attributes."""
    seq = InputSeq(type=2, badf=1, pintro=0x3C, nparam=3, ninter=1, final=ord("m"))
    seq.param[0] = 38
    seq.param[1] = 5
    seq.dflag[0] = 0
    seq.inter[0] = 0x3F
    assert seq.type == 2
    assert seq.final == ord("m")
    assert seq.param[:2] == [38, 5]
    assert seq.inter[0] == 0x3F
