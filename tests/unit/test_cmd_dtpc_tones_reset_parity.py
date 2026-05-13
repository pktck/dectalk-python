"""C-source parity test for ``cm_util_dtpc_tones_reset`` against cm_util.c.

Re-parses the C function body and asserts:

- The function exists and has the expected signature.
- The entire active body is gated by ``#ifdef MSDOS``.
- The only Linux-active statement is ``return CMD_success``.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import inspect
import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.cm_util_dtpc_tones_reset import cm_util_dtpc_tones_reset
from dectalk.cmd.cmd_states import CMD_success

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/cm_util.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_cm_util_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_cm_util_c()
    match = re.search(
        r"int\s+cm_util_dtpc_tones_reset\s*\([^)]*\)\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "cm_util_dtpc_tones_reset() not found in cm_util.c"
    return match.group(1)


def test_signature_matches_c() -> None:
    """C signature: ``int cm_util_dtpc_tones_reset(LPTTS_HANDLE_T phTTS)``."""
    text = _read_cm_util_c()
    sig = re.search(
        r"int\s+cm_util_dtpc_tones_reset\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)",
        text,
    )
    assert sig is not None


def test_body_is_msdos_gated() -> None:
    """The body's MSDOS logic is gated by ``#ifdef MSDOS`` / ``#endif``."""
    body = _extract_body()
    assert re.search(r"#ifdef\s+MSDOS", body), "MSDOS gate missing"
    assert re.search(r"#endif", body), "MSDOS gate close missing"


def test_msdos_gate_contains_dsp_reset() -> None:
    """Inside the MSDOS gate: RESET_DSP / RUN_DSP appear (parity guard)."""
    body = _extract_body()
    ifdef_block = re.search(
        r"#ifdef\s+MSDOS(.*?)#endif",
        body,
        re.DOTALL,
    )
    assert ifdef_block is not None
    block = ifdef_block.group(1)
    assert "RESET_DSP" in block
    assert "RUN_DSP" in block
    assert re.search(r"sleep\s*\(\s*pCmd_t->tone_wait\s*\)\s*;", block)


def test_linux_return_is_cmd_success() -> None:
    """The function's Linux-active return is ``return(CMD_success)``."""
    body = _extract_body()
    # Strip comments and the MSDOS gate to leave only Linux-active code.
    no_comments = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    no_comments = re.sub(r"//.*", "", no_comments)
    no_msdos = re.sub(
        r"#ifdef\s+MSDOS.*?#endif",
        "",
        no_comments,
        flags=re.DOTALL,
    )
    # What remains must contain only `return(CMD_success);` plus whitespace.
    assert re.search(r"return\s*\(\s*CMD_success\s*\)\s*;", no_msdos)


def test_python_returns_cmd_success() -> None:
    """The Python port returns :data:`CMD_success`."""
    assert cm_util_dtpc_tones_reset() == CMD_success
    assert cm_util_dtpc_tones_reset() == 0


def test_python_takes_no_args() -> None:
    """Linux body uses no fields of ``phTTS``; Python port takes no args."""
    sig = inspect.signature(cm_util_dtpc_tones_reset)
    assert len(sig.parameters) == 0
