"""C-source parity test for ``getbegtar`` against ph_setar.c.

Re-parses the C body via brace-depth tracking and asserts the
beginning-of-phone target lookup still exists in the develop branch
with its expected ``gettar`` delegation and diphthong handling. Also
checks the Python shim raises ``NotImplementedError`` as documented.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph.getbegtar import getbegtar
from dectalk.ph.tts_handle import TtsHandle

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/ph_setar.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_setar_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the body of ``short getbegtar(LPTTS_HANDLE_T, int)``."""
    text = _read_setar_c()
    match = re.search(
        r"\bshort\s+getbegtar\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*,\s*int\s+\w+\s*\)\s*\n\{",
        text,
    )
    assert match is not None, "getbegtar definition not found in ph_setar.c"
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
    assert depth == 0, "getbegtar body had unbalanced braces"
    return text[start : i - 1]


# -- C-source structural assertions ----------------------------------------


def test_signature_matches_c() -> None:
    """C signature: ``short getbegtar(LPTTS_HANDLE_T phTTS, int nfone)``."""
    text = _read_setar_c()
    assert re.search(r"\bshort\s+getbegtar\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*,\s*int\s+\w+\s*\)", text)


def test_calls_gettar() -> None:
    """Body opens with ``temp = gettar(phTTS, nfone)``."""
    body = _extract_body()
    assert re.search(r"temp\s*=\s*gettar\s*\(\s*phTTS\s*,\s*nfone\s*\)", body)


def test_diphthong_branch() -> None:
    """Body enters the diphthong branch when ``temp < -1``."""
    body = _extract_body()
    assert re.search(r"temp\s*<\s*-\s*1", body)
    assert re.search(r"p_diph\s*\[\s*-\s*temp\s*\]", body)


def test_par_type_is_form_freq_gate() -> None:
    """Body gates the per-language coartic on ``par_type IS_FORM_FREQ``."""
    body = _extract_body()
    assert re.search(r"par_type\s+IS_FORM_FREQ", body)


def test_per_language_special_coartic() -> None:
    """Body dispatches to ``us_special_coartic`` / ``gr_*`` / ``la_*`` / ``sp_*``."""
    body = _extract_body()
    for fn in (
        "us_special_coartic",
        "gr_special_coartic",
        "la_special_coartic",
        "sp_special_coartic",
    ):
        assert fn in body, f"missing call to {fn}"


def test_returns_temp() -> None:
    """Body returns the computed ``temp`` value."""
    body = _extract_body()
    assert re.search(r"return\s*\(\s*temp\s*\)", body)


# -- Python behavioural tests ----------------------------------------------


def test_python_shim_raises_not_implemented() -> None:
    """Shim raises ``NotImplementedError`` per the deferred-port contract."""
    handle = TtsHandle()
    with pytest.raises(NotImplementedError, match=r"dectalk\._capi"):
        getbegtar(handle, 0)


def test_python_shim_error_mentions_phase_plan() -> None:
    """Error message points at the plan file so callers can find context."""
    handle = TtsHandle()
    with pytest.raises(NotImplementedError) as exc_info:
        getbegtar(handle, 3)
    assert "Phase E" in str(exc_info.value)
