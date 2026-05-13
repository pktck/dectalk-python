"""C-source parity test for ``EmptyVtmPipe`` against vtmiont.c.

Asserts the C body's pipe-drain structure is documented; the
Python port is an architectural no-op so the parity check is
limited to existence + shape rather than behavioural equivalence.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import inspect
import os
import re
from pathlib import Path

import pytest

from dectalk.vtm.empty_vtm_pipe import empty_vtm_pipe

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/vtm/vtmiont.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_vtmiont_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_vtmiont_c()
    match = re.search(
        r"void\s+EmptyVtmPipe\s*\([^)]*\)\s*\n\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "EmptyVtmPipe body not found"
    return match.group(1)


def test_signature_matches_c() -> None:
    """C signature: ``void EmptyVtmPipe(PKSD_T pKsd_t)``."""
    text = _read_vtmiont_c()
    sig = re.search(r"void\s+EmptyVtmPipe\s*\(\s*PKSD_T\s+\w+\s*\)", text)
    assert sig is not None


def test_drains_pipe_via_read_pipe_loop() -> None:
    """The body walks the queue via ``read_pipe(... &wControl, 1)``."""
    body = _extract_body()
    assert re.search(
        r"read_pipe\s*\(\s*pKsd_t->vtm_pipe\s*,\s*&\s*wControl\s*,\s*1\s*\)",
        body,
    )


def test_uses_drain_interlock_flag() -> None:
    """The C source uses ``bVtmDrainRequested`` as the inter-thread interlock."""
    body = _extract_body()
    assert "bVtmDrainRequested" in body


def test_python_returns_none() -> None:
    """The Python shim is a synchronous no-op returning ``None``."""
    assert empty_vtm_pipe() is None


def test_python_takes_no_args() -> None:
    """``pKsd_t`` is the only C arg; Python takes nothing (no pipe to drain)."""
    sig = inspect.signature(empty_vtm_pipe)
    assert len(sig.parameters) == 0
