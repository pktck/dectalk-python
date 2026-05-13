"""C-source parity test for the synchronous ``sync_main`` shim.

Re-parses ``src/dapi/src/vtm/sync.c`` and asserts:

- The Linux build declares the thread entry via the
  ``OP_THREAD_ROUTINE(sync_main, LPTTS_HANDLE_T phTTS)`` macro inside
  the appropriate ``#if defined(__linux__)`` family of guards.
- The macro is used exactly once for ``sync_main`` -- the C source
  defines the same routine twice (one ``WIN32`` arm and one POSIX
  arm); the POSIX arm is the one our Linux build compiles.
- The body returns via ``OP_THREAD_RETURN`` (the Linux ``void``
  pthread return convention).

Plus a Python-side behavioural check: the
:func:`dectalk.vtm.sync_main.sync_main_tick` shim exists, returns
``None``, and the module documents its synchronous-pipeline
divergence from the C threaded model.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.vtm import sync_main as sync_main_module
from dectalk.vtm.sync_main import sync_main_tick

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/vtm/sync.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_sync_c() -> str:
    """Read sync.c with CRLF line endings normalised."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


# --------------------------------------------------------------------------
# C-source structural parity.
# --------------------------------------------------------------------------


def test_op_thread_routine_macro_present_for_sync_main() -> None:
    """``OP_THREAD_ROUTINE(sync_main, LPTTS_HANDLE_T phTTS)`` is in sync.c."""
    text = _read_sync_c()
    match = re.search(
        r"OP_THREAD_ROUTINE\s*\(\s*sync_main\s*,\s*LPTTS_HANDLE_T\s+\w+\s*\)",
        text,
    )
    assert match is not None, "OP_THREAD_ROUTINE(sync_main, LPTTS_HANDLE_T ...) not found in sync.c"


def test_op_thread_routine_uses_sync_main_name() -> None:
    """The first macro argument is exactly the identifier ``sync_main``.

    Catches a future drift where the C source might rename the routine
    (e.g. ``sync_main`` -> ``sync_thread_main``) without us noticing.
    """
    text = _read_sync_c()
    match = re.search(r"OP_THREAD_ROUTINE\s*\(\s*(\w+)\s*,", text)
    assert match is not None, "no OP_THREAD_ROUTINE invocation found in sync.c"
    assert match.group(1) == "sync_main", f"OP_THREAD_ROUTINE name drifted to '{match.group(1)}'"


def test_macro_lives_in_posix_branch() -> None:
    """The macro form sits inside the ``__linux__`` / ``__osf__`` guard.

    sync.c declares the same entry twice -- once as
    ``DWORD __stdcall sync_main(...)`` under ``#ifdef WIN32`` and once
    as ``OP_THREAD_ROUTINE(sync_main, ...)`` under the POSIX family.
    Our Linux build compiles the POSIX arm, so the macro line must be
    preceded by an ``#if`` that mentions ``__linux__``.
    """
    text = _read_sync_c()
    macro_idx = text.find("OP_THREAD_ROUTINE(sync_main")
    assert macro_idx != -1, "OP_THREAD_ROUTINE(sync_main, ...) not found"
    # Look backward up to the previous '#if' line and check the guard.
    preceding = text[:macro_idx]
    last_if = preceding.rfind("#if")
    assert last_if != -1, "no preceding #if before OP_THREAD_ROUTINE(sync_main, ...)"
    line_end = text.find("\n", last_if)
    if line_end == -1:
        line_end = len(text)
    guard_line = text[last_if:line_end]
    assert "__linux__" in guard_line, (
        f"OP_THREAD_ROUTINE(sync_main, ...) is not gated by a Linux guard: {guard_line!r}"
    )


def test_op_thread_return_present() -> None:
    """The body returns via ``OP_THREAD_RETURN`` (Linux pthread idiom)."""
    text = _read_sync_c()
    assert re.search(r"\bOP_THREAD_RETURN\b", text), (
        "OP_THREAD_RETURN not found in sync.c -- thread exit path drifted"
    )


# --------------------------------------------------------------------------
# Python shim behaviour and divergence documentation.
# --------------------------------------------------------------------------


def test_sync_main_tick_returns_none() -> None:
    """The synchronous shim is a no-op returning ``None``."""
    assert sync_main_tick() is None


def test_sync_main_tick_is_callable_with_no_args() -> None:
    """The shim is callable with no arguments (a plain tick entry point)."""
    # Should not raise.
    result = sync_main_tick()
    assert result is None


def test_module_documents_thread_model_divergence() -> None:
    """The module docstring records the C-thread vs Python-inline split."""
    doc = sync_main_module.__doc__
    assert doc is not None, "sync_main module is missing its docstring"
    # Mentions the C source it ports from.
    assert "sync.c" in doc
    # Mentions the macro it stands in for.
    assert "OP_THREAD_ROUTINE" in doc
    # Documents why the Python port is a no-op.
    lowered = doc.lower()
    assert "synchronous" in lowered or "synchronously" in lowered
    assert "thread" in lowered


def test_all_exports_sync_main_tick() -> None:
    """``__all__`` lists the tick entry point so it's part of the public API."""
    assert "sync_main_tick" in sync_main_module.__all__
