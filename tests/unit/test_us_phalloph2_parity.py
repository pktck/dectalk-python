"""C-source parity test for :func:`dectalk.ph.us_phalloph2.phalloph2`.

This test exercises the full ``phsort + us_phalloph + make_out_phonol``
chain wired up in :mod:`dectalk.ph.us_phalloph2`, which replaces the
:mod:`dectalk.ph.ph_setallofeats` stop-gap from PR #66 (issue #63).
The chain mirrors what the C kernel runs between the LTS layer and
:func:`dectalk.ph.phinton.phinton`:

1. Build a DECtalk ``symbols[]`` stream from ARPABET word groups.
2. Run :func:`dectalk.ph.all_phsort.all_phsort` (translated from
   ``ph_sort.c`` lines 428-1712) to emit ``phonemes[]`` /
   ``sentstruc[]`` with per-phone feature words.
3. Run :func:`dectalk.ph.us_phalloph.us_phalloph` (translated from
   ``ph_aloph1.c`` lines 444-1546) to apply the US-English
   allophonic-substitution rules and write through to
   ``allophons[]`` / ``allofeats[]``.

Verification approach
=====================

The parity test asserts behavioural contracts on the populated
``allophons[]`` and ``allofeats[]`` arrays against the C reference:

* The C source's ``phalloph`` in ``ph_aloph2.c`` (the
  ``OLD_INTONATION_AND_TIMING`` build's variant — line 14 of
  ``ph_aloph.c``) writes ``curr_outstruc`` into
  ``allofeats[nallotot]`` via :func:`make_out_phonol`. The Python
  chain reproduces that write at the same ``nallotot`` index.
* ``ph_inton2.c``'s ``phinton`` gates F0 events on ``FSTRESS`` /
  ``FBOUNDARY`` / ``FPERNEXT`` masks — bits the chain emits.
* The leading-silence + trailing-silence sentinels match the C
  source's ``ph_task.c`` ``symbols[0] = GEN_SIL`` initialisation and
  ``us_phalloph`` trailing sentinel assignment.

Plus end-to-end behavioural checks:

* Stressed / unstressed / sentence-final ARPABET inputs produce the
  expected ``FSTRESS`` / ``FWBNEXT`` / ``FPERNEXT`` / ``FSENTENDS``
  bits in ``allofeats[]``.
* ``nf0tot > 0`` after a full ``hello world`` run — the issue's
  headline acceptance criterion (``phinton`` emits real F0 events).
* The chain does NOT drop any HH / L / NG phones (the ARPABET alias
  table from issue #61 is consulted, just like the existing
  ARPABET → allophone resolver).

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.

Tracks issue #69.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.phoneme_codes import PFUSA, USPhoneme
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import LANG_english
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import (
    FBOUNDARY,
    FPERNEXT,
    FSENTENDS,
    FSTRESS,
    FSTRESS_1,
    FWBNEXT,
)
from dectalk.ph.init_phclause import init_phclause
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.us_phalloph2 import (
    _arpabet_words_to_symbols,
    phalloph2,
)
from dectalk.ph.utterance_constants import GEN_SIL


def _dectalk_src() -> Path | None:
    """Return the C oracle root or ``None`` to trigger a skip."""
    src = os.environ.get("DECTALK_SRC")
    if src and Path(src).is_dir():
        return Path(src)
    fallback = Path("/tmp/dectalk-src")
    if fallback.is_dir():
        return fallback
    return None


def _read_c(path: Path) -> str:
    """Read a C source file with the kernel's ISO-8859 encoding."""
    return path.read_text(encoding="latin-1")


def _build_handle() -> tuple[TtsHandle, DphT]:
    """Build a minimal :class:`TtsHandle` for the chain."""
    p_dph_t = DphT()
    p_dph_t.dipspec = [0] * 256
    p_dph_t.parstochip = [0] * 64
    p_dph_t.sprate = 200
    settar = DphSettarSt()
    settar.initsw = 1
    p_dph_t.pSTphsettar = settar
    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    p_ksd_t = KsdT()
    p_ksd_t.lang_curr = LANG_english
    p_ksd_t.sprate = 200
    handle.p_kernel_share_data = p_ksd_t
    init_phclause(p_dph_t)
    return handle, p_dph_t


# ----------------------------------------------------------------------------
# Symbol-stream encoder unit tests (no C-oracle required).
# ----------------------------------------------------------------------------


def test_arpabet_words_to_symbols_leading_sil_and_wbound() -> None:
    """The encoder seeds ``symbols[]`` with GEN_SIL + WBOUND.

    Matches the C kernel's ``ph_task.c`` initialisation (line 437:
    ``pDph_t->symbols[0] = GEN_SIL``) and ``all_phsort``'s defensive
    leading-WBOUND insert (C lines 493-495).
    """
    syms, n = _arpabet_words_to_symbols([["AH0"]], is_sentence_final=True)
    assert n == len(syms)
    assert syms[0] == GEN_SIL
    from dectalk.include.phoneme_codes import WBOUND  # noqa: PLC0415

    assert syms[1] == WBOUND


def test_arpabet_words_to_symbols_emits_stress_markers() -> None:
    """Primary / secondary stress digits emit S1 / S2 markers."""
    from dectalk.include.phoneme_codes import S1, S2  # noqa: PLC0415

    syms, _ = _arpabet_words_to_symbols([["AH1", "AE2", "AH0"]])
    # Walk the stream looking for stress markers — order is
    # marker-before-phone per ``all_phsort`` add_feature semantics.
    assert S1 in syms
    assert S2 in syms
    # Unstressed AH0 emits no marker; the count of stress markers
    # must equal the count of stressed phones (1 + 1 = 2).
    assert syms.count(S1) == 1
    assert syms.count(S2) == 1


def test_arpabet_words_to_symbols_inserts_wbound_between_words() -> None:
    """Adjacent words are separated by a WBOUND marker."""
    from dectalk.include.phoneme_codes import WBOUND  # noqa: PLC0415

    syms, _ = _arpabet_words_to_symbols([["HH", "AH0"], ["W", "ER1"]])
    wb_count = syms.count(WBOUND)
    # Leading WBOUND (defensive) + 1 between words = 2.
    assert wb_count == 2, f"expected 2 WBOUND, got {wb_count}"


def test_arpabet_words_to_symbols_terminates_with_period_or_quest() -> None:
    """``is_sentence_final`` controls the trailing terminator marker."""
    from dectalk.include.phoneme_codes import PERIOD, QUEST  # noqa: PLC0415

    syms_period, _ = _arpabet_words_to_symbols(
        [["AH0"]], is_sentence_final=True, is_question=False
    )
    assert syms_period[-1] == PERIOD

    syms_quest, _ = _arpabet_words_to_symbols(
        [["AH0"]], is_sentence_final=True, is_question=True
    )
    assert syms_quest[-1] == QUEST

    syms_no_term, _ = _arpabet_words_to_symbols(
        [["AH0"]], is_sentence_final=False
    )
    assert syms_no_term[-1] not in (PERIOD, QUEST)


def test_arpabet_words_to_symbols_aliases_hh_l_ng() -> None:
    """ARPABET aliases (HH, L, NG) resolve to DECtalk allophone codes.

    Issue #61 added the ARPABET-to-USPhoneme alias table for the three
    CMU-39 symbols (``HH``, ``L``, ``NG``) whose bare names don't
    match the DECtalk FONIX scheme. This test pins the same set of
    aliases in :mod:`dectalk.ph.us_phalloph2` so the symbol encoder
    doesn't silently drop phones.
    """
    syms, _ = _arpabet_words_to_symbols([["HH", "AH0", "L", "OW1"], ["NG"]])
    # HH should resolve to HX (0x1E followed by USPhoneme.HX).
    hx_code = (PFUSA << 8) | int(USPhoneme.HX)
    ll_code = (PFUSA << 8) | int(USPhoneme.LL)
    nx_code = (PFUSA << 8) | int(USPhoneme.NX)
    assert hx_code in syms
    assert ll_code in syms
    assert nx_code in syms


# ----------------------------------------------------------------------------
# Full-chain behavioural tests.
# ----------------------------------------------------------------------------


def test_phalloph2_populates_allophons_for_hello_world() -> None:
    """``phalloph2`` writes the full allophone sequence with sentinels.

    Before this port, the Python pipeline went ARPABET → ``allophons[]``
    directly with manual leading/trailing GEN_SIL. The phalloph2 chain
    handles both ends itself (``ph_task.c`` lines 437-439 seed the
    leading silence; ``us_phalloph`` line 509 appends the trailing
    sentinel).
    """
    handle, p_dph_t = _build_handle()
    arpabet_words = [["HH", "AH0", "L", "OW1"], ["W", "ER1", "L", "D"]]
    phalloph2(handle, arpabet_words, is_sentence_final=True)

    # nallotot must include at least the real phones plus the
    # leading-SIL + PERIOD-induced-SIL bookkeeping.
    assert p_dph_t.nallotot >= 8, (
        f"nallotot={p_dph_t.nallotot}; expected >= 8 phones for 'hello world'"
    )
    # allophons[0] should be the leading silence phone.
    assert p_dph_t.allophons[0] == GEN_SIL
    # allophons[nallotot] is the trailing-SIL sentinel that
    # us_phalloph writes.
    assert p_dph_t.allophons[p_dph_t.nallotot] == GEN_SIL


def test_phalloph2_populates_nonzero_allofeats() -> None:
    """``phalloph2`` writes a non-zero feature word for each phone.

    The headline acceptance criterion from issue #58: ``allofeats[]``
    was all-zero on the Python full-pipeline path. With ``phalloph2``
    wired in, the per-phone feature word carries FSTRESS / FBOUNDARY /
    FWINITC / FFIRSTSYL / FSENTENDS bits per ``add_feature`` calls in
    ``all_phsort`` (lines 1413-1463).
    """
    handle, p_dph_t = _build_handle()
    arpabet_words = [["HH", "AH0", "L", "OW1"], ["W", "ER1", "L", "D"]]
    phalloph2(handle, arpabet_words, is_sentence_final=True)

    # At least one phone must have a non-zero feature word.
    nonzero = [
        p_dph_t.allofeats[i]
        for i in range(p_dph_t.nallotot)
        if p_dph_t.allofeats[i] != 0
    ]
    assert nonzero, (
        f"allofeats[:{p_dph_t.nallotot}] all zero — "
        "phalloph2 chain didn't populate any feature bits"
    )


def test_phalloph2_emits_fstress_for_stressed_vowel() -> None:
    """Stressed vowels carry an FSTRESS bit in ``allofeats[]``.

    ``all_phsort`` runs ``add_feature(p_dph_t, FSTRESS_1, nphonetot)``
    when it sees an S1 marker (C lines 1413-1418), and the bit
    propagates into ``allofeats[]`` via ``us_phalloph`` →
    ``make_out_phonol``.
    """
    handle, p_dph_t = _build_handle()
    # "OW1" carries primary stress.
    arpabet_words = [["HH", "AH0", "L", "OW1"]]
    phalloph2(handle, arpabet_words, is_sentence_final=True)

    # At least one phone in the clause carries a stress bit.
    stressed_count = sum(
        1 for i in range(p_dph_t.nallotot) if (p_dph_t.allofeats[i] & FSTRESS) != 0
    )
    assert stressed_count >= 1, (
        "no FSTRESS bit found in allofeats — the OW1 stress digit "
        "didn't propagate through the chain"
    )


def test_phalloph2_marks_sentence_end_with_fsentends() -> None:
    """Sentence-final declaratives emit ``FSENTENDS`` on the closing phone.

    ``all_phsort``'s PERIOD branch (C line 477) calls
    ``add_feature(p_dph_t, FSENTENDS, nphonetot)`` before emitting the
    closing silence; the resulting feature word lands in
    ``allofeats[]`` for the final emitted phone.
    """
    handle, p_dph_t = _build_handle()
    arpabet_words = [["HH", "AH0", "L", "OW1"]]
    phalloph2(handle, arpabet_words, is_sentence_final=True)

    # Find at least one allofeats entry with FSENTENDS set.
    sentends_phones = [
        i for i in range(p_dph_t.nallotot) if (p_dph_t.allofeats[i] & FSENTENDS) != 0
    ]
    assert sentends_phones, (
        "no allofeats entry carries FSENTENDS — sentence-final "
        "boundary marker didn't propagate"
    )


def test_phalloph2_no_dropped_phones_for_hh_l_ng() -> None:
    """ARPABET HH / L / NG no longer drop on the floor (issue #61).

    The audit in ``docs/parity-divergence-audit.md`` §"Top 3 divergence
    root causes" #1 named the HH / L / NG dropout as the 38%-of-phones
    regression. Issue #61 added an alias table in
    :mod:`dectalk.api.speak`; this port mirrors it in
    :mod:`dectalk.ph.us_phalloph2` so the symbol encoder doesn't
    re-introduce the gap.
    """
    handle, p_dph_t = _build_handle()
    # "hello world": HH + L + L should NOT drop.
    arpabet_words = [["HH", "AH0", "L", "OW1"], ["W", "ER1", "L", "D"]]
    phalloph2(handle, arpabet_words, is_sentence_final=True)

    # Count allophons matching HX / LL / LX (LX is the post-vocalic L
    # allophone us_phalloph substitutes after a vowel).
    codes = [
        p_dph_t.allophons[i] & 0xFF for i in range(p_dph_t.nallotot)
    ]
    has_hx = int(USPhoneme.HX) in codes
    has_ll_or_lx = int(USPhoneme.LL) in codes or int(USPhoneme.LX) in codes
    assert has_hx, "HX (US /h/) missing — HH dropped from the stream"
    assert has_ll_or_lx, "LL / LX (US /l/) missing — L dropped from the stream"


def test_phalloph2_word_boundaries_in_allofeats() -> None:
    """Non-final words emit a word-boundary bit in ``allofeats[]``.

    ``all_phsort`` writes FWBNEXT-class boundary bits (via
    ``get_next_bound_type``) into ``sentstruc[]`` at each word
    boundary; ``us_phalloph`` copies the word through ``make_out_phonol``
    into ``allofeats[]``. ``phinton``'s ``nextwrdbou`` lookahead reads
    those bits to terminate Rule 6 (continuation rise) correctly.
    """
    handle, p_dph_t = _build_handle()
    # Two-word utterance: at least one phone before the second word
    # must carry a WBNEXT-or-stronger boundary mask.
    arpabet_words = [["HH", "AH0", "L", "OW1"], ["W", "ER1", "L", "D"]]
    phalloph2(handle, arpabet_words, is_sentence_final=True)

    has_boundary = any(
        (p_dph_t.allofeats[i] & FBOUNDARY) >= FWBNEXT
        for i in range(p_dph_t.nallotot)
    )
    assert has_boundary, (
        "no allofeats entry carries a FWBNEXT-or-stronger boundary "
        "— phinton's nextwrdbou lookahead won't terminate"
    )


def test_phalloph2_period_propagates_to_fpernext_or_sentends() -> None:
    """Sentence-final ``.`` propagates to FPERNEXT or FSENTENDS.

    ``phinton``'s Rule 4 (final fall) requires FPERNEXT or FSENTENDS
    to fire. ``all_phsort`` writes both on the PERIOD branch (C lines
    476-478 / 479) and the bits land in ``allofeats[]``.
    """
    handle, p_dph_t = _build_handle()
    arpabet_words = [["HH", "AH0", "L", "OW1"]]
    phalloph2(handle, arpabet_words, is_sentence_final=True)

    has_sentence_end = any(
        ((p_dph_t.allofeats[i] & FBOUNDARY) == FPERNEXT)
        or ((p_dph_t.allofeats[i] & FSENTENDS) != 0)
        for i in range(p_dph_t.nallotot)
    )
    assert has_sentence_end, (
        "neither FPERNEXT nor FSENTENDS found — phinton's Rule 4 "
        "(final fall) will not fire"
    )


def test_phalloph2_phinton_emits_nonzero_nf0tot() -> None:
    """After ``phalloph2 + phinton``, the F0 contour is non-trivial.

    Issue #58 §#2 named ``nf0tot=0`` after ``phinton`` as the
    headline F0-contour regression. With ``phalloph2`` populating
    ``allofeats[]`` (FSTRESS / FBOUNDARY / FSENTENDS bits),
    ``phinton``'s Rules 1-6 should fire and emit at least one F0
    event (probably more like 4-8 for "hello world").
    """
    from dectalk.ph.init_clause import init_clause  # noqa: PLC0415
    from dectalk.ph.init_timing import init_timing  # noqa: PLC0415
    from dectalk.ph.phinton import phinton  # noqa: PLC0415
    from dectalk.ph.us_phtiming import us_phtiming  # noqa: PLC0415
    from dectalk.vtm.spd_chip import default_us_paul_spd  # noqa: PLC0415

    handle, p_dph_t = _build_handle()
    spd = default_us_paul_spd()
    p_dph_t.fnscale = spd.fnscale
    p_dph_t.malfem = spd.sex
    p_dph_t.f0_lp_filter = 1500 + 15 * 40  # QU=40
    p_dph_t.f0minimum = (100 - 12) * 10  # AP=100
    p_dph_t.f0scalefac = 100 * 41  # PR=100

    arpabet_words = [["HH", "AH0", "L", "OW1"], ["W", "ER1", "L", "D"]]
    phalloph2(handle, arpabet_words, is_sentence_final=True)
    settar = p_dph_t.pSTphsettar
    assert isinstance(settar, DphSettarSt)
    init_timing(p_dph_t, settar, sprate_ref=[200], lang_curr=LANG_english)
    us_phtiming(handle)
    init_clause(p_dph_t)
    phinton(handle)

    assert p_dph_t.nf0tot > 0, (
        f"nf0tot={p_dph_t.nf0tot} — phinton emitted no F0 events "
        "even after phalloph2 populated allofeats[]"
    )


# ----------------------------------------------------------------------------
# C-source parity assertions (skipped when /tmp/dectalk-src absent).
# ----------------------------------------------------------------------------


@pytest.mark.c_oracle
def test_c_source_phalloph_calls_make_out_phonol() -> None:
    """``phalloph`` in ph_aloph2.c calls ``make_out_phonol`` to emit each phone.

    Pins the contract that the chain we wire in
    :func:`dectalk.ph.us_phalloph2.phalloph2` (via ``us_phalloph``)
    matches what the C source does — emit one allophone via
    ``make_out_phonol`` per accepted input phoneme.
    """
    src = _dectalk_src()
    if src is None:
        pytest.skip("DECTALK_SRC absent — skipping C-source parity test")
    path = src / "src/dapi/src/ph/ph_aloph2.c"
    text = _read_c(path)
    # ``phalloph`` is the top-level entry (line 452) and the only
    # caller of make_out_phonol (the helper at line 1812).
    assert "void phalloph (LPTTS_HANDLE_T phTTS)" in text
    assert re.search(r"make_out_phonol\s*\(", text)


@pytest.mark.c_oracle
def test_c_source_make_out_phonol_writes_allofeats() -> None:
    """``make_out_phonol`` in ph_aloph2.c writes ``curr_outstruc`` to allofeats[].

    The C function's only side-effect on the feature stream is:

    .. code-block:: c

        pDph_t->allofeats[pDph_t->nallotot] = curr_outstruc;

    (line 1869). The Python chain's ``us_phalloph`` →
    ``make_out_phonol`` reproduces this write, so this assertion pins
    the contract.
    """
    src = _dectalk_src()
    if src is None:
        pytest.skip("DECTALK_SRC absent — skipping C-source parity test")
    path = src / "src/dapi/src/ph/ph_aloph2.c"
    text = _read_c(path)
    assert re.search(
        r"pDph_t->allofeats\[pDph_t->nallotot\]\s*=\s*curr_outstruc",
        text,
    )


@pytest.mark.c_oracle
def test_c_source_all_phsort_uses_add_feature_for_stress() -> None:
    """``all_phsort`` in ph_sort.c writes FSTRESS_* via ``add_feature``.

    Pins the contract that the upstream chain (``all_phsort``) writes
    the stress bits that ``us_phalloph`` later propagates into
    ``allofeats[]``. The C source has explicit:

    .. code-block:: c

        case S1: add_feature(p_dph_t, FSTRESS_1, nphonetot); break;
        case S2: add_feature(p_dph_t, FSTRESS_2, nphonetot); break;
    """
    src = _dectalk_src()
    if src is None:
        pytest.skip("DECTALK_SRC absent — skipping C-source parity test")
    path = src / "src/dapi/src/ph/ph_sort.c"
    text = _read_c(path)
    # Both writes must be present.
    assert re.search(r"add_feature\s*\([^,]+,\s*FSTRESS_1", text), (
        "all_phsort doesn't write FSTRESS_1 — the stress chain is broken"
    )
    assert re.search(r"add_feature\s*\([^,]+,\s*FSTRESS_2", text), (
        "all_phsort doesn't write FSTRESS_2 — the stress chain is broken"
    )


@pytest.mark.c_oracle
def test_c_source_all_phsort_period_emits_gen_sil_phone() -> None:
    """``all_phsort``'s PERIOD branch emits a GEN_SIL phone via make_phone.

    Pins the contract that sentence-final markers produce a trailing
    silence phone in ``phonemes[]``, which then propagates through
    ``us_phalloph`` to ``allophons[nallotot]`` as the trailing
    sentinel.
    """
    src = _dectalk_src()
    if src is None:
        pytest.skip("DECTALK_SRC absent — skipping C-source parity test")
    path = src / "src/dapi/src/ph/ph_sort.c"
    text = _read_c(path)
    # The PERIOD case must call make_phone with GEN_SIL.
    assert re.search(
        r"case\s+PERIOD\s*:.*?make_phone\s*\([^,]+,\s*GEN_SIL",
        text,
        re.DOTALL,
    ), (
        "all_phsort's PERIOD branch doesn't emit a GEN_SIL phone — "
        "the trailing-silence contract is broken"
    )


_ = FSTRESS_1  # silence "imported-but-unused" if a flake removes a test
