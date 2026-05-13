"""Verify get_stress_of_conson matches p_us_sr1.c."""

from __future__ import annotations

from dectalk.include.phoneme_codes import (
    COMMA,
    EXCLAIM,
    S1,
    S2,
    SBOUND,
    SEMPH,
    USPhoneme,
)
from dectalk.include.usp_codes import (
    USP_IY,
    USP_K,
    USP_LL,
    USP_M,
    USP_P,
    USP_R,
    USP_S,
    USP_T,
    USP_W,
)
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FEMPHASIS, FNOSTRESS, FSTRESS_1, FSTRESS_2
from dectalk.ph.get_stress_of_conson import get_stress_of_conson


def _state(symbols: list[int], nphonetot: int = 1, sentstruc_size: int = 4) -> DphT:
    """Build a minimal DphT with the given symbols + sentstruc scratch."""
    state = DphT()
    state.symbols = list(symbols)
    state.nsymbtot = len(symbols)
    state.nphonetot = nphonetot
    state.sentstruc = [FNOSTRESS] * sentstruc_size
    return state


def test_single_consonant_then_s1_sets_fstress_1() -> None:
    """``/t/[1]`` is a legal one-consonant onset: stress should propagate."""
    # symbols[0] = /t/ (the consonant under test), symbols[1] = S1 marker.
    state = _state([USP_T, S1], nphonetot=1)
    get_stress_of_conson(state, 0, compound_destress=0)
    assert state.sentstruc is not None
    assert state.sentstruc[0] & FSTRESS_1
    assert not (state.sentstruc[0] & FSTRESS_2)


def test_single_consonant_then_s2_sets_fstress_2() -> None:
    """A secondary stress marker promotes the consonant to FSTRESS_2."""
    state = _state([USP_T, S2], nphonetot=1)
    get_stress_of_conson(state, 0, compound_destress=0)
    assert state.sentstruc is not None
    assert state.sentstruc[0] & FSTRESS_2


def test_single_consonant_then_semph_sets_femphasis() -> None:
    """An emphatic stress marker OR's FEMPHASIS onto the current phoneme."""
    state = _state([USP_T, SEMPH], nphonetot=1)
    get_stress_of_conson(state, 0, compound_destress=0)
    assert state.sentstruc is not None
    assert state.sentstruc[0] & FEMPHASIS


def test_legal_pair_cluster_str_two_consonants() -> None:
    """``/t/ /r/ [1]`` is a legal CLUSTER_TRYS pair: stress propagates."""
    # /t/ at msym=0, /r/ at 1, S1 at 2 -> mcl=2, cluster(t, r) == CLUSTER_TRYS.
    state = _state([USP_T, USP_R, S1], nphonetot=1)
    get_stress_of_conson(state, 0, compound_destress=0)
    assert state.sentstruc is not None
    assert state.sentstruc[0] & FSTRESS_1


def test_legal_triple_cluster_str() -> None:
    """``/s/ /t/ /r/ [1]`` is /str/: legal triple onset, stress propagates."""
    state = _state([USP_S, USP_T, USP_R, S1], nphonetot=1)
    get_stress_of_conson(state, 0, compound_destress=0)
    assert state.sentstruc is not None
    assert state.sentstruc[0] & FSTRESS_1


def test_illegal_pair_cluster_no_stress() -> None:
    """``/p/ /m/ [1]`` is not a legal English onset: no stress added."""
    state = _state([USP_P, USP_M, S1], nphonetot=1)
    get_stress_of_conson(state, 0, compound_destress=0)
    assert state.sentstruc is not None
    # cluster(p, m) == NOCLUSTER -> early return, no stress.
    assert state.sentstruc[0] == FNOSTRESS


def test_illegal_triple_non_s_leader_no_stress() -> None:
    """``/k/ /t/ /r/ [1]``: leader isn't /s/, so the triple is rejected."""
    # /t/ /r/ is CLUSTER_TRYS, but only /s/ may sit in front of it.
    state = _state([USP_K, USP_T, USP_R, S1], nphonetot=1)
    get_stress_of_conson(state, 0, compound_destress=0)
    assert state.sentstruc is not None
    assert state.sentstruc[0] == FNOSTRESS


def test_quadruple_consonants_early_return() -> None:
    """More than 3 consonants between msym and stress: early return."""
    # symbols: 4 consonants, then S1. mcl = 4 > 3 -> immediate return.
    state = _state([USP_S, USP_T, USP_R, USP_W, S1], nphonetot=1)
    get_stress_of_conson(state, 0, compound_destress=0)
    assert state.sentstruc is not None
    assert state.sentstruc[0] == FNOSTRESS


def test_vowel_before_stress_returns() -> None:
    """If a syllabic phoneme appears before the stress marker, return."""
    # /t/ /iy/ [1] -> /iy/ is FSYLL, so we return before seeing S1.
    state = _state([USP_T, USP_IY, S1], nphonetot=1)
    get_stress_of_conson(state, 0, compound_destress=0)
    assert state.sentstruc is not None
    assert state.sentstruc[0] == FNOSTRESS


def test_boundary_before_stress_returns() -> None:
    """An SBOUND..EXCLAIM marker before the stress symbol stops the scan."""
    # /t/ SBOUND [1] -> SBOUND falls in [SBOUND, EXCLAIM] -> return.
    state = _state([USP_T, SBOUND, S1], nphonetot=1)
    get_stress_of_conson(state, 0, compound_destress=0)
    assert state.sentstruc is not None
    assert state.sentstruc[0] == FNOSTRESS


def test_comma_boundary_in_range_returns() -> None:
    """COMMA is within SBOUND..EXCLAIM and also halts the scan."""
    assert SBOUND <= COMMA <= EXCLAIM
    state = _state([USP_T, COMMA, S1], nphonetot=1)
    get_stress_of_conson(state, 0, compound_destress=0)
    assert state.sentstruc is not None
    assert state.sentstruc[0] == FNOSTRESS


def test_compound_destress_is_ignored() -> None:
    """The ``compound_destress`` argument has no effect (C-API parity)."""
    # Same single-consonant scenario, but with compound_destress = 1.
    state = _state([USP_T, S1], nphonetot=1)
    get_stress_of_conson(state, 0, compound_destress=1)
    assert state.sentstruc is not None
    assert state.sentstruc[0] & FSTRESS_1
    # And the same with compound_destress = 0 produces an identical effect.
    state2 = _state([USP_T, S1], nphonetot=1)
    get_stress_of_conson(state2, 0, compound_destress=0)
    assert state2.sentstruc == state.sentstruc


def test_currphone_writes_to_nphonetot_minus_1() -> None:
    """add_feature writes to ``nphonetot - 1``: confirm via nphonetot=3."""
    # With nphonetot=3, CURRPHONE = 2; sentstruc[2] should get FSTRESS_1.
    state = _state([USP_T, S1], nphonetot=3, sentstruc_size=4)
    get_stress_of_conson(state, 0, compound_destress=0)
    assert state.sentstruc is not None
    assert state.sentstruc[0] == FNOSTRESS
    assert state.sentstruc[1] == FNOSTRESS
    assert state.sentstruc[2] & FSTRESS_1


def test_legal_pair_sw_cluster() -> None:
    """``/s/ /w/`` is a regular CLUSTER (not CLUSTER_TRYS); stress propagates."""
    state = _state([USP_S, USP_W, S1], nphonetot=1)
    get_stress_of_conson(state, 0, compound_destress=0)
    assert state.sentstruc is not None
    assert state.sentstruc[0] & FSTRESS_1


def test_triple_cluster_pair_is_regular_cluster_rejects() -> None:
    """For mcl==3, the inner pair must be CLUSTER_TRYS; CLUSTER alone fails."""
    # /s/ /s/ /w/ : the inner (S, W) is CLUSTER (not CLUSTER_TRYS),
    # so even with a leading /s/ the triple rule rejects it.
    state = _state([USP_S, USP_S, USP_W, S1], nphonetot=1)
    get_stress_of_conson(state, 0, compound_destress=0)
    assert state.sentstruc is not None
    assert state.sentstruc[0] == FNOSTRESS


def test_no_stress_marker_in_range_no_op() -> None:
    """If the scan reaches nsymbtot without hitting a stress marker, no-op."""
    state = _state([USP_T, USP_R], nphonetot=1)
    get_stress_of_conson(state, 0, compound_destress=0)
    assert state.sentstruc is not None
    assert state.sentstruc[0] == FNOSTRESS


def test_msym_at_last_index_no_op() -> None:
    """``msym + 1 >= nsymbtot``: the for-loop body never executes."""
    state = _state([USP_T], nphonetot=1)
    get_stress_of_conson(state, 0, compound_destress=0)
    assert state.sentstruc is not None
    assert state.sentstruc[0] == FNOSTRESS


def test_legal_kr_pair_promotes_stress() -> None:
    """``/k/ /r/ [1]``: k+r is CLUSTER_TRYS, promotion succeeds."""
    state = _state([USP_K, USP_R, S1], nphonetot=1)
    get_stress_of_conson(state, 0, compound_destress=0)
    assert state.sentstruc is not None
    assert state.sentstruc[0] & FSTRESS_1


def test_sentinel_phoneme_value_usphoneme_iy_in_range() -> None:
    """Defensive: USPhoneme.IY value is FSYLL; treat as vowel boundary."""
    # Direct sanity: the raw USPhoneme.IY=1 has FSYLL set in us_featb.
    state = _state([USP_T, int(USPhoneme.IY), S1], nphonetot=1)
    # The element at index 1 is a bare integer (USPhoneme.IY = 1). Stripped
    # by & PVALUE -> 1. phone_feature(1) returns us_featb[1] which has FSYLL.
    get_stress_of_conson(state, 0, compound_destress=0)
    assert state.sentstruc is not None
    assert state.sentstruc[0] == FNOSTRESS


def test_legal_skl_triple_cluster() -> None:
    """``/s/ /k/ /l/ [1]``: legal /skl/ triple onset."""
    # /k/ /ll/ is CLUSTER_TRYS, prefixed by /s/ -> stress propagates.
    state = _state([USP_S, USP_K, USP_LL, S1], nphonetot=1)
    get_stress_of_conson(state, 0, compound_destress=0)
    assert state.sentstruc is not None
    assert state.sentstruc[0] & FSTRESS_1
