"""Verify ``ls_adju_suffixscan`` parity with ls_adju.c."""

from __future__ import annotations

from dectalk.lts.phone_list import SNONE, ls_rule_add_phone
from dectalk.lts.structs import PFSYLAB, Phone
from dectalk.lts.syllable_scan import NSYL, SPRI, SyllabicWord, ls_adju_suffixscan


def _build_chain(n: int, sylab_at: list[int], stresses: list[int] | None = None) -> list[Phone]:
    """Build an n-PHONE chain with PFSYLAB at specified indices.

    Args:
        n: Total number of PHONEs.
        sylab_at: Indices where PFSYLAB is set.
        stresses: Optional per-PHONE stress codes (defaults to SNONE).

    Returns:
        The PHONE list (forward order).
    """
    plist: list[Phone] = []
    for _ in range(n):
        ls_rule_add_phone(plist, sph=0, uph=0)
    # ls_rule_add_phone prepends; reverse to get forward order matching indices.
    plist.reverse()
    # Restore the linked-list pointers after reversing.
    for i, p in enumerate(plist):
        p.p_fp = plist[i + 1] if i + 1 < len(plist) else None
        p.p_bp = plist[i - 1] if i > 0 else None
    for idx in sylab_at:
        plist[idx].p_flag |= PFSYLAB
    if stresses is not None:
        for i, s in enumerate(stresses):
            plist[i].p_stress = s
    return plist


def test_suffixscan_empty_word() -> None:
    """Zero PHONEs: nsyl=0, rsyl=0, psyl=-1."""
    plist = _build_chain(0, [])
    if plist:
        word = ls_adju_suffixscan(plist[0], None)
    else:
        # Need a head — use a sentinel phone but lpp == head.
        head = Phone()
        word = ls_adju_suffixscan(head, head)
    assert word is not None
    assert word.nsyl == 0
    assert word.rsyl == 0
    assert word.psyl == -1


def test_suffixscan_single_syllable_unstressed() -> None:
    """A single PFSYLAB without stress: nsyl=1, rsyl=1 (>= nsyl), psyl=-1."""
    plist = _build_chain(3, sylab_at=[0])
    word = ls_adju_suffixscan(plist[0], None)
    assert word is not None
    assert word.nsyl == 1
    # rsyl was never set (no stress), so it's set to nsyl at the end.
    assert word.rsyl == 1
    assert word.psyl == -1
    assert word.sylp == [plist[0]]


def test_suffixscan_single_syllable_with_primary_stress() -> None:
    """A single stressed syllable: rsyl=0 (first stressed), psyl=0 (primary)."""
    plist = _build_chain(3, sylab_at=[0], stresses=[SPRI, SNONE, SNONE])
    word = ls_adju_suffixscan(plist[0], None)
    assert word is not None
    assert word.nsyl == 1
    assert word.rsyl == 0
    assert word.psyl == 0


def test_suffixscan_multiple_syllables() -> None:
    """Three PFSYLAB markers: nsyl=3, sylp lists all three."""
    plist = _build_chain(7, sylab_at=[0, 3, 5])
    word = ls_adju_suffixscan(plist[0], None)
    assert word is not None
    assert word.nsyl == 3
    assert word.sylp == [plist[0], plist[3], plist[5]]


def test_suffixscan_secondary_stress_sets_rsyl_not_psyl() -> None:
    """Secondary stress (< SPRI) sets rsyl but leaves psyl unset."""
    plist = _build_chain(
        5,
        sylab_at=[0, 2],
        stresses=[SPRI - 1, SNONE, SNONE, SNONE, SNONE],  # secondary < SPRI on syl 0
    )
    word = ls_adju_suffixscan(plist[0], None)
    assert word is not None
    # rsyl is set on the first stressed syllable (syl 0).
    assert word.rsyl == 0
    # psyl stays -1 because no syllable reached SPRI.
    assert word.psyl == -1


def test_suffixscan_overflow_returns_none() -> None:
    """More than NSYL syllables: returns None (matches C FALSE)."""
    # Build NSYL+1 syllables, each with a PFSYLAB.
    plist = _build_chain(NSYL + 1, sylab_at=list(range(NSYL + 1)))
    word = ls_adju_suffixscan(plist[0], None)
    assert word is None


def test_suffixscan_walks_with_lpp_sentinel() -> None:
    """``lpp`` parameter terminates the walk early."""
    plist = _build_chain(5, sylab_at=[0, 2, 4])
    # Stop after the first 3 PHONEs.
    word = ls_adju_suffixscan(plist[0], plist[3])
    assert word is not None
    # Only 2 syllables visited (at index 0 and 2).
    assert word.nsyl == 2


def test_suffixscan_default_state() -> None:
    """Default SyllabicWord state."""
    w = SyllabicWord()
    assert w.nsyl == 0
    assert w.rsyl == -1
    assert w.psyl == -1
    assert w.sylp == []
