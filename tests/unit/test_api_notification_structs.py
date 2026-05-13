"""Verify VisualData / MarkData / SinkData match tts.h."""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest

from dectalk.api.notification_structs import MarkData, SinkData, VisualData

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/api/tts.h")


def _parse_struct_fields(tag: str) -> set[str] | None:
    """Return field names of ``typedef struct <tag> { ... }``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"typedef\s+struct\s+{re.escape(tag)}\s*\{{(.*?)\}}"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    names: set[str] = set()
    for m in re.finditer(
        r"^\s*(?:QWORD|DWORD|char|PVOID)\s+(\w+)\s*;",
        body,
        re.MULTILINE,
    ):
        names.add(m.group(1))
    return names


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_visual_data_fields_match_c() -> None:
    """``VisualData`` matches ``VISUAL_DATA_STRUCT``."""
    c_fields = _parse_struct_fields("VISUAL_DATA_STRUCT")
    assert c_fields is not None
    py_fields = {f.name for f in fields(VisualData)}
    assert py_fields == c_fields


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_mark_data_fields_match_c() -> None:
    """``MarkData`` matches ``MARK_DATA_STRUCT``."""
    c_fields = _parse_struct_fields("MARK_DATA_STRUCT")
    assert c_fields is not None
    py_fields = {f.name for f in fields(MarkData)}
    assert py_fields == c_fields


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_sink_data_fields_match_c() -> None:
    """``SinkData`` matches ``SINK_DATA_STRUCT``."""
    c_fields = _parse_struct_fields("SINK_DATA_STRUCT")
    assert c_fields is not None
    py_fields = {f.name for f in fields(SinkData)}
    assert py_fields == c_fields


def test_defaults() -> None:
    """Default-constructed structs have all-zero / None fields."""
    vd = VisualData()
    md = MarkData()
    sd = SinkData()
    assert vd.qTimeStamp == 0
    assert vd.dwPhoneme == 0
    assert md.qTimeStamp == 0
    assert md.dwMarkValue == 0
    assert sd.qwTime == 0
    assert sd.pvNotifySink is None


def test_all_use_slots() -> None:
    """All three structs are slots dataclasses."""
    for instance in (VisualData(), MarkData(), SinkData()):
        assert not hasattr(instance, "__dict__")
