"""Behavioural tests for the Python port of ``us_phalloph``.

The C source lives in ``src/dapi/src/ph/ph_aloph1.c`` lines 444-1546;
the Python port mirrors the ENGLISH_US path through the function.
Each test exercises one rule branch and asserts that the allophone
output / feature flags / nallotot are populated as expected.

These tests do not depend on the C oracle — they construct a minimal
:class:`~dectalk.ph.dph_t.DphT` and exercise the function directly.
"""

from __future__ import annotations

from dectalk.include.usp_codes import (
    USP_AE,
    USP_AX,
    USP_CH,
    USP_DH,
    USP_ER,
    USP_EY,
    USP_F,
    USP_IY,
    USP_M,
    USP_N,
    USP_OR,
    USP_R,
    USP_RR,
    USP_T,
    USP_YU,
)
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.mode_flags import MODE_CITATION
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import (
    FBOUNDARY,
    FHAT_BEGINS,
    FSTRESS_1,
    FWBNEXT,
    FWINITC,
)
from dectalk.ph.inton_constants import NORMAL
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.us_phalloph import us_phalloph
from dectalk.ph.utterance_constants import GEN_SIL


def _make_handle(
    phonemes: list[int],
    sentstruc: list[int],
    *,
    f0mode: int = NORMAL,
    docitation: int = 0,
    modeflag: int = 0,
) -> TtsHandle:
    """Build a populated TtsHandle for us_phalloph.

    Allocates output buffers slightly larger than ``len(phonemes)`` so
    ``make_out_phonol`` can append without resizing on every call.
    """
    p_dph_t = DphT()
    p_dph_t.phonemes = list(phonemes)
    p_dph_t.sentstruc = list(sentstruc)
    p_dph_t.nphonetot = len(phonemes)
    p_dph_t.user_durs = [0] * (len(phonemes) + 8)
    p_dph_t.user_f0 = [0] * (len(phonemes) + 8)
    p_dph_t.allophons = [0] * (len(phonemes) + 16)
    p_dph_t.allofeats = [0] * (len(phonemes) + 16)
    p_dph_t.nallotot = 0
    p_dph_t.f0mode = f0mode
    p_dph_t.docitation = docitation

    p_ksd_t = KsdT()
    p_ksd_t.modeflag = modeflag

    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    handle.p_kernel_share_data = p_ksd_t
    return handle


def test_silence_only_input_populates_one_allophone() -> None:
    """A single GEN_SIL phone goes through unchanged.

    The function should write exactly one allophone (the silence),
    bump ``nallotot`` to 1, and leave the sentinel slot at GEN_SIL.
    """
    handle = _make_handle([GEN_SIL], [0])
    us_phalloph(handle)

    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)
    assert p_dph_t.nallotot == 1
    assert p_dph_t.allophons[0] == GEN_SIL
    # Sentinel slot after the last written allophone.
    assert p_dph_t.allophons[1] == GEN_SIL
    assert p_dph_t.allofeats[1] == 0


def test_simple_vowel_writes_allofeats_with_stress() -> None:
    """A stressed vowel triggers FHAT_BEGINS on the output struc.

    Input: [AE] with FSTRESS_1 + FBOUNDARY=FWBNEXT (word-final). The
    hat-pattern bookkeeping sees a stressed syllabic in NORMAL f0mode,
    rises (FHAT_BEGINS), then immediately falls (last clause-stress
    → FHAT_ENDS).
    """
    handle = _make_handle(
        [USP_AE],
        [FSTRESS_1 | FWBNEXT],  # primary stress, word-final.
    )
    us_phalloph(handle)

    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)
    assert p_dph_t.nallotot == 1
    # The phone itself doesn't get rewritten (AE has no rule that fires).
    assert p_dph_t.allophons[0] == USP_AE
    # Stress bits preserved.
    assert (p_dph_t.allofeats[0] & FSTRESS_1) != 0
    # Hat-begin marker added by the intonation bookkeeping.
    assert (p_dph_t.allofeats[0] & FHAT_BEGINS) != 0


def test_consonant_cluster_dh_iy_ax_replaces_ax_with_iy() -> None:
    """Rule 1a: "the" → /dh iy/ before a syllabic.

    Input: [DH, AX, AE] with sentstruc[0]=FWINITC, sentstruc[1]=FBOUNDARY.
    The rule fires for n=1 because:
      - phonemes[n+1] = AE is FSYLL+
      - curr_inph = AX
      - sentstruc[n] & FBOUNDARY != 0
      - phonemes[n-1] = DH
      - sentstruc[n-1] & FWINITC != 0
    Output: allophons[1] should be USP_IY, not USP_AX.
    """
    handle = _make_handle(
        [USP_DH, USP_AX, USP_AE],
        [FWINITC, FBOUNDARY, FSTRESS_1],
    )
    us_phalloph(handle)

    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)
    assert p_dph_t.nallotot == 3
    assert p_dph_t.allophons[0] == USP_DH
    # Rule 1a fired: AX → IY.
    assert p_dph_t.allophons[1] == USP_IY
    assert p_dph_t.allophons[2] == USP_AE
    # allofeats records carry the sentstruc bits.
    assert p_dph_t.allofeats[0] == FWINITC
    # allofeats[1] carries FBOUNDARY.
    assert (p_dph_t.allofeats[1] & FBOUNDARY) == FBOUNDARY
    # The stressed vowel at idx 2 picks up FHAT_BEGINS.
    assert (p_dph_t.allofeats[2] & FHAT_BEGINS) != 0


def test_postvocalic_r_after_ae_collapses_to_er() -> None:
    """Rule 2: postvocalic /R/ after [AE] collapses prev to ER, deletes R.

    Input: [AE, R] (n=0: AE word-init stressed; n=1: R unstressed).
    At n=1, the rule fires:
      - curr_instruc & (FSTRESS|FWINITC) == 0
      - phone_feature(phonemes[n-1]=AE) & FVOWEL != 0
      - curr_inph == R
      - symlas == AE → replace allophons[nallotot-1] = USP_ER + delete_short
    Output: only 1 allophone (the original AE slot replaced by ER), R deleted.
    """
    handle = _make_handle(
        [USP_AE, USP_R],
        [0, 0],
    )
    us_phalloph(handle)

    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)
    # The R got deleted (delete_short branch); only one allophone remains.
    assert p_dph_t.nallotot == 1
    # The previous slot's allophone was promoted to ER.
    assert p_dph_t.allophons[0] == USP_ER


def test_t_d_before_y_palatalizes_to_ch_jh() -> None:
    """Rule 3: /t,d/ before unstressed /yu/ palatalize to /ch,jh/.

    Input: [T, YU] with sentstruc[1] unstressed.
    Output: allophons[0] should be USP_CH (T was palatalized).
    """
    handle = _make_handle(
        [USP_T, USP_YU],
        [0, 0],
    )
    us_phalloph(handle)

    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)
    assert p_dph_t.nallotot == 2
    assert p_dph_t.allophons[0] == USP_CH


def test_citation_mode_unreduces_initial_a_to_ey() -> None:
    """Citation-mode rule: leading [AX] at n=1 before sil → EY.

    Input: [SIL, AX, SIL] in citation mode. The rule fires for n=1.
    """
    handle = _make_handle(
        [GEN_SIL, USP_AX, GEN_SIL],
        [0, 0, 0],
        modeflag=MODE_CITATION,
        docitation=1,
    )
    us_phalloph(handle)

    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)
    # AX → EY in citation when next is sil and n == 1.
    assert p_dph_t.allophons[1] == USP_EY


def test_unstressed_dh_after_n_becomes_n() -> None:
    """Rule 4: unstressed /dh/ after /n/ becomes /n/.

    Input: [N, DH] with sentstruc[1] unstressed.
    Output: allophons[1] should be USP_N (the dh was assimilated).
    """
    handle = _make_handle(
        [USP_N, USP_DH],
        [0, 0],
    )
    us_phalloph(handle)

    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)
    assert p_dph_t.nallotot == 2
    assert p_dph_t.allophons[1] == USP_N


def test_for_rr_unreduce_rewrites_next_inph_to_or() -> None:
    """Rule 1b: "for" → /f or/ if followed by vowel or sil.

    Input: [F, RR, AE] with sentstruc[1] unstressed monosyl. Rule fires
    because phonemes[n+2] = AE is FSYLL+. After the rule, the in-place
    phonemes[1] is rewritten to USP_OR.
    """
    handle = _make_handle(
        [USP_F, USP_RR, USP_AE],
        [0, 0, 0],  # n=1 is unstressed FMONOSYL by default.
    )
    us_phalloph(handle)

    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)
    # phonemes[1] should have been rewritten from RR to OR.
    assert p_dph_t.phonemes is not None
    assert p_dph_t.phonemes[1] == USP_OR


def test_long_phrase_clears_citation() -> None:
    """nphonetot >= 6 forces docitation = 0 at the top of the loop."""
    handle = _make_handle(
        [USP_DH, USP_AX, USP_AE, USP_M, USP_T, GEN_SIL],
        [0] * 6,
        docitation=1,
        modeflag=MODE_CITATION,
    )
    us_phalloph(handle)

    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)
    assert p_dph_t.docitation == 0
    # At least most of the input phones get emitted (some rules may delete).
    assert p_dph_t.nallotot >= 5
