"""C-source parity test for ``la_gettar`` against src/dapi/src/ph/p_la_st1.c.

Re-parses the C body via brace-depth tracking and asserts the function
still exists in the develop branch with its expected control flow:

- pphotr stride uses ``LA_TOT_ALLOPHONES`` (= 39).
- par_type dispatches on ``IS_FORM_FREQ_OR_BW`` / ``IS_AV_OR_AH`` /
  ``IS_PARALLEL_FORM_AMP`` / ``IS_NASAL_ZERO_FREQ``.
- LA-specific rule literals (``LAP_N``, ``LAP_R``, ``LAP_F`` etc.)
  and the magic constants ``300``, ``90``, ``-100`` from the
  formant-frequency branch are present.
- TILT cascade hits ``LAP_DH``/``LAP_GH`` band and writes ``24``.

Also exercises :func:`dectalk.ph.la_gettar.la_gettar` end-to-end with
a minimal :class:`~dectalk.ph.dph_t.DphT` to confirm:

- the FORM_FREQ branch reads ``p_tar[(phone & PVALUE) + pphotr]``;
- the FZ branch returns ``NASAL_ZERO_BOUNDARY`` for nasal phones and
  ``NON_NASAL_ZERO`` otherwise;
- the LA-specific F1 reduction for /r/ following back vowels fires.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import cast

import pytest

from dectalk.include.lap_codes import (
    LAP_A,
    LAP_F,
    LAP_I,
    LAP_J,
    LAP_N,
    LAP_O,
    LAP_R,
)
from dectalk.include.usp_codes import USP_M
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FSTRESS_1
from dectalk.ph.la_gettar import la_gettar
from dectalk.ph.numeric_constants import AP, AV, B3, F1, FZ
from dectalk.ph.parameter_tables import partyp
from dectalk.ph.rom_tables import la_femtar, la_maltar
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import NASAL_ZERO_BOUNDARY, NON_NASAL_ZERO

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/p_la_st1.c"


def _read_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the body (between outer ``{}``) of the C ``la_gettar`` function."""
    text = _read_c()
    pattern = re.compile(r"\bla_gettar\s*\(")
    for match in pattern.finditer(text):
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
        while i < len(text) and text[i] in " \t\n\r":
            i += 1
        if i >= len(text) or text[i] != "{":
            continue
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
        if depth == 0:
            return text[start : i - 1]
    raise AssertionError(f"la_gettar definition not found in {_C_FILE.name}")


# -- C-source structural assertions ----------------------------------------

_skip_no_csrc = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


@_skip_no_csrc
def test_signature_exists_in_c() -> None:
    """``short la_gettar(LPTTS_HANDLE_T phTTS, int nphone_temp)`` defined."""
    assert re.search(r"\bshort\s+la_gettar\s*\(\s*LPTTS_HANDLE_T\s+phTTS", _read_c())


@_skip_no_csrc
def test_body_uses_la_tot_allophones_stride() -> None:
    """C body multiplies npar by ``LA_TOT_ALLOPHONES`` (39)."""
    body = _extract_body()
    assert "LA_TOT_ALLOPHONES" in body
    # Both the np < PFZ and np >= PFZ branches multiply by it.
    assert re.search(r"npar\s*\)?\s*\*\s*LA_TOT_ALLOPHONES", body)
    assert re.search(r"\(\s*npar\s*-\s*1\s*\)\s*\*\s*LA_TOT_ALLOPHONES", body)


@_skip_no_csrc
def test_body_dispatches_on_partype() -> None:
    """C body switches on ``par_type`` via the four ``IS_*`` macros."""
    body = _extract_body()
    assert re.search(r"par_type\s*=\s*partyp\s*\[\s*npar\s*\]", body)
    for macro in (
        "IS_FORM_FREQ_OR_BW",
        "IS_AV_OR_AH",
        "IS_PARALLEL_FORM_AMP",
        "IS_NASAL_ZERO_FREQ",
    ):
        assert macro in body, f"missing par_type branch {macro}"


@_skip_no_csrc
def test_b3_nasal_clamp_uses_300_not_1600() -> None:
    """C body clamps B3 for /n/, /nh/, /nx/ to ``300`` (post-1996 EDB fix)."""
    body = _extract_body()
    # Three nasal codes are tested adjacent to high-front vowels.
    assert re.search(r"phone_temp\s*==\s*LAP_N\b", body)
    assert re.search(r"phone_temp\s*==\s*LAP_NH\b", body)
    assert re.search(r"phone_temp\s*==\s*LAP_NX\b", body)
    assert re.search(r"tartemp\s*=\s*300\s*;", body)


@_skip_no_csrc
def test_b3_after_f_uses_90() -> None:
    """C body sets B3 to ``90`` for high-front vowels after /f/."""
    body = _extract_body()
    assert re.search(r"phlas_temp\s*==\s*LAP_F", body)
    assert re.search(r"tartemp\s*=\s*90\s*;", body)


@_skip_no_csrc
def test_r_rr_back_vowel_reduces_f1() -> None:
    """C body reduces F1 by ``100`` for /r/ /rr/ following /o/ /u/."""
    body = _extract_body()
    assert re.search(r"phone_temp\s*==\s*LAP_R\b", body)
    assert re.search(r"phone_temp\s*==\s*LAP_RR\b", body)
    assert re.search(r"phlas_temp\s*==\s*LAP_O\b", body)
    assert re.search(r"phlas_temp\s*==\s*LAP_U\b", body)
    assert re.search(r"tartemp\s*-=\s*100\s*;", body)


@_skip_no_csrc
def test_av_branch_applies_unstressed_minus_3_and_plus_10_hack() -> None:
    """C body reduces AV by 3 for unstressed segments, then +10 ("EAB HACK")."""
    body = _extract_body()
    assert re.search(r"npar\s*==\s*AV\s*-\s*1", body)
    # FSTRESS bit-mask check for unstressed segments.
    assert re.search(r"FSTRESS\)\s*IS_MINUS", body)
    assert re.search(r"tartemp\s*-=\s*3\s*;", body)
    # The "+10 hack" line is preserved with its slightly chaotic comment.
    assert re.search(r"tartemp\s*\+=\s*10", body)


@_skip_no_csrc
def test_ap_branch_uses_fixed_phoneme_amplitudes() -> None:
    """C body's AP branch sets fixed amplitudes for /r/-/rr/, /ll/, /j/."""
    body = _extract_body()
    assert re.search(r"phone_temp\s*==\s*LAP_R\s*\|\|\s*phone_temp\s*==\s*LAP_RR", body)
    assert re.search(r"tartemp\s*=\s*33", body)
    assert re.search(r"phone_temp\s*==\s*LAP_LL", body)
    assert re.search(r"tartemp\s*=\s*10", body)
    assert re.search(r"phone_temp\s*==\s*LAP_J", body)
    assert re.search(r"tartemp\s*=\s*25", body)


@_skip_no_csrc
def test_tilt_branch_writes_voicebar_24_and_voiced_plosive_12() -> None:
    """C body's TILT cascade hits magic values 12, 24, 6, 7."""
    body = _extract_body()
    # PTILT is the spectral-tilt parameter.
    assert "PTILT" in body
    # Voiced plosive (FVOICD | FPLOSV) gets 12.
    assert re.search(r"FVOICD\s*\|\s*FPLOSV", body)
    assert re.search(r"tartemp\s*=\s*12", body)
    # /dh/-/gh/ pseudo-voicing band gets 24.
    assert re.search(r"phone_temp\s*>=\s*LAP_DH", body)
    assert re.search(r"phone_temp\s*<=\s*LAP_GH", body)
    assert re.search(r"tartemp\s*=\s*24", body)


@_skip_no_csrc
def test_nasal_zero_branch_uses_nasal_zero_boundary() -> None:
    """C body's FZ branch returns NASAL_ZERO_BOUNDARY (not _CONS) for nasals."""
    body = _extract_body()
    # The C source explicitly uses NASAL_ZERO_BOUNDARY here -- a deliberate
    # difference from US English which uses NASAL_ZERO_CONS.
    assert "NASAL_ZERO_BOUNDARY" in body
    assert "NON_NASAL_ZERO" in body


@_skip_no_csrc
def test_uses_la_place_for_back_front_vowel_check() -> None:
    """C body consults ``la_place[]`` with the ``F2BACKI`` bit."""
    body = _extract_body()
    assert "la_place" in body
    assert "F2BACKI" in body


# -- Python behavioural tests ---------------------------------------------


def _make_handle(
    *,
    phones: list[int],
    np_param: int,
    malfem: int = 1,
    sprate: int = 200,
) -> tuple[TtsHandle, DphT]:
    """Build a minimal TtsHandle + DphT populated for la_gettar."""
    p_dph_t = DphT()
    p_dph_t.allophons = phones
    p_dph_t.allofeats = [0] * len(phones)
    p_dph_t.nallotot = len(phones)
    p_dph_t.malfem = malfem
    # Wire LA tables exactly as gettar._load_la_tables would.
    if malfem == 1:
        p_dph_t.p_tar = list(la_maltar)
    else:
        p_dph_t.p_tar = list(la_femtar)
    p_dph_t.p_amp = [0] * 1000
    p_dph_t.p_diph = [0, 0]

    settar = DphSettarSt()
    settar.np = np_param
    settar.par_type = partyp[np_param - F1]
    p_dph_t.pSTphsettar = settar

    p_ksd_t = KsdT()
    p_ksd_t.sprate = sprate

    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    handle.p_kernel_share_data = p_ksd_t
    return handle, p_dph_t


def test_fz_branch_returns_non_nasal_zero_for_vowel() -> None:
    """la_gettar(FZ) returns NON_NASAL_ZERO when the phone has no FNASAL bit."""
    handle, _state = _make_handle(phones=[0, LAP_A, 0], np_param=FZ)
    result = la_gettar(handle, 1)
    assert result == NON_NASAL_ZERO


def test_fz_branch_returns_nasal_zero_boundary_for_nasal() -> None:
    """la_gettar(FZ) returns NASAL_ZERO_BOUNDARY (370) on a nasal phone.

    Note: ``phone_feature`` currently routes all fonts to ``us_featb``,
    so we use the US-font /m/ code (``US_M = 31``) to get the FNASAL
    bit. When :mod:`dectalk.ph.timing` grows LA-aware ``phone_feature``,
    swap to LAP_M here.
    """
    handle, _state = _make_handle(phones=[0, USP_M, 0], np_param=FZ)
    result = la_gettar(handle, 1)
    assert result == NASAL_ZERO_BOUNDARY


def test_form_freq_branch_reads_p_tar() -> None:
    """la_gettar(F1) on a vowel reads ``p_tar[(phone & 0xFF) + pphotr]``."""
    handle, state = _make_handle(phones=[0, LAP_A, 0], np_param=F1)
    # LAP_A & PVALUE == 1, pphotr = 0 * 39 = 0, so we read la_maltar[1].
    expected = la_maltar[1]
    result = la_gettar(handle, 1)
    # The B3 / F1-back-vowel tweaks don't fire for F1 on a plain vowel.
    assert result == expected
    # Side-effect: p_dphsettar.par_type was cached.
    settar = cast(DphSettarSt, state.pSTphsettar)
    assert settar.par_type == partyp[F1 - F1]


def test_form_freq_branch_b3_clamps_to_300_for_n_adjacent_to_i() -> None:
    """la_gettar(B3) on /n/ adjacent to /i/ clamps to 300 (post-EDB-96)."""
    # phones[1] = LAP_N, phones[2] = LAP_I (front vowel).
    handle, _ = _make_handle(phones=[0, LAP_N, LAP_I, 0], np_param=B3)
    result = la_gettar(handle, 1)
    assert result == 300


def test_form_freq_branch_f1_reduces_for_r_after_o() -> None:
    """la_gettar(F1) for /r/ following /o/ reduces the base target by 100."""
    handle, _ = _make_handle(phones=[LAP_O, LAP_R, 0], np_param=F1)
    # phone = LAP_R has low-8 == 30, pphotr = 0, so base is la_maltar[30].
    base = la_maltar[LAP_R & 0xFF]
    result = la_gettar(handle, 1)
    assert result == base - 100


def test_form_freq_branch_b3_uses_90_for_i_after_f() -> None:
    """la_gettar(B3) for /i/ following /f/ rewrites to 90 (F2BACKI rule)."""
    handle, _ = _make_handle(phones=[LAP_F, LAP_I, 0], np_param=B3)
    result = la_gettar(handle, 1)
    assert result == 90


def test_ap_branch_returns_33_for_r() -> None:
    """la_gettar(AP) on /r/ returns the LA-specific aspiration amplitude 33."""
    # AP is the 8th parameter (npar==8 with F1==1).
    handle, _ = _make_handle(phones=[0, LAP_R, 0], np_param=AP)
    result = la_gettar(handle, 1)
    assert result == 33


def test_ap_branch_returns_25_for_j() -> None:
    """la_gettar(AP) on /j/ (LAP_J) returns 25 (Castilian flavour)."""
    handle, _ = _make_handle(phones=[0, LAP_J, 0], np_param=AP)
    result = la_gettar(handle, 1)
    assert result == 25


def test_av_branch_reads_p_tar_and_adds_plus_10_hack() -> None:
    """la_gettar(AV) on a vowel reads ``p_tar`` and adds the EAB +10 hack.

    For ``np = AV = 8`` and ``F1 = 1``, ``npar = 7``. Because ``np >= FZ``
    the C source shifts the index down by 1 (no PAP row), so
    ``pphotr = (npar - 1) * 39 = 234``; the lookup is
    ``la_maltar[(phone & 0xFF) + 234]``.
    """
    handle, state = _make_handle(phones=[0, LAP_A, 0], np_param=AV)
    # Mark the segment as stressed so the -3 unstressed rule skips.
    state.allofeats[1] = FSTRESS_1
    # AV is npar = 7, pphotr = (7 - 1) * 39 = 234.
    expected_base = la_maltar[(LAP_A & 0xFF) + 234]
    result = la_gettar(handle, 1)
    # Nonzero AV gets the +10 hack.
    if expected_base:
        assert result == expected_base + 10
    else:
        assert result == 0
