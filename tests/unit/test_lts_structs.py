"""Verify the core LTS dataclasses + helpers against ls_defs.h.

Re-parses the C struct field definitions and bit-flag values at
test time so the Python port stays in sync with future C-source
revisions.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.lts import structs as s


def _src_path() -> Path | None:
    """Locate ``ls_defs.h`` in the local C source clone, if present."""
    root_env = os.environ.get("DECTALK_SRC")
    candidates = [
        Path(root_env) if root_env else None,
        Path("/tmp/dectalk-src/src"),
    ]
    for root in candidates:
        if root is None:
            continue
        p = root / "dapi/src/lts/ls_defs.h"
        if p.exists():
            return p
    return None


def _read_ls_defs() -> str:
    path = _src_path()
    if path is None:
        pytest.skip("ls_defs.h not available on this host")
    return path.read_bytes().decode("latin-1").replace("\r\n", "\n")


# ---- PF* boundary flags match #defines ----


@pytest.mark.parametrize(
    ("name", "constant"),
    [
        ("PFDASH", s.PFDASH),
        ("PFSTAR", s.PFSTAR),
        ("PFHASH", s.PFHASH),
        ("PFPLUS", s.PFPLUS),
        ("PFSYLAB", s.PFSYLAB),
        ("PFRFUSE", s.PFRFUSE),
        ("PFLEFTC", s.PFLEFTC),
        ("PFBLOCK", s.PFBLOCK),
    ],
)
def test_pf_flags_match_c_source(name: str, constant: int) -> None:
    """Each PF* bit equals its ``#define`` from ls_defs.h."""
    src = _read_ls_defs()
    m = re.search(rf"#define\s+{name}\s+(0x[0-9a-fA-F]+)", src)
    assert m, f"#define {name} not found"
    assert int(m.group(1), 0) == constant


def test_pf_compound_flags() -> None:
    """PFBOUND and PFMORPH are unions of single-bit flags."""
    assert s.PFBOUND == s.PFDASH | s.PFSTAR | s.PFHASH
    assert s.PFMORPH == s.PFDASH | s.PFSTAR | s.PFHASH | s.PFPLUS


@pytest.mark.parametrize(
    ("name", "constant"),
    [
        ("LS_ANY_STRESS", s.LS_ANY_STRESS),
        ("LS_STRESS_1", s.LS_STRESS_1),
        ("LS_STRESS_2", s.LS_STRESS_2),
        ("LS_STRESS_3", s.LS_STRESS_3),
        ("LSSBOUND", s.LSSBOUND),
        ("LSVOWEL", s.LSVOWEL),
    ],
)
def test_spanish_stress_bits_match(name: str, constant: int) -> None:
    """Spanish/French stress bits match the C #defines."""
    src = _read_ls_defs()
    m = re.search(rf"#define\s+{name}\s+(\d+)", src)
    assert m, f"#define {name} not found"
    assert int(m.group(1)) == constant


# ---- struct shapes ----


def test_item_default_construction() -> None:
    """An empty ITEM has nword=0 and zeroed word slots."""
    item = s.Item()
    assert item.i_nword == 0
    assert item.i_word == [0, 0, 0, 0]


def test_item_with_words() -> None:
    """An ITEM holds up to 4 words."""
    item = s.Item(i_nword=2, i_word=[0x1234, 0x5678, 0, 0])
    assert item.i_nword == 2
    assert item.i_word[0] == 0x1234
    assert item.i_word[1] == 0x5678


def test_phone_default_construction() -> None:
    """A PHONE has all fields zero and no neighbours."""
    p = s.Phone()
    assert p.p_fp is None
    assert p.p_bp is None
    assert p.p_flag == 0
    assert p.p_stress == 0
    assert p.p_sphone == 0
    assert p.p_uphone == 0


def test_phone_linked_list() -> None:
    """PHONE nodes can be doubly-linked."""
    head = s.Phone()
    mid = s.Phone(p_bp=head)
    tail = s.Phone(p_bp=mid)
    head.p_fp = mid
    mid.p_fp = tail

    assert s.next_(head) is mid
    assert s.next_(mid) is tail
    assert s.next_(tail) is None
    assert s.prev(tail) is mid
    assert s.prev(mid) is head
    assert s.prev(head) is None


def test_letter_default_construction() -> None:
    """A LETTER holds a 16-bit character code."""
    ell = s.Letter()
    assert ell.l_ch == 0


def test_letter_holds_grapheme() -> None:
    """LETTER.l_ch round-trips Latin-1 bytes."""
    for ch in ("a", "Z", "é", "ñ"):
        ell = s.Letter(l_ch=ord(ch))
        assert ell.l_ch == ord(ch)


def test_num_default_construction() -> None:
    """An empty NUM has all-None pointer pairs."""
    n = s.Num()
    assert n.n_ilp is None and n.n_irp is None
    assert n.n_flp is None and n.n_frp is None
    assert n.n_elp is None and n.n_erp is None


def test_num_holds_letter_pointers() -> None:
    """NUM can store pointer pairs into a LETTER stream."""
    lp = s.Letter(l_ch=ord("1"))
    rp = s.Letter(l_ch=ord("0"))
    n = s.Num(n_ilp=lp, n_irp=rp)
    assert n.n_ilp is lp
    assert n.n_irp is rp


def test_graph_default_construction() -> None:
    """A GRAPH has zeroed grapheme code and features."""
    g = s.Graph()
    assert g.g_graph == 0
    assert g.g_feats == 0


# ---- LSIS* predicates ----


def test_ls_is_stress() -> None:
    """LSISSTRESS tests p_flag & LS_ANY_STRESS."""
    assert s.ls_is_stress(s.Phone(p_flag=s.LS_STRESS_1)) is True
    assert s.ls_is_stress(s.Phone(p_flag=s.LS_STRESS_2)) is True
    assert s.ls_is_stress(s.Phone(p_flag=s.LS_STRESS_3)) is True
    assert s.ls_is_stress(s.Phone(p_flag=0)) is False
    assert s.ls_is_stress(s.Phone(p_flag=s.LSVOWEL)) is False


def test_ls_is_sbound() -> None:
    """LSISSBOUND tests p_flag & LSSBOUND."""
    assert s.ls_is_sbound(s.Phone(p_flag=s.LSSBOUND)) is True
    assert s.ls_is_sbound(s.Phone(p_flag=0)) is False
    assert s.ls_is_sbound(s.Phone(p_flag=s.LSVOWEL)) is False


def test_ls_is_vowel() -> None:
    """LSISVOWEL tests p_flag & LSVOWEL."""
    assert s.ls_is_vowel(s.Phone(p_flag=s.LSVOWEL)) is True
    assert s.ls_is_vowel(s.Phone(p_flag=0)) is False
    assert s.ls_is_vowel(s.Phone(p_flag=s.LSSBOUND)) is False


def test_ls_is_predicates_combine() -> None:
    """A PHONE can satisfy multiple LSIS* predicates simultaneously."""
    p = s.Phone(p_flag=s.LS_STRESS_1 | s.LSVOWEL | s.LSSBOUND)
    assert s.ls_is_stress(p) is True
    assert s.ls_is_sbound(p) is True
    assert s.ls_is_vowel(p) is True
