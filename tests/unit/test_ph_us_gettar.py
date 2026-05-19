"""Behavioural tests for the Python port of ``us_gettar``.

The C source lives in ``src/dapi/src/ph/p_us_st1.c``; the Python
port mirrors its branchy par_type-dispatched body. Each test
exercises one branch of the dispatch and asserts the return value
against hand-derived expectations (no oracle dependency).
"""

from __future__ import annotations

from typing import cast

import pytest

from dectalk.include.usp_codes import (
    USP_AA,
    USP_EH,
    USP_HX,
    USP_IY,
    USP_M,
    USP_N,
    USP_Q,
    USP_S,
)
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FDUMMY_VOWEL, FSTRESS_1
from dectalk.ph.numeric_constants import AV, B2, F1, FZ, TILT
from dectalk.ph.parameter_tables import partyp
from dectalk.ph.rom_tables import us_femamp, us_femtar
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.us_gettar import us_gettar
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
) -> TtsHandle:
    """Build a TtsHandle populated for us_gettar.

    Loads female US tables (matching the default p_tar / p_amp
    selection in init_variables before any malfem == MALE switch).
    """
    p_dph_t = DphT()
    p_dph_t.allophons = [GEN_SIL] * nallotot
    p_dph_t.allofeats = [0] * nallotot
    p_dph_t.nallotot = nallotot
    p_dph_t.nphone = nphone
    p_dph_t.durfon = durfon

    # Seed the three surrounding phone codes that get_phone reads.
    if phlas is not None:
        p_dph_t.allophons[nphone - 1] = phlas
    p_dph_t.allophons[nphone] = phone
    if phnex is not None:
        p_dph_t.allophons[nphone + 1] = phnex

    # Load the female US tables (us_gettar reads p_tar and p_amp via
    # the per-thread DphT pointer; the C source initialises these in
    # gettar's table-loading prologue).
    p_dph_t.p_tar = list(us_femtar)
    p_dph_t.p_amp = list(us_femamp)
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
    """us_gettar writes ``partyp[npar]`` into ``pDphsettar.par_type``."""
    handle = _make_handle(np_idx=F1, phone=USP_AA)
    settar = cast(DphSettarSt, cast(DphT, handle.p_ph_thread_data).pSTphsettar)  # type: ignore[union-attr]
    us_gettar(handle, 1)
    assert settar.par_type == partyp[F1 - 1]


# --- Nasal-zero-frequency branch (par_type == 1, np == FZ) ---------------


def test_nasal_zero_returns_consonant_value_for_nasal() -> None:
    """During a nasal segment, FZ targets ``NASAL_ZERO_CONS``."""
    handle = _make_handle(np_idx=FZ, phone=USP_N)
    assert us_gettar(handle, 1) == NASAL_ZERO_CONS


def test_nasal_zero_returns_non_nasal_default_for_non_nasal() -> None:
    """For a non-nasal segment, FZ falls back to ``NON_NASAL_ZERO``."""
    handle = _make_handle(np_idx=FZ, phone=USP_AA)
    assert us_gettar(handle, 1) == NON_NASAL_ZERO


# --- Formant-frequency branch (par_type > 2) -----------------------------


def test_form_freq_reads_p_tar() -> None:
    """For F1..F3/B1..B3, target = ``p_tar[(phone & PVALUE) + pphotr]``."""
    handle = _make_handle(np_idx=F1, phone=USP_AA)
    # npar = F1 - F1 = 0; pphotr = 0; expected = us_femtar[AA & PVALUE]
    expected = us_femtar[USP_AA & 0xFF]
    assert us_gettar(handle, 1) == expected


def test_form_freq_diphthong_sentinel_returned_verbatim() -> None:
    """Targets < -1 (diphthong sentinels) flow through unchanged."""
    handle = _make_handle(np_idx=F1, phone=USP_AA)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    # Poison the masked table slot to a sentinel value.
    cast(list[int], p_dph_t.p_tar)[USP_AA & 0xFF] = -5
    assert us_gettar(handle, 1) == -5


def test_b3_clamped_to_1600_for_n_adjacent_to_high_front() -> None:
    """B3 of /n/ clamps to 1600 when adjacent to a high-front vowel."""
    # us_place[IY=1] has F2BACKF (128) set, so an IY in the *previous*
    # slot triggers the clamp via the second arm of the OR.
    handle = _make_handle(np_idx=F1 + 6, phone=USP_N, phlas=USP_IY)
    assert us_gettar(handle, 1) == 1600


# --- AV/AP branch (par_type == 0) ----------------------------------------


def test_glottal_stop_loses_30_at_slow_rate() -> None:
    """USP_Q drops AV by 30 when ``sprate < 100``."""
    base = _make_handle(np_idx=AV, phone=USP_Q, sprate=200)
    slow = _make_handle(np_idx=AV, phone=USP_Q, sprate=50)
    assert us_gettar(base, 1) - us_gettar(slow, 1) == 30


def test_dummy_vowel_reduces_av_by_12() -> None:
    """Dummy-vowel flag in allofeats subtracts 12 from AV."""
    base = _make_handle(np_idx=AV, phone=USP_AA)
    poisoned = _make_handle(np_idx=AV, phone=USP_AA)
    cast(DphT, poisoned.p_ph_thread_data).allofeats[1] = FDUMMY_VOWEL  # type: ignore[union-attr]
    # Both go through the unstressed branch (allofeats stress==0), so
    # the dummy-vowel delta isolates to a -12 difference *modulo* any
    # later corrections. With a vowel like AA we don't hit any other
    # phoneme-specific tweak, so the comparison is clean.
    assert us_gettar(base, 1) - us_gettar(poisoned, 1) == 12


def test_hx_aspiration_53_before_front_vowel() -> None:
    """AP for /hx/ is 53 before a front vowel (begtyp==1)."""
    handle = _make_handle(np_idx=AV + 1, phone=USP_HX, phnex=USP_IY)
    assert us_gettar(handle, 1) == 53


def test_hx_aspiration_56_before_back_vowel() -> None:
    """AP for /hx/ jumps to 56 before a back vowel (begtyp!=1)."""
    handle = _make_handle(np_idx=AV + 1, phone=USP_HX, phnex=USP_AA)
    assert us_gettar(handle, 1) == 56


def test_ap_zero_for_non_hx() -> None:
    """AP is 0 for anything that isn't /hx/."""
    handle = _make_handle(np_idx=AV + 1, phone=USP_EH)
    assert us_gettar(handle, 1) == 0


def test_hx_voiced_target_54_when_unstressed_after_voiced() -> None:
    """/hx/ AV = 54 if preceded by voiced segment and unstressed."""
    handle = _make_handle(np_idx=AV, phone=USP_HX, phlas=USP_AA)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    # Mark nphone slot as not-stress-1 (FSTRESS_1 bit off keeps the
    # voiced-/hx/ rule firing).
    p_dph_t.allofeats[1] = 0  # FSTRESS_1 == 0o1
    # Confirm the rule fires (overrides whatever p_tar said).
    assert us_gettar(handle, 1) == 54 - 4  # 54 from rule, -4 from unstressed


def test_hx_voiced_rule_skipped_when_stress_1_set() -> None:
    """/hx/ AV = 54 rule skips when FSTRESS_1 flag is set."""
    handle = _make_handle(np_idx=AV, phone=USP_HX, phlas=USP_AA)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    p_dph_t.allofeats[1] = FSTRESS_1
    # Result depends on p_tar[HX] + unstressed nudge; just assert it's
    # NOT the post-rule value (54 or 54-4).
    result = us_gettar(handle, 1)
    assert result not in (54, 50)


# --- Parallel-formant-amplitude branch (par_type == 2) --------------------


def test_tilt_zero_for_silence() -> None:
    """TILT target is 0 for GEN_SIL phones."""
    handle = _make_handle(np_idx=TILT, phone=GEN_SIL)
    assert us_gettar(handle, 1) == 0


def test_tilt_20_for_hx() -> None:
    """TILT target is 20 for /hx/."""
    handle = _make_handle(np_idx=TILT, phone=USP_HX)
    assert us_gettar(handle, 1) == 20


def test_tilt_3_for_plain_vowel() -> None:
    """TILT target is +3 when begtyp != 1 and endtyp != 1 (e.g. AA)."""
    # AA: us_begtyp=2 and us_endtyp=2 -> the front-vowel +6 branch is
    # skipped and we land on the default +3.
    handle = _make_handle(np_idx=TILT, phone=USP_AA)
    assert us_gettar(handle, 1) == 3


def test_tilt_6_for_nasal() -> None:
    """TILT target is +6 for a nasal segment (e.g. /m/)."""
    handle = _make_handle(np_idx=TILT, phone=USP_M)
    assert us_gettar(handle, 1) == 6


def test_tilt_7_for_voiceless_obstruent() -> None:
    """TILT target is +7 for a voiceless obstruent (e.g. /s/)."""
    handle = _make_handle(np_idx=TILT, phone=USP_S)
    assert us_gettar(handle, 1) == 7


# --- Sanity guard ---------------------------------------------------------


def test_us_gettar_does_not_mutate_dph_state_outside_par_type() -> None:
    """us_gettar's only side-effect is writing settar.par_type."""
    handle = _make_handle(np_idx=B2, phone=USP_AA)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    initial_nphone = p_dph_t.nphone
    initial_durfon = p_dph_t.durfon
    initial_allofeats = list(p_dph_t.allofeats)
    us_gettar(handle, 1)
    assert p_dph_t.nphone == initial_nphone
    assert p_dph_t.durfon == initial_durfon
    assert p_dph_t.allofeats == initial_allofeats


# Trivial guard so pytest still runs the module if all USP_* constants
# get unused at some point (defensive against accidental import-prune).
def test_imports_resolve() -> None:
    assert pytest is not None
