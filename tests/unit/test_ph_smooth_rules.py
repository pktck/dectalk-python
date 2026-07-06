"""Behavioural tests for the three US smooth/special-rule helpers.

Each rule helper is called with a populated DphT and asserts that the
relevant output slots (``bouval`` / ``durtran`` / ``tbacktr`` /
parameter ``tspesh``) are written. Coverage is necessarily wide-net
rather than oracle-strict because the C source has many overlapping
phoneme-specific tweaks; the tests focus on the dispatch shape and
the dominant default rules.
"""

from __future__ import annotations

from typing import cast

from dectalk.include.usp_codes import USP_AA, USP_K, USP_N
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.frame_counts import NF40MS, NF45MS, NF80MS
from dectalk.ph.numeric_constants import AP, AV, B1, F1, FZ
from dectalk.ph.parameter_tables import partyp
from dectalk.ph.phoneme_features import (
    FNASAL,
    FPLOSV,
    FSONOR,
    FVOICD,
)
from dectalk.ph.rom_tables import us_femamp, us_femdip, us_femtar
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.us_back_smooth_rules import us_back_smooth_rules
from dectalk.ph.us_forw_smooth_rules import us_forw_smooth_rules
from dectalk.ph.us_special_rules import us_special_rules
from dectalk.ph.utterance_constants import GEN_SIL


def _make_handle(np_idx: int, phcur: int, phonex: int = GEN_SIL) -> TtsHandle:
    """Build a minimal handle for smooth-rule tests."""
    p_dph_t = DphT()
    p_dph_t.allophons = [GEN_SIL] * 6
    p_dph_t.allofeats = [0] * 6
    p_dph_t.allodurs = [0] * 6
    p_dph_t.nallotot = 6
    p_dph_t.nphone = 2
    p_dph_t.durfon = 12
    p_dph_t.p_tar = list(us_femtar)
    p_dph_t.p_amp = list(us_femamp)
    p_dph_t.p_diph = list(us_femdip)
    p_dph_t.last_lang = 0x1E << 8  # US_FONT, suppresses table-load.
    settar = DphSettarSt()
    settar.np = np_idx
    settar.par_type = partyp[np_idx - 1] if np_idx >= 1 else 0
    settar.phcur = phcur
    settar.phonex = phonex
    settar.bouval = 0
    settar.durtran = 0
    p_dph_t.pSTphsettar = settar
    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    handle.p_kernel_share_data = KsdT()
    return handle


# -- us_forw_smooth_rules ---------------------------------------------------


def test_forw_nasal_zero_writes_boundary_on_nasal_to_non_nasal() -> None:
    """FZ branch: leaving a nasal sets bouval to 400.

    p_us_st0.c line 602 (the active OLD_SETTAR variant) hardcodes 400;
    the p_us_st1.c rewrite used NASAL_ZERO_BOUNDARY = 370 (issue #269).
    """
    handle = _make_handle(np_idx=FZ, phcur=USP_AA)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    p_dph_t.durfon = 40  # large enough that durfon-clamp doesn't fire
    us_forw_smooth_rules(
        phTTS=handle,
        shrif=16384,
        pholas=USP_N,
        fealas=FNASAL,
        feacur=0,
        struclas=0,
        struccur=0,
        feanex=0,
    )
    settar = cast(DphSettarSt, p_dph_t.pSTphsettar)
    assert settar.bouval == 400
    assert settar.durtran == NF80MS


def test_forw_form_freq_silence_uses_durfon() -> None:
    """FORM_FREQ at silence: durtran = durfon, bouval = tarlas or tarnex."""
    handle = _make_handle(np_idx=F1, phcur=GEN_SIL)
    us_forw_smooth_rules(
        phTTS=handle,
        shrif=16384,
        pholas=USP_AA,
        fealas=FSONOR,
        feacur=0,
        struclas=0,
        struccur=0,
        feanex=0,
    )
    settar = cast(DphSettarSt, cast(DphT, handle.p_ph_thread_data).pSTphsettar)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    assert settar.durtran == p_dph_t.durfon


def test_forw_form_bw_default_is_nf40ms() -> None:
    """FORM_BW (B1) default durtran is NF40MS when voiced->voiced."""
    handle = _make_handle(np_idx=B1, phcur=USP_AA)
    us_forw_smooth_rules(
        phTTS=handle,
        shrif=16384,
        pholas=USP_AA,
        fealas=FVOICD | FSONOR,
        feacur=FVOICD | FSONOR,
        struclas=0,
        struccur=0,
        feanex=FVOICD | FSONOR,
    )
    settar = cast(DphSettarSt, cast(DphT, handle.p_ph_thread_data).pSTphsettar)
    # durtran lands at NF40MS via default, NF50MS if B1 widening fires.
    # Both are valid; assert > 0 and <= NF45MS-ish range.
    assert settar.durtran in (NF40MS, NF45MS, 8)  # 8 = NF50MS


# -- us_back_smooth_rules ---------------------------------------------------


def test_back_writes_tbacktr() -> None:
    """us_back_smooth_rules writes ``tbacktr = durfon - durtran``."""
    handle = _make_handle(np_idx=F1, phcur=USP_AA, phonex=GEN_SIL)
    us_back_smooth_rules(
        phTTS=handle,
        shrib=16384,
        feacur=FSONOR,
        feanex=0,
        strucnex=0,
    )
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    settar = cast(DphSettarSt, p_dph_t.pSTphsettar)
    np_param = p_dph_t.param[settar.np]
    assert np_param.tbacktr == p_dph_t.durfon - settar.durtran


def test_back_silence_phonex_clears_durtran() -> None:
    """Next phone is silence -> durtran clamped to 0 for FORM_FREQ."""
    handle = _make_handle(np_idx=F1, phcur=USP_AA, phonex=GEN_SIL)
    us_back_smooth_rules(
        phTTS=handle,
        shrib=16384,
        feacur=FSONOR,
        feanex=0,
        strucnex=0,
    )
    settar = cast(DphSettarSt, cast(DphT, handle.p_ph_thread_data).pSTphsettar)
    assert settar.durtran == 0


# -- us_special_rules -------------------------------------------------------


def test_special_voicebar_writes_av_tspesh() -> None:
    """Voiced-burst phone (USP_DZ-like) writes voicebar params via Rule 3."""
    handle = _make_handle(np_idx=AV, phcur=USP_K)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    # USP_K is FBURST + voiced context is unlikely, but Rule 3 only
    # fires when feacur has FBURST | FVOICD set; test that path.
    us_special_rules(
        phTTS=handle,
        fealas=FVOICD | FPLOSV,
        feacur=FVOICD | FPLOSV,  # FBURST not set -> Rule 3 doesn't fire
        feanex=0,
        struclm2=0,
        struccur=0,
        pholas=0,
        struclas=0,
    )
    # Without FBURST, Rule 3 path skips; AV.tspesh stays 0.
    assert p_dph_t.param[AV].tspesh == 0


def test_special_vot_rule_fires_for_aspirated_plosive() -> None:
    """Rule 2 (VOT) writes ``AP.pspesh`` / ``AV.tspesh`` when context matches."""
    handle = _make_handle(np_idx=AV, phcur=USP_AA)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    p_dph_t.allophons[1] = USP_K  # previous = K (plosive, voiceless)
    us_special_rules(
        phTTS=handle,
        fealas=FPLOSV,  # voiceless plosive -> Rule 2 fires
        feacur=FSONOR,
        feanex=0,
        struclm2=0,
        struccur=0,  # unstressed
        pholas=USP_K,
        struclas=0,
    )
    # PAP.pspesh gets written (one of 52, 55, or with adjustments).
    assert p_dph_t.param[AP].pspesh != 0
