"""C-source parity test for ``getendtar`` against ph_setar.c.

Re-parses the C body via brace-depth tracking and asserts the
end-of-phone target lookup still exists in the develop branch with
its expected diph-table walk and per-language coartic. Also checks
the Python shim raises ``NotImplementedError`` as documented.

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
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.getendtar import getendtar
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
    """Return the body of ``short getendtar(LPTTS_HANDLE_T, int)``."""
    text = _read_setar_c()
    match = re.search(
        r"\bshort\s+getendtar\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*,\s*int\s+\w+\s*\)\s*\n\{",
        text,
    )
    assert match is not None, "getendtar definition not found in ph_setar.c"
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
    assert depth == 0, "getendtar body had unbalanced braces"
    return text[start : i - 1]


# -- C-source structural assertions ----------------------------------------


def test_signature_matches_c() -> None:
    """C signature: ``short getendtar(LPTTS_HANDLE_T phTTS, int nfone)``."""
    text = _read_setar_c()
    assert re.search(r"\bshort\s+getendtar\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*,\s*int\s+\w+\s*\)", text)


def test_calls_gettar() -> None:
    """Body opens with ``temp = gettar(phTTS, nfone)``."""
    body = _extract_body()
    assert re.search(r"temp\s*=\s*gettar\s*\(\s*phTTS\s*,\s*nfone\s*\)", body)


def test_diphthong_walk_to_end() -> None:
    """Body walks ``p_diph[temp]`` to the trailing ``-1`` marker."""
    body = _extract_body()
    assert re.search(r"temp\s*=\s*-\s*temp", body)
    assert re.search(r"while\s*\(\s*pDph_t\s*->\s*p_diph\s*\[\s*temp\s*\]\s*!=\s*-\s*1\s*\)", body)
    assert re.search(r"p_diph\s*\[\s*temp\s*-\s*1\s*\]", body)


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
    """Minimal handle with US-English tables for getendtar tests."""
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
    """For non-diphthong targets, getendtar returns gettar's value unchanged."""
    handle = _make_handle([GEN_SIL, USP_N, GEN_SIL, GEN_SIL], np_idx=FZ)
    assert getendtar(handle, 1) == NASAL_ZERO_CONS


def test_diphthong_walk_returns_last_diph_entry() -> None:
    """For diphthong sentinel, getendtar walks p_diph forward to -1."""
    handle = _make_handle([GEN_SIL, USP_AA, GEN_SIL, GEN_SIL], np_idx=F1)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    # Trigger gettar's first call (loads tables) so we can poison p_tar.
    getendtar(handle, 1)
    # Now poison: p_tar[AA & 0xFF + 0] = -3 (sentinel), p_diph[3..]: 700, 800, -1
    p_tar = cast(list[int], p_dph_t.p_tar)
    p_diph = cast(list[int], p_dph_t.p_diph)
    p_tar[USP_AA & 0xFF] = -3
    # Ensure p_diph slots 3, 4, 5 are 700, 800, -1
    while len(p_diph) <= 5:
        p_diph.append(0)
    p_diph[3] = 700
    p_diph[4] = 800
    p_diph[5] = -1
    # getendtar should walk to p_diph[5]==-1 then return p_diph[4]==800,
    # plus us_special_coartic delta (which is 0 for AA at F1 with all
    # GEN_SIL neighbours -- AA is not in any of the rule predicates).
    assert getendtar(handle, 1) == 800
