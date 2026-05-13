"""C-source parity tests for the kernel synchronisation no-ops in services.c.

Re-parses each function's C source body and asserts:

- ``wait_semaphore`` (Linux ``P_SEMAPHORE`` branch) has an empty body.
- ``signal_semaphore`` has an empty body.
- ``kernel_disable`` body is ``#ifdef MSDOS`` ... ``#endif`` followed by
  ``return( 0 );`` — the Linux build only returns 0.

Each function also has a behavioural assertion: the Python port can be
called with valid arguments and returns the expected value (``None`` or
``0``).

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.synchronization import (
    kernel_disable,
    signal_semaphore,
    wait_semaphore,
)

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / (
    "src/dapi/src/kernel/services.c"
)

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_services_c() -> str:
    """Read services.c with CRLF endings normalised."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _strip_comments(body: str) -> str:
    """Remove ``/* ... */`` block and ``// ...`` line comments from a body."""
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    return body


# ---------------------------------------------------------------------------
# wait_semaphore: Linux branch is the P_SEMAPHORE prototype with an empty body
# ---------------------------------------------------------------------------


def test_wait_semaphore_linux_branch_body_is_empty() -> None:
    """``wait_semaphore`` Linux branch (``P_SEMAPHORE``) body is empty.

    The C source declares three prototypes for ``wait_semaphore`` — one
    each for WIN32, the Linux/OSF/VxWorks/... family (the ``P_SEMAPHORE``
    variant), and ARM7 — followed by a single shared function body. We
    assert that the Linux ``P_SEMAPHORE`` prototype exists, that the
    Linux platform is among the ``#if defined`` guards selecting it, and
    that the shared body is empty.
    """
    text = _read_services_c()
    # Locate the Linux-selecting `#if defined ... __linux__ ... #endif`
    # block that wraps the `P_SEMAPHORE` prototype.
    linux_proto_re = (
        r"#if\s+defined[^\n]*__linux__[^\n]*\n"
        r"void\s+wait_semaphore\s*\(\s*P_SEMAPHORE\s+\w+\s*\)\s*\n"
        r"#endif"
    )
    proto_match = re.search(linux_proto_re, text)
    assert proto_match is not None, (
        "Linux P_SEMAPHORE prototype of wait_semaphore not found in services.c"
    )
    # After the last `#endif` of the prototype stack the shared body opens.
    body_match = re.search(
        r"#ifdef\s+ARM7\s*\n"
        r"void\s+wait_semaphore[^\n]*\n"
        r"#endif\s*\n"
        r"\{([^{}]*)\}",
        text,
    )
    assert body_match is not None, "shared wait_semaphore body not found in services.c"
    body = _strip_comments(body_match.group(1))
    assert body.strip() == "", f"expected empty wait_semaphore body, got {body!r}"


# ---------------------------------------------------------------------------
# signal_semaphore: empty body
# ---------------------------------------------------------------------------


def test_signal_semaphore_body_is_empty() -> None:
    """``signal_semaphore`` body contains only whitespace in services.c."""
    text = _read_services_c()
    match = re.search(
        r"void\s+signal_semaphore\s*\(\s*int\s*\*\s*\w+\s*\)\s*\{([^{}]*)\}",
        text,
    )
    assert match is not None, "signal_semaphore not found in services.c"
    body = _strip_comments(match.group(1))
    assert body.strip() == "", f"expected empty signal_semaphore body, got {body!r}"


# ---------------------------------------------------------------------------
# kernel_disable: MSDOS-gated body + return( 0 );
# ---------------------------------------------------------------------------


def test_kernel_disable_body_is_msdos_gated_with_return_zero() -> None:
    """``kernel_disable`` body is ``#ifdef MSDOS`` ... ``#endif`` + ``return(0);``."""
    text = _read_services_c()
    match = re.search(
        r"unsigned\s+int\s+kernel_disable\s*\(\s*PKSD_T\s+\w+\s*\)\s*\{(?P<body>.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "kernel_disable definition not found in services.c"
    body = _strip_comments(match.group("body"))

    # The MSDOS block must be present and gated by #ifdef MSDOS / #endif.
    assert re.search(r"#ifdef\s+MSDOS", body), "missing #ifdef MSDOS block"
    assert re.search(r"#endif", body), "missing #endif"

    # Strip the MSDOS-gated block; the only remaining statement on Linux is
    # `return( 0 );`.
    stripped = re.sub(
        r"#ifdef\s+MSDOS.*?#endif",
        "",
        body,
        flags=re.DOTALL,
    )
    remainder = re.sub(r"\s+", " ", stripped).strip()
    # Accept any whitespace inside the parentheses around 0.
    assert re.fullmatch(r"return\s*\(\s*0\s*\)\s*;", remainder), (
        f"Linux build of kernel_disable should reduce to `return(0);`, got: {remainder!r}"
    )


# ---------------------------------------------------------------------------
# Behavioural smoke tests for the Python ports
# ---------------------------------------------------------------------------


def test_wait_semaphore_python_is_noop() -> None:
    """``wait_semaphore(...)`` returns ``None``."""
    assert wait_semaphore(None) is None
    assert wait_semaphore(object()) is None
    assert wait_semaphore(0) is None


def test_signal_semaphore_python_is_noop() -> None:
    """``signal_semaphore(...)`` returns ``None``."""
    assert signal_semaphore(None) is None
    assert signal_semaphore(object()) is None
    assert signal_semaphore(0) is None


def test_kernel_disable_python_returns_zero() -> None:
    """``kernel_disable(KsdT)`` returns ``0`` and leaves state unchanged."""
    ksd = KsdT()
    snapshot_cmd_flush = ksd.cmd_flush
    snapshot_lang_curr = ksd.lang_curr
    assert kernel_disable(ksd) == 0
    # State must be untouched.
    assert ksd.cmd_flush == snapshot_cmd_flush
    assert ksd.lang_curr == snapshot_lang_curr


def test_repeated_calls_are_idempotent() -> None:
    """The three helpers stay no-ops / return 0 across repeated calls."""
    ksd = KsdT()
    for _ in range(3):
        assert wait_semaphore(None) is None
        assert signal_semaphore(None) is None
        assert kernel_disable(ksd) == 0
