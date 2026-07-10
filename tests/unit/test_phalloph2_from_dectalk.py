"""Unit tests for :func:`dectalk.ph.us_phalloph2.phalloph2_from_dectalk`.

The synth path (``_render_clause_full``) was unified onto the byte-exact
``text_to_dectalk_phonemes`` stream: it decodes that ASCII stream into the
packed ``symbols[]`` array via :func:`parse_phoneme_stream` and runs the real
``all_phsort + us_phalloph`` chain. These tests lock in the allophone-stream
wins that unification produced (issues #237 / #217 / #238 / #218) so a future
regression in the byte-exact path is caught.

They do **not** require the C oracle: ``text_to_dectalk_phonemes`` is the
pure-Python LTS+dic stage (already byte-parity-tested against the C library
elsewhere), and the chain under test is pure Python. They run in the standard
CI matrix.
"""

from __future__ import annotations

from dectalk.api.speak import text_to_dectalk_phonemes
from dectalk.include.all_phon_counts import MAX_PHONES
from dectalk.include.phoneme_codes import (
    PERIOD,
    PFUSA,
    QUEST,
    SPECIALWORD,
    WBOUND,
    USPhoneme,
)
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import LANG_english
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.init_phclause import init_phclause
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.us_phalloph2 import (
    _dectalk_stream_to_symbols,
    phalloph2_from_dectalk,
    phalloph2_from_symbols,
    split_dectalk_stream_clauses,
)


def _allophones(text: str) -> tuple[int, list[str]]:
    """Run the byte-exact chain for ``text`` and return (nallotot, names)."""
    p_dph_t = DphT()
    p_dph_t.dipspec = [0] * 256
    p_dph_t.parstochip = [0] * 64
    p_dph_t.sprate = 180
    p_dph_t.pSTphsettar = DphSettarSt()
    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    p_ksd_t = KsdT()
    p_ksd_t.lang_curr = LANG_english
    p_ksd_t.sprate = 180
    handle.p_kernel_share_data = p_ksd_t
    init_phclause(p_dph_t)

    phalloph2_from_dectalk(handle, text_to_dectalk_phonemes(text))
    n = p_dph_t.nallotot
    names: list[str] = []
    for i in range(n):
        offset = p_dph_t.allophons[i] & 0xFF
        try:
            names.append(USPhoneme(offset).name)
        except ValueError:
            names.append(f"?{offset}")
    return n, names


# ---------------------------------------------------------------------------
# _dectalk_stream_to_symbols (no chain run).
# ---------------------------------------------------------------------------


def test_stream_to_symbols_leading_sil_then_wbound() -> None:
    """The decoder prepends a leading GEN_SIL phone + WBOUND (ph_task.c)."""
    syms, n = _dectalk_stream_to_symbols(text_to_dectalk_phonemes("hello world"))
    assert n == len(syms)
    assert syms[0] == (PFUSA << 8) | int(USPhoneme.SIL)
    assert syms[1] == WBOUND


def test_stream_to_symbols_appends_implicit_period() -> None:
    """An unpunctuated stream gets a trailing PERIOD; a punctuated one does not."""
    syms_plain, _ = _dectalk_stream_to_symbols(text_to_dectalk_phonemes("hello world"))
    assert syms_plain[-1] == PERIOD

    # A question mark already terminates the clause -> no implicit PERIOD added,
    # and the terminator is QUEST (not PERIOD).
    syms_q, _ = _dectalk_stream_to_symbols(text_to_dectalk_phonemes("is it raining?"))
    assert syms_q[-1] == QUEST
    assert syms_q.count(PERIOD) == 0


def test_stream_to_symbols_control_codes_pass_through_unshifted() -> None:
    """Allophones are font-shifted; control codes (>= MAX_PHONES) are not."""
    syms, _ = _dectalk_stream_to_symbols(text_to_dectalk_phonemes("hello world"))
    # Every real phoneme slot carries the US font in its high byte; every
    # control marker is a bare small integer with no high byte.
    for s in syms:
        if s >> 8:
            assert (s >> 8) == PFUSA
            assert (s & 0xFF) < MAX_PHONES
        else:
            assert s >= MAX_PHONES


# ---------------------------------------------------------------------------
# Full-chain allophone-stream wins.
# ---------------------------------------------------------------------------


def test_she_sells_no_spurious_s_allophones() -> None:
    """``she sells sea shells`` -> nallotot 14 (no spurious cross-word S) -- #237.

    The old per-word ARPABET path emitted ``… LX LL S S IY …`` (nallotot 16);
    the byte-exact path inherits the C-faithful ``… LX Z S IY …`` (14), with
    the word-final ``-s`` correctly voiced to Z and no doubled sibilant.
    """
    n, names = _allophones("she sells sea shells")
    assert n == 14, f"expected nallotot=14, got {n}: {names}"
    # No two adjacent S allophones anywhere in the stream.
    assert not any(names[i] == "S" and names[i + 1] == "S" for i in range(len(names) - 1)), (
        f"spurious adjacent S allophones: {names}"
    )
    # Word-final plural -s voiced to Z (sells / shells).
    assert names.count("Z") == 2, f"expected 2 voiced Z, got {names}"


def test_acronym_is_spelled_letter_by_letter() -> None:
    """``BBC`` -> B IY B IY S IY (spelled), not the LTS reading -- #217."""
    n, names = _allophones("BBC")
    # SIL B IY B IY S IY SIL
    assert names == ["SIL", "B", "IY", "B", "IY", "S", "IY", "SIL"], names
    assert n == 8


def test_digit_expansion_inserts_and() -> None:
    """``999`` includes the ") eh n d" "and" allophones -- #238.

    ``number_to_words(999)`` is "nine hundred and ninety nine"; the byte-exact
    path carries the digit-expansion "and" the old synth path dropped. We look
    for the EH N D run that spells "and" in the allophone stream.
    """
    _, names = _allophones("999")
    joined = " ".join(names)
    assert "EH N D" in joined, f"missing 'and' (EH N D) run in {names}"


def test_internal_comma_emits_native_gen_sil() -> None:
    """``hello, world.`` -> a single internal GEN_SIL from the COMMA marker -- #218.

    Leading sentinel + one internal (comma) + trailing sentinel = 3 GEN_SIL,
    with the internal one sitting between the two words rather than collapsing.
    """
    n, names = _allophones("hello, world.")
    gen_sil_positions = [i for i, nm in enumerate(names) if nm == "SIL"]
    assert len(gen_sil_positions) == 3, f"expected 3 GEN_SIL, got {names}"
    # The internal SIL is neither the first nor the last allophone.
    internal = gen_sil_positions[1]
    assert 0 < internal < n - 1, f"internal SIL at edge: {names}"


def test_clean_prompt_count_unchanged() -> None:
    """``hello world`` stays at the C-faithful nallotot=10 (no regression)."""
    n, names = _allophones("hello world")
    assert names == [
        "SIL",
        "HX",
        "AX",
        "LL",
        "OW",
        "W",
        "RR",
        "LX",
        "D",
        "SIL",
    ], names
    assert n == 10


# ---------------------------------------------------------------------------
# Citation-mode wiring: SPECIALWORD -> docitation (issue #309).
# ---------------------------------------------------------------------------


def _make_handle() -> TtsHandle:
    """Fresh engine handle in the same shape the synth path builds."""
    p_dph_t = DphT()
    p_dph_t.dipspec = [0] * 256
    p_dph_t.parstochip = [0] * 64
    p_dph_t.sprate = 180
    p_dph_t.pSTphsettar = DphSettarSt()
    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    p_ksd_t = KsdT()
    p_ksd_t.lang_curr = LANG_english
    p_ksd_t.sprate = 180
    handle.p_kernel_share_data = p_ksd_t
    init_phclause(p_dph_t)
    return handle


def _clause_allophones(handle: TtsHandle, symbols: list[int], nsymbtot: int) -> list[str]:
    """Run one clause through the chain and name its allophones."""
    phalloph2_from_symbols(handle, symbols, nsymbtot)
    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)
    names: list[str] = []
    for i in range(p_dph_t.nallotot):
        offset = p_dph_t.allophons[i] & 0xFF
        try:
            names.append(USPhoneme(offset).name)
        except ValueError:
            names.append(f"?{offset}")
    return names


def test_splitter_keeps_specialword_in_its_clause() -> None:
    """``a. b? c!`` -> the ``^`` marker lands in clause 0 only."""
    clauses = split_dectalk_stream_clauses(text_to_dectalk_phonemes("a. b? c!"))
    assert len(clauses) == 3
    marker_hits = [any(s == SPECIALWORD for s in syms) for syms, _ in clauses]
    assert marker_hits == [True, False, False], marker_hits


def test_specialword_arms_citation_ax_becomes_ey() -> None:
    """Clause-1 "a" of ``a. b? c!`` says citation-form EY, not reduced AX.

    ph_task.c:621 sets ``docitation = 1`` on the SPECIALWORD marker; with
    the MODE_CITATION boot default (#307) the ph_aloph1.c:718 unreduce
    rule then rewrites the lone [AX] to [EY] (issue #309: the binary says
    EY du=48 where the unwired Python said AX du=34).
    """
    handle = _make_handle()
    clauses = split_dectalk_stream_clauses(text_to_dectalk_phonemes("a. b? c!"))
    names = _clause_allophones(handle, *clauses[0])
    assert "EY" in names and "AX" not in names, names

    # ph_claus.c:307 clears the flag after the clause's phalloph visit.
    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)
    assert p_dph_t.docitation == 0


def test_without_specialword_ax_stays_reduced() -> None:
    """The same clause minus the ``^`` marker keeps the reduced AX."""
    handle = _make_handle()
    clauses = split_dectalk_stream_clauses(text_to_dectalk_phonemes("a. b? c!"))
    symbols = [s for s in clauses[0][0] if s != SPECIALWORD]
    names = _clause_allophones(handle, symbols, len(symbols))
    assert "AX" in names and "EY" not in names, names


def test_citation_does_not_leak_across_clauses() -> None:
    """docitation is per-clause: clause 2 of ``a. b? c!`` is unaffected.

    The SPECIALWORD in clause 0 must not leave citation mode armed for
    later clauses (ph_claus.c:307 clears it after every phalloph visit).
    """
    clauses = split_dectalk_stream_clauses(text_to_dectalk_phonemes("a. b? c!"))

    seq_handle = _make_handle()
    _clause_allophones(seq_handle, *clauses[0])
    seq_clause1 = _clause_allophones(seq_handle, *clauses[1])

    solo_handle = _make_handle()
    solo_clause1 = _clause_allophones(solo_handle, *clauses[1])

    assert seq_clause1 == solo_clause1
