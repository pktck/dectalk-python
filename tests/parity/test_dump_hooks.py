"""Smoke tests for the per-stage parity-dump infrastructure.

Validates the kernel-stage dump hook added by
``tests/parity/c_patches/0002-stage-boundary-dumps.patch``. The hook is
gated on ``DECTALK_DUMP_DIR``; :py:meth:`dectalk._capi.CAPI.dump_pipeline`
points it at a fresh temp dir per call and reads the result back.

Skips cleanly when the C oracle (source-built libtts + shipped binary)
is not present.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dectalk._capi import CAPI, CAPIError

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_BIN_ROOT = Path(os.environ.get("DECTALK_BIN", "/tmp/dectalk-binary-stable"))


def _have_artefacts() -> bool:
    """True if both the source-built libtts.so and the shipped binary exist."""
    has_lib = any(_SRC_ROOT.glob("src/dtalkml/build/*/us/release/libtts.so")) and any(
        _SRC_ROOT.glob("src/dapi/build/dectalk/*/us/release/libtts_us.so")
    )
    has_bin = (_BIN_ROOT / "say").is_file() and (_BIN_ROOT / "DECtalk.conf").is_file()
    return has_lib and has_bin


pytestmark = pytest.mark.skipif(
    not _have_artefacts(),
    reason="locally-built libtts or shipped DECtalk binary not present",
)


@pytest.fixture(scope="module")
def capi() -> CAPI:
    """Module-scoped CAPI instance reused across the dump-hook tests."""
    return CAPI(src_root=_SRC_ROOT, data_root=_BIN_ROOT)


def test_kernel_dump_is_non_empty(capi: CAPI) -> None:
    """The kernel dump for ``hello world`` must contain non-trivial bytes."""
    dumps = capi.dump_pipeline("hello world", ["kernel"])
    assert "kernel" in dumps
    payload = dumps["kernel"]
    assert payload, "kernel dump was empty — patch not applied or hook misfired?"
    # The hook writes one ``kernel_write <length>`` line per chunk, plus
    # a hex-byte line. The minimum useful dump has at least a header
    # token and the literal "hello" somewhere in the hex payload.
    assert b"kernel_write" in payload
    # 'h' is 0x68, 'e' is 0x65, 'l' is 0x6c, 'o' is 0x6f. We don't
    # assert exact bytes (the say binary may append a force char) — just
    # that the input text shows through.
    assert b"68" in payload  # 'h'
    assert b"6f" in payload  # 'o'


def test_kernel_dump_is_deterministic(capi: CAPI) -> None:
    """Two back-to-back calls with the same input must yield byte-identical dumps."""
    a = capi.dump_pipeline("hello world", ["kernel"])["kernel"]
    b = capi.dump_pipeline("hello world", ["kernel"])["kernel"]
    assert a == b, f"kernel dumps diverged across calls: {len(a)} B vs {len(b)} B"


def test_unsupported_stage_raises(capi: CAPI) -> None:
    """Asking for a stage we haven't implemented yet is a CAPIError."""
    with pytest.raises(CAPIError):
        capi.dump_pipeline("hello", ["vtm"])
