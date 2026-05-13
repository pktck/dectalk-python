"""Verify LtsT mirrors ``LTS_T`` struct from ls_data.h."""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest

from dectalk.lts.lts_t import LtsT

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/lts/ls_data.h")


def _parse_field_names() -> set[str] | None:
    """Return the set of field names in ``LTS_TAG`` struct."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(
        r"typedef\s+struct\s+LTS_TAG(.*?)\}\s*LTS_T;",
        text,
        re.DOTALL,
    )
    if not match:
        return None
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    seen: set[str] = set()
    for m in re.finditer(
        r"^\s*(?:unsigned\s+|signed\s+)?([A-Za-z_][A-Za-z_0-9]*)\s+\*?\s*([a-zA-Z_][a-zA-Z_0-9]*)\s*(\[[^;]+\])?\s*;",
        body,
        re.MULTILINE,
    ):
        if m.group(1) in ("LTS_TAG", "struct", "typedef"):
            continue
        seen.add(m.group(2))
    return seen


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_field_set_matches_c() -> None:
    """Every unique C field maps to a Python dataclass attribute."""
    c_fields = _parse_field_names()
    assert c_fields is not None
    py_fields = {f.name for f in fields(LtsT)}
    assert c_fields == py_fields


def test_default_construction_does_not_raise() -> None:
    """Default-constructed instance is fully initialised."""
    state = LtsT()
    assert state is not None


def test_uses_slots() -> None:
    """``LtsT`` is a slots dataclass."""
    state = LtsT()
    assert not hasattr(state, "__dict__")


def test_field_count_is_66() -> None:
    """The C struct has 66 declared fields."""
    assert len(fields(LtsT)) == 66


def test_phead_default_none() -> None:
    """``phead`` (phone-list head) defaults to None."""
    state = LtsT()
    assert state.phead is None
