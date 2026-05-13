"""Verify HLSyn frame / state structs match hlsynapi.h."""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest

from dectalk.ph.hlsyn_structs import (
    FricativeGains,
    HLFrame,
    HLState,
    TableRow,
)

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/hlsynapi.h")


def _parse_struct_fields(tag: str) -> set[str] | None:
    """Return the set of field names in ``typedef struct <tag> { ... };``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"(?:typedef\s+)?struct\s+{re.escape(tag)}\s*\{{(.*?)\}}"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    names: set[str] = set()
    for m in re.finditer(
        r"^\s*(?:unsigned\s+|signed\s+)?([A-Za-z_][A-Za-z_0-9]*)\s+\*?\s*([a-zA-Z_][a-zA-Z_0-9]*)\s*(\[[^;]+\])?\s*;",
        body,
        re.MULTILINE,
    ):
        names.add(m.group(2))
    return names


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_hl_frame_fields_match_c() -> None:
    """``HLFrame`` Python fields match the C ``tagHLFrame`` struct."""
    c_fields = _parse_struct_fields("tagHLFrame")
    assert c_fields is not None
    py_fields = {f.name for f in fields(HLFrame)}
    assert c_fields == py_fields


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_hl_state_fields_match_c() -> None:
    """``HLState`` Python fields match the C ``HLStateTag`` struct."""
    c_fields = _parse_struct_fields("HLStateTag")
    assert c_fields is not None
    py_fields = {f.name for f in fields(HLState)}
    assert c_fields == py_fields


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_table_row_fields_match_c() -> None:
    """``TableRow`` has exactly ``Column1`` + ``Column2``."""
    c_fields = _parse_struct_fields("TableRowTag")
    assert c_fields is not None
    assert c_fields == {"Column1", "Column2"}
    assert {f.name for f in fields(TableRow)} == {"Column1", "Column2"}


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_fricative_gains_fields_match_c() -> None:
    """``FricativeGains`` has A2f, A3f, A4f, A5f, Ab."""
    c_fields = _parse_struct_fields("FricativeGainsTag")
    assert c_fields is not None
    assert c_fields == {"A2f", "A3f", "A4f", "A5f", "Ab"}
    py_fields = {f.name for f in fields(FricativeGains)}
    assert py_fields == c_fields


def test_hl_frame_defaults_zero() -> None:
    """Default ``HLFrame`` is all-zero."""
    frame = HLFrame()
    for f in fields(frame):
        assert getattr(frame, f.name) in (0, 0.0)


def test_hl_state_defaults_zero() -> None:
    """Default ``HLState`` is all-zero."""
    state = HLState()
    for f in fields(state):
        assert getattr(state, f.name) in (0, 0.0)


def test_uses_slots() -> None:
    """All four structs are slots dataclasses."""
    for cls in (HLFrame, HLState, TableRow, FricativeGains):
        instance = cls()
        assert not hasattr(instance, "__dict__")
