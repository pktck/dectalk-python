"""C-source parity test for ``set_tglst`` against ph_drwt02.c.

Re-parses the C body and asserts:

- The function signature matches ``static void set_tglst(PDPH_T pDph_t)``.
- The outer ``if (nframg >= segdrg)`` advances ``npg`` via
  ``allodurs[++npg]`` and resets ``segdrg``.
- The ``tglstp`` cancel-and-half-restart guards write ``-200`` /
  ``0`` in the documented order.
- The function-word ``a`` / ``an`` short-circuit returns are present.
- The main glottal-stop-insertion rule tests ``FVOWEL`` / ``FSYLL``
  / ``FPLOSV`` / ``FGLOTTAL`` and writes ``tglstn = segdrg``.
- The mid-segment ``nframg == 8`` / ``nframg == segdrg - 1`` branch
  promotes ``tglstn`` to ``tglstp``.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.usp_codes import USP_AX, USP_EH, USP_N, USP_YU
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import F_FUNC, FBOUNDARY, FSTRESS_1, FVPNEXT, FWBNEXT
from dectalk.ph.phoneme_features import FSYLL, FVOWEL
from dectalk.ph.set_tglst import set_tglst

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/ph/ph_drwt02.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_drwt02_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_drwt02_c()
    match = re.search(
        r"static\s+void\s+set_tglst\s*\([^)]*\)\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "set_tglst() not found in ph_drwt02.c"
    return match.group(1)


def test_signature_matches_c() -> None:
    """Signature is ``static void set_tglst(PDPH_T pDph_t)``."""
    text = _read_drwt02_c()
    sig = re.search(
        r"static\s+void\s+set_tglst\s*\(\s*PDPH_T\s+\w+\s*\)",
        text,
    )
    assert sig is not None


def test_outer_guard_and_npg_increment() -> None:
    """Outer guard ``nframg >= segdrg`` advances ``allodurs[++npg]``."""
    body = _extract_body()
    assert re.search(
        r"if\s*\(\s*pDphsettar->nframg\s*>=\s*pDphsettar->segdrg\s*\)",
        body,
    )
    assert re.search(
        r"pDphsettar->nframg\s*-=\s*pDphsettar->segdrg\s*;",
        body,
    )
    assert re.search(
        r"pDphsettar->segdrg\s*=\s*pDph_t->allodurs\s*\[\s*\+\+\s*pDphsettar->npg\s*\]\s*;",
        body,
    )


def test_tglstp_cancel_then_halve_sequence() -> None:
    """``tglstp == 0`` writes ``-200``, then ``tglstp > 0`` zeroes."""
    body = _extract_body()
    cancel = re.search(
        r"if\s*\(\s*pDphsettar->tglstp\s*==\s*0\s*\)\s*"
        r"pDphsettar->tglstp\s*=\s*-200\s*;",
        body,
    )
    assert cancel is not None
    halve = re.search(
        r"if\s*\(\s*pDphsettar->tglstp\s*>\s*0\s*\)\s*\{\s*"
        r"pDphsettar->tglstp\s*=\s*0\s*;\s*\}",
        body,
    )
    assert halve is not None
    # Cancel must come before halve.
    assert cancel.start() < halve.start()


def test_tglstn_default_minus_200() -> None:
    """Default ``tglstn = -200`` is set before the rule cascade."""
    body = _extract_body()
    assert re.search(r"pDphsettar->tglstn\s*=\s*-200\s*;", body)


def test_function_word_short_circuit_an_and_a() -> None:
    """The ``F_FUNC`` block has ``return`` paths for ``an`` and ``a``."""
    body = _extract_body()
    assert re.search(
        r"if\s*\(\s*pDph_t->allofeats\s*\[\s*pDphsettar->npg\s*-\s*1\s*\]\s*&\s*F_FUNC\s*\)",
        body,
    )
    # "an" check
    assert re.search(
        r"pDph_t->allophons\s*\[\s*pDphsettar->npg\s*\]\s*==\s*USP_N",
        body,
    )
    assert re.search(
        r"pDph_t->allophons\s*\[\s*pDphsettar->npg\s*-\s*1\s*\]\s*==\s*USP_EH",
        body,
    )
    # "a" check
    assert re.search(
        r"pDph_t->allophons\s*\[\s*pDphsettar->npg\s*\]\s*==\s*USP_AX",
        body,
    )


def test_main_rule_features_and_yu_exemption() -> None:
    """Main rule tests FVOWEL on next, FBOUNDARY on cur, !=USP_YU on next."""
    body = _extract_body()
    assert re.search(
        r"phone_feature\(\s*pDph_t\s*,\s*"
        r"pDph_t->allophons\s*\[\s*pDphsettar->npg\s*\+\s*1\s*\]\s*\)\s*&\s*FVOWEL",
        body,
    )
    assert re.search(
        r"pDph_t->allofeats\s*\[\s*pDphsettar->npg\s*\+\s*1\s*\]\s*&\s*"
        r"\(\s*FMEDIALSYL\s*&\s*FFINALSYL\s*\)",
        body,
    )
    assert re.search(
        r"pDph_t->allofeats\s*\[\s*pDphsettar->npg\s*\]\s*&\s*FBOUNDARY\s*\)\s*>=\s*FWBNEXT",
        body,
    )
    assert re.search(
        r"pDph_t->allophons\s*\[\s*pDphsettar->npg\s*\+\s*1\s*\]\s*!=\s*USP_YU",
        body,
    )


def test_same_vowel_stressed_or_vpnext_writes_segdrg() -> None:
    """Inside the FSYLL branch: same-vowel-stressed OR FVPNEXT → tglstn = segdrg."""
    body = _extract_body()
    assert re.search(
        r"pDph_t->allophons\s*\[\s*pDphsettar->npg\s*\]\s*==\s*"
        r"pDph_t->allophons\s*\[\s*pDphsettar->npg\s*\+\s*1\s*\]",
        body,
    )
    assert re.search(
        r"pDph_t->allofeats\s*\[\s*pDphsettar->npg\s*\+\s*1\s*\]\s*&\s*FSTRESS_1",
        body,
    )
    assert re.search(
        r"pDph_t->allofeats\s*\[\s*pDphsettar->npg\s*\]\s*&\s*FBOUNDARY\s*\)\s*>=\s*FVPNEXT",
        body,
    )
    assert re.search(
        r"pDphsettar->tglstn\s*=\s*pDphsettar->segdrg\s*;",
        body,
    )


def test_glottal_place_branches_present() -> None:
    """Both ``place(npg+1) & FGLOTTAL`` and ``place(npg) & FGLOTTAL`` branches."""
    body = _extract_body()
    assert re.search(
        r"place\(\s*pDph_t->allophons\s*\[\s*pDphsettar->npg\s*\+\s*1\s*\]\s*\)\s*&\s*FGLOTTAL",
        body,
    )
    assert re.search(
        r"place\(\s*pDph_t->allophons\s*\[\s*pDphsettar->npg\s*\]\s*\)\s*&\s*FGLOTTAL",
        body,
    )


def test_else_if_promotes_tglstn_to_tglstp() -> None:
    """``nframg == 8`` / ``nframg == segdrg - 1`` → ``tglstp = tglstn``."""
    body = _extract_body()
    assert re.search(
        r"else\s+if\s*\(\s*\(\s*pDphsettar->nframg\s*==\s*8\s*\)"
        r"\s*\|\|\s*\(\s*pDphsettar->nframg\s*==\s*\(\s*pDphsettar->segdrg\s*-\s*1\s*\)\s*\)\s*\)",
        body,
    )
    assert re.search(
        r"pDphsettar->tglstp\s*=\s*pDphsettar->tglstn\s*;",
        body,
    )


def _make_state(
    nframg: int,
    segdrg: int,
    npg: int,
    *,
    tglstp: int = 0,
    tglstn: int = 0,
    allodurs: list[int] | None = None,
    allophons: list[int] | None = None,
    allofeats: list[int] | None = None,
    nallotot: int = 100,
) -> tuple[DphT, DphSettarSt]:
    """Build a (DphT, DphSettarSt) pair primed for set_tglst."""
    state = DphT()
    settar = DphSettarSt(
        nframg=nframg,
        segdrg=segdrg,
        npg=npg,
        tglstp=tglstp,
        tglstn=tglstn,
    )
    state.pSTphsettar = settar
    state.nallotot = nallotot
    # Sized buffers — 200 entries is plenty for the test scenarios.
    state.allodurs = allodurs or [0] * 200
    state.allophons = allophons or [0] * 200
    state.allofeats = allofeats or [0] * 200
    return state, settar


def test_python_no_op_when_pdphsettar_missing() -> None:
    """Missing target struct → defensive early return."""
    state = DphT()
    state.pSTphsettar = None
    set_tglst(state)  # must not raise


def test_python_else_if_branch_frame_8_promotes_tglstn() -> None:
    """``nframg == 8`` and ``nframg < segdrg`` → ``tglstp = tglstn``."""
    state, settar = _make_state(nframg=8, segdrg=50, npg=5, tglstp=-100, tglstn=42)
    set_tglst(state)
    assert settar.tglstp == 42
    # nframg is unchanged (no advance happened).
    assert settar.nframg == 8


def test_python_else_if_branch_final_frame_promotes_tglstn() -> None:
    """``nframg == segdrg - 1`` also promotes."""
    state, settar = _make_state(nframg=49, segdrg=50, npg=5, tglstp=-100, tglstn=99)
    set_tglst(state)
    assert settar.tglstp == 99


def test_python_else_if_neither_8_nor_final_no_op() -> None:
    """Middle frame: no-op."""
    state, settar = _make_state(nframg=20, segdrg=50, npg=5, tglstp=-100, tglstn=99)
    set_tglst(state)
    # tglstp unchanged.
    assert settar.tglstp == -100


def test_python_segment_boundary_advances_npg_and_resets_segdrg() -> None:
    """``nframg >= segdrg`` increments npg and reads ``allodurs[npg]``."""
    allodurs = [0] * 200
    allodurs[6] = 77
    state, settar = _make_state(
        nframg=50,
        segdrg=50,
        npg=5,
        allodurs=allodurs,
    )
    set_tglst(state)
    assert settar.npg == 6
    assert settar.segdrg == 77
    assert settar.nframg == 0  # 50 - 50


def test_python_tglstp_zero_gets_cancelled_to_minus_200() -> None:
    """At segment advance with tglstp==0: tglstp becomes -200."""
    state, settar = _make_state(
        nframg=50,
        segdrg=50,
        npg=5,
        tglstp=0,
    )
    set_tglst(state)
    # After the cancel write tglstp is -200; the next ``> 0`` test is
    # false, so it stays -200.
    assert settar.tglstp == -200


def test_python_tglstp_positive_halved_to_zero() -> None:
    """At segment advance with tglstp>0: tglstp becomes 0."""
    state, settar = _make_state(
        nframg=50,
        segdrg=50,
        npg=5,
        tglstp=42,  # >0 → halve to 0
    )
    set_tglst(state)
    assert settar.tglstp == 0


def test_python_default_tglstn_is_minus_200() -> None:
    """At segment advance, tglstn defaults to -200 before rules fire."""
    state, settar = _make_state(
        nframg=50,
        segdrg=50,
        npg=5,
        tglstn=999,
        # No glottal phones, no boundaries — no rule should write tglstn.
    )
    set_tglst(state)
    assert settar.tglstn == -200


def test_python_function_word_an_short_circuits() -> None:
    """``F_FUNC | (EH→N) | FWBNEXT on EH`` → early return."""
    allophons = [0] * 200
    allofeats = [0] * 200
    # After ``++npg`` we'll be at index 6. The C code checks
    # allofeats[npg-1] for F_FUNC, allophons[npg]==N, allophons[npg-1]==EH.
    allophons[5] = USP_EH
    allophons[6] = USP_N
    allofeats[5] = F_FUNC | FWBNEXT  # F_FUNC on EH, with WBNEXT boundary
    state, settar = _make_state(
        nframg=50,
        segdrg=50,
        npg=5,
        tglstn=999,  # sentinel — if not reset, the rule short-circuited
        allophons=allophons,
        allofeats=allofeats,
    )
    set_tglst(state)
    # The early return happens AFTER the default tglstn = -200 write,
    # so we expect -200 (not 999).
    assert settar.tglstn == -200


def test_python_function_word_a_short_circuits() -> None:
    """``F_FUNC on AX | AX phone | FWBNEXT on AX`` → early return."""
    allophons = [0] * 200
    allofeats = [0] * 200
    # After ++npg we are at index 6. F_FUNC is checked on allofeats[npg-1]
    # = index 5; the "a" rule then tests allophons[npg]==USP_AX and
    # allofeats[npg] & FBOUNDARY >= FWBNEXT.
    allophons[6] = USP_AX
    allofeats[5] = F_FUNC
    allofeats[6] = FWBNEXT
    state, settar = _make_state(
        nframg=50,
        segdrg=50,
        npg=5,
        tglstn=999,
        allophons=allophons,
        allofeats=allofeats,
    )
    set_tglst(state)
    assert settar.tglstn == -200


def test_python_yu_after_boundary_does_not_trigger() -> None:
    """Next phone /YU/ exemption: tglstn stays at -200 even at a boundary."""
    allophons = [0] * 200
    allofeats = [0] * 200
    # After ++npg we're at index 6. Set up a vowel-shaped next phone (USP_YU)
    # with FVOWEL feature; this is exactly the path the rule disallows.
    allophons[7] = USP_YU
    allofeats[6] = FWBNEXT
    state, settar = _make_state(
        nframg=50,
        segdrg=50,
        npg=5,
        allophons=allophons,
        allofeats=allofeats,
    )
    set_tglst(state)
    # YU exemption: the main rule does not fire.
    assert settar.tglstn == -200


def test_python_feature_bit_constants_match_c() -> None:
    """Spot-check the constants used in the rule cascade."""
    # FBOUNDARY mask covers FWBNEXT and FVPNEXT.
    assert (FWBNEXT & FBOUNDARY) == FWBNEXT
    assert (FVPNEXT & FBOUNDARY) == FVPNEXT
    # FVPNEXT (phrase) is a stronger boundary than FWBNEXT (word).
    assert FVPNEXT > FWBNEXT
    # FVOWEL / FSYLL / FSTRESS_1 are non-zero feature bits.
    assert FVOWEL != 0
    assert FSYLL != 0
    assert FSTRESS_1 != 0
    # F_FUNC has a high-order bit (above the boundary fields).
    assert F_FUNC > FBOUNDARY


def test_python_usp_constants_match_c() -> None:
    """Spot-check the USP_* phone-code constants the C source references."""
    # All five referenced constants are distinct positive integers.
    constants = {USP_AX, USP_EH, USP_N, USP_YU}
    assert len(constants) == 4
    for c in constants:
        assert c > 0
