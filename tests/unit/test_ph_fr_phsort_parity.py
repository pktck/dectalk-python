"""C-source parity test for ``fr_phsort`` against ph_sort.c.

Re-parses the C body via brace-depth tracking and asserts the
French-specific sort engine still exists in the develop branch and
returns TRUE at the end. Also checks the Python port runs without
error against a minimally-populated handle.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import cast

import pytest

from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import LANG_french
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
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


def _make_handle() -> TtsHandle:
    """Return a minimally-populated handle keyed for ``LANG_french``."""
    p_dph_t = DphT()
    p_dph_t.pSTphsettar = DphSettarSt()
    p_dph_t.symbols = []
    p_dph_t.nsymbtot = 0
    p_dph_t.user_durs = []
    p_dph_t.user_f0 = []
    p_dph_t.sentstruc = [0] * 32
    p_ksd_t = KsdT()
    p_ksd_t.lang_curr = LANG_french
    p_ksd_t.sprate = 200
    handle = TtsHandle()
    handle.p_kernel_share_data = p_ksd_t
    handle.p_ph_thread_data = p_dph_t
    return handle


def test_empty_input_returns_true() -> None:
    """An empty symbol stream returns TRUE (1) without raising."""
    handle = _make_handle()
    assert fr_phsort(handle) == 1


def test_halting_aborts_returning_false() -> None:
    """Setting ``halting`` on the kernel handle short-circuits to FALSE."""
    handle = _make_handle()
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    p_ksd_t = cast(KsdT, handle.p_kernel_share_data)
    p_dph_t.symbols = [5, 0x70]  # phoneme + FrontMot
    p_dph_t.nsymbtot = len(p_dph_t.symbols)
    p_ksd_t.halting = 1
    assert fr_phsort(handle) == 0


def test_f0mode_set_to_normal_on_entry() -> None:
    """The clause sweep resets ``f0mode`` to NORMAL (1)."""
    handle = _make_handle()
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    p_dph_t.f0mode = 99  # poison value
    fr_phsort(handle)
    assert p_dph_t.f0mode == 1  # NORMAL
