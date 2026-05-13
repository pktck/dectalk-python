"""C-source parity test for ``phsettar`` against ph_setar.c.

Re-parses the C body via brace-depth tracking and asserts the
top-level target-setting driver still exists in the develop branch
with its expected init_variables call and main parameter loop.
Also checks the Python shim raises ``NotImplementedError`` as
documented.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph.phsettar import phsettar
from dectalk.ph.tts_handle import TtsHandle

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/ph_setar.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_setar_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the body of the top-level ``phsettar`` driver."""
    text = _read_setar_c()
    match = re.search(r"\bvoid\s+phsettar\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)\s*\n\{", text)
    assert match is not None, "phsettar definition not found in ph_setar.c"
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
    assert depth == 0, "phsettar body had unbalanced braces"
    return text[start : i - 1]


# -- C-source structural assertions ----------------------------------------


def test_signature_matches_c() -> None:
    """C signature: ``void phsettar(LPTTS_HANDLE_T phTTS)``."""
    text = _read_setar_c()
    assert re.search(r"\bvoid\s+phsettar\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)", text)


def test_calls_init_variables() -> None:
    """Body opens with an ``init_variables(phTTS, ...)`` call."""
    body = _extract_body()
    assert re.search(r"init_variables\s*\(\s*phTTS", body)


def test_main_loop_iterates_pf1_to_ptilt() -> None:
    """Body loops ``pDphsettar->np`` from &PF1 to &PTILT."""
    body = _extract_body()
    assert re.search(r"pDphsettar\s*->\s*np\s*=\s*&\s*PF1", body)
    assert re.search(r"<=\s*&\s*PTILT", body)


def test_calls_getbegtar_and_gettar_and_make_dip() -> None:
    """Inside the main loop, body calls getbegtar / gettar / make_dip."""
    body = _extract_body()
    assert re.search(r"\bgetbegtar\s*\(", body)
    assert re.search(r"\bgettar\s*\(", body)
    assert re.search(r"\bmake_dip\s*\(", body)


def test_breathysw_toggle() -> None:
    """Body toggles ``breathysw`` based on phcur / FSENTENDS."""
    body = _extract_body()
    assert re.search(r"breathysw\s*=\s*0", body)
    assert re.search(r"breathysw\s*=\s*1", body)


def test_function_is_long() -> None:
    """The body is large (>300 lines) -- matches the ~700-line C function."""
    body = _extract_body()
    assert body.count("\n") > 300, (
        f"phsettar body was only {body.count(chr(10))} lines; expected >300"
    )


# -- Python behavioural tests ----------------------------------------------


def test_python_shim_raises_not_implemented() -> None:
    """Shim raises ``NotImplementedError`` per the deferred-port contract."""
    handle = TtsHandle()
    with pytest.raises(NotImplementedError, match=r"dectalk\._capi"):
        phsettar(handle)


def test_python_shim_error_mentions_phase_plan() -> None:
    """Error message points at the plan file so callers can find context."""
    handle = TtsHandle()
    with pytest.raises(NotImplementedError) as exc_info:
        phsettar(handle)
    assert "Phase E" in str(exc_info.value)
