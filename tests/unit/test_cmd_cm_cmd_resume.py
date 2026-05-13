"""Verify cm_cmd_resume matches cm_copt.c (Linux no-op port)."""

from __future__ import annotations

import inspect
import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.cm_cmd_resume import cm_cmd_resume
from dectalk.cmd.cmd_states import CMD_success
from dectalk.cmd.cmd_t import CmdT

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/cm_copt.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body(fn_name: str) -> str:
    """Return ``int <fn_name>(...) { ... }`` body with matched braces."""
    text = _read_c()
    pat = re.compile(rf"\bint\s+{re.escape(fn_name)}\s*\(", re.MULTILINE)
    match = pat.search(text)
    assert match is not None, f"{fn_name} not found in cm_copt.c"
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


def _strip_inactive(body: str) -> str:
    """Drop comments and the inactive ``#ifdef MSDOS`` block.

    Leaves the Linux-active portion (including the
    ``#if defined(WIN32) || ... || __linux__ || ...`` branch).
    """
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//[^\n]*", "", body)
    body = re.sub(r"#ifdef\s+MSDOS.*?#endif", "", body, flags=re.DOTALL)
    return body


def test_signature_matches_c() -> None:
    """C signature: ``int cm_cmd_resume(LPTTS_HANDLE_T phTTS)``."""
    text = _read_c()
    sig = re.search(
        r"int\s+cm_cmd_resume\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)",
        text,
    )
    assert sig is not None


def test_linux_branch_calls_cm_cmd_sync_and_resume() -> None:
    """The Linux-active body calls ``cm_cmd_sync`` and ``TextToSpeechResume``."""
    active = _strip_inactive(_extract_body("cm_cmd_resume"))
    flat = re.sub(r"\s+", " ", active)
    assert "cm_cmd_sync" in flat, "expected cm_cmd_sync call in Linux body"
    assert "TextToSpeechResume" in flat, "expected TextToSpeechResume call in Linux body"


def test_linux_branch_returns_cmd_flushing_when_sync_flushes() -> None:
    """Linux body bails with ``CMD_flushing`` when ``cm_cmd_sync`` says so."""
    active = _strip_inactive(_extract_body("cm_cmd_resume"))
    flat = re.sub(r"\s+", " ", active)
    pattern = (
        r"if\s*\(\s*cm_cmd_sync\s*\(\s*\w+\s*\)\s*==\s*CMD_flushing\s*\)"
        r"\s*return\s*\(?\s*CMD_flushing"
    )
    assert re.search(pattern, flat), (
        f"expected CMD_flushing short-circuit in Linux body, got: {flat!r}"
    )


def test_linux_branch_returns_cmd_success() -> None:
    """The fall-through return is ``CMD_success``."""
    active = _strip_inactive(_extract_body("cm_cmd_resume"))
    flat = re.sub(r"\s+", " ", active)
    assert re.search(r"return\s*\(?\s*CMD_success", flat)


def test_python_signature_takes_cmd_t() -> None:
    """Python port takes a single :class:`CmdT` for signature parity."""
    sig = inspect.signature(cm_cmd_resume)
    params = list(sig.parameters.values())
    assert len(params) == 1
    # The parameter's annotation reads as the bare ``CmdT`` name under
    # ``from __future__ import annotations``; tolerate both forms.
    annotation = params[0].annotation
    assert annotation in {CmdT, "CmdT"}


def test_python_returns_cmd_success() -> None:
    """The Python port returns :data:`CMD_success` unconditionally."""
    cmd = CmdT()
    assert cm_cmd_resume(cmd) == CMD_success
    assert cm_cmd_resume(cmd) == 0


def test_python_does_not_mutate_cmd_state() -> None:
    """No-op port doesn't touch any CmdT fields."""
    cmd = CmdT()
    cmd.params = [42]
    cmd.param_index = 7
    cm_cmd_resume(cmd)
    assert cmd.params == [42]
    assert cmd.param_index == 7
