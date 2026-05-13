"""C-source parity test for ``gettar`` against ph_setar.c.

Re-parses the C body via brace-depth tracking and asserts the
per-phone target-lookup dispatcher still exists in the develop
branch with its expected per-language table switching. Also checks
the Python shim raises ``NotImplementedError`` as documented.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph.gettar import gettar
from dectalk.ph.tts_handle import TtsHandle

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/ph_setar.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_setar_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the body of ``int gettar(LPTTS_HANDLE_T, int)``.

    The C source has both a prototype (``int gettar(LPTTS_HANDLE_T phTTS,
    int phone);``) and the definition. The definition's brace opens on
    the same line via ``) {`` -- the prototype ends in ``;``.
    """
    text = _read_setar_c()
    # Look for the definition: name(...args...) {
    for match in re.finditer(
        r"\bint\s+gettar\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*,\s*int\s+\w+\s*\)\s*\{",
        text,
    ):
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
        if depth == 0:
            return text[start : i - 1]
    raise AssertionError("gettar definition not found in ph_setar.c")


# -- C-source structural assertions ----------------------------------------


def test_signature_matches_c() -> None:
    """C signature: ``int gettar(LPTTS_HANDLE_T phTTS, int phone)``."""
    text = _read_setar_c()
    assert re.search(r"\bint\s+gettar\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*,\s*int\s+\w+\s*\)", text)


def test_uses_get_phone_with_phone_plus_index() -> None:
    """Body indexes ``get_phone(pDph_t, phone + index[count])``."""
    body = _extract_body()
    assert re.search(r"get_phone\s*\(\s*pDph_t\s*,\s*\(?\s*phone\s*\+\s*index", body)


def test_per_language_p_diph_p_tar_branches() -> None:
    """Body re-points ``p_diph`` / ``p_tar`` per-language."""
    body = _extract_body()
    assert re.search(r"p_diph\s*=", body)
    assert re.search(r"p_tar\s*=", body)
    for lang in ("us_maldip", "us_femdip", "uk_maldip", "uk_femdip", "gr_maldip"):
        assert lang in body, f"missing {lang!r} table assignment"


def test_last_lang_tracking() -> None:
    """Body caches ``pDph_t->last_lang`` to skip redundant re-pointing."""
    body = _extract_body()
    assert re.search(r"last_lang", body)


def test_loops_over_index_array() -> None:
    """Body iterates ``while (count <= 3)`` over the ``index[4]`` array."""
    body = _extract_body()
    assert re.search(r"count\s*<=\s*3", body)
    assert re.search(r"index\s*\[\s*4\s*\]\s*=\s*\{\s*0\s*,\s*1\s*,\s*2\s*,\s*-1\s*\}", body)


# -- Python behavioural tests ----------------------------------------------


def test_python_shim_raises_not_implemented() -> None:
    """Shim raises ``NotImplementedError`` per the deferred-port contract."""
    handle = TtsHandle()
    with pytest.raises(NotImplementedError, match=r"dectalk\._capi"):
        gettar(handle, 0)


def test_python_shim_error_mentions_phase_plan() -> None:
    """Error message points at the plan file so callers can find context."""
    handle = TtsHandle()
    with pytest.raises(NotImplementedError) as exc_info:
        gettar(handle, 5)
    assert "Phase E" in str(exc_info.value)
