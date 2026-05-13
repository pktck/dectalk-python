"""Verify DtSemaphore / QueueSemaphore / Gate match kernel.h."""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest

from dectalk.kernel.sync_primitives import DtSemaphore, Gate, QueueSemaphore

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/include/kernel.h")


def _parse_struct_fields(tag: str) -> set[str] | None:
    """Return the field names of ``typedef struct <tag> { ... }``."""
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
        r"^\s*(?:volatile\s+)?(?:unsigned\s+)?(?:struct\s+\S+\s+)?"
        r"(?:[A-Za-z_][A-Za-z_0-9]*)\s+(?:_far\s+)?\*?\s*([a-zA-Z_][a-zA-Z_0-9]*)\s*;",
        body,
        re.MULTILINE,
    ):
        names.add(m.group(1))
    return names


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_dt_semaphore_fields_match_c() -> None:
    """``DtSemaphore`` fields match the C struct."""
    c_fields = _parse_struct_fields("DT_SEMAPHORE_struct")
    assert c_fields is not None
    py_fields = {f.name for f in fields(DtSemaphore)}
    assert py_fields == c_fields


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_queue_semaphore_fields_match_c() -> None:
    """``QueueSemaphore`` fields match the C struct."""
    c_fields = _parse_struct_fields("queue_semaphore")
    assert c_fields is not None
    py_fields = {f.name for f in fields(QueueSemaphore)}
    assert py_fields == c_fields


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_gate_fields_match_c() -> None:
    """``Gate`` fields match the C struct."""
    c_fields = _parse_struct_fields("GATE_struct")
    assert c_fields is not None
    py_fields = {f.name for f in fields(Gate)}
    assert py_fields == c_fields


def test_defaults_are_zero_or_none() -> None:
    """All three primitives default to 0 / None."""
    sem = DtSemaphore()
    qsem = QueueSemaphore()
    gate = Gate()
    assert sem.value == 0
    assert sem.queue is None
    assert qsem.head is None
    assert qsem.tail is None
    assert qsem.process is None
    assert gate.value == 0
    assert gate.state == 0
    assert gate.block_queue is None
    assert gate.wait_queue is None


def test_all_use_slots() -> None:
    """All three structs are slots dataclasses."""
    for instance in (DtSemaphore(), QueueSemaphore(), Gate()):
        assert not hasattr(instance, "__dict__")
