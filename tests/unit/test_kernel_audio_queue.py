"""Verify QueueT mirrors ``QUEUE_TAG`` from audiodef.h."""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest

from dectalk.kernel.audio_queue import QueueT

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/include/audiodef.h")


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_field_set_matches_c() -> None:
    """The C struct's field set matches the Python dataclass."""
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(
        r"typedef\s+struct\s+QUEUE_TAG\s*\{(.*?)\}\s*QUEUE_T",
        text,
        re.DOTALL,
    )
    assert match is not None
    body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    c_fields = {
        name
        for name in re.findall(
            r"^\s*(?:LPAUDIO_T|int)\s+(\w+)\s*;",
            body,
            re.MULTILINE,
        )
    }
    py_fields = {f.name for f in fields(QueueT)}
    assert c_fields == py_fields


def test_default_queue_is_empty() -> None:
    """Default-constructed queue has zeroed counters and no buffer."""
    queue = QueueT()
    assert queue.pQueueStart is None
    assert queue.iInputPosition == 0
    assert queue.iOutputPosition == 0
    assert queue.iQueueCount == 0
    assert queue.iQueueLength == 0


def test_uses_slots() -> None:
    """``QueueT`` is a slots dataclass."""
    queue = QueueT()
    assert not hasattr(queue, "__dict__")


def test_field_count_is_seven() -> None:
    """``QueueT`` has 7 fields (3 pointers + 4 ints)."""
    assert len(fields(QueueT)) == 7
