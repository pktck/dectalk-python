"""C-source parity test for ``all_phsort`` against ph_sort.c.

Re-parses the C body via brace-depth tracking and asserts the
default per-language sort engine still exists in the develop
branch with the expected entry / argument types / per-language
branches. Also checks the Python shim raises ``NotImplementedError``
as documented.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph.all_phsort import all_phsort
from dectalk.ph.tts_handle import TtsHandle

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/ph_sort.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_ph_sort_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the body of ``all_phsort`` via brace-depth tracking.

    There's only one ``int all_phsort (LPTTS_HANDLE_T phTTS)``
    definition in ph_sort.c.
    """
    text = _read_ph_sort_c()
    match = re.search(r"\bint\s+all_phsort\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)\s*\n\{", text)
    assert match is not None, "all_phsort definition not found in ph_sort.c"
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
    assert depth == 0, "all_phsort body had unbalanced braces"
    return text[start : i - 1]


# -- C-source structural assertions ----------------------------------------


def test_signature_matches_c() -> None:
    """C signature: ``int all_phsort(LPTTS_HANDLE_T phTTS)``."""
    text = _read_ph_sort_c()
    assert re.search(r"\bint\s+all_phsort\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)", text)


def test_body_unpacks_kernel_share_data() -> None:
    """Body loads ``pKsd_t = phTTS->pKernelShareData``."""
    body = _extract_body()
    assert re.search(r"PKSD_T\s+\w+\s*=\s*phTTS\s*->\s*pKernelShareData", body)


def test_body_unpacks_ph_thread_data() -> None:
    """Body loads ``pDph_t = phTTS->pPHThreadData``."""
    body = _extract_body()
    assert re.search(r"PDPH_T\s+\w+\s*=\s*phTTS\s*->\s*pPHThreadData", body)


def test_body_has_per_language_dispatch() -> None:
    """The big sort engine has per-language branches keyed on ``lang_curr``."""
    body = _extract_body()
    # German is the most prominent in-band branch in the all_phsort body.
    assert re.search(r"lang_curr\s*==\s*LANG_german", body)


def test_body_initialises_per_phone_state() -> None:
    """Body resets clause-level counters such as ``nphonetot`` / ``did_del``."""
    body = _extract_body()
    assert re.search(r"pDph_t\s*->\s*nphonetot\s*=\s*0", body)
    assert re.search(r"pDphsettar\s*->\s*did_del\s*=\s*0", body)


def test_function_is_long() -> None:
    """The body is large (>500 lines) -- matches the ~1284-line C function."""
    body = _extract_body()
    assert body.count("\n") > 500, (
        f"all_phsort body was only {body.count(chr(10))} lines; expected >500"
    )


# -- Python behavioural tests ----------------------------------------------


def test_python_shim_raises_not_implemented() -> None:
    """Shim raises ``NotImplementedError`` per the deferred-port contract."""
    handle = TtsHandle()
    with pytest.raises(NotImplementedError, match=r"dectalk\._capi"):
        all_phsort(handle)


def test_python_shim_error_mentions_phase_plan() -> None:
    """Error message points at the plan file so callers can find context."""
    handle = TtsHandle()
    with pytest.raises(NotImplementedError) as exc_info:
        all_phsort(handle)
    assert "Phase E" in str(exc_info.value)
    assert "smooth-hoare" in str(exc_info.value)
