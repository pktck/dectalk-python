"""Verify cm_cmd_log matches cm_copt.c (deferred Python no-op stub)."""

from __future__ import annotations

import inspect
import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.cm_cmd_log import cm_cmd_log
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
    """C signature: ``int cm_cmd_log(LPTTS_HANDLE_T phTTS)``."""
    text = _read_c()
    sig = re.search(
        r"int\s+cm_cmd_log\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)",
        text,
    )
    assert sig is not None


def test_linux_body_iterates_param_index() -> None:
    """Linux body iterates ``i < pCmd_t->param_index``."""
    active = _strip_inactive(_extract_body("cm_cmd_log"))
    flat = re.sub(r"\s+", " ", active)
    assert re.search(
        r"for\s*\(\s*\w+\s*=\s*0\s*;\s*\w+\s*<\s*\(?\s*int\s*\)?\s*pCmd_t\s*->\s*param_index",
        flat,
    ), f"expected param_index loop in Linux body, got: {flat!r}"


def test_linux_body_calls_cm_util_string_match_on_log_options() -> None:
    """Linux body matches each parameter against ``log_options``."""
    active = _strip_inactive(_extract_body("cm_cmd_log"))
    flat = re.sub(r"\s+", " ", active)
    assert re.search(
        r"cm_util_string_match\s*\(\s*log_options\s*,",
        flat,
    ), "expected cm_util_string_match(log_options, ...) in Linux body"


def test_linux_body_opens_or_closes_log() -> None:
    """Linux body references at least one log-file helper (deferred in Python)."""
    active = _strip_inactive(_extract_body("cm_cmd_log"))
    # At least one Open/Close-style helper call must appear. The C body only
    # references ``OpenLogFile`` directly (the ``Close`` path is gated by
    # an inactive ``#ifdef``), so we don't require both — just one.
    assert (
        "OpenLogFile" in active
        or "OpenDbgLogFile" in active
        or "CloseLogFile" in active
        or "CloseDbgLogFile" in active
    ), "expected an Open/Close LogFile helper call in Linux body"


def test_linux_body_returns_cmd_success() -> None:
    """Linux body's terminal return is ``CMD_success``."""
    active = _strip_inactive(_extract_body("cm_cmd_log"))
    flat = re.sub(r"\s+", " ", active)
    assert re.search(r"return\s*\(?\s*CMD_success", flat)


def test_python_signature_takes_cmd_t() -> None:
    """Python port takes a single :class:`CmdT` for signature parity."""
    sig = inspect.signature(cm_cmd_log)
    params = list(sig.parameters.values())
    assert len(params) == 1
    annotation = params[0].annotation
    assert annotation in {CmdT, "CmdT"}


def test_python_returns_cmd_success() -> None:
    """The Python port returns :data:`CMD_success` unconditionally."""
    cmd = CmdT()
    assert cm_cmd_log(cmd) == CMD_success
    assert cm_cmd_log(cmd) == 0


def test_python_accepts_any_params() -> None:
    """Even an unknown keyword is accepted by the deferred no-op stub."""
    cmd = CmdT()
    cmd.pString = [b"text", b"on"]
    cmd.param_index = 2
    assert cm_cmd_log(cmd) == CMD_success


def test_python_does_not_mutate_cmd_state() -> None:
    """No-op port doesn't touch any CmdT fields."""
    cmd = CmdT()
    cmd.pString = [b"phonemes", b"off"]
    cmd.param_index = 2
    cm_cmd_log(cmd)
    assert cmd.pString == [b"phonemes", b"off"]
    assert cmd.param_index == 2
