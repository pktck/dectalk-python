"""C-source parity tests for the trivial kernel stubs in kernel/services.c.

Re-parses each function's C source body and asserts:

- ``set_gpio`` / ``clr_gpio`` / ``vol_up`` / ``vol_down`` / ``vol_set``
  have empty bodies in the (relevant build branch of the) C source.
- ``kernel_enable`` has a body that is only ``#ifdef MSDOS`` ... ``#endif``
  followed by ``return;`` — the Linux build executes nothing.
- ``putseq`` Linux branch (``#if defined __linux__ ...``) contains
  ``return(0);``.

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

from dectalk.kernel.kernel_stubs import (
    clr_gpio,
    kernel_enable,
    putseq,
    set_gpio,
    sleep_ms,
    vol_down,
    vol_set,
    vol_up,
)
from dectalk.kernel.ksd_t import KsdT

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


def _extract_function_body(name: str, signature: str) -> str:
    """Return the body (between the outermost braces) of ``name``.

    ``signature`` is a regex matching the prototype up to and including
    the opening ``{``. We greedily consume up to the first ``^}`` line
    (start-of-line close-brace), which matches the canonical kernel
    formatting in services.c.
    """
    text = _read_services_c()
    match = re.search(
        signature + r"\s*\{(?P<body>.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, f"{name}() definition not found in services.c"
    body = match.group("body")
    # Strip block comments and line comments but PRESERVE preprocessor
    # directives — the parity test for kernel_enable needs to see
    # ``#ifdef MSDOS`` / ``#endif`` markers.
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    return body


# ---------------------------------------------------------------------------
# Empty-body stubs: set_gpio / clr_gpio
# ---------------------------------------------------------------------------


def test_set_gpio_body_is_empty() -> None:
    """``set_gpio`` body contains only whitespace in services.c."""
    body = _extract_function_body("set_gpio", r"void\s+set_gpio\s*\(\s*int\s+dummy\s*\)")
    assert body.strip() == "", f"expected empty body, got {body!r}"


def test_clr_gpio_body_is_empty() -> None:
    """``clr_gpio`` body contains only whitespace in services.c."""
    body = _extract_function_body("clr_gpio", r"void\s+clr_gpio\s*\(\s*int\s+dummy\s*\)")
    assert body.strip() == "", f"expected empty body, got {body!r}"


# ---------------------------------------------------------------------------
# kernel_enable: MSDOS-gated body + return;
# ---------------------------------------------------------------------------


def test_kernel_enable_body_is_msdos_gated_with_return() -> None:
    """``kernel_enable`` body is only ``#ifdef MSDOS`` ... ``#endif`` + ``return;``."""
    body = _extract_function_body(
        "kernel_enable",
        r"void\s+kernel_enable\s*\(\s*PKSD_T\s+\w+\s*,\s*unsigned\s+int\s+flags\s*\)",
    )
    # The MSDOS block must be present and gated by #ifdef MSDOS.
    assert re.search(r"#ifdef\s+MSDOS", body), "missing #ifdef MSDOS block"
    assert re.search(r"#endif", body), "missing #endif"
    # The only non-preprocessor statement outside that block is ``return;``.
    # Strip preprocessor directives and the MSDOS block body, then check
    # what's left.
    stripped = re.sub(
        r"#ifdef\s+MSDOS.*?#endif",
        "",
        body,
        flags=re.DOTALL,
    )
    # Remove blank lines / whitespace.
    remainder = re.sub(r"\s+", " ", stripped).strip()
    assert remainder == "return;", (
        f"Linux build of kernel_enable should reduce to `return;`, got: {remainder!r}"
    )


# ---------------------------------------------------------------------------
# vol_up / vol_down / vol_set: entire definitions are MSDOS-only
# ---------------------------------------------------------------------------


def _msdos_block() -> str:
    """Return the giant ``#ifdef MSDOS`` block holding the vol_* funcs."""
    text = _read_services_c()
    # Pick the MSDOS block whose body contains vol_up / vol_down / vol_set.
    # Search the source for an #ifdef MSDOS ... #endif region that owns
    # all three function definitions and return its body.
    for match in re.finditer(
        r"#ifdef\s+MSDOS\s*(.*?)#endif",
        text,
        re.DOTALL,
    ):
        block = match.group(1)
        if "void vol_up" in block and "void vol_down" in block and "void vol_set" in block:
            return block
    pytest.fail("Could not find the #ifdef MSDOS block holding vol_up/vol_down/vol_set")
    return ""  # pragma: no cover — pytest.fail raises


def test_vol_up_body_is_empty_and_msdos_only() -> None:
    """``vol_up`` definition lives only under ``#ifdef MSDOS`` with an empty body."""
    block = _msdos_block()
    match = re.search(r"void\s+vol_up\s*\(\s*int\s+count\s*\)\s*\{([^{}]*)\}", block)
    assert match is not None, "vol_up not found inside #ifdef MSDOS"
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    assert body.strip() == "", f"expected empty vol_up body, got {body!r}"


def test_vol_down_body_is_empty_and_msdos_only() -> None:
    """``vol_down`` definition lives only under ``#ifdef MSDOS`` with an empty body."""
    block = _msdos_block()
    match = re.search(r"void\s+vol_down\s*\(\s*int\s+count\s*\)\s*\{([^{}]*)\}", block)
    assert match is not None, "vol_down not found inside #ifdef MSDOS"
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    assert body.strip() == "", f"expected empty vol_down body, got {body!r}"


def test_vol_set_body_is_empty_and_msdos_only() -> None:
    """``vol_set`` definition lives only under ``#ifdef MSDOS`` with an empty body."""
    block = _msdos_block()
    match = re.search(r"void\s+vol_set\s*\(\s*int\s+count\s*\)\s*\{([^{}]*)\}", block)
    assert match is not None, "vol_set not found inside #ifdef MSDOS"
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    assert body.strip() == "", f"expected empty vol_set body, got {body!r}"


# ---------------------------------------------------------------------------
# putseq: Linux branch returns 0
# ---------------------------------------------------------------------------


def test_putseq_linux_branch_returns_zero() -> None:
    """``putseq`` Linux branch (``__linux__`` gated) body is ``return(0);``."""
    text = _read_services_c()
    # Find the #if defined __linux__ block that wraps int putseq( void *sp ).
    match = re.search(
        r"#if\s+defined\s+__linux__[^\n]*\n"
        r"int\s+putseq\s*\(\s*void\s*\*\s*sp\s*\)\s*\{([^{}]*)\}",
        text,
        re.DOTALL,
    )
    assert match is not None, "Linux branch of putseq not found"
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    assert re.search(r"return\s*\(\s*0\s*\)\s*;", body), (
        f"expected `return(0);` in Linux putseq body, got {body!r}"
    )


# ---------------------------------------------------------------------------
# sleep: services.c only defines it under #ifdef WIN32
# ---------------------------------------------------------------------------


def test_sleep_only_defined_under_win32() -> None:
    """No ``void sleep( unsigned int ... )`` definition exists outside ``#ifdef WIN32``."""
    text = _read_services_c()
    # The sleep definition block: WIN32-gated only.
    match = re.search(
        r"#ifdef\s+WIN32\s*\n"
        r"void\s+sleep\s*\(\s*unsigned\s+int\s+uiTimeInMsec\s*\)\s*\{[^{}]*\}\s*\n"
        r"#endif",
        text,
    )
    assert match is not None, "expected WIN32-gated sleep() definition in services.c"
    # And there must be no other un-gated `void sleep(` definition.
    # Count all `void sleep(` *definitions* (a `{` must follow on the same
    # line or the next, distinguishing from prototypes).
    definitions = re.findall(r"void\s+sleep\s*\([^)]*\)\s*\{", text)
    assert len(definitions) == 1, f"expected exactly 1 sleep() definition, got {len(definitions)}"


# ---------------------------------------------------------------------------
# Behavioural smoke tests for the Python ports
# ---------------------------------------------------------------------------


def test_set_gpio_python_is_noop() -> None:
    """``set_gpio(...)`` returns ``None``."""
    assert set_gpio(0) is None
    assert set_gpio(0xFF) is None
    assert set_gpio(-1) is None


def test_clr_gpio_python_is_noop() -> None:
    """``clr_gpio(...)`` returns ``None``."""
    assert clr_gpio(0) is None
    assert clr_gpio(0xFF) is None
    assert clr_gpio(-1) is None


def test_kernel_enable_python_is_noop() -> None:
    """``kernel_enable(KsdT, flags)`` returns ``None`` without mutating state."""
    ksd = KsdT()
    snapshot_cmd_flush = ksd.cmd_flush
    snapshot_lang_curr = ksd.lang_curr
    assert kernel_enable(ksd, 0) is None
    assert kernel_enable(ksd, 0xDEADBEEF) is None
    # State unchanged.
    assert ksd.cmd_flush == snapshot_cmd_flush
    assert ksd.lang_curr == snapshot_lang_curr


def test_vol_up_python_is_noop() -> None:
    """``vol_up(...)`` returns ``None``."""
    assert vol_up(0) is None
    assert vol_up(99) is None
    assert vol_up(-1) is None


def test_vol_down_python_is_noop() -> None:
    """``vol_down(...)`` returns ``None``."""
    assert vol_down(0) is None
    assert vol_down(99) is None
    assert vol_down(-1) is None


def test_vol_set_python_is_noop() -> None:
    """``vol_set(...)`` returns ``None``."""
    assert vol_set(0) is None
    assert vol_set(50) is None
    assert vol_set(99) is None
    assert vol_set(-1) is None


def test_putseq_python_returns_zero() -> None:
    """``putseq(sp)`` returns ``0`` regardless of input."""
    assert putseq(None) == 0
    assert putseq(object()) == 0
    assert putseq(b"\x00" * 8) == 0


def test_sleep_ms_python_is_noop() -> None:
    """``sleep_ms(...)`` returns ``None`` (Python kernel does not actually sleep)."""
    assert sleep_ms(0) is None
    assert sleep_ms(100) is None
    assert sleep_ms(99999) is None


def test_repeated_calls_are_idempotent() -> None:
    """All stubs stay no-ops across repeated calls."""
    ksd = KsdT()
    for _ in range(3):
        assert set_gpio(1) is None
        assert clr_gpio(1) is None
        assert kernel_enable(ksd, 0) is None
        assert vol_up(1) is None
        assert vol_down(1) is None
        assert vol_set(50) is None
        assert putseq(None) == 0
        assert sleep_ms(0) is None
