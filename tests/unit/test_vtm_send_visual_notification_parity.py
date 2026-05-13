"""C-source parity test for ``SendVisualNotification`` against vtmiont.c.

Re-parses the C body and asserts the payload-build structure matches
the Python port's :class:`VisualNotification` shape.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.vtm.send_visual_notification import (
    VisualNotification,
    send_visual_notification,
)

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/vtm/vtmiont.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_vtmiont_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_vtmiont_c()
    match = re.search(
        r"void\s+SendVisualNotification\s*\([^)]*\)\s*\n\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "SendVisualNotification body not found"
    return match.group(1)


def test_signature_matches_c() -> None:
    """C signature: ``void SendVisualNotification(LPTTS_HANDLE_T, DWORD, DWORD, DWORD)``."""
    text = _read_vtmiont_c()
    sig = re.search(
        r"void\s+SendVisualNotification\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*,"
        r"\s*DWORD\s+dwPhoneme\s*,\s*DWORD\s+dwDuration\s*,\s*DWORD\s+dwNextPhoneme\s*\)",
        text,
    )
    assert sig is not None


def test_full_range_branch_passes_phoneme_through() -> None:
    """``uiFullRangeMarks`` branch writes the full phoneme code."""
    body = _extract_body()
    assert re.search(
        r"pvdPacket->dwPhoneme\s*=\s*dwPhoneme\s*;",
        body,
    )


def test_masked_branch_truncates_to_low_byte() -> None:
    """Default branch masks to the low byte."""
    body = _extract_body()
    assert re.search(
        r"pvdPacket->dwPhoneme\s*=\s*dwPhoneme\s*&\s*0x00ff",
        body,
    )
    assert re.search(
        r"pvdPacket->dwNextPhoneme\s*=\s*dwNextPhoneme\s*&\s*0x00ff",
        body,
    )


def test_duration_is_passed_through() -> None:
    """``dwDuration`` is copied into the payload."""
    body = _extract_body()
    assert re.search(r"pvdPacket->dwDuration\s*=\s*dwDuration\s*;", body)


def test_python_masked_branch_truncates() -> None:
    """Default Python port path masks both phonemes to the low byte."""
    payload = send_visual_notification(
        phoneme=0xAB10,
        duration=100,
        next_phoneme=0xCD20,
    )
    assert payload.phoneme == 0x10
    assert payload.next_phoneme == 0x20
    assert payload.duration == 100


def test_python_full_range_marks_passes_through() -> None:
    """``full_range_marks=True`` keeps the full phoneme code."""
    payload = send_visual_notification(
        phoneme=0xAB10,
        duration=100,
        next_phoneme=0xCD20,
        full_range_marks=True,
    )
    assert payload.phoneme == 0xAB10
    assert payload.next_phoneme == 0xCD20


def test_python_invokes_sink_with_payload() -> None:
    """``visual_sink`` is called once per notification with the payload."""
    captured: list[VisualNotification] = []
    payload = send_visual_notification(
        phoneme=10,
        duration=50,
        next_phoneme=20,
        visual_sink=captured.append,
    )
    assert captured == [payload]
    assert captured[0].phoneme == 10
    assert captured[0].next_phoneme == 20
    assert captured[0].duration == 50


def test_python_no_op_without_sink() -> None:
    """Without a sink the call still returns the payload but emits no side-effect."""
    payload = send_visual_notification(phoneme=1, duration=2, next_phoneme=3)
    assert payload.phoneme == 1
    assert payload.next_phoneme == 3
    assert payload.duration == 2


def test_python_queued_sample_count_carried() -> None:
    """The queued-sample-count snapshot rides on the payload."""
    payload = send_visual_notification(
        phoneme=1,
        duration=2,
        next_phoneme=3,
        queued_sample_count=999_999,
    )
    assert payload.queued_sample_count == 999_999
