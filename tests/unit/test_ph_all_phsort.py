"""Behavioural tests for the US-English ``all_phsort`` port.

These tests construct ``DphT`` / ``KsdT`` directly and assert that
:func:`all_phsort` populates ``phonemes[]``, ``sentstruc[]``, and the
clause-level counters correctly.

The tests exercise the **US-English** path; the function raises
:class:`NotImplementedError` for other languages.
"""

from __future__ import annotations

import pytest

from dectalk.include.cmd_codes import PVALUE
from dectalk.include.defs import FALSE, TRUE
from dectalk.include.phoneme_codes import (
    COMMA,
    NEW_PARAGRAPH,
    PERIOD,
    PPSTART,
    S1,
    VPSTART,
    WBOUND,
)
from dectalk.include.usp_codes import USP_HX, USP_IY, USP_LL, USP_OW
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import (
    LANG_british,
    LANG_english,
    LANG_german,
    LANG_latin_american,
    LANG_spanish,
)
from dectalk.ph.all_phsort import all_phsort
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FSTRESS_1, PRESSBOUND
from dectalk.ph.numeric_constants import NPHON_MAX
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import (
    COMMACLAUSE,
    DECLARATIVE,
    GEN_SIL,
)


def _make_handle(symbols: list[int], sprate: int = 180, lang: int = LANG_english) -> TtsHandle:
    """Build a TtsHandle populated for an all_phsort run."""
    nsymb = len(symbols)
    # Buffer-sized arrays the function reads / writes during the pass.
    buf = NPHON_MAX + 16

    dph = DphT()
    dph.symbols = list(symbols) + [0] * (buf - nsymb)
    dph.nsymbtot = nsymb
    dph.user_durs = [0] * buf
    dph.user_f0 = [0] * buf
    dph.user_offset = [0] * buf
    dph.phonemes = [0] * buf
    dph.sentstruc = [0] * buf
    dph.pSTphsettar = DphSettarSt()

    ksd = KsdT()
    ksd.lang_curr = lang
    ksd.sprate = sprate
    ksd.halting = 0

    return TtsHandle(p_kernel_share_data=ksd, p_ph_thread_data=dph)


def test_empty_input_returns_true_and_zero_phonetot() -> None:
    """An empty symbols stream returns TRUE with nphonetot == 0."""
    handle = _make_handle([])
    rv = all_phsort(handle)
    assert rv == TRUE
    dph = handle.p_ph_thread_data
    assert isinstance(dph, DphT)
    assert dph.nphonetot == 0


def test_halting_aborts_with_false() -> None:
    """If pKsd->halting is set, pass 1 returns early with FALSE."""
    handle = _make_handle([WBOUND, USP_HX, USP_IY, WBOUND])
    ksd = handle.p_kernel_share_data
    assert isinstance(ksd, KsdT)
    ksd.halting = 1
    rv = all_phsort(handle)
    assert rv == FALSE


def test_simple_word_emits_phonemes() -> None:
    """A single word's symbols round-trip into ``phonemes[]``.

    Stream: ``WBOUND HX IY WBOUND PERIOD`` -- "hi".
    """
    symbols = [WBOUND, USP_HX, USP_IY, WBOUND, PERIOD]
    handle = _make_handle(symbols)
    rv = all_phsort(handle)
    assert rv == TRUE

    dph = handle.p_ph_thread_data
    assert isinstance(dph, DphT)
    # Two real phonemes (HX, IY) + the PERIOD-emitted GEN_SIL.
    assert dph.nphonetot >= 2
    assert dph.phonemes is not None
    # The two consonant/vowel slots are filled with the input codes.
    emitted = dph.phonemes[: dph.nphonetot]
    assert USP_HX in emitted
    assert USP_IY in emitted
    # PERIOD emits a GEN_SIL filler.
    assert GEN_SIL in emitted


def test_period_sets_declarative_clausetype() -> None:
    """A trailing PERIOD sets ``clausetype = DECLARATIVE``."""
    handle = _make_handle([WBOUND, USP_HX, USP_IY, WBOUND, PERIOD])
    all_phsort(handle)
    dph = handle.p_ph_thread_data
    assert isinstance(dph, DphT)
    assert dph.clausetype == DECLARATIVE


def test_comma_sets_commaclause_then_declarative_after_two() -> None:
    """First COMMA -> COMMACLAUSE; second COMMA -> DECLARATIVE."""
    # First COMMA only.
    handle1 = _make_handle([WBOUND, USP_HX, USP_IY, WBOUND, COMMA])
    all_phsort(handle1)
    dph1 = handle1.p_ph_thread_data
    assert isinstance(dph1, DphT)
    assert dph1.clausetype == COMMACLAUSE

    # Two COMMAs -> declarative promotion.
    handle2 = _make_handle([WBOUND, USP_HX, USP_IY, WBOUND, COMMA, USP_LL, USP_OW, WBOUND, COMMA])
    all_phsort(handle2)
    dph2 = handle2.p_ph_thread_data
    assert isinstance(dph2, DphT)
    assert dph2.clausetype == DECLARATIVE


def test_word_count_advances_on_wbound() -> None:
    """Each WBOUND increments ``number_words`` in the output pass."""
    symbols = [WBOUND, USP_HX, USP_IY, WBOUND, USP_LL, USP_OW, WBOUND, PERIOD]
    handle = _make_handle(symbols)
    all_phsort(handle)
    dph = handle.p_ph_thread_data
    assert isinstance(dph, DphT)
    # Three WBOUNDs in the input stream.
    assert dph.number_words == 3


def test_stress_marker_attaches_to_next_phone() -> None:
    """S1 in pass 2 adds the FSTRESS_1 feature to nphonetot's slot."""
    handle = _make_handle([WBOUND, S1, USP_HX, USP_IY, WBOUND, PERIOD])
    all_phsort(handle)
    dph = handle.p_ph_thread_data
    assert isinstance(dph, DphT)
    assert dph.sentstruc is not None
    # The first emitted phoneme should have FSTRESS_1 in its sentstruc.
    assert (dph.sentstruc[0] & FSTRESS_1) == FSTRESS_1


def test_leading_word_boundary_repair() -> None:
    """If symbols[1] != WBOUND-raw and nsymbtot > 2, one is inserted."""
    # Start with no leading WBOUND.
    symbols = [USP_HX, USP_IY, WBOUND, PERIOD]
    handle = _make_handle(symbols)
    all_phsort(handle)
    dph = handle.p_ph_thread_data
    assert isinstance(dph, DphT)
    # symbols[1] is now WBOUND (raw value 111).
    assert (dph.symbols[1] & PVALUE) == WBOUND


def test_slow_rate_demotes_ppstart_to_vpstart() -> None:
    """When sprate <= 140, PPSTART becomes VPSTART."""
    handle = _make_handle([WBOUND, USP_HX, USP_IY, PPSTART, WBOUND, PERIOD], sprate=120)
    all_phsort(handle)
    dph = handle.p_ph_thread_data
    assert isinstance(dph, DphT)
    # PPSTART at index 3 should have been promoted to VPSTART
    # (unless the clause-final-word rule fired first and turned it
    # into a WBOUND). Either outcome is acceptable: the C rule says
    # the symbol must no longer be a bare PPSTART at slow rate.
    assert dph.symbols[3] != PPSTART or (dph.symbols[3] & PVALUE) in (
        VPSTART & PVALUE,
        WBOUND & PVALUE,
    )


@pytest.mark.parametrize(
    "lang",
    [LANG_british, LANG_german, LANG_spanish, LANG_latin_american],
)
def test_non_us_languages_raise_not_implemented(lang: int) -> None:
    """Non-US-English language codes raise NotImplementedError."""
    handle = _make_handle([WBOUND, USP_HX, USP_IY, WBOUND], lang=lang)
    with pytest.raises(NotImplementedError, match="Phase E"):
        all_phsort(handle)


def test_pass1_did_del_back_up() -> None:
    """If delete_symbol fires (adjacent NEW_PARAGRAPH), n backs up.

    Verified indirectly: two adjacent NEW_PARAGRAPHs collapse into one
    in the output, so the final stream has only one PRESSBOUND marker.
    """
    handle = _make_handle(
        [
            WBOUND,
            USP_HX,
            USP_IY,
            WBOUND,
            NEW_PARAGRAPH,
            NEW_PARAGRAPH,
            PERIOD,
        ]
    )
    all_phsort(handle)
    dph = handle.p_ph_thread_data
    assert isinstance(dph, DphT)
    assert dph.sentstruc is not None
    # Count how many slots carry the PRESSBOUND bit.
    presses = sum(1 for v in dph.sentstruc[: dph.nphonetot + 2] if (v & PRESSBOUND))
    # One NEW_PARAGRAPH survived; it ORs PRESSBOUND into two slots
    # (nextphone and nphonetot+1), so we expect at most two.
    assert presses <= 2
