"""Behavioural and C-source parity tests for the Python port of ``uk_gettar``.

The C source lives in ``src/dapi/src/ph/p_uk_st1.c``; the Python port
mirrors its branchy par_type-dispatched body. Each test exercises one
branch of the dispatch and asserts the return value against
hand-derived expectations.

These tests are the UK-English mirror of ``test_ph_us_gettar.py``;
the UK source is structurally identical to the US one but uses
different constants (UK_TOT_ALLOPHONES, AV dummy-vowel delta, /hx/ AP
levels, TILT branch).

The C-source re-parsing helpers near the bottom skip cleanly when
``DECTALK_SRC`` is unset.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import cast

import pytest

from dectalk.include.usp_codes import (
    USP_AA,
    USP_EH,
    USP_HX,
    USP_IY,
    USP_M,
    USP_N,
    USP_OW,
    USP_Q,
    USP_S,
)
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FDUMMY_VOWEL, FSTRESS_1
from dectalk.ph.numeric_constants import AV, B2, F1, FEMALE, FZ, MALE, TILT
from dectalk.ph.parameter_tables import partyp
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.uk_gettar import uk_gettar
from dectalk.ph.uk_rom_tables import uk_femamp, uk_femtar
from dectalk.ph.utterance_constants import (
    GEN_SIL,
    NASAL_ZERO_CONS,
    NON_NASAL_ZERO,
)


def _make_handle(
    *,
    np_idx: int,
    phone: int,
    nphone: int = 1,
    phlas: int | None = None,
    phnex: int | None = None,
    nallotot: int = 4,
    durfon: int = 12,
    sprate: int = 200,
    malfem: int = FEMALE,
) -> TtsHandle:
    """Build a TtsHandle populated for uk_gettar (female UK tables)."""
    p_dph_t = DphT()
    p_dph_t.allophons = [GEN_SIL] * nallotot
    p_dph_t.allofeats = [0] * nallotot
    p_dph_t.nallotot = nallotot
    p_dph_t.nphone = nphone
    p_dph_t.durfon = durfon
    p_dph_t.malfem = malfem

    # Seed the three surrounding phone codes that get_phone reads.
    if phlas is not None:
        p_dph_t.allophons[nphone - 1] = phlas
    p_dph_t.allophons[nphone] = phone
    if phnex is not None:
        p_dph_t.allophons[nphone + 1] = phnex

    # Load the female UK tables (uk_gettar reads p_tar and p_amp via
    # the per-thread DphT pointer; the C source initialises these in
    # gettar's table-loading prologue).
    p_dph_t.p_tar = list(uk_femtar)
    p_dph_t.p_amp = list(uk_femamp)
    p_dph_t.p_diph = []  # not exercised by these branches

    settar = DphSettarSt()
    settar.np = np_idx
    settar.phcur = phone
    p_dph_t.pSTphsettar = settar

    p_ksd_t = KsdT()
    p_ksd_t.sprate = sprate

    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    handle.p_kernel_share_data = p_ksd_t
    return handle


# --- par_type dispatch sanity --------------------------------------------


def test_par_type_is_cached_into_settar() -> None:
    """uk_gettar writes ``partyp[npar]`` into ``pDphsettar.par_type``."""
    handle = _make_handle(np_idx=F1, phone=USP_AA)
    settar = cast(DphSettarSt, cast(DphT, handle.p_ph_thread_data).pSTphsettar)
    uk_gettar(handle, 1)
    assert settar.par_type == partyp[F1 - 1]


# --- Nasal-zero-frequency branch (par_type == 1, np == FZ) ---------------


def test_nasal_zero_returns_consonant_value_for_nasal() -> None:
    """During a nasal segment, FZ targets ``NASAL_ZERO_CONS``."""
    handle = _make_handle(np_idx=FZ, phone=USP_N)
    assert uk_gettar(handle, 1) == NASAL_ZERO_CONS


def test_nasal_zero_returns_non_nasal_default_for_non_nasal() -> None:
    """For a non-nasal segment, FZ falls back to ``NON_NASAL_ZERO``."""
    handle = _make_handle(np_idx=FZ, phone=USP_AA)
    assert uk_gettar(handle, 1) == NON_NASAL_ZERO


# --- Formant-frequency branch (par_type > 2) -----------------------------


def test_form_freq_reads_p_tar() -> None:
    """For F1..F3/B1..B3, target = ``p_tar[(phone & PVALUE) + pphotr]``."""
    # Pick a phone whose UK F1 entry is non-sentinel and non-zero so
    # the read is unambiguous. uk_femtar[USP_AA & 0xFF] for AA == 6
    # is 480 (verified by quick eyeball of p_uk_rom.c output).
    handle = _make_handle(np_idx=F1, phone=USP_AA)
    expected = uk_femtar[USP_AA & 0xFF]
    assert uk_gettar(handle, 1) == expected


def test_form_freq_diphthong_sentinel_returned_verbatim() -> None:
    """Targets < -1 (diphthong sentinels) flow through unchanged."""
    handle = _make_handle(np_idx=F1, phone=USP_AA)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    # Poison the masked table slot to a sentinel value.
    cast(list[int], p_dph_t.p_tar)[USP_AA & 0xFF] = -5
    assert uk_gettar(handle, 1) == -5


def test_b3_clamped_to_1600_for_n_adjacent_to_high_front() -> None:
    """B3 of /n/ clamps to 1600 when adjacent to a high-front vowel."""
    # uk_place[IY=1] has F2BACKF (128) set, so an IY in the *previous*
    # slot triggers the clamp via the second arm of the OR (same as US).
    handle = _make_handle(np_idx=F1 + 6, phone=USP_N, phlas=USP_IY)
    assert uk_gettar(handle, 1) == 1600


# --- AV/AP branch (par_type == 0) ----------------------------------------


def test_glottal_stop_loses_30_at_slow_rate() -> None:
    """USP_Q drops AV by 30 when ``sprate < 100``."""
    base = _make_handle(np_idx=AV, phone=USP_Q, sprate=200)
    slow = _make_handle(np_idx=AV, phone=USP_Q, sprate=50)
    assert uk_gettar(base, 1) - uk_gettar(slow, 1) == 30


def test_dummy_vowel_reduces_av_by_7() -> None:
    """Dummy-vowel flag in allofeats subtracts 7 from AV (UK; US is 12)."""
    base = _make_handle(np_idx=AV, phone=USP_AA)
    poisoned = _make_handle(np_idx=AV, phone=USP_AA)
    cast(DphT, poisoned.p_ph_thread_data).allofeats[1] = FDUMMY_VOWEL
    # Both go through the unstressed branch (allofeats stress==0), so
    # the dummy-vowel delta isolates to a -7 difference.
    assert uk_gettar(base, 1) - uk_gettar(poisoned, 1) == 7


def test_hx_aspiration_50_before_front_vowel() -> None:
    """AP for /hx/ is 50 before a front vowel (begtyp==1) in UK."""
    handle = _make_handle(np_idx=AV + 1, phone=USP_HX, phnex=USP_IY)
    # Unstressed reduction (-4) applies to AP in UK (unlike US).
    assert uk_gettar(handle, 1) == 50 - 4


def test_hx_aspiration_52_before_back_vowel() -> None:
    """AP for /hx/ jumps to 52 before a back vowel (begtyp!=1) in UK."""
    handle = _make_handle(np_idx=AV + 1, phone=USP_HX, phnex=USP_AA)
    assert uk_gettar(handle, 1) == 52 - 4


def test_ap_zero_for_non_hx() -> None:
    """AP is 0 for anything that isn't /hx/."""
    handle = _make_handle(np_idx=AV + 1, phone=USP_EH)
    assert uk_gettar(handle, 1) == 0


def test_hx_voiced_target_54_when_unstressed_after_voiced() -> None:
    """/hx/ AV = 54 if preceded by voiced segment and unstressed."""
    handle = _make_handle(np_idx=AV, phone=USP_HX, phlas=USP_AA)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    p_dph_t.allofeats[1] = 0  # FSTRESS_1 == 0o1
    # 54 from rule, -4 from unstressed reduction.
    assert uk_gettar(handle, 1) == 54 - 4


def test_hx_voiced_rule_skipped_when_stress_1_set() -> None:
    """/hx/ AV = 54 rule skips when FSTRESS_1 flag is set."""
    handle = _make_handle(np_idx=AV, phone=USP_HX, phlas=USP_AA)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    p_dph_t.allofeats[1] = FSTRESS_1
    # Result depends on uk_femtar[HX] + unstressed nudge; just assert
    # it's NOT the post-rule value (54 or 54-4 == 50).
    result = uk_gettar(handle, 1)
    assert result not in (54, 50)


# --- Parallel-formant-amplitude branch (par_type == 2) --------------------


def test_tilt_zero_for_silence() -> None:
    """TILT target is 0 for GEN_SIL phones."""
    handle = _make_handle(np_idx=TILT, phone=GEN_SIL)
    assert uk_gettar(handle, 1) == 0


def test_tilt_20_for_hx() -> None:
    """TILT target is 20 for /hx/."""
    handle = _make_handle(np_idx=TILT, phone=USP_HX)
    assert uk_gettar(handle, 1) == 20


def test_tilt_20_for_dummy_vowel() -> None:
    """UK TILT target is 20 for dummy vowel (US version is 10)."""
    handle = _make_handle(np_idx=TILT, phone=USP_AA)
    cast(DphT, handle.p_ph_thread_data).allofeats[1] = FDUMMY_VOWEL
    assert uk_gettar(handle, 1) == 20


def test_tilt_female_front_vowel_plus_6() -> None:
    """Female front-vowel TILT = 6 in UK (begtyp/endtyp == 1 case)."""
    # AA: us_begtyp == 2, us_endtyp == 2; need a phone whose begtyp == 1.
    # IY has us_begtyp == 1 and us_endtyp == 1 (front vowel).
    handle = _make_handle(np_idx=TILT, phone=USP_IY, malfem=FEMALE)
    assert uk_gettar(handle, 1) == 6


def test_tilt_male_front_vowel_plus_3() -> None:
    """Male front-vowel TILT = 3 in UK (vs US always +3)."""
    handle = _make_handle(np_idx=TILT, phone=USP_IY, malfem=MALE)
    assert uk_gettar(handle, 1) == 3


def test_tilt_6_for_nasal() -> None:
    """TILT target is 6 for a nasal segment (UK uses assignment, =6)."""
    handle = _make_handle(np_idx=TILT, phone=USP_M)
    assert uk_gettar(handle, 1) == 6


def test_tilt_7_for_voiceless_obstruent() -> None:
    """TILT target is 7 for a voiceless obstruent (e.g. /s/)."""
    handle = _make_handle(np_idx=TILT, phone=USP_S)
    assert uk_gettar(handle, 1) == 7


def test_tilt_ow_gets_extra_10() -> None:
    """UK /ow/ gets TILT += 10 (no equivalent in US)."""
    # OW (allophone code 11) has us_begtyp==3, us_endtyp==3 (back
    # vowel: not front, not obstruent, not nasal). It falls to the
    # UKP_OW branch.
    handle = _make_handle(np_idx=TILT, phone=USP_OW)
    assert uk_gettar(handle, 1) == 10


# --- AV/AP unstressed -4 applies to AP (UK-specific) ---------------------


def test_ap_unstressed_minus_4() -> None:
    """UK: unstressed -4 also reduces AP (US applies it only to AV)."""
    # /hx/ before /aa/: AP target before unstressed bias is 52.
    handle = _make_handle(np_idx=AV + 1, phone=USP_HX, phnex=USP_AA)
    # No FSTRESS flag set in allofeats → unstressed branch fires.
    assert uk_gettar(handle, 1) == 52 - 4


# --- Sanity guard ---------------------------------------------------------


def test_uk_gettar_does_not_mutate_dph_state_outside_par_type() -> None:
    """uk_gettar's only side-effect is writing settar.par_type."""
    handle = _make_handle(np_idx=B2, phone=USP_AA)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    initial_nphone = p_dph_t.nphone
    initial_durfon = p_dph_t.durfon
    initial_allofeats = list(p_dph_t.allofeats)
    uk_gettar(handle, 1)
    assert p_dph_t.nphone == initial_nphone
    assert p_dph_t.durfon == initial_durfon
    assert p_dph_t.allofeats == initial_allofeats


def test_imports_resolve() -> None:
    assert pytest is not None


# --- C-source parity (skips when DECTALK_SRC is unset) -------------------

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/p_uk_st1.c"


def _read_c_body() -> str:
    """Read p_uk_st1.c and extract the body of ``short uk_gettar(...) {...}``."""
    text = _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")
    m = re.search(r"short\s+uk_gettar\s*\([^)]*\)\s*\{", text)
    if m is None:
        raise AssertionError("uk_gettar definition not found in p_uk_st1.c")
    start = m.end()
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    return text[start : i - 1]


_skip_no_oracle = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


@_skip_no_oracle
def test_c_uses_uk_tot_allophones_for_stride() -> None:
    """The C body references ``UK_TOT_ALLOPHONES`` for the stride."""
    body = _read_c_body()
    assert "UK_TOT_ALLOPHONES" in body, "uk_gettar C body lost UK_TOT_ALLOPHONES"


@_skip_no_oracle
def test_c_reads_uk_place_for_b3_clamp() -> None:
    """The B3-of-/n/ clamp branch reads ``uk_place`` (not us_place)."""
    body = _read_c_body()
    # The C body checks F2BACKI/F2BACKF against uk_place.
    assert "uk_place" in body, "uk_gettar lost uk_place reference"
    assert "F2BACKI" in body and "F2BACKF" in body


@_skip_no_oracle
def test_c_dummy_vowel_av_delta_is_seven() -> None:
    """C body subtracts ``7`` from AV for dummy vowel (US uses 12)."""
    body = _read_c_body()
    # Find the AV dummy-vowel branch and assert the magic number is 7.
    av_section = re.search(
        r"if\s*\(\s*\(\s*pDph_t->allofeats\[nphone_temp\]\s*&\s*FDUMMY_VOWEL\)"
        r".*?tartemp\s*-=\s*(\d+)",
        body,
        re.S,
    )
    assert av_section is not None, "AV dummy-vowel reduction branch not found"
    assert av_section.group(1) == "7", (
        f"UK uk_gettar AV dummy-vowel delta drifted from 7 to {av_section.group(1)}"
    )


@_skip_no_oracle
def test_c_hx_aspiration_targets() -> None:
    """C body sets HX AP target 50 / 52 (front / back vowel)."""
    body = _read_c_body()
    # Look for "tartemp = 50;" and "tartemp = 52;" in the HX AP branch.
    assert re.search(r"tartemp\s*=\s*50\s*;", body), "UK HX AP=50 target missing"
    assert re.search(r"tartemp\s*=\s*52\s*;", body), "UK HX AP=52 target missing"


@_skip_no_oracle
def test_c_tilt_ow_special_branch() -> None:
    """C body adds +10 to TILT for UKP_OW (UK-specific TILT branch)."""
    body = _read_c_body()
    assert re.search(r"phone_temp\s*==\s*UKP_OW", body), "UK OW special TILT branch missing"
    # The body of the OW branch should add 10.
    assert re.search(r"UKP_OW[^}]*tartemp\s*\+=\s*10", body, re.S), "UK TILT += 10 for OW drifted"


@_skip_no_oracle
def test_c_female_front_vowel_plus_6() -> None:
    """C body biases TILT by +6 for females on front vowels."""
    body = _read_c_body()
    # The branch is gated by `pDph_t->malfem == FEMALE`.
    assert re.search(
        r"malfem\s*==\s*FEMALE[^}]*tartemp\s*\+=\s*6",
        body,
        re.S,
    ), "UK female front-vowel TILT += 6 branch drifted"
