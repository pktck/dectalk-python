"""C-source parity test for ``prdurs`` / ``prphdurs`` against ph_timng.c.

Re-parses the C source files and asserts:

- ``prdurs`` body is gated entirely by ``#ifdef EABDEBUG``.
- ``prphdurs`` body is gated by ``#ifdef EABDEBUG`` and
  ``#ifdef VERBOSE`` (both undefined in the Linux build).
- Neither has any Linux-active code outside the preprocessor
  gates.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph.dph_t import DphT
from dectalk.ph.prdurs import prdurs, prphdurs

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/ph/ph_timng.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_timng_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body(func: str) -> str:
    text = _read_timng_c()
    match = re.search(
        rf"void\s+{re.escape(func)}\s*\([^)]*\)\s*\{{(.+?)^\}}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, f"{func}() not found in ph_timng.c"
    return match.group(1)


def test_prdurs_signature_matches_c() -> None:
    """C signature: ``void prdurs(PDPH_T, short phocur, short durinh, ...)``."""
    text = _read_timng_c()
    sig = re.search(
        r"void\s+prdurs\s*\(\s*PDPH_T\s+\w+\s*,\s*"
        r"short\s+phocur\s*,\s*short\s+durinh\s*,\s*"
        r"short\s+durmin\s*,\s*short\s+deldur\s*,\s*"
        r"short\s+prcnt\s*,\s*int\s+n\s*\)",
        text,
    )
    assert sig is not None


def test_prphdurs_signature_matches_c() -> None:
    """C signature: ``void prphdurs(PDPH_T pDph_t)``."""
    text = _read_timng_c()
    sig = re.search(r"void\s+prphdurs\s*\(\s*PDPH_T\s+\w+\s*\)", text)
    assert sig is not None


def test_prdurs_body_is_eabdebug_gated() -> None:
    """``prdurs`` body has its print logic entirely inside ``#ifdef EABDEBUG``."""
    body = _extract_body("prdurs")
    assert re.search(r"#ifdef\s+EABDEBUG", body)
    assert re.search(r"#endif", body)


def test_prphdurs_body_has_both_gates() -> None:
    """``prphdurs`` body has both ``#ifdef EABDEBUG`` and ``#ifdef VERBOSE``."""
    body = _extract_body("prphdurs")
    assert re.search(r"#ifdef\s+EABDEBUG", body)
    assert re.search(r"#ifdef\s+VERBOSE", body)
    assert len(re.findall(r"#endif", body)) >= 2


def test_prdurs_has_no_linux_active_statements() -> None:
    """``prdurs`` outside the EABDEBUG block contains no executable statements."""
    body = _extract_body("prdurs")
    # Strip comments and the EABDEBUG-gated block.
    stripped = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    stripped = re.sub(r"//.*", "", stripped)
    stripped = re.sub(
        r"#ifdef\s+EABDEBUG.*?#endif",
        "",
        stripped,
        flags=re.DOTALL,
    )
    # The remaining body should be only whitespace.
    assert stripped.strip() == ""


def test_prphdurs_has_no_linux_active_statements() -> None:
    """``prphdurs`` outside the EABDEBUG/VERBOSE block contains no executable statements."""
    body = _extract_body("prphdurs")
    stripped = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    stripped = re.sub(r"//.*", "", stripped)
    # Use a manual depth-tracker for nested #ifdef ... #endif blocks.
    depth = 0
    out_chars: list[str] = []
    for line in stripped.split("\n"):
        token = line.strip()
        if token.startswith("#ifdef") or token.startswith("#ifndef") or token.startswith("#if "):
            depth += 1
            continue
        if token.startswith("#endif"):
            depth = max(0, depth - 1)
            continue
        if depth == 0:
            out_chars.append(line)
    assert "".join(out_chars).strip() == ""


def test_python_prdurs_is_no_op() -> None:
    """Calling the Python port produces no observable effect."""
    state = DphT()
    state.f0 = 42
    prdurs(state, 1, 10, 5, 3, 100, 7)
    # No fields touched.
    assert state.f0 == 42


def test_python_prphdurs_is_no_op() -> None:
    """Calling the Python port produces no observable effect."""
    state = DphT()
    state.f0 = 42
    prphdurs(state)
    assert state.f0 == 42
