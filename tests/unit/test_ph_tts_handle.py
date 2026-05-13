"""Verify TtsHandle mirrors ``TTS_HANDLE_TAG`` from ph_data.h."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.ph.tts_handle import TtsHandle

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_data.h")


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_field_set_matches_c() -> None:
    """The C struct's field set matches the Python dataclass."""
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(
        r"struct\s+TTS_HANDLE_TAG\s*\{(.*?)\}\s*;",
        text,
        re.DOTALL,
    )
    assert match is not None
    body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.DOTALL)
    c_fields = {
        name
        for name in re.findall(
            r"^\s*(?:PKSD_T|PDPH_T)\s+(\w+)\s*;",
            body,
            re.MULTILINE,
        )
    }
    py_fields = {"pKernelShareData", "pPHThreadData"}
    assert c_fields == py_fields


def test_default_handle_has_null_pointers() -> None:
    """Default-constructed handle has both pointer fields ``None``."""
    handle = TtsHandle()
    assert handle.p_kernel_share_data is None
    assert handle.p_ph_thread_data is None


def test_handle_uses_slots() -> None:
    """``TtsHandle`` is a slots dataclass."""
    handle = TtsHandle()
    assert not hasattr(handle, "__dict__")


def test_handle_carries_arbitrary_state() -> None:
    """Both fields accept arbitrary objects (KSD_T / DPH_T placeholders)."""
    ksd_stub = {"sprate": 180}
    dph_stub = ["param"]
    handle = TtsHandle(p_kernel_share_data=ksd_stub, p_ph_thread_data=dph_stub)
    assert handle.p_kernel_share_data is ksd_stub
    assert handle.p_ph_thread_data is dph_stub
