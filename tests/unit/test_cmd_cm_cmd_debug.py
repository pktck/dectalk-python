"""Verify cm_cmd_debug matches cm_copt.c (Linux no-op port)."""

from __future__ import annotations

import inspect
import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.cm_cmd_debug import cm_cmd_debug
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


def _strip_comments(body: str) -> str:
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//[^\n]*", "", body)
    return body


def _strip_inactive(body: str) -> str:
    """Drop ``#ifdef MSDOS`` / ``WIN32`` / ``SAPI5DECTALK`` blocks."""
    body = _strip_comments(body)
    for guard in ("MSDOS", "WIN32", "SAPI5DECTALK"):
        body = re.sub(rf"#ifdef\s+{guard}.*?#endif", "", body, flags=re.DOTALL)
    return body


def test_signature_matches_c() -> None:
    """C signature: ``int cm_cmd_debug(LPTTS_HANDLE_T phTTS)``."""
    text = _read_c()
    sig = re.search(
        r"int\s+cm_cmd_debug\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)",
        text,
    )
    assert sig is not None


def test_linux_body_calls_cm_cmd_sync() -> None:
    """Linux body calls ``cm_cmd_sync(phTTS)`` (mfg 04/27/1998 fix)."""
    active = _strip_inactive(_extract_body("cm_cmd_debug"))
    flat = re.sub(r"\s+", " ", active)
    # At least one un-commented cm_cmd_sync call.
    assert "cm_cmd_sync" in flat, "expected cm_cmd_sync call in Linux body"


def test_linux_body_sets_debug_switch() -> None:
    """Linux body assigns ``pKsd_t->debug_switch = pCmd_t->params[0]``."""
    active = _strip_inactive(_extract_body("cm_cmd_debug"))
    flat = re.sub(r"\s+", " ", active)
    assert re.search(
        r"pKsd_t\s*->\s*debug_switch\s*=\s*pCmd_t\s*->\s*params\s*\[\s*0\s*\]",
        flat,
    ), f"expected debug_switch assignment in Linux body, got: {flat!r}"


def test_linux_body_returns_cmd_success() -> None:
    """Linux body returns ``CMD_success``."""
    active = _strip_inactive(_extract_body("cm_cmd_debug"))
    flat = re.sub(r"\s+", " ", active)
    assert re.search(r"return\s*\(?\s*CMD_success", flat)


def test_python_signature_takes_cmd_t() -> None:
    """Python port takes a single :class:`CmdT` for signature parity."""
    sig = inspect.signature(cm_cmd_debug)
    params = list(sig.parameters.values())
    assert len(params) == 1
    annotation = params[0].annotation
    assert annotation in {CmdT, "CmdT"}


def test_python_returns_cmd_success() -> None:
    """The Python port returns :data:`CMD_success` unconditionally."""
    cmd = CmdT()
    assert cm_cmd_debug(cmd) == CMD_success
    assert cm_cmd_debug(cmd) == 0


def test_python_accepts_any_params_value() -> None:
    """Any value of ``params[0]`` is accepted (no validation in C source)."""
    for value in (0, 1, 7, -1, 0xFFFF):
        cmd = CmdT()
        cmd.params = [value]
        assert cm_cmd_debug(cmd) == CMD_success


def test_python_does_not_mutate_cmd_state() -> None:
    """No-op port doesn't touch any CmdT fields."""
    cmd = CmdT()
    cmd.params = [42]
    cmd.param_index = 1
    cm_cmd_debug(cmd)
    assert cmd.params == [42]
    assert cmd.param_index == 1
