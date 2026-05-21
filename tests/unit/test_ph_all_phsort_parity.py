"""C-source parity test for ``all_phsort`` against ph_sort.c.

Re-parses the C body via brace-depth tracking and asserts the
default per-language sort engine still exists in the develop
branch with the expected entry / argument types / per-language
branches. Also checks the Python port runs without error against
a minimally-populated handle.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import cast

import pytest

from dectalk.include.phoneme_codes import PERIOD, S1, WBOUND, USPhoneme
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import LANG_english
from dectalk.ph.all_phsort import all_phsort
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.prosody_constants import DECLARATIVE
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


def _make_handle(lang: int = LANG_english) -> TtsHandle:
    """Return a minimally-populated handle that ``all_phsort`` accepts."""
    p_dph_t = DphT()
    p_dph_t.pSTphsettar = DphSettarSt()
    p_dph_t.symbols = []
    p_dph_t.nsymbtot = 0
    p_dph_t.user_durs = []
    p_dph_t.user_f0 = []
    p_ksd_t = KsdT()
    p_ksd_t.lang_curr = lang
    p_ksd_t.sprate = 200
    handle = TtsHandle()
    handle.p_kernel_share_data = p_ksd_t
    handle.p_ph_thread_data = p_dph_t
    return handle


def test_empty_input_returns_true() -> None:
    """An empty symbol stream returns TRUE (1) without raising."""
    handle = _make_handle()
    assert all_phsort(handle) == 1


def test_halting_aborts_returning_false() -> None:
    """Setting ``halting`` on the kernel handle short-circuits to FALSE."""
    handle = _make_handle()
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    p_ksd_t = cast(KsdT, handle.p_kernel_share_data)
    p_dph_t.symbols = [S1, int(USPhoneme.AE), WBOUND, PERIOD]
    p_dph_t.nsymbtot = len(p_dph_t.symbols)
    p_ksd_t.halting = 1
    assert all_phsort(handle) == 0


def test_clausetype_set_on_period() -> None:
    """A clause-ending PERIOD sets ``clausetype == DECLARATIVE``."""
    handle = _make_handle()
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    p_dph_t.symbols = [WBOUND, S1, int(USPhoneme.AE), WBOUND, PERIOD]
    p_dph_t.nsymbtot = len(p_dph_t.symbols)
    all_phsort(handle)
    assert p_dph_t.clausetype == DECLARATIVE
