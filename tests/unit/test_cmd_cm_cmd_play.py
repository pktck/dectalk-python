"""Verify cm_cmd_play matches cmd_wav.c (deferred Python no-op stub)."""

from __future__ import annotations

import inspect
import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.cm_cmd_play import cm_cmd_play
from dectalk.cmd.cmd_states import CMD_success
from dectalk.cmd.cmd_t import CmdT

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/cmd_wav.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body(fn_name: str) -> str:
    """Return ``int <fn_name>(...) { ... }`` body with matched braces.

    ``cm_cmd_play`` lives inside an outer ``#if defined(WIN32) || ...
    || __linux__ || ...`` block in cmd_wav.c, so the regex needs to
    skip past comment lines to locate the definition. We use the
    first match — there is only one.
    """
    text = _read_c()
    pat = re.compile(rf"\bint\s+{re.escape(fn_name)}\s*\(", re.MULTILINE)
    match = pat.search(text)
    assert match is not None, f"{fn_name} not found in cmd_wav.c"
    i = text.index("{", match.end())
    depth = 0
    j = i
    while j < len(text):
        ch = text[j]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[i + 1 : j]
        j += 1
    msg = f"unterminated body for {fn_name}"
    raise AssertionError(msg)


def _strip_comments(body: str) -> str:
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//[^\n]*", "", body)
    return body


def _strip_inactive(body: str) -> str:
    """Drop ``#ifdef MSDOS`` / ``WIN32`` / ``SAPI5DECTALK`` / ``UNDER_CE`` blocks."""
    body = _strip_comments(body)
    for guard in ("MSDOS", "WIN32", "SAPI5DECTALK", "UNDER_CE"):
        body = re.sub(rf"#ifdef\s+{guard}.*?#endif", "", body, flags=re.DOTALL)
    return body


def test_signature_matches_c() -> None:
    """C signature: ``int cm_cmd_play(LPTTS_HANDLE_T phTTS)``."""
    text = _read_c()
    sig = re.search(
        r"int\s+cm_cmd_play\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)",
        text,
    )
    assert sig is not None


def test_function_is_inside_linux_active_block() -> None:
    """``cm_cmd_play`` is defined inside the ``__linux__``-active guard."""
    text = _read_c()
    # Find the ``int cm_cmd_play`` declaration.
    pat = re.compile(r"\bint\s+cm_cmd_play\s*\(", re.MULTILINE)
    match = pat.search(text)
    assert match is not None
    # Walk back to confirm the most recent ``#if`` block enabling Linux.
    head = text[: match.start()]
    # Find the last ``#if defined`` with __linux__ before the function.
    last_if = head.rfind("__linux__")
    assert last_if != -1, "cm_cmd_play is not guarded by a __linux__-enabling #if"


def test_linux_body_calls_cm_cmd_sync() -> None:
    """Linux body calls ``cm_cmd_sync(phTTS)`` to flush pending text."""
    active = _strip_inactive(_extract_body("cm_cmd_play"))
    flat = re.sub(r"\s+", " ", active)
    assert "cm_cmd_sync" in flat, "expected cm_cmd_sync call in Linux body"


def test_linux_body_handles_audio_output_state() -> None:
    """Linux body branches on ``phTTS->dwOutputState == STATE_OUTPUT_AUDIO``."""
    active = _strip_inactive(_extract_body("cm_cmd_play"))
    flat = re.sub(r"\s+", " ", active)
    assert "STATE_OUTPUT_AUDIO" in flat, "expected STATE_OUTPUT_AUDIO branch in Linux body"


def test_linux_body_returns_cmd_success() -> None:
    """Linux body's terminal return is ``CMD_success``."""
    active = _strip_inactive(_extract_body("cm_cmd_play"))
    flat = re.sub(r"\s+", " ", active)
    assert re.search(r"return\s*\(?\s*CMD_success", flat)


def test_python_signature_takes_cmd_t() -> None:
    """Python port takes a single :class:`CmdT` for signature parity."""
    sig = inspect.signature(cm_cmd_play)
    params = list(sig.parameters.values())
    assert len(params) == 1
    annotation = params[0].annotation
    assert annotation in {CmdT, "CmdT"}


def test_python_returns_cmd_success() -> None:
    """The Python port returns :data:`CMD_success` unconditionally."""
    cmd = CmdT()
    assert cm_cmd_play(cmd) == CMD_success
    assert cm_cmd_play(cmd) == 0


def test_python_accepts_any_filename_string() -> None:
    """Any value of ``pString[0]`` is accepted by the deferred stub."""
    cmd = CmdT()
    cmd.pString = [b"some_file.wav"]
    cmd.param_index = 1
    assert cm_cmd_play(cmd) == CMD_success


def test_python_does_not_mutate_cmd_state() -> None:
    """No-op stub doesn't touch any CmdT fields."""
    cmd = CmdT()
    cmd.pString = [b"clip.wav"]
    cmd.param_index = 1
    cm_cmd_play(cmd)
    assert cmd.pString == [b"clip.wav"]
    assert cmd.param_index == 1
