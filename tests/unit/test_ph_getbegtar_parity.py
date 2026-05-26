"""C-source parity test for ``getbegtar`` against ph_setar.c.

Re-parses the C body via brace-depth tracking and asserts the
beginning-of-phone target lookup still exists in the develop branch
with its expected ``gettar`` delegation, diphthong handling, and
per-language ``*_special_coartic`` dispatch.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import cast

import pytest

from dectalk.include.usp_codes import USP_AA, USP_N
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph import getbegtar as getbegtar_mod
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.getbegtar import getbegtar
from dectalk.ph.numeric_constants import F1, FZ
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL, NASAL_ZERO_CONS

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


def _make_handle(phones: list[int], np_idx: int) -> TtsHandle:
    """Minimal handle with US-English tables for getbegtar tests."""
    p_dph_t = DphT()
    p_dph_t.allophons = list(phones)
    p_dph_t.allofeats = [0] * len(phones)
    p_dph_t.nallotot = len(phones)
    p_dph_t.nphone = 1
    p_dph_t.last_lang = 0
    settar = DphSettarSt()
    settar.np = np_idx
    p_dph_t.pSTphsettar = settar
    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    handle.p_kernel_share_data = KsdT()
    return handle


def test_non_diphthong_delegates_to_gettar() -> None:
    """For non-diphthong targets, getbegtar returns gettar's value unchanged."""
    handle = _make_handle([GEN_SIL, USP_N, GEN_SIL, GEN_SIL], np_idx=FZ)
    # N + FZ -> NASAL_ZERO_CONS (positive, non-sentinel).
    assert getbegtar(handle, 1) == NASAL_ZERO_CONS


def test_form_freq_path_executable() -> None:
    """getbegtar runs end-to-end for the F1+AA non-diphthong path."""
    handle = _make_handle([GEN_SIL, USP_AA, GEN_SIL, GEN_SIL], np_idx=F1)
    # AA at F1 is a normal positive target from the table; the
    # diphthong branch (and us_special_coartic call) is skipped.
    result = getbegtar(handle, 1)
    assert result > 0
    # Confirm us_special_coartic wasn't invoked: par_type would be 3.
    settar = cast(DphSettarSt, cast(DphT, handle.p_ph_thread_data).pSTphsettar)
    assert settar.par_type == 3


def test_no_unported_branches() -> None:
    """The Python shim should not raise NotImplementedError for any font.

    Since gr/la/sp_special_coartic are all ported, getbegtar should
    dispatch into them rather than raise for non-US fonts. We verify
    by inspecting the source for the absence of NotImplementedError.
    """
    assert getbegtar_mod.__file__ is not None
    src = Path(getbegtar_mod.__file__).read_text(encoding="utf-8")
    assert "raise NotImplementedError" not in src, (
        "getbegtar still has an unported NotImplementedError branch"
    )
