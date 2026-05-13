"""C-source parity test for ``fr_phsort`` against ph_sort.c.

Re-parses the C body via brace-depth tracking and asserts the
French-specific sort engine still exists in the develop branch and
returns TRUE at the end. Also checks the Python shim raises
``NotImplementedError`` as documented.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph.fr_phsort import fr_phsort
from dectalk.ph.tts_handle import TtsHandle

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/ph_sort.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_ph_sort_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the body of ``fr_phsort`` via brace-depth tracking."""
    text = _read_ph_sort_c()
    match = re.search(r"\bint\s+fr_phsort\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)\s*\n\{", text)
    assert match is not None, "fr_phsort definition not found in ph_sort.c"
    start = match.end()
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    assert depth == 0, "fr_phsort body had unbalanced braces"
    return text[start : i - 1]


# -- C-source structural assertions ----------------------------------------


def test_signature_matches_c() -> None:
    """C signature: ``int fr_phsort(LPTTS_HANDLE_T phTTS)``."""
    text = _read_ph_sort_c()
    assert re.search(r"\bint\s+fr_phsort\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)", text)


def test_body_unpacks_kernel_share_data() -> None:
    """Body loads ``pKsd_t = phTTS->pKernelShareData``."""
    body = _extract_body()
    assert re.search(r"PKSD_T\s+\w+\s*=\s*phTTS\s*->\s*pKernelShareData", body)


def test_body_unpacks_ph_thread_data() -> None:
    """Body loads ``pDph_t = phTTS->pPHThreadData``."""
    body = _extract_body()
    assert re.search(r"PDPH_T\s+\w+\s*=\s*phTTS\s*->\s*pPHThreadData", body)


def test_body_returns_true() -> None:
    """The French sort engine returns TRUE on success (see ``return TRUE;``)."""
    body = _extract_body()
    assert re.search(r"\breturn\s+TRUE\s*;", body)


def test_french_engine_comment_present() -> None:
    """End-of-function comment marks the body as French-specific."""
    text = _read_ph_sort_c()
    # The C source uses the comment ``// phsort () for FRENCH`` at the
    # end of fr_phsort's body.
    assert re.search(r"phsort\s*\(\s*\)\s*for\s+FRENCH", text, re.IGNORECASE)


# -- Python behavioural tests ----------------------------------------------


def test_python_shim_raises_not_implemented() -> None:
    """Shim raises ``NotImplementedError`` per the deferred-port contract."""
    handle = TtsHandle()
    with pytest.raises(NotImplementedError, match=r"dectalk\._capi"):
        fr_phsort(handle)


def test_python_shim_error_mentions_phase_plan() -> None:
    """Error message points at the plan file so callers can find context."""
    handle = TtsHandle()
    with pytest.raises(NotImplementedError) as exc_info:
        fr_phsort(handle)
    assert "Phase E" in str(exc_info.value)
