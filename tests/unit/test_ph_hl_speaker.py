"""Verify HLSpeaker mirrors ``HLSpeakerTag`` from hlsynapi.h."""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest

from dectalk.ph.hl_speaker import HLSpeaker

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/hlsynapi.h")


def _parse_field_names() -> set[str] | None:
    """Return the set of unique field names in ``HLSpeakerTag`` struct."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(
        r"typedef\s+struct\s+HLSpeakerTag(.*?)\}\s*HLSpeaker;",
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
        if m.group(1) in ("HLSpeakerTag", "struct", "typedef"):
            continue
        seen.add(m.group(2))
    return seen


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_field_set_matches_c() -> None:
    """Every C field maps to a Python dataclass attribute."""
    c_fields = _parse_field_names()
    assert c_fields is not None
    py_fields = {f.name for f in fields(HLSpeaker)}
    assert c_fields == py_fields


def test_default_construction_does_not_raise() -> None:
    """Default-constructed instance is fully initialised."""
    speaker = HLSpeaker()
    assert speaker is not None


def test_uses_slots() -> None:
    """``HLSpeaker`` is a slots dataclass."""
    speaker = HLSpeaker()
    assert not hasattr(speaker, "__dict__")


def test_field_count_is_107() -> None:
    """The C struct has 107 unique field names."""
    assert len(fields(HLSpeaker)) == 107


def test_float_fields_default_zero() -> None:
    """Spot-check that float fields default to 0.0."""
    speaker = HLSpeaker()
    for name in ("Val", "f1Min", "f1Max", "agm", "OQm"):
        assert getattr(speaker, name) == 0.0


def test_table_fields_default_none() -> None:
    """Spot-check that TableRow / FricativeGains fields default to None."""
    speaker = HLSpeaker()
    for name in ("anaTable", "anbTable", "f1cTable", "anK2Table"):
        assert getattr(speaker, name) is None
