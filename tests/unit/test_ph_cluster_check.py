"""Verify ``us_phcluster`` parity with p_us_sr1.c.

Cross-validates the PH-side cluster-legality function against the
documented cluster rules (mirrors the LTS-side ls_adju_cluster
test, but with font-encoded inputs).
"""

from __future__ import annotations

import pytest

from dectalk.include.phoneme_codes import PFUSA, USPhoneme
from dectalk.ph import cluster_check as cc

_PSFONT = 8


def _usp(code: USPhoneme) -> int:
    return (PFUSA << _PSFONT) | int(code)


def test_pl_is_cluster_trys() -> None:
    """PL is a TRYS cluster (PL → PLAY, SPL → SPLAY)."""
    assert cc.us_phcluster(_usp(USPhoneme.P), _usp(USPhoneme.LL)) == cc.CLUSTER_TRYS


def test_bl_is_cluster() -> None:
    """BL is a plain CLUSTER (no SBL onset in English)."""
    assert cc.us_phcluster(_usp(USPhoneme.B), _usp(USPhoneme.LL)) == cc.CLUSTER


def test_kw_is_trys() -> None:
    """KW is TRYS — QUICK / SQUASH both legal."""
    assert cc.us_phcluster(_usp(USPhoneme.K), _usp(USPhoneme.W)) == cc.CLUSTER_TRYS


def test_sm_is_cluster() -> None:
    """SM is CLUSTER."""
    assert cc.us_phcluster(_usp(USPhoneme.S), _usp(USPhoneme.M)) == cc.CLUSTER


def test_pb_is_nocluster() -> None:
    """PB has no English onset."""
    assert cc.us_phcluster(_usp(USPhoneme.P), _usp(USPhoneme.B)) == cc.NOCLUSTER


def test_first_not_in_switch_is_nocluster() -> None:
    """A first phoneme outside the switch returns NOCLUSTER."""
    assert cc.us_phcluster(_usp(USPhoneme.M), _usp(USPhoneme.LL)) == cc.NOCLUSTER
    assert cc.us_phcluster(_usp(USPhoneme.N), _usp(USPhoneme.R)) == cc.NOCLUSTER


def test_raw_codes_not_in_switch() -> None:
    """Raw (un-font-encoded) codes return NOCLUSTER."""
    # USP_P = (0x1E << 8) | US_P. Raw US_P alone shouldn't match.
    assert cc.us_phcluster(int(USPhoneme.P), int(USPhoneme.LL)) == cc.NOCLUSTER


def test_constant_values() -> None:
    """NOCLUSTER/CLUSTER/CLUSTER_TRYS match the C source #defines."""
    expected_nocluster = 0
    expected_cluster = 1
    expected_cluster_trys = 2
    assert expected_nocluster == cc.NOCLUSTER
    assert expected_cluster == cc.CLUSTER
    assert expected_cluster_trys == cc.CLUSTER_TRYS


@pytest.mark.parametrize(
    ("f_name", "s_name", "expected"),
    [
        # P
        ("P", "LL", "CLUSTER_TRYS"),
        ("P", "R", "CLUSTER_TRYS"),
        # B
        ("B", "LL", "CLUSTER"),
        ("B", "R", "CLUSTER"),
        # F
        ("F", "R", "CLUSTER_TRYS"),
        ("F", "LL", "CLUSTER"),
        # T
        ("T", "R", "CLUSTER_TRYS"),
        ("T", "W", "CLUSTER"),
        # D / TH
        ("D", "R", "CLUSTER"),
        ("D", "W", "CLUSTER"),
        ("TH", "R", "CLUSTER"),
        ("TH", "W", "CLUSTER"),
        # K
        ("K", "R", "CLUSTER_TRYS"),
        ("K", "LL", "CLUSTER_TRYS"),
        ("K", "W", "CLUSTER_TRYS"),
        # G
        ("G", "R", "CLUSTER"),
        ("G", "LL", "CLUSTER"),
        ("G", "W", "CLUSTER"),
        # S
        ("S", "W", "CLUSTER"),
        ("S", "LL", "CLUSTER"),
        ("S", "P", "CLUSTER"),
        ("S", "T", "CLUSTER"),
        ("S", "K", "CLUSTER"),
        ("S", "M", "CLUSTER"),
        ("S", "N", "CLUSTER"),
        ("S", "F", "CLUSTER"),
        # SH
        ("SH", "W", "CLUSTER"),
        ("SH", "LL", "CLUSTER"),
        ("SH", "P", "CLUSTER"),
        ("SH", "T", "CLUSTER"),
        ("SH", "R", "CLUSTER"),
        ("SH", "M", "CLUSTER"),
        ("SH", "N", "CLUSTER"),
    ],
)
def test_all_documented_clusters(f_name: str, s_name: str, expected: str) -> None:
    """Each (first, second) pair from the C switch yields the documented code."""
    f = _usp(getattr(USPhoneme, f_name))
    s = _usp(getattr(USPhoneme, s_name))
    code_map = {
        "NOCLUSTER": cc.NOCLUSTER,
        "CLUSTER": cc.CLUSTER,
        "CLUSTER_TRYS": cc.CLUSTER_TRYS,
    }
    assert cc.us_phcluster(f, s) == code_map[expected]
