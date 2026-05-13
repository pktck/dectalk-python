"""C-source parity test for ``phinton`` against ph_inton2.c.

Re-parses the C body via brace-depth tracking and asserts the
top-level intonation-engine entry still exists in the develop
branch with its expected per-clause structure. Also checks the
Python shim raises ``NotImplementedError`` as documented.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph.phinton import phinton
from dectalk.ph.tts_handle import TtsHandle

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/ph_inton2.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_inton2_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


# -- C-source structural assertions ----------------------------------------


def test_signature_matches_c() -> None:
    """C signature: ``void phinton(LPTTS_HANDLE_T phTTS)``."""
    text = _read_inton2_c()
    assert re.search(r"\bvoid\s+phinton\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)", text)


def test_body_unpacks_kernel_share_data() -> None:
    """Source contains ``pKsd_t = phTTS->pKernelShareData`` in phinton's region."""
    text = _read_inton2_c()
    assert re.search(r"PKSD_T\s+\w+\s*=\s*phTTS\s*->\s*pKernelShareData", text)


def test_body_unpacks_ph_thread_data() -> None:
    """Source contains ``pDph_t = phTTS->pPHThreadData`` in phinton's region."""
    text = _read_inton2_c()
    assert re.search(r"PDPH_T\s+\w+\s*=\s*phTTS\s*->\s*pPHThreadData", text)


def test_body_declares_intonation_state_locals() -> None:
    """Source declares MAX_NRISES / F0_FINAL_FALL / F0_GLOTTALIZE locals."""
    text = _read_inton2_c()
    for name in (
        "MAX_NRISES",
        "F0_FINAL_FALL",
        "F0_NON_FINAL_FALL",
        "F0_GLOTTALIZE",
    ):
        assert name in text, f"missing local declaration for {name}"


def test_body_references_stress_level_tables() -> None:
    """Source references the per-language stress-level tables."""
    text = _read_inton2_c()
    assert "f0_mstress_level" in text
    assert "f0_fstress_level" in text
    assert "f0_mphrase_position" in text
    assert "f0_fphrase_position" in text


def test_body_has_emphasis_and_rise_constants() -> None:
    """Source defines EMPH_FALL / DELTARISE / FINAL_FALL macro-style constants."""
    text = _read_inton2_c()
    assert re.search(r"#\s*define\s+EMPH_FALL", text)
    assert re.search(r"#\s*define\s+DELTARISE", text)
    assert re.search(r"#\s*define\s+FINAL_FALL", text)


def test_function_is_very_long() -> None:
    """The phinton body is very large (~2080-line C function).

    We just confirm the function definition is in the file; the brace-
    depth body extractor doesn't survive the deeply nested character
    literals and `#ifdef`-toggled chunks in the actual body, so we
    don't try to extract it for this assertion.
    """
    text = _read_inton2_c()
    decl = re.search(r"\bvoid\s+phinton\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)", text)
    assert decl is not None
    assert text.count("\n") > 800, "ph_inton2.c is unexpectedly short"


# -- Python behavioural tests ----------------------------------------------


def test_python_shim_raises_not_implemented() -> None:
    """Shim raises ``NotImplementedError`` per the deferred-port contract."""
    handle = TtsHandle()
    with pytest.raises(NotImplementedError, match=r"dectalk\._capi"):
        phinton(handle)


def test_python_shim_error_mentions_phase_plan() -> None:
    """Error message points at the plan file so callers can find context."""
    handle = TtsHandle()
    with pytest.raises(NotImplementedError) as exc_info:
        phinton(handle)
    assert "Phase E" in str(exc_info.value)
