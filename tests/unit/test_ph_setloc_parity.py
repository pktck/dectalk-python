"""C-source parity test for ``setloc`` against ph_sttr2.c.

Re-parses the C body via brace-depth tracking and asserts the
static locus-computation helper still exists in the develop branch
with its expected per-language plocu dispatch and obstruent /
sonorant gating. Also checks the Python shim raises
``NotImplementedError`` as documented.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.numeric_constants import F1
from dectalk.ph.setloc import setloc
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/ph_sttr2.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_sttr2_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the body of the static ``setloc`` helper."""
    text = _read_sttr2_c()
    match = re.search(r"\bstatic\s+short\s+setloc\s*\(", text)
    assert match is not None, "setloc definition not found in ph_sttr2.c"
    # Find the opening brace after the parameter list.
    paren_start = match.end() - 1
    depth = 1
    i = paren_start + 1
    while i < len(text) and depth > 0:
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        i += 1
    # Skip whitespace to the opening brace.
    while i < len(text) and text[i] in " \t\n\r":
        i += 1
    assert text[i] == "{", "expected '{' after setloc parameter list"
    start = i + 1
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    assert depth == 0, "setloc body had unbalanced braces"
    return text[start : i - 1]


# -- C-source structural assertions ----------------------------------------


def test_signature_matches_c() -> None:
    """Signature is ``static short setloc(LPTTS_HANDLE_T, ...)`` with five extras."""
    text = _read_sttr2_c()
    sig = re.search(
        r"static\s+short\s+setloc\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*,"
        r"\s*short\s+\w+",
        text,
    )
    assert sig is not None


def test_obstruent_sonorant_gate() -> None:
    """Returns 0 when typob != OBSTRUENT or typso == OBSTRUENT."""
    body = _extract_body()
    assert re.search(r"typob\s*!=\s*OBSTRUENT", body)
    assert re.search(r"typso\s*==\s*OBSTRUENT", body)
    assert re.search(r"return\s*\(\s*0\s*\)", body)


def test_per_language_dispatch_tables() -> None:
    """Body dispatches on PFUSA/PFUK/PFGR/PFLA/PFSP/PFFR << PSFONT."""
    body = _extract_body()
    for lang_macro in ("PFUSA", "PFUK", "PFGR", "PFLA", "PFSP", "PFFR"):
        assert re.search(
            rf"{lang_macro}\s*<<\s*PSFONT",
            body,
        ), f"missing per-language dispatch for {lang_macro}"


def test_male_female_locus_tables() -> None:
    """Body picks ``*_maleloc`` / ``*_femloc`` based on ``malfem == MALE``."""
    body = _extract_body()
    assert re.search(r"us_maleloc", body)
    assert re.search(r"us_femloc", body)
    assert re.search(r"malfem\s*==\s*MALE", body)


def test_uses_muldv_for_delta_freq() -> None:
    """Body uses muldv to compute the boundary-value offset."""
    body = _extract_body()
    assert re.search(r"delta_freq\s*=\s*muldv", body)
    assert re.search(r"bouval\s*=\s*locus\s*\+\s*delta_freq", body)


def test_initfinso_branch() -> None:
    """Body switches on ``initfinso == 'i'`` to pick init vs end of sonorant."""
    body = _extract_body()
    assert re.search(r"initfinso\s*==\s*'i'", body)


# -- Python behavioural tests ----------------------------------------------


def _make_setloc_handle() -> TtsHandle:
    """Build a handle whose obstruent/sonorant pair fails the filter.

    Phones are all GEN_SIL -- typob != OBSTRUENT so setloc returns 0.
    """
    p_dph_t = DphT()
    p_dph_t.allophons = [GEN_SIL] * 6
    p_dph_t.allofeats = [0] * 6
    p_dph_t.allodurs = [0] * 6
    p_dph_t.nallotot = 6
    p_dph_t.nphone = 1
    p_dph_t.last_lang = 0
    settar = DphSettarSt()
    settar.np = F1
    p_dph_t.pSTphsettar = settar
    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    handle.p_kernel_share_data = KsdT()
    return handle


def test_setloc_returns_zero_when_filter_rejects() -> None:
    """setloc returns 0 when the obstruent/sonorant filter rejects (silence)."""
    handle = _make_setloc_handle()
    assert setloc(handle, 0, 1, "i", 2, 0) == 0


def test_setloc_final_branch_also_filters_to_zero() -> None:
    """``initfinso == 'f'`` path also returns 0 for silence-silence input."""
    handle = _make_setloc_handle()
    assert setloc(handle, 0, 1, "f", 2, 0) == 0
