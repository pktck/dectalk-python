"""C-source parity test for ``fr_gettar`` against p_fr_st1.c.

Re-parses the C body via brace-depth tracking and asserts the
French per-parameter target-lookup helper still exists in the
develop branch with the expected dispatch structure. Also exercises
the Python port end-to-end on each ``par_type`` branch via a
hand-rolled :class:`~dectalk.ph.dph_t.DphT` -- the shipped binary
does not link the French target tables, so this test stands on its
own (no oracle round-trip).

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import cast

import pytest

from dectalk.include.phoneme_codes import PFFR
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.fr_gettar import fr_gettar
from dectalk.ph.fr_target_tables import (
    Cibles_FEMALE,
    Cibles_MALE,
    N_PARAM_FR,
    cibles_flat,
)
from dectalk.ph.numeric_constants import A2, AV, B2, F1, F2, F3, FZ, TILT
from dectalk.ph.parameter_tables import partyp
from dectalk.ph.rom_tables import us_femamp, us_femdip
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL

# French phoneme code F_R == 19 (cf. include/l_fr_ph.h); apply the
# language font bits to construct an in-allophons-style entry.
_PSFONT_BITS: int = 8
_FFR: int = PFFR << _PSFONT_BITS
_FP_A: int = _FFR | 1
_FP_R: int = _FFR | 19
_FP_S: int = _FFR | 27  # voiceless fricative; row 27 has TLT==7.
_FP_AN: int = _FFR | 13  # nasalised vowel; AH/AP column 6 == 50.

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/p_fr_st1.c"


def _read_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the body of ``short fr_gettar(...)`` via brace tracking."""
    text = _read_c()
    pattern = re.compile(r"\bfr_gettar\s*\(")
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
    raise AssertionError(f"fr_gettar definition not found in {_C_FILE.name}")


# -- C-source structural assertions ----------------------------------------

_SKIP_NO_SRC = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


@_SKIP_NO_SRC
def test_signature_exists_in_c() -> None:
    """``short fr_gettar(LPTTS_HANDLE_T phTTS, int nphone_temp)`` exists."""
    text = _read_c()
    assert re.search(
        r"\bshort\s+fr_gettar\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*,\s*int\s+\w+\s*\)",
        text,
    )


@_SKIP_NO_SRC
def test_body_dispatches_on_par_type() -> None:
    """The four ``par_type`` branches all appear in the C body."""
    body = _extract_body()
    assert "IS_FORM_FREQ_OR_BW" in body
    assert "IS_NASAL_ZERO_FREQ" in body
    assert "IS_AV_OR_AH" in body
    assert "IS_PARALLEL_FORM_AMP" in body


@_SKIP_NO_SRC
def test_body_loads_male_or_female_cibles_on_language_switch() -> None:
    """C body swaps ``Cibles_Defaut`` between ``Cibles_MALE``/``Cibles_FEMALE``."""
    body = _extract_body()
    assert "Cibles_Defaut" in body
    assert "Cibles_MALE" in body
    assert "Cibles_FEMALE" in body
    assert "PFFR" in body  # language tag


@_SKIP_NO_SRC
def test_body_walks_three_phones_for_form_freq_fallback() -> None:
    """Form-freq fallback chain references ``phlas/phnex/nphone+2``."""
    body = _extract_body()
    # Forward look-ahead via get_phone(..., nphone_temp+2).
    assert re.search(r"nphone_temp\s*\+\s*2", body)
    # Diphthong walk pattern.
    assert "p_diph" in body
    # parini default fallback.
    assert "parini" in body


@_SKIP_NO_SRC
def test_body_reads_partyp_array() -> None:
    """C body caches ``partyp[npar]`` into ``pDphsettar->par_type``."""
    body = _extract_body()
    assert re.search(r"par_type\s*=\s*partyp\s*\[", body)


@_SKIP_NO_SRC
def test_body_indexes_cibles_with_pphotr_offsets() -> None:
    """The C body uses ``pphotr = npar + 9`` for form/bw and ``npar - 9`` for A2-AB."""
    body = _extract_body()
    assert re.search(r"pphotr\s*=\s*npar\s*\+\s*9", body)
    assert re.search(r"pphotr\s*=\s*npar\s*-\s*9", body)


@_SKIP_NO_SRC
def test_table_dimensions_match_c() -> None:
    """C declares ``Cibles_MALE/FEMALE [42][N_PARAM]`` (N_PARAM=17)."""
    text = _C_FILE.parent.joinpath("p_fr_rom.c").read_bytes().decode("latin-1")
    assert "Cibles_MALE [42] [N_PARAM]" in text
    assert "Cibles_FEMALE [42] [N_PARAM]" in text
    assert len(Cibles_MALE) == 42
    assert len(Cibles_FEMALE) == 42
    assert all(len(row) == N_PARAM_FR for row in Cibles_MALE)
    assert all(len(row) == N_PARAM_FR for row in Cibles_FEMALE)


# -- Python behavioural tests ---------------------------------------------


def _make_handle(
    *,
    np_idx: int,
    phone: int,
    nphone: int = 1,
    phlas: int | None = None,
    phnex: int | None = None,
    nallotot: int = 4,
    use_female: bool = True,
) -> TtsHandle:
    """Build a TtsHandle populated for fr_gettar.

    Loads the French female ``Cibles_Defaut`` by default. Wires the
    surrounding three allophone slots so :func:`get_phone` resolves.
    """
    p_dph_t = DphT()
    p_dph_t.allophons = [GEN_SIL] * nallotot
    p_dph_t.allofeats = [0] * nallotot
    p_dph_t.nallotot = nallotot
    p_dph_t.nphone = nphone

    # Seed surrounding phone codes.
    if phlas is not None:
        p_dph_t.allophons[nphone - 1] = phlas
    p_dph_t.allophons[nphone] = phone
    if phnex is not None:
        p_dph_t.allophons[nphone + 1] = phnex

    # fr_gettar shares p_amp / p_diph with US (the C source assigns
    # us_maldip / us_maltar in the French language-switch block).
    p_dph_t.p_diph = list(us_femdip)
    p_dph_t.p_amp = list(us_femamp)
    p_dph_t.Cibles_Defaut = cibles_flat(
        Cibles_FEMALE if use_female else Cibles_MALE,
    )

    settar = DphSettarSt()
    settar.np = np_idx
    settar.phcur = phone
    p_dph_t.pSTphsettar = settar

    p_ksd_t = KsdT()
    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    handle.p_kernel_share_data = p_ksd_t
    return handle


def test_par_type_is_cached_into_settar() -> None:
    """fr_gettar writes ``partyp[npar]`` into ``pDphsettar.par_type``."""
    handle = _make_handle(np_idx=F1, phone=_FP_A)
    settar = cast(DphSettarSt, cast(DphT, handle.p_ph_thread_data).pSTphsettar)
    fr_gettar(handle, 1)
    assert settar.par_type == partyp[F1 - 1]


def test_form_freq_reads_cibles_default() -> None:
    """For F1, target = ``Cibles_Defaut[(phone & PVALUE) * N_PARAM + 9]``."""
    handle = _make_handle(np_idx=F1, phone=_FP_A)
    # F_A row 1, col 9 (F1) = female 895.
    assert fr_gettar(handle, 1) == Cibles_FEMALE[1][9]


def test_form_freq_f2_reads_col10() -> None:
    """F2 reads column 10 of ``Cibles_Defaut``."""
    handle = _make_handle(np_idx=F2, phone=_FP_A)
    assert fr_gettar(handle, 1) == Cibles_FEMALE[1][10]


def test_form_freq_f3_reads_col11() -> None:
    """F3 reads column 11 of ``Cibles_Defaut``."""
    handle = _make_handle(np_idx=F3, phone=_FP_A)
    assert fr_gettar(handle, 1) == Cibles_FEMALE[1][11]


def test_form_freq_b1_reads_col13() -> None:
    """B1 (np=F1+4) reads column 13 of ``Cibles_Defaut``."""
    # B1 numeric value is 5 (F1=1, F2=2, F3=3, FZ=4, B1=5).
    handle = _make_handle(np_idx=F1 + 4, phone=_FP_A)
    assert fr_gettar(handle, 1) == Cibles_FEMALE[1][13]


def test_nasal_zero_reads_col12() -> None:
    """FZ (nasal-zero frequency) reads column 12 of ``Cibles_Defaut``."""
    handle = _make_handle(np_idx=FZ, phone=_FP_AN)
    assert fr_gettar(handle, 1) == Cibles_FEMALE[13][12]


def test_av_reads_col7() -> None:
    """AV reads column 7 of ``Cibles_Defaut``."""
    handle = _make_handle(np_idx=AV, phone=_FP_A)
    assert fr_gettar(handle, 1) == Cibles_FEMALE[1][7]


def test_ah_reads_col6_for_nasalised_vowel() -> None:
    """AH/AP reads column 6 of ``Cibles_Defaut``; AN row has 50/0 depending on voice."""
    # AH/AP is the parameter immediately after AV (np = AV + 1).
    handle = _make_handle(np_idx=AV + 1, phone=_FP_AN, use_female=False)
    assert fr_gettar(handle, 1) == Cibles_MALE[13][6]


def test_tilt_reads_col8() -> None:
    """TILT reads column 8 of ``Cibles_Defaut``."""
    handle = _make_handle(np_idx=TILT, phone=_FP_S)
    # F_S row index 27, col 8 (TLT) = female 10.
    assert fr_gettar(handle, 1) == Cibles_FEMALE[27][8]


def test_parallel_form_amp_a2_for_r_reads_col0() -> None:
    """A2 for F_R (where ptram == 0) reads column 0 of ``Cibles_Defaut``."""
    # F_R is the only row in Cibles where A2..A5 are non-zero.
    handle = _make_handle(np_idx=A2, phone=_FP_R)
    # ptram(_FP_R) is 0 for French allophones, so we hit the "else"
    # branch that reads Cibles_Defaut[row * N_PARAM + (npar - 9)].
    assert fr_gettar(handle, 1) == Cibles_FEMALE[19][0]


def test_form_freq_b3_clamp_path_does_not_apply_to_french() -> None:
    """fr_gettar has no B2/B3 nasal-clamp tweaks (unlike us_gettar)."""
    # Female /N/ row 38, B2 column 14 == 300. fr_gettar should return
    # exactly that value regardless of phlas/phnex (no B3 clamp logic).
    handle = _make_handle(
        np_idx=B2,
        phone=_FFR | 38,  # F_N
        phlas=_FFR | 8,  # F_I (high-front vowel)
        phnex=_FFR | 8,
    )
    assert fr_gettar(handle, 1) == Cibles_FEMALE[38][14]


def test_fr_gettar_does_not_mutate_dph_state_outside_par_type() -> None:
    """fr_gettar's only side-effect is writing ``settar.par_type``."""
    handle = _make_handle(np_idx=F1, phone=_FP_A)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    initial_nphone = p_dph_t.nphone
    initial_allofeats = list(p_dph_t.allofeats)
    fr_gettar(handle, 1)
    assert p_dph_t.nphone == initial_nphone
    assert p_dph_t.allofeats == initial_allofeats


def test_cibles_male_and_female_diverge_on_at_least_one_row() -> None:
    """The two voice tables should genuinely differ (smoke test on extraction)."""
    diffs = sum(
        1
        for row_male, row_female in zip(Cibles_MALE, Cibles_FEMALE, strict=True)
        if row_male != row_female
    )
    assert diffs >= 30  # nearly all 42 rows differ; allow slack for the SIL rows.
