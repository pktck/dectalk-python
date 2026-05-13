"""Verify TtsHandleFull fields are a subset of TTS_HANDLE_T from tts.h."""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest

from dectalk.api.tts_handle import TtsHandleFull

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/api/tts.h")


def _parse_field_names() -> set[str] | None:
    """Return field names in ``TTS_HANDLE_TAG`` (across all #ifdef branches)."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(
        r"struct\s+TTS_HANDLE_TAG\s*\{(.*?)\}\s*;",
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
        if m.group(1) in ("typedef", "struct"):
            continue
        names.add(m.group(2))
    return names


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_python_fields_subset_of_c() -> None:
    """Every Python field appears in the C struct (under some #ifdef branch)."""
    c_fields = _parse_field_names()
    assert c_fields is not None
    py_fields = {f.name for f in fields(TtsHandleFull)}
    # Python models a strict subset (skipping Win32-specific fields).
    missing = py_fields - c_fields
    assert not missing, f"Python-only fields: {missing}"


def test_default_construction_does_not_raise() -> None:
    """Default-constructed instance is fully initialised."""
    handle = TtsHandleFull()
    assert handle is not None


def test_uses_slots() -> None:
    """``TtsHandleFull`` is a slots dataclass."""
    handle = TtsHandleFull()
    assert not hasattr(handle, "__dict__")


def test_five_thread_pointers_default_none() -> None:
    """The 5 main per-thread state pointers default to None."""
    handle = TtsHandleFull()
    for name in (
        "pKernelShareData",
        "pCMDThreadData",
        "pLTSThreadData",
        "pVTMThreadData",
        "pPHThreadData",
    ):
        assert getattr(handle, name) is None


def test_counter_fields_default_zero() -> None:
    """Counter / flag fields default to 0."""
    handle = TtsHandleFull()
    for name in ("uiTextThreadExit", "uiThreadError", "uiQueuedCharacterCount"):
        assert getattr(handle, name) == 0


def test_carries_arbitrary_state() -> None:
    """All pointer fields accept arbitrary objects."""
    ksd = {"sprate": 180}
    handle = TtsHandleFull(pKernelShareData=ksd)
    assert handle.pKernelShareData is ksd
