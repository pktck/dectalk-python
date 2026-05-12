"""Verify the PHONE-list helpers (ls_util_copyword, ls_rule_add_phone)."""

from __future__ import annotations

from dectalk.lts import phone_list as pl
from dectalk.lts.structs import Letter, Phone


def test_copyword_simple() -> None:
    """Copy a 5-letter word terminated by EOS."""
    src = [Letter(l_ch=ord(c)) for c in "hello"] + [Letter(l_ch=pl.EOS)]
    out = pl.ls_util_copyword(src)
    assert len(out) == 6  # 5 letters + EOS
    for i, ch in enumerate("hello"):
        assert out[i].l_ch == ord(ch)
    assert out[-1].l_ch == pl.EOS


def test_copyword_stops_at_first_eos() -> None:
    """A non-terminal EOS truncates the copy."""
    src = [Letter(l_ch=ord("a")), Letter(l_ch=pl.EOS), Letter(l_ch=ord("b"))]
    out = pl.ls_util_copyword(src)
    assert [lp.l_ch for lp in out] == [ord("a"), pl.EOS]


def test_copyword_empty() -> None:
    """Empty word still produces an EOS terminator."""
    out = pl.ls_util_copyword([Letter(l_ch=pl.EOS)])
    assert len(out) == 1
    assert out[0].l_ch == pl.EOS


def test_copyword_returns_new_letters() -> None:
    """Output LETTERs are distinct objects, not references to source."""
    src = [Letter(l_ch=ord("x")), Letter(l_ch=pl.EOS)]
    out = pl.ls_util_copyword(src)
    assert out[0] is not src[0]
    # Mutating the source must not affect the copy.
    src[0].l_ch = ord("z")
    assert out[0].l_ch == ord("x")


def test_iter_phone_list_until_sil() -> None:
    """Phones are emitted in order; SIL terminates."""
    phones = pl.iter_phone_list_until_sil([1, 2, 3, 0, 99])
    assert phones == [1, 2, 3]


def test_iter_phone_list_handles_font_encoded_sil() -> None:
    """A font-encoded SIL_US byte (PFUSA<<8|0) also terminates."""
    phones = pl.iter_phone_list_until_sil([1, 2, pl.SIL_US, 99])
    assert phones == [1, 2]


def test_iter_phone_list_no_sil_returns_all() -> None:
    """Without a SIL byte, all input is returned."""
    phones = pl.iter_phone_list_until_sil([5, 6, 7])
    assert phones == [5, 6, 7]


def test_iter_phone_list_accepts_bytes() -> None:
    """Bytes input is iterable as a sequence of ints."""
    phones = pl.iter_phone_list_until_sil(b"\x01\x02\x00\x99")
    assert phones == [1, 2]


def test_add_phone_to_empty_list() -> None:
    """First add: new PHONE has no neighbours."""
    plist: list[Phone] = []
    p = pl.ls_rule_add_phone(plist, sph=10, uph=20)
    assert plist == [p]
    assert p.p_sphone == 10
    assert p.p_uphone == 20
    assert p.p_stress == pl.SNONE
    assert p.p_flag == 0
    assert p.p_fp is None
    assert p.p_bp is None


def test_add_phone_prepends() -> None:
    """Subsequent adds: new PHONE goes to the front of the list."""
    plist: list[Phone] = []
    p1 = pl.ls_rule_add_phone(plist, sph=1, uph=1)
    p2 = pl.ls_rule_add_phone(plist, sph=2, uph=2)
    p3 = pl.ls_rule_add_phone(plist, sph=3, uph=3)
    # Order: p3 (front), p2, p1
    assert plist == [p3, p2, p1]


def test_add_phone_links_forward_and_backward() -> None:
    """The doubly-linked list pointers are wired correctly."""
    plist: list[Phone] = []
    p1 = pl.ls_rule_add_phone(plist, sph=1, uph=1)
    p2 = pl.ls_rule_add_phone(plist, sph=2, uph=2)
    # p2 → p1 forward; p1 → p2 backward.
    assert p2.p_fp is p1
    assert p1.p_bp is p2
    # p2 is at the front so p_bp is None.
    assert p2.p_bp is None
    # p1 is at the back so p_fp is None.
    assert p1.p_fp is None


def test_add_phone_inserts_in_middle_of_chain() -> None:
    """Adding a 3rd PHONE re-wires the head correctly."""
    plist: list[Phone] = []
    pl.ls_rule_add_phone(plist, sph=10, uph=10)
    pl.ls_rule_add_phone(plist, sph=20, uph=20)
    p_new = pl.ls_rule_add_phone(plist, sph=30, uph=30)
    # New head is p_new; its forward link is the previous head.
    assert plist[0] is p_new
    assert p_new.p_fp is plist[1]
    assert plist[1].p_bp is p_new
