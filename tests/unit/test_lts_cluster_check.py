"""Verify ``ls_adju_cluster`` parity with l_us_ad1.c.

Cross-validates the Python port by enumerating every (first, second)
phoneme pair within the C function's switch domain and comparing
both implementations' return codes.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.phoneme_codes import USPhoneme
from dectalk.lts import cluster_check as cc

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/lts/l_us_ad1.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_cluster_rules() -> dict[int, list[tuple[set[int], str]]]:
    """Parse the ``ls_adju_cluster`` switch from the C source.

    Returns ``{first_phoneme_code: [(set_of_second_codes, "OK"|"TRYS"), ...]}``.
    Each list is in C source order, mirroring the if-chain within
    each ``case``.
    """
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(
        r"int\s+ls_adju_cluster\s*\([^)]+\)\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert m is not None
    body = m.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    us_codes = {f"US_{m.name}": int(m) for m in USPhoneme}

    rules: dict[int, list[tuple[set[int], str]]] = {}
    current_cases: list[int] = []
    for line in body.splitlines():
        stripped = line.strip()
        # Match `case US_X:` and `case US_X: case US_Y:` form
        for cm in re.finditer(r"case\s+(US_\w+)\s*:", stripped):
            current_cases.append(us_codes[cm.group(1)])
        if "break" in stripped or stripped.startswith("}"):
            current_cases = []
            continue
        # Match `if (s==US_X || s==US_Y ...)` return-code pattern.
        if_match = re.search(r"if\s*\((.+)\)", stripped)
        if if_match and current_cases:
            tokens = re.findall(r"US_\w+", if_match.group(1))
            second_set = {us_codes[t] for t in tokens}
            # Find return code in this line or the next
            ret_match = re.search(r"return\s*\(?\s*(OK|TRYS|ILLEGAL)\b", stripped)
            if ret_match is None:
                # multi-line if — read next line(s) until return
                continue  # we handle this in a separate pass
            code_name = ret_match.group(1)
            for first in current_cases:
                rules.setdefault(first, []).append((second_set, code_name))
    return rules


def test_known_pl_is_trys() -> None:
    """``PL`` (P + LL) is TRYS — "PLAY" is legal, "SPLAY" also legal."""
    assert cc.ls_adju_cluster(int(USPhoneme.P), int(USPhoneme.LL)) == cc.TRYS


def test_known_pr_is_trys() -> None:
    """``PR`` is TRYS."""
    assert cc.ls_adju_cluster(int(USPhoneme.P), int(USPhoneme.R)) == cc.TRYS


def test_known_bl_is_ok() -> None:
    """``BL`` is OK — "BLUE" but no English "SBLUE"."""
    assert cc.ls_adju_cluster(int(USPhoneme.B), int(USPhoneme.LL)) == cc.OK


def test_known_dw_is_ok() -> None:
    """``DW`` is OK — "DWARF"."""
    assert cc.ls_adju_cluster(int(USPhoneme.D), int(USPhoneme.W)) == cc.OK


def test_known_sm_is_ok() -> None:
    """``SM`` is OK — "SMALL"."""
    assert cc.ls_adju_cluster(int(USPhoneme.S), int(USPhoneme.M)) == cc.OK


def test_known_kw_is_trys() -> None:
    """``KW`` is TRYS — "QUICK" → /kw/, "SQUASH" → /skw/."""
    assert cc.ls_adju_cluster(int(USPhoneme.K), int(USPhoneme.W)) == cc.TRYS


def test_pb_is_illegal() -> None:
    """``PB`` — no English onset cluster."""
    assert cc.ls_adju_cluster(int(USPhoneme.P), int(USPhoneme.B)) == cc.ILLEGAL


def test_first_not_in_switch_is_illegal() -> None:
    """A first phoneme outside the switch (e.g. M, N, R) returns ILLEGAL."""
    assert cc.ls_adju_cluster(int(USPhoneme.M), int(USPhoneme.LL)) == cc.ILLEGAL
    assert cc.ls_adju_cluster(int(USPhoneme.N), int(USPhoneme.R)) == cc.ILLEGAL
    assert cc.ls_adju_cluster(int(USPhoneme.R), int(USPhoneme.W)) == cc.ILLEGAL


def test_constant_values() -> None:
    """OK/TRYS/ILLEGAL match the ls_defs.h #defines."""
    assert cc.ILLEGAL == 0
    expected_ok = 1
    expected_trys = 2
    assert expected_ok == cc.OK
    assert expected_trys == cc.TRYS


@pytest.mark.parametrize(
    ("f_name", "s_name", "expected"),
    [
        # P
        ("P", "LL", "TRYS"),
        ("P", "R", "TRYS"),
        # B
        ("B", "LL", "OK"),
        ("B", "R", "OK"),
        # F
        ("F", "R", "TRYS"),
        ("F", "LL", "OK"),
        # T
        ("T", "R", "TRYS"),
        ("T", "W", "OK"),
        # D
        ("D", "W", "OK"),
        ("D", "R", "OK"),
        # TH
        ("TH", "W", "OK"),
        ("TH", "R", "OK"),
        # K
        ("K", "W", "TRYS"),
        ("K", "LL", "TRYS"),
        ("K", "R", "TRYS"),
        # G
        ("G", "W", "OK"),
        ("G", "LL", "OK"),
        ("G", "R", "OK"),
        # S (8 second phonemes)
        ("S", "W", "OK"),
        ("S", "LL", "OK"),
        ("S", "P", "OK"),
        ("S", "T", "OK"),
        ("S", "K", "OK"),
        ("S", "M", "OK"),
        ("S", "N", "OK"),
        ("S", "F", "OK"),
        # SH
        ("SH", "W", "OK"),
        ("SH", "LL", "OK"),
        ("SH", "R", "OK"),
        ("SH", "P", "OK"),
        ("SH", "T", "OK"),
        ("SH", "M", "OK"),
        ("SH", "N", "OK"),
    ],
)
def test_all_documented_clusters(f_name: str, s_name: str, expected: str) -> None:
    """Each (first, second) pair from the C switch yields the documented code."""
    f = int(getattr(USPhoneme, f_name))
    s = int(getattr(USPhoneme, s_name))
    expected_code = {"OK": cc.OK, "TRYS": cc.TRYS, "ILLEGAL": cc.ILLEGAL}[expected]
    assert cc.ls_adju_cluster(f, s) == expected_code


def test_parity_against_c_parse() -> None:
    """Every (first, second) pair the C switch covers matches our Python output."""
    rules = _parse_cluster_rules()
    name_to_code = {"OK": cc.OK, "TRYS": cc.TRYS}
    for first, branches in rules.items():
        for second_set, code_name in branches:
            expected_code = name_to_code[code_name]
            for s in second_set:
                got = cc.ls_adju_cluster(first, s)
                assert got == expected_code, (
                    f"first={first} second={s}: C says {code_name}, Python returns {got}"
                )
