"""Shared fixtures for the parity test suite.

The parity tests build a tiny C harness (`c_harness/llsyn_dump.c`) around
the FONIX `LLSynthesize()` and run it side-by-side with our Python
:func:`dectalk.hlsyn.synthesize.ll_synthesize`. They depend on:

- a working C compiler (``gcc`` / ``cc`` / ``clang`` / ``$CC``, or MSVC
  ``cl.exe`` on Windows), and
- the C source tree shipped under ``tests/parity/c_harness/``.

Tests skip cleanly when those preconditions aren't met so the suite
still runs in environments without a compiler. The built binary is
*never* committed to git — each runner builds its own (the binary path
is in `.gitignore`); we also invalidate any stale binary that isn't
executable on the current platform before deciding whether to rebuild.
"""

from __future__ import annotations

import contextlib
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

C_HARNESS_DIR: Path = Path(__file__).parent / "c_harness"
_BINARY_NAME: str = "llsyn_dump.exe" if sys.platform == "win32" else "llsyn_dump"
HARNESS_BINARY: Path = C_HARNESS_DIR / _BINARY_NAME
HARNESS_SOURCES: list[Path] = [
    C_HARNESS_DIR / name for name in ("llsyn_dump.c", "reson.c", "voice.c", "sample.c", "frame.c")
]


def _which_unix_cc() -> str | None:
    """Find a Unix-style C compiler (gcc/cc/clang) in PATH or via ``$CC``."""
    return (
        os.environ.get("CC") or shutil.which("gcc") or shutil.which("clang") or shutil.which("cc")
    )


def _which_msvc() -> str | None:
    """Find Microsoft's ``cl.exe`` (only meaningful on Windows runners)."""
    if sys.platform != "win32":
        return None
    return shutil.which("cl") or shutil.which("cl.exe")


def _is_stale_binary(path: Path) -> bool:
    """True when the cached binary won't run on the current platform.

    A leftover Linux ELF on a macOS / Windows runner satisfies
    ``Path.exists()`` but can't actually be executed. We detect that case
    by checking the file header bytes against the host platform.
    """
    if not path.exists():
        return True
    try:
        with path.open("rb") as fh:
            head = fh.read(4)
    except OSError:
        return True
    is_elf = head.startswith(b"\x7fELF")
    is_macho = head[:4] in (b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf",
                            b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe",
                            b"\xca\xfe\xba\xbe")  # fmt: skip
    is_pe = head.startswith(b"MZ")
    if sys.platform == "linux":
        return not is_elf
    if sys.platform == "darwin":
        return not is_macho
    if sys.platform == "win32":
        return not is_pe
    return False  # unknown platform — trust whatever's there


def _build_unix(cc: str) -> tuple[int, str]:
    """Compile the harness with a Unix-style compiler. Returns (rc, stderr)."""
    cmd = [cc, "-O2", "-o", str(HARNESS_BINARY), *(str(p) for p in HARNESS_SOURCES), "-lm"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.returncode, result.stderr


def _build_msvc(cl: str) -> tuple[int, str]:
    """Compile the harness with MSVC ``cl.exe``. Returns (rc, stderr)."""
    # cl: /Fe<exe>  /TC  <sources>
    cmd = [
        cl,
        "/nologo",
        "/O2",
        "/TC",  # treat .c sources as C
        f"/Fe:{HARNESS_BINARY}",
        *(str(p) for p in HARNESS_SOURCES),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.returncode, result.stderr


@pytest.fixture(scope="session")
def llsyn_dump() -> Path:
    """Build the C parity harness if a compiler is available; skip otherwise.

    Skips the test rather than failing when:
    - no C compiler is reachable on the runner;
    - compilation fails (we surface stderr in the skip reason);
    - the cached binary on disk is stale (built for a different OS).
    """
    if _is_stale_binary(HARNESS_BINARY):
        # Drop the foreign artifact so the rebuild path runs.
        with contextlib.suppress(OSError):
            HARNESS_BINARY.unlink(missing_ok=True)

    if HARNESS_BINARY.exists() and os.access(HARNESS_BINARY, os.X_OK):
        return HARNESS_BINARY

    unix_cc = _which_unix_cc()
    msvc = _which_msvc()
    if unix_cc is not None:
        rc, err = _build_unix(unix_cc)
    elif msvc is not None:
        rc, err = _build_msvc(msvc)
    else:
        pytest.skip(
            f"no C compiler available on {platform.system()}; skipping LLSynthesize parity tests"
        )

    if rc != 0:
        pytest.skip(f"could not build C harness: {err.strip() or 'see compiler output'}")
    return HARNESS_BINARY


# -- Stop-hook gate: fail-fast for test_binary_wav_parity.py ---------------
#
# The end-to-end binary-WAV parity test parametrizes ~133k corpus prompts.
# When the .claude/hooks/stop_continue.sh stop-hook runs it as a gate to
# decide whether to allow the assistant to stop, we want it to exit on the
# FIRST mismatch -- not after the full ~37h corpus walk. We can't add `-x`
# to the hook itself (hook files require user re-approval to edit), so this
# repo-side conftest hook does the same job: when DECTALK_PARITY_FAIL_FAST
# is set (which the hook can do via its own env), or whenever the runner
# is the stop-hook (detected via DECTALK_DISABLE_CAPI=1), short-circuit
# after the first parity failure.

_parity_module_path = "test_binary_wav_parity.py"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark the binary-WAV parity test for fail-fast under stop-hook context.

    When run under DECTALK_DISABLE_CAPI=1 (the hook's gate condition) or
    when DECTALK_PARITY_FAIL_FAST=1 is set explicitly, configure session
    fail-fast so the first WAV mismatch ends the run. We do this by
    setting the session's ``stop`` flag from the report hook below; this
    function just records whether fail-fast should be active.
    """
    fail_fast = (
        os.environ.get("DECTALK_PARITY_FAIL_FAST", "0") == "1"
        or os.environ.get("DECTALK_DISABLE_CAPI", "0") == "1"
    )
    if not fail_fast:
        return
    for item in items:
        if _parity_module_path in str(item.fspath):
            item.add_marker(pytest.mark.binary_wav_parity_gate)


def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> None:
    """Halt the session on first binary-WAV parity failure under stop-hook."""
    if call.excinfo is None or call.when != "call":
        return
    if not any(
        marker.name == "binary_wav_parity_gate" for marker in item.iter_markers()
    ):
        return
    session = item.session
    session.shouldstop = (
        "stop-hook gate: first binary-WAV parity mismatch encountered; "
        "halting before the remaining corpus prompts"
    )
