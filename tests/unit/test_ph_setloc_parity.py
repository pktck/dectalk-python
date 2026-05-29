"""C-source parity test for ``setloc`` against ph_sttr2.c.

Re-parses the C body via brace-depth tracking and asserts the
static locus-computation helper still exists in the develop branch
with its expected per-language plocu dispatch and obstruent /
sonorant gating. Also exercises the Python port at the
filter-rejection boundary (the path callers most often hit when
phonemes are silence or a non-obstruent leads the pair) and on a
happy-path with a synthetic US locus table to verify the
``muldv``-based ``bouval`` write-back.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.cmd_codes import PSFONT
from dectalk.include.phoneme_codes import PFUSA, USPhoneme
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph import setloc as setloc_module
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.numeric_constants import F1, F2, MALE
from dectalk.ph.rom_tables import us_maleloc, us_plocu
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


def test_rounded_sonor_cons_remap_to_back_rounded_vowel() -> None:
    """Body remaps ROUNDED_SONOR_CONS sonorant class to BACK_ROUNDED_VOWEL locus."""
    body = _extract_body()
    assert re.search(r"typso\s*==\s*ROUNDED_SONOR_CONS", body)
    assert re.search(r"sontyx\s*=\s*BACK_ROUNDED_VOWEL", body)


def test_low_vowel_remap_to_back() -> None:
    """Body remaps low-vowel sonorant (typso == 6) to back-unrounded (sontyx == 2)."""
    body = _extract_body()
    # The comment is `typso == 6) //LOW_VOWEL)` in the C source.
    assert re.search(r"typso\s*==\s*6", body)
    assert re.search(r"sontyx\s*=\s*2", body)


def test_locus_triplet_stride() -> None:
    """Body adds ``3 * (pDphsettar->np - &PF1)`` to ploc for F1/F2/F3 stride."""
    body = _extract_body()
    assert re.search(r"ploc\s*\+\s*\(?\s*3\s*\*\s*\(\s*pDphsettar->np\s*-\s*&PF1\s*\)", body)


def test_durtran_via_mstofr() -> None:
    """Body writes ``pDphsettar->durtran = mstofr(p_locus[ploc+2])``."""
    body = _extract_body()
    assert re.search(r"durtran\s*=\s*mstofr\s*\(", body)


def test_f2back_affil_branch() -> None:
    """Body has the F2-back-cavity prcnt-reduction branch."""
    body = _extract_body()
    # The C uses ``f2backaffil IS_PLUS`` (a macro) and tests np == &PF2.
    assert re.search(r"f2backaffil\s+IS_PLUS", body)
    assert re.search(r"pDphsettar->np\s*==\s*&PF2", body)


def test_vv_coartic_branch_calls_helper() -> None:
    """Body calls ``vv_coartic_across_c`` when both segments are vowels at F2."""
    body = _extract_body()
    assert re.search(r"vv_coartic_across_c\s*\(", body)
    assert re.search(r"phone_feature\(\s*pDph_t\s*,\s*fonsonor\s*\)\s*&\s*FVOWEL", body)
    assert re.search(r"phone_feature\(\s*pDph_t\s*,\s*fonvowel\s*\)\s*&\s*FVOWEL", body)


def test_returns_one_on_success() -> None:
    """Body ends with ``return (1)`` on the success path."""
    body = _extract_body()
    assert re.search(r"return\s*\(\s*1\s*\)", body)


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


def test_setloc_happy_path_us_s_iy_writes_bouval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """US `S` (obstruent) → `IY` (front vowel) succeeds and writes ``bouval``.

    Walks one full pass through the US-font branch with a synthetic
    ``curval``. ``S`` has ``us_endtyp == 4`` (OBSTRUENT) and ``IY``
    has ``us_begtyp == 1`` (FRONT_VOWEL == sontyx 1), so the filter
    passes and the F1 row of ``us_maleloc`` should be applied.
    """
    # Stub getbegtar/getendtar to return a deterministic curval so we
    # don't have to set up the whole gettar/diph chain.
    fake_curval = 700

    def _stub_curval(_h: TtsHandle, _n: int) -> int:
        return fake_curval

    monkeypatch.setattr(setloc_module, "getbegtar", _stub_curval)
    monkeypatch.setattr(setloc_module, "getendtar", _stub_curval)

    fonobst_us_s = (PFUSA << PSFONT) | int(USPhoneme.S)
    fonsonor_us_iy = (PFUSA << PSFONT) | int(USPhoneme.IY)
    fonvowel_us_iy = fonsonor_us_iy

    p_dph_t = DphT()
    p_dph_t.allophons = [fonobst_us_s, fonsonor_us_iy, fonvowel_us_iy, GEN_SIL]
    p_dph_t.allofeats = [0] * 4
    p_dph_t.allodurs = [0] * 4
    p_dph_t.nallotot = 4
    p_dph_t.malfem = MALE
    settar = DphSettarSt()
    settar.np = F1
    p_dph_t.pSTphsettar = settar
    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    handle.p_kernel_share_data = KsdT()

    rc = setloc(handle, nfonobst=0, nfonsonor=1, initfinso="i", nfonvowel=2, feanex=0)

    # Filter passed and a non-zero locus entry exists for S+sontyx=1.
    assert rc == 1

    # us_plocu[41] == 73 (the /S/ FRONT-block locus pointer) under the
    # active 57-strided ROM. F1 has sontyx stride 0, so the triplet is
    # us_maleloc[73..75] == (310, 40, 40).
    s_locus_ptr = us_plocu[int(USPhoneme.S)]
    assert s_locus_ptr == 73
    locus_freq = us_maleloc[s_locus_ptr]
    prcnt = us_maleloc[s_locus_ptr + 1]
    # bouval = locus + muldv(prcnt, curval - locus, 100)
    #        = 310 + ((40 * (700 - 310)) / 100) under integer arithmetic.
    expected_delta = (prcnt * (fake_curval - locus_freq)) // 100
    assert settar.bouval == locus_freq + expected_delta
    # The C source's `p_locus` pointer must be assigned to us_maleloc.
    assert p_dph_t.p_locus is not None
    assert list(p_dph_t.p_locus[:3]) == list(us_maleloc[:3])


def test_setloc_returns_zero_when_np_above_f3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Filter rejects when ``np > F3`` -- only F1/F2/F3 get a locus."""

    # Even with valid obstruent/sonorant, np > F3 should bail with 0.
    def _stub_curval(_h: TtsHandle, _n: int) -> int:
        return 500

    monkeypatch.setattr(setloc_module, "getbegtar", _stub_curval)
    fonobst_us_s = (PFUSA << PSFONT) | int(USPhoneme.S)
    fonsonor_us_iy = (PFUSA << PSFONT) | int(USPhoneme.IY)
    p_dph_t = DphT()
    p_dph_t.allophons = [fonobst_us_s, fonsonor_us_iy, GEN_SIL]
    p_dph_t.allofeats = [0] * 3
    p_dph_t.allodurs = [0] * 3
    p_dph_t.nallotot = 3
    p_dph_t.malfem = MALE
    settar = DphSettarSt()
    settar.np = F2 + 10  # above F3
    p_dph_t.pSTphsettar = settar
    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    handle.p_kernel_share_data = KsdT()
    assert setloc(handle, 0, 1, "i", 2, 0) == 0
