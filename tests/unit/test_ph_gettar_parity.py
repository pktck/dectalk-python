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
from typing import cast

import pytest

from dectalk.include.usp_codes import USP_AA, USP_K, USP_N
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.gettar import gettar
from dectalk.ph.numeric_constants import F1, F2, F3, FZ
from dectalk.ph.rom_tables import us_femamp, us_femdip, us_femtar
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.us_gettar import us_gettar
from dectalk.ph.utterance_constants import GEN_SIL, NASAL_ZERO_CONS, NON_NASAL_ZERO

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


def _make_handle(
    *,
    phones: list[int],
    np_idx: int,
    nphone: int = 1,
    malfem: int = 0,
) -> TtsHandle:
    """Build a TtsHandle with a populated DphT for gettar testing.

    ``phones`` is the ``allophons[]`` array; ``nphone`` is the current
    walk position (passed as the ``phone`` argument to gettar). The
    fixture leaves last_lang as 0 so the first call triggers the
    table-loading branch.
    """
    p_dph_t = DphT()
    p_dph_t.allophons = list(phones)
    p_dph_t.allofeats = [0] * len(phones)
    p_dph_t.nallotot = len(phones)
    p_dph_t.nphone = nphone
    p_dph_t.malfem = malfem
    p_dph_t.last_lang = 0
    settar = DphSettarSt()
    settar.np = np_idx
    p_dph_t.pSTphsettar = settar
    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    handle.p_kernel_share_data = KsdT()
    return handle


def test_first_call_loads_us_tables() -> None:
    """First US-English call repoints ``p_tar`` / ``p_amp`` / ``p_diph``."""
    handle = _make_handle(phones=[GEN_SIL, USP_AA, GEN_SIL, GEN_SIL], np_idx=FZ)
    gettar(handle, 1)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    assert p_dph_t.p_tar is not None
    assert p_dph_t.p_amp is not None
    assert p_dph_t.p_diph is not None


def test_last_lang_caches_after_load() -> None:
    """After the first call, ``last_lang`` matches the loaded font."""
    handle = _make_handle(phones=[GEN_SIL, USP_AA, GEN_SIL, GEN_SIL], np_idx=FZ)
    gettar(handle, 1)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    assert p_dph_t.last_lang == (0x1E << 8)  # PFUSA << PSFONT


def test_fz_returns_non_nasal_for_non_nasal_phone() -> None:
    """FZ target for AA is NON_NASAL_ZERO (no nasal flag)."""
    handle = _make_handle(phones=[GEN_SIL, USP_AA, GEN_SIL, GEN_SIL], np_idx=FZ)
    assert gettar(handle, 1) == NON_NASAL_ZERO


def test_fz_returns_nasal_const_for_nasal_phone() -> None:
    """FZ target for N is NASAL_ZERO_CONS."""
    handle = _make_handle(phones=[GEN_SIL, USP_N, GEN_SIL, GEN_SIL], np_idx=FZ)
    assert gettar(handle, 1) == NASAL_ZERO_CONS


def test_k_coarticulation_f2_plus_300() -> None:
    """When the current phone is /k/ and np is F2, target gains +300."""
    # Compare the same setup with phone=AA vs phone=K. The K position
    # adds 300 to whatever us_gettar returned for the F2 target.
    base = _make_handle(phones=[GEN_SIL, USP_AA, GEN_SIL, GEN_SIL], np_idx=F2)
    kop = _make_handle(phones=[GEN_SIL, USP_K, GEN_SIL, GEN_SIL], np_idx=F2)
    assert gettar(kop, 1) - gettar(base, 1) == 300 + (
        # The base+K value also differs by whatever us_gettar reports;
        # subtract that natural delta so we isolate the K rule.
        _us_f2_target(USP_K) - _us_f2_target(USP_AA)
    )


def test_k_coarticulation_f3_plus_500() -> None:
    """When the current phone is /k/ and np is F3, target gains +500."""
    base = _make_handle(phones=[GEN_SIL, USP_AA, GEN_SIL, GEN_SIL], np_idx=F3)
    kop = _make_handle(phones=[GEN_SIL, USP_K, GEN_SIL, GEN_SIL], np_idx=F3)
    assert gettar(kop, 1) - gettar(base, 1) == 500 + (_us_f3_target(USP_K) - _us_f3_target(USP_AA))


def _us_f2_target(phone: int) -> int:
    """Helper: read us_femtar's F2 row directly."""
    return us_femtar[(phone & 0xFF) + 1 * 71]


def _us_f3_target(phone: int) -> int:
    """Helper: read us_femtar's F3 row directly."""
    return us_femtar[(phone & 0xFF) + 2 * 71]


def test_non_us_uk_fr_sp_font_raises_not_implemented() -> None:
    """GR/LA fonts still raise pending their *_gettar port."""
    # GR font is 0x1C, so build a phone code with that high byte.
    handle = _make_handle(
        phones=[GEN_SIL, 0x1C00 | 6, GEN_SIL, GEN_SIL],  # GR-font AA
        np_idx=FZ,
    )
    with pytest.raises(NotImplementedError, match=r"GR/LA|gr_/la_"):
        gettar(handle, 1)


def test_npar_zero_index_F1_returns_us_gettar() -> None:  # noqa: N802 -- F1 is C macro name
    """For F1 on AA the gettar return matches a direct us_gettar call."""
    handle = _make_handle(phones=[GEN_SIL, USP_AA, GEN_SIL, GEN_SIL], np_idx=F1)
    direct_handle = _make_handle(
        phones=[GEN_SIL, USP_AA, GEN_SIL, GEN_SIL],
        np_idx=F1,
    )
    # Pre-load tables in the direct-call fixture to match the
    # gettar-loaded state.
    p_dph_t = cast(DphT, direct_handle.p_ph_thread_data)
    p_dph_t.p_tar = list(us_femtar)
    p_dph_t.p_amp = list(us_femamp)
    p_dph_t.p_diph = list(us_femdip)
    expected = us_gettar(direct_handle, 1)
    assert gettar(handle, 1) == expected
