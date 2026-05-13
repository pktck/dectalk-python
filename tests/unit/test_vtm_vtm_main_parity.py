"""C-source parity test for the synchronous ``vtm_main`` shim.

Re-parses ``src/dapi/src/vtm/vtmiont.c`` and asserts:

- The Linux build declares the thread entry via the
  ``OP_THREAD_ROUTINE(vtm_main, LPTTS_HANDLE_T phTTS)`` macro inside
  the ``#elif defined __linux__`` family of guards (with the inner
  ``#ifndef SINGLE_THREADED`` selecting the threaded form).
- The macro is used for the identifier ``vtm_main``.
- The body returns via ``OP_THREAD_RETURN`` somewhere in the
  function (the Linux ``void`` pthread return convention).

Plus a Python-side behavioural check: the
:func:`dectalk.vtm.vtm_main.vtm_main_tick` shim exists, returns
``None``, and the module documents its synchronous-pipeline
divergence from the C threaded model.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.vtm import vtm_main as vtm_main_module
from dectalk.vtm.vtm_main import vtm_main_tick

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/vtm/vtmiont.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_vtmiont_c() -> str:
    """Read vtmiont.c with CRLF line endings normalised."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


# --------------------------------------------------------------------------
# C-source structural parity.
# --------------------------------------------------------------------------


def test_op_thread_routine_macro_present_for_vtm_main() -> None:
    """``OP_THREAD_ROUTINE(vtm_main, LPTTS_HANDLE_T phTTS)`` is in vtmiont.c."""
    text = _read_vtmiont_c()
    match = re.search(
        r"OP_THREAD_ROUTINE\s*\(\s*vtm_main\s*,\s*LPTTS_HANDLE_T\s+\w+\s*\)",
        text,
    )
    assert match is not None, (
        "OP_THREAD_ROUTINE(vtm_main, LPTTS_HANDLE_T ...) not found in vtmiont.c"
    )


def test_op_thread_routine_uses_vtm_main_name() -> None:
    """The macro's first argument is exactly the identifier ``vtm_main``.

    Catches a future drift where the C source might rename the routine
    (e.g. ``vtm_main`` -> ``vtm_thread_main``) without us noticing.
    """
    text = _read_vtmiont_c()
    match = re.search(r"OP_THREAD_ROUTINE\s*\(\s*(\w+)\s*,", text)
    assert match is not None, "no OP_THREAD_ROUTINE invocation found in vtmiont.c"
    assert match.group(1) == "vtm_main", f"OP_THREAD_ROUTINE name drifted to '{match.group(1)}'"


def test_macro_gated_by_single_threaded_else() -> None:
    """The macro lives inside the ``#else`` of an ``#ifdef SINGLE_THREADED``.

    vtmiont.c declares ``vtm_main`` four ways: ``WIN32``, the POSIX
    ``SINGLE_THREADED`` plain-function form, the POSIX threaded form
    via ``OP_THREAD_ROUTINE``, and a fall-through plain-function form.
    Our Linux build does not define ``SINGLE_THREADED``, so the
    ``OP_THREAD_ROUTINE`` arm is the active one. Verify the macro
    line is immediately preceded by ``#else`` (the threaded branch
    of the SINGLE_THREADED switch).
    """
    text = _read_vtmiont_c()
    macro_idx = text.find("OP_THREAD_ROUTINE(vtm_main")
    assert macro_idx != -1, "OP_THREAD_ROUTINE(vtm_main, ...) not found"
    preceding = text[:macro_idx]
    last_directive = max(
        preceding.rfind("#else"),
        preceding.rfind("#if"),
        preceding.rfind("#elif"),
        preceding.rfind("#ifdef"),
        preceding.rfind("#ifndef"),
    )
    assert last_directive != -1, "no preceding preprocessor directive before macro"
    # The directive immediately above the macro should be ``#else``
    # (the threaded branch of the SINGLE_THREADED conditional).
    line_end = preceding.find("\n", last_directive)
    if line_end == -1:
        line_end = len(preceding)
    guard_line = text[last_directive:line_end]
    assert guard_line.startswith("#else"), (
        f"OP_THREAD_ROUTINE(vtm_main, ...) is not in the SINGLE_THREADED #else "
        f"branch: preceding directive is {guard_line!r}"
    )


def test_op_thread_return_present() -> None:
    """The body returns via ``OP_THREAD_RETURN`` (Linux pthread idiom)."""
    text = _read_vtmiont_c()
    assert re.search(r"\bOP_THREAD_RETURN\b", text), (
        "OP_THREAD_RETURN not found in vtmiont.c -- thread exit path drifted"
    )


# --------------------------------------------------------------------------
# Python shim behaviour and divergence documentation.
# --------------------------------------------------------------------------


def test_vtm_main_tick_returns_none() -> None:
    """The synchronous shim is a no-op returning ``None``."""
    assert vtm_main_tick() is None


def test_vtm_main_tick_is_callable_with_no_args() -> None:
    """The shim is callable with no arguments (a plain tick entry point)."""
    # Should not raise.
    result = vtm_main_tick()
    assert result is None


def test_module_documents_thread_model_divergence() -> None:
    """The module docstring records the C-thread vs Python-inline split."""
    doc = vtm_main_module.__doc__
    assert doc is not None, "vtm_main module is missing its docstring"
    # Mentions the C source it ports from.
    assert "vtmiont.c" in doc
    # Mentions the macro it stands in for.
    assert "OP_THREAD_ROUTINE" in doc
    # Documents why the Python port is a no-op.
    lowered = doc.lower()
    assert "synchronous" in lowered or "synchronously" in lowered
    assert "thread" in lowered


def test_all_exports_vtm_main_tick() -> None:
    """``__all__`` lists the tick entry point so it's part of the public API."""
    assert "vtm_main_tick" in vtm_main_module.__all__
