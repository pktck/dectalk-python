"""Verify CmdT mirrors ``CMD_T`` struct from cm_data.h."""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest

from dectalk.cmd.cmd_t import CmdT

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/cmd/cm_data.h")


def _parse_field_names() -> set[str] | None:
    """Return the set of field names in ``CMD_TAG`` struct."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(
        r"typedef\s+struct\s+CMD_TAG(.*?)\}\s*CMD_T;",
        text,
        re.DOTALL,
    )
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
        if m.group(1) in ("CMD_TAG", "struct", "typedef"):
            continue
        names.add(m.group(2))
    return names


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_field_set_matches_c() -> None:
    """Every C field maps to a Python dataclass attribute."""
    c_fields = _parse_field_names()
    assert c_fields is not None
    py_fields = {f.name for f in fields(CmdT)}
    assert c_fields == py_fields


def test_default_construction_does_not_raise() -> None:
    """Default-constructed instance is fully initialised."""
    state = CmdT()
    assert state is not None


def test_uses_slots() -> None:
    """``CmdT`` is a slots dataclass."""
    state = CmdT()
    assert not hasattr(state, "__dict__")


def test_field_count_is_68() -> None:
    """The C struct has 68 unique field names after de-duping #ifdef branches."""
    assert len(fields(CmdT)) == 68


def test_scalar_fields_default_zero() -> None:
    """Spot-check a few scalar fields default to 0."""
    state = CmdT()
    for name in ("parse_state", "error_mode", "punct_mode", "p_count", "param_index"):
        assert getattr(state, name) == 0


def test_array_fields_default_empty_list() -> None:
    """Spot-check that array fields default to empty lists."""
    state = CmdT()
    for name in ("params", "defaults", "string_buff", "setv"):
        value = getattr(state, name)
        assert isinstance(value, list)
        assert value == []
